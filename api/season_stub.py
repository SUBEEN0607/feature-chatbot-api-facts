"""STUB of the sim.season contract (docs/GAME-V2-SPEC.md §11) so the API and persona layer can be built and
tested before sim/season.py lands. api/season_engine.py switches to the real module automatically.

Deliberately simple and clearly labelled: a monthly P&L from the hero base case with a calendar index,
price elasticity, a few lever effects, events, one seeded draw and a fixed p10/p90 band. Every mechanism is
tagged 가정 (stub). Numbers from here must never be presented as the model's.
"""
from __future__ import annotations

import copy
import random
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
MONTHS = [10, 11, 12, 1, 2, 3]
CALENDAR = {10: ("10월", "축제와 중간고사", 1.00), 11: ("11월", "평범한 달", 0.97), 12: ("12월", "연말 회식 시즌", 1.10),
            1: ("1월", "겨울방학", 0.86), 2: ("2월", "방학과 설 연휴", 0.84), 3: ("3월", "개강", 1.02)}
EVENTS = {  # id: (label, month probability, revenue factor, cost delta per month, tag)
    "pork_up": ("돼지고기 도매가 상승", 0.25, 1.00, 600_000, "가정 (stub)"),
    "rain_week": ("비 오는 주간", 0.30, 0.96, 0, "가정 (stub)"),
    "competitor_open": ("근처 고깃집 개점", 0.15, 0.92, 0, "가정 (stub)"),
    "viral_blog": ("맛집 블로거 방문", 0.10, 1.06, 0, "가정 (stub)"),
    "staff_quit": ("알바 갑작스런 퇴사", 0.12, 0.97, 0, "가정 (stub)"),
}
SEGMENTS = ["twenties", "office", "family"]


def _pnl() -> dict:
    return yaml.safe_load((REPO / "research" / "hero_base.yaml").read_text(encoding="utf-8"))["_pnl_base"]


def default_plan() -> dict:
    p = _pnl()
    return {"meat_price": int(p["t_meat"]), "soju_price": 5000, "meat_grade": "domestic", "menu_extras": [],
            "banchan": 5, "staff_grilling": False, "staff_per_shift": 2, "close_hour": 24, "lunch": False,
            "terrace": True, "marketing_budget": 0, "group_reservations": False, "hygiene": "normal"}


def new_season(seed: int, mode: str) -> dict:
    return {"engine": "stub", "mode": mode, "seed": seed, "month_index": 0, "cash": 20_000_000, "rating": 4.2,
            "review_count": 180, "awareness": 1.0, "regular_share": 0.25, "fatigue": 30,
            "negative_months": 0, "closed": False, "plan": default_plan(), "history": []}


def draw_events(state: dict) -> list[str]:
    rng = random.Random(state["seed"] * 100 + state["month_index"])
    return [e for e, (_, prob, *_r) in EVENTS.items() if rng.random() < prob][:2]


def _month_numbers(state: dict, plan: dict, events: list[str]) -> dict:
    p = _pnl()
    month = MONTHS[state["month_index"] % len(MONTHS)]
    _, _, cal = CALENDAR[month]
    price_ratio = plan["meat_price"] / p["t_meat"]
    demand = cal * price_ratio ** -0.8 * (1 + 0.07 * (state["rating"] - 4.2)) * state["awareness"]
    demand *= 1.03 if plan["terrace"] else 1.0
    demand *= 1 + 0.000_000_02 * plan["marketing_budget"]
    for e in events:
        demand *= EVENTS[e][2]
    staff_cap = 1.0 if plan["staff_per_shift"] >= 2 else 0.9
    covers = p["covers_month"] * min(demand, 1.25) * staff_cap
    ticket = plan["meat_price"] * (p["rev_meat"] / p["t_meat"] / p["covers_month"]) + \
        plan["soju_price"] * (p["rev_alc"] / 4500 / p["covers_month"]) + p["t_side"]
    revenue = covers * ticket
    grade_cost = {"imported": 0.8, "domestic": 1.0, "aged": 1.25}[plan["meat_grade"]]
    food = p["food"] * covers / p["covers_month"] * grade_cost + sum(EVENTS[e][3] for e in events)
    labor = p["labor"] + (plan["staff_per_shift"] - 2) * p["l_pt"] / 2
    fixed = p["rent"] + p["mgmt"]
    fees = revenue * 0.9 * 0.0095
    op = revenue - food - labor - fixed - fees
    return {"month": month, "covers": covers, "revenue": revenue, "ticket": ticket, "food": food, "labor": labor,
            "fixed": fixed, "fees": fees, "op": op}


def preview(state: dict, plan: dict, events: list[str] | None = None) -> dict:
    n = _month_numbers(state, plan, list(events or []))
    return {"engine": "stub", "plan": plan, "expected": {k: round(n[k]) for k in ("covers", "revenue", "op")},
            "labels": [{"mechanism": "stub preview", "tag": "가정 (stub)"}]}


def play_month(state: dict, plan: dict, events: list[str]) -> dict:
    rng = random.Random(state["seed"] * 1000 + state["month_index"])
    base = _month_numbers(state, default_plan(), [])
    n = _month_numbers(state, plan, events)
    noise = rng.gauss(0, 0.05)
    draw = {k: round(n[k] * (1 + noise)) if k in ("covers", "revenue") else round(n[k]) for k in n if k != "month"}
    draw["op"] = round(n["op"] + (draw["revenue"] - n["revenue"]) * 0.6)
    band = {k: {"p10": round(n[k] * 0.9), "p50": round(n[k]), "p90": round(n[k] * 1.1)} for k in ("covers", "revenue", "op")}
    waterfall = [{"driver": "수요·가격", "delta": round(n["revenue"] - base["revenue"])},
                 {"driver": "식재료비", "delta": -round(n["food"] - base["food"])},
                 {"driver": "인건비", "delta": -round(n["labor"] - base["labor"])},
                 {"driver": "이번 달 운", "delta": draw["op"] - round(n["op"])}]
    s = copy.deepcopy(state)
    s["cash"] = round(s["cash"] + draw["op"])
    s["negative_months"] = s["negative_months"] + 1 if s["cash"] < 0 else 0
    s["closed"] = s["negative_months"] >= 2
    wait = 4 + (8 if plan["staff_per_shift"] < 2 else 0) + (5 if "staff_quit" in events else 0)
    price_hi = plan["meat_price"] > default_plan()["meat_price"]
    reviews = []
    for i in range(6):
        seg = SEGMENTS[i % 3]
        codes = []
        if wait >= 10:
            codes.append("long_wait")
        if price_hi:
            codes.append("price_high")
        if plan["meat_grade"] == "aged":
            codes.append("meat_good")
        if plan["staff_grilling"]:
            codes.append("staff_grilled")
        if not codes:
            codes.append(rng.choice(["meat_good", "friendly", "good_value"]))
        stars = max(1, min(5, round(4.3 - 0.8 * ("long_wait" in codes) - 0.5 * ("price_high" in codes)
                                     + 0.4 * ("meat_good" in codes) + rng.uniform(-0.6, 0.6))))
        reviews.append({"id": f"r{s['month_index'] + 1}-{i + 1}", "segment": seg, "stars": stars,
                        "party_size": {"twenties": 4, "office": 4, "family": 3}[seg] - (i % 2),
                        "wait_min": wait + i % 3, "reason_codes": codes,
                        "drivers": {"wait_min": wait + i % 3, "meat_price": plan["meat_price"],
                                    "soju_price": plan["soju_price"], "meat_grade": plan["meat_grade"],
                                    "staff_grilling": plan["staff_grilling"]}})
    s["rating"] = round(min(5.0, max(1.0, 0.8 * s["rating"] + 0.2 * sum(r["stars"] for r in reviews) / len(reviews))), 2)
    s["review_count"] += len(reviews)
    s["fatigue"] = max(0, min(100, s["fatigue"] + (15 if plan["staff_per_shift"] < 2 else -5)))
    s["plan"] = plan
    s["history"] = s["history"] + [{"month": n["month"], "op": draw["op"], "cash": s["cash"]}]
    s["month_index"] += 1
    month = n["month"]
    return {"engine": "stub", "month": month, "calendar": {"label": CALENDAR[month][0], "note": CALENDAR[month][1],
                                                        "demand_index": CALENDAR[month][2]},
            "events": [{"id": e, "label": EVENTS[e][0], "tag": EVENTS[e][4]} for e in events],
            "plan": plan, "draw": {"kpis": draw, **band}, "waterfall": waterfall, "state_after": s,
            "reviews": reviews, "owner_line": {"mood": "worried" if draw["op"] < 0 else "ok"},
            "night_events": [], "labels": [{"mechanism": "season stub", "tag": "가정 (stub)"}]}


# --- §12.1 in-night decisions (stub: one labelled decision point so the API and persona paths are testable) ---
STUB_DP = {"id": "dp-walkin_group", "kind": "walkin_group", "title_ko": "예약 없는 회식", "clock_min": 180, "clock": "20:00",
           "prompt_ko": "예약 없이 단체 손님이 들어왔습니다. 테이블은 거의 찼습니다.", "default": "turn_away",
           "monthly_count": 2, "count_tag": "가정 (stub)",
           "options": [{"id": "seat", "label_ko": "테이블 두 개 붙여 받는다", "effect_hint_ko": "큰 계산서 한 장", "tag": "가정 (stub)",
                        "source_id": None, "downside_ko": "줄 서 있던 손님이 더 기다리다 돌아간다"},
                       {"id": "turn_away", "label_ko": "죄송하다고 돌려보낸다", "effect_hint_ko": "지금 손님들의 자리를 지킨다",
                        "tag": "가정 (stub)", "source_id": None, "downside_ko": "단체 매출을 놓친다"}]}


def start_month(state: dict, plan: dict, events: list[str] | None = None) -> dict:
    month = MONTHS[state["month_index"] % len(MONTHS)]
    return {"engine": "stub", "month": month, "month_index": state["month_index"],
            "calendar": {"label": CALENDAR[month][0], "note": CALENDAR[month][1], "demand_index": CALENDAR[month][2]},
            "events": [{"id": e, "label": EVENTS[e][0], "tag": EVENTS[e][4]} for e in (events or [])], "plan": plan,
            "night": {"night": {"dow": "sat"}, "events": []}, "decision_points": [copy.deepcopy(STUB_DP)],
            "seed": state["seed"]}


_play_month_v1 = play_month


def play_month(state: dict, plan: dict, events: list[str], night_choices: dict | None = None) -> dict:  # noqa: F811
    r = _play_month_v1(state, plan, events)
    choice = (night_choices or {}).get(STUB_DP["id"], STUB_DP["default"])
    if choice not in {o["id"] for o in STUB_DP["options"]}:
        raise ValueError(f"unknown option {choice} for {STUB_DP['id']}")
    seat = choice == "seat"
    nd = {"id": STUB_DP["id"], "kind": "walkin_group", "option_id": choice, "default": STUB_DP["default"], "monthly_count": 2,
          "night_delta": {"revenue": 300_000 if seat else 0, "op": 150_000 if seat else 0, "covers": 9 if seat else 0,
                          "walkaways": 2 if seat else 0, "satisfaction": -0.02 if seat else 0.0},
          "month_delta": {"revenue": 600_000 if seat else 0, "op": 300_000 if seat else 0}, "state_delta": {}}
    r["decision_points"] = [copy.deepcopy(STUB_DP)]
    r["night_decisions"] = [nd]
    r["waterfall"] = r["waterfall"] + [{"driver": "밤 결정: 예약 없는 회식", "key": f"dp:{STUB_DP['id']}", "kind": "step",
                                        "delta": nd["month_delta"]["op"]}]
    if seat and r["reviews"]:
        r["reviews"][0]["cause_decisions"] = [STUB_DP["id"]]
        if len(r["reviews"]) > 1:
            r["reviews"][1]["decision_party"] = STUB_DP["id"]
            r["reviews"][1]["segment"] = "office"
    return r
