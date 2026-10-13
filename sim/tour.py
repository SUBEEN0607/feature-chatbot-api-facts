"""Welcome tour data (engines/_shared/ui/TOUR-SPEC.md): a 7-stop P&L walk of the default plan's first month with NO
external events (외부 사건이 없는 평소 달; a drawn event such as festival_week would present a boosted month as the
baseline), built from the season engine and the ontology. One generator for every front end: the web game reads
web/public/data/tour.json, Unity and Unreal read the copy in engines/_shared/ui/tour.json.

Inputs: sim.season (preview of the default plan with events=[] and its sensitivity on that same event-free month,
and the parameter values the engine used; the result does not depend on the season seed),
ontology/criteria.csv + edges.csv (names, units, formulas, which input feeds which driver), research/hero_base.yaml
(confidence, source, reviewed_by). Every number in the file is one of those values or arithmetic on them; the stop
list below only says which criterion, which camera anchor, which parameters and which lever, never a number.

  python -m sim.tour                      # write web/public/data/tour.json (+ the engines copy when that folder exists)
  python -m sim.tour --check              # exit 1 if the committed file differs from a fresh build
  python -m sim.tour --engines PATH       # copy target (default: ../engines/_shared/ui next to the repo)
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path

import yaml

from agents.ko import MINUS, eun, ieyo, man_won, won_ko
from sim import season as S
from sim.params import ROOT

OUT = ROOT / "web" / "public" / "data" / "tour.json"
# the declared baseline, one wording and one definition game-wide (sim.season.BASELINE_LABEL, baseline_inputs)
BASELINE_KO = S.BASELINE_LABEL
ENGINES = ROOT.parent / "engines" / "_shared" / "ui"

# plan lever -> the criterion it sets (a parameter row is tagged 레버 when the player can move it)
LEVER_CRITERION = {
    "meat_price": "prd_meat_price", "soju_price": "prd_alcohol_price", "meat_grade": "cst_meat_cost_per_portion",
    "banchan": "svc_banchan_count", "staff_grilling": "svc_staff_grilling", "staff_per_shift": "sto_parttimers",
    "close_hour": "drv_open_hours", "terrace": "sto_terrace", "marketing_budget": "mkt_sponsorship",
    "review_event": "mkt_review_event", "menu_extras": "prd_menu_count", "hygiene": "svc_cleanliness",
}
LEVER_KO = {"meat_price": "삼겹살 1인분", "soju_price": "소주 한 병", "meat_grade": "원육", "menu_extras": "메뉴 추가",
            "banchan": "반찬 가짓수", "staff_grilling": "직원이 구워주기", "staff_per_shift": "교대당 알바 수",
            "close_hour": "마감 시간", "lunch": "점심 영업", "terrace": "야장", "marketing_budget": "SNS 협찬 예산",
            "review_event": "리뷰 이벤트", "group_reservations": "단체·회식 예약", "hygiene": "청결 관리"}
# how the card says one step up / down of a lever (the amount comes from the sim's own step)
STEP_VERB = {"close_hour": ("늦게 닫으면", "일찍 닫으면"), "staff_per_shift": ("늘리면", "줄이면"), "banchan": ("늘리면", "줄이면"),
             "meat_grade": ("올리면 (숙성)", "내리면 (수입 냉동)"), "hygiene": ("올리면", "내리면")}
STEP_UNIT = {"meat_price": "원", "soju_price": "원", "banchan": "가지", "staff_per_shift": "명", "close_hour": "시간",
             "marketing_budget": "원"}

# The confirmed walk (TOUR-SPEC.md): anchor object, driver node, side, the parameters on its card (inputs of that
# node in edges.csv), the levers whose sim step the card shows, the 사장님 question. stat = the preview field.
STOPS = [
    {"anchor": "sign", "criterion_id": "drv_rent", "side": "cost", "stat": "rent", "params": ["sto_area_pyeong"],
     "levers": [], "question_ko": "간판부터 볼게요. 이 자리 월세가 한 달에 얼마쯤일까요?"},
    {"anchor": "menu_board", "criterion_id": "drv_ticket", "side": "revenue", "stat": "ticket",
     "params": ["prd_meat_price", "prd_portions_per_cover", "prd_alcohol_price", "prd_alcohol_per_cover", "prd_side_spend_per_cover"],
     "levers": ["meat_price"], "question_ko": "메뉴판이에요. 손님 한 분이 저녁 한 번에 얼마쯤 쓰실까요?"},
    {"anchor": "tables", "criterion_id": "drv_covers", "side": "revenue", "stat": "covers",
     "params": ["drv_seats", "sto_occupancy", "sto_table_turns", "drv_dwell_time", "drv_open_hours"],
     "levers": ["close_hour", "terrace"], "question_ko": "테이블이에요. 한 달에 손님이 몇 분쯤 앉으실까요?"},
    {"anchor": "grill", "criterion_id": "drv_food_cost", "side": "cost", "stat": "cogs",
     "params": ["cst_meat_cost_per_portion", "prd_portions_per_cover", "cst_alcohol_cost_per_bottle", "cst_side_cost_ratio",
                "cst_banchan_cost_per_cover"],
     "levers": ["meat_grade"], "question_ko": "불판 위 고기예요. 한 달 식재료비가 얼마쯤 나올까요?"},
    {"anchor": "staff", "criterion_id": "drv_labor_cost", "side": "cost", "stat": "labor",
     "params": ["sto_parttimers", "sto_parttime_shift_hours", "sto_parttime_wage", "cst_holiday_pay_factor", "cst_owner_imputed_wage"],
     "levers": ["staff_per_shift"], "question_ko": "직원들이에요. 한 달 인건비가 얼마쯤일까요? 제 몫까지 넣어서요"},
    {"anchor": "fridge", "criterion_id": "prd_alcohol_price", "side": "revenue", "stat": None,
     "params": ["prd_alcohol_price", "prd_alcohol_per_cover", "cst_alcohol_cost_per_bottle"], "feeds": ["drv_ticket", "drv_food_cost"],
     "levers": ["soju_price"], "question_ko": "소주 냉장고예요. 매출에서 술이 차지하는 몫이 얼마쯤일까요?"},
    {"anchor": "room", "criterion_id": "drv_operating_profit", "side": "result", "stat": "op", "params": [],
     "levers": [], "question_ko": "마지막으로 가게 전체예요. 이번 달 남는 돈, 영업이익은 얼마쯤일까요?"},
]
PNL_LINES = [("cogs", "drv_food_cost"), ("labor", "drv_labor_cost"), ("rent", "drv_rent"), ("mgmt", "drv_mgmt_cost"), ("fees", "drv_fees")]


def formula_ko(notes: str) -> str | None:
    """The '= …' clause of a criterion's notes when it is a formula in Korean terms; a parenthetical aside in English
    is dropped, anything else still carrying Latin text is not a formula (shared with web/scripts/sync_data.py)."""
    m = re.search(r"=\s*([^.]+)", notes or "")
    if not m:
        return None
    f = re.sub(r"\s*\([^)]*[A-Za-z][^)]*\)", "", m.group(1)).strip()
    ok = re.search(r"[가-힣]", f) and re.search(r"[×÷+−]", f) and not re.search(r"[A-Za-z]", f)
    return f if ok else None


def _num(v: float, d: int = 2) -> str:
    """Plain Korean number: thousands separators, no trailing zeros, the UI minus."""
    s = f"{abs(v):,.{d}f}".rstrip("0").rstrip(".") if not float(v).is_integer() else f"{abs(int(v)):,}"
    return f"{MINUS if v < 0 else ''}{s}"


def display(v: float, unit: str) -> str:
    if unit.startswith("₩/월"):
        return man_won(v)
    if unit.startswith("₩"):
        return won_ko(v)
    if unit == "비율":
        return f"{_num(v * 100, 1)}%"
    tail = {"명/월": "명", "명/일": "명", "분": "분", "시간/일": "시간", "시간": "시간", "석": "석", "일/월": "일", "평": "평",
            "인분/인": "인분", "병/인": "병", "명": "명", "개": "개", "배수": "배", "회/일": "회"}
    return f"{_num(v)}{tail.get(unit, ' ' + unit)}"


def buckets(order: int, v: float, unit: str) -> tuple[list[dict], int]:
    """Four fixed-width buckets on round numbers around the value; the answer sits in the 2nd tile on even stops and
    the 3rd on odd ones, so its position never depends on the number. Bounds: min inclusive, max exclusive."""
    a = abs(v) if v else 1.0
    mag = 10 ** math.floor(math.log10(a * 0.15))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= a * 0.15)
    lo = math.floor(v / step) * step
    k = 1 + order % 2
    edges = [lo - (k - 1) * step + i * step for i in range(3)]
    mw = man_won(1e4)[1:]   # the money suffix as man_won writes it ("만원" or "만 원"): ranges print it once at the end
    f = (lambda x: display(x, unit)) if not unit.startswith("₩/월") else (lambda x: man_won(x)[: -len(mw)] + "만")
    tail = mw[1:] if unit.startswith("₩/월") else ""
    labels = [f"{f(edges[0])}{tail} 아래", f"{f(edges[0])}~{f(edges[1])}{tail}", f"{f(edges[1])}~{f(edges[2])}{tail}", f"{f(edges[2])}{tail} 넘게"]
    bounds = [(None, edges[0]), (edges[0], edges[1]), (edges[1], edges[2]), (edges[2], None)]
    out = [{"label_ko": lab, "min": lo_, "max": hi_} for lab, (lo_, hi_) in zip(labels, bounds)]
    ans = next(i for i, (lo_, hi_) in enumerate(bounds) if (lo_ is None or v >= lo_) and (hi_ is None or v < hi_))
    return out, ans


def _sens_entry(lever: str, sens: dict) -> dict | None:
    s = sens.get(lever)
    if not s or not (s.get("up") or s.get("down")):
        return None
    step = s.get("step") or ""
    m = re.search(r"[\d,]+", step)
    if lever == "marketing_budget" and m:
        step_ko = man_won(int(m.group(0).replace(",", "")))
    elif m:
        step_ko = f"{m.group(0)}{STEP_UNIT.get(lever, '')}"
    else:
        step_ko = "한 단계" if "단계" in step else "켜고 끄기"
    pick = lambda d: {"op": round(d["op"]), "covers": round(d["covers"])} if d else None  # noqa: E731
    if step_ko == "켜고 끄기":
        up_ko, down_ko = "켜면", "끄면"
    else:
        v_up, v_down = STEP_VERB.get(lever, ("올리면", "내리면"))
        up_ko, down_ko = f"{step_ko} {v_up}", f"{step_ko} {v_down}"
    return {"lever": lever, "lever_ko": LEVER_KO[lever], "step_ko": step_ko, "up_ko": up_ko, "down_ko": down_ko,
            "up": pick(s.get("up")), "down": pick(s.get("down"))}


def build() -> dict:
    crit = {r["criterion_id"]: r for r in csv.DictReader(open(ROOT / "ontology" / "criteria.csv", encoding="utf-8"))}
    edges = list(csv.DictReader(open(ROOT / "ontology" / "edges.csv", encoding="utf-8")))
    hero = yaml.safe_load(open(ROOT / "research" / "hero_base.yaml", encoding="utf-8"))
    state, plan, events = S.baseline_inputs()   # no external events: the baseline month, not a festival or a price shock
    pv = S.preview(state, plan, events)
    ex, sens = pv["expected"], pv.get("sensitivity") or {}
    calc, su = S._calibrated(state, plan, events)    # the same month the preview reports, with the parameters it ran on
    used = su["params"]

    def row(cid: str) -> dict:
        h, c = hero.get(cid) or {}, crit[cid]
        src = (h.get("source_id") or c.get("source_id") or "")
        return {"h": h, "c": c, "sources": [x for x in re.split(r"[;,]\s*", src) if x], "confidence": h.get("confidence"),
                "reviewed": bool(h.get("reviewed_by"))}

    def param(pid: str, parents: list[str]) -> dict:
        r = row(pid)
        assert any(e["from_id"] == pid and e["to_id"] in parents for e in edges) or crit[pid]["driver_node"] in parents, \
            f"{pid} does not feed {parents} in the ontology"
        value = used.get(pid, r["h"].get("base"))
        lever = next((k for k, c in LEVER_CRITERION.items() if c == pid), None)
        conf = r["confidence"]   # None for a derived row (it has no confidence of its own)
        tag = "레버" if lever else (f"근거 {', '.join(r['sources'])}" if r["sources"] else "가정")
        return {"criterion_id": pid, "name_ko": crit[pid]["name_ko"], "value": value, "unit": crit[pid]["unit"],
                "display_ko": display(value, crit[pid]["unit"]) if isinstance(value, (int, float)) else str(value),
                "confidence": conf, "source_ids": r["sources"], "is_lever": bool(lever), "lever": lever, "tag_ko": tag,
                "reviewed": r["reviewed"]}

    revenue, alcohol_share = ex["revenue"], calc["alcohol_share"]
    stops = []
    for i, sp in enumerate(STOPS, start=1):
        cid = sp["criterion_id"]
        c, r = crit[cid], row(cid)
        if cid == "prd_alcohol_price":
            # 주류 is a term of 객단가 (병/인 × 주류가): the headline is its share of 매출, the sim's own alcohol_share
            value, unit = alcohol_share, "비율"
            formula = "병/인 × 주류가 ÷ 객단가"
            parent_formula = formula_ko(crit["drv_ticket"]["notes"])
            assert parent_formula and "병/인 × 주류가" in parent_formula
        else:
            value = ex[sp["stat"]]
            unit = "명/월" if cid == "drv_covers" else c["unit"]
            formula = formula_ko(c["notes"])
        params = [param(p, sp.get("feeds", [cid])) for p in sp["params"]]
        bks, ans = buckets(i, value, unit)
        share = alcohol_share if cid == "prd_alcohol_price" else value / revenue if unit.startswith("₩/월") and cid != "drv_revenue" else None
        disp = display(value, unit)
        name = c["name_ko"] if cid != "prd_alcohol_price" else "주류 매출 비중"
        if cid == "drv_operating_profit":
            reveal = f"매출 {man_won(revenue)}에서 다섯 가지 비용을 빼면 {man_won(value)}, 매출의 {_num(value / revenue * 100, 1)}%가 남아요"
        elif cid == "prd_alcohol_price":
            pr, bpc = used["prd_alcohol_price"], used["prd_alcohol_per_cover"]
            reveal = f"소주 한 병 {won_ko(pr)}, 손님 한 명이 {_num(bpc)}병쯤 마셔서 매출의 {_num(value * 100, 1)}%가 술이에요"
        elif share is not None:
            reveal = f"{eun(name)} 한 달 {disp}, 매출의 {_num(share * 100, 1)}%예요"
        else:
            reveal = f"{eun(name)} {ieyo(disp)}"
        prelim = (not r["reviewed"]) or r["confidence"] == "L" or any(not p["reviewed"] or p["confidence"] == "L" for p in params) \
            or c["method"] == "derived"
        stops.append({
            "order": i, "anchor": sp["anchor"], "criterion_id": cid, "title_ko": name, "side": sp["side"],
            "value": value, "unit": unit, "display_ko": disp, "share_of_revenue": share,
            "formula_ko": formula, "params": params,
            "sensitivity": [e for e in (_sens_entry(lv, sens) for lv in sp["levers"]) if e],
            "question_ko": sp["question_ko"], "buckets": bks, "answer_bucket": ans, "reveal_ko": reveal,
            "source_ids": r["sources"], "confidence": r["confidence"], "preliminary": bool(prelim),
        })
    cost = sum(ex[k] for k, _ in PNL_LINES)
    return {
        "version": 1, "month": pv["month"], "month_ko": (pv.get("calendar") or {}).get("label", f"{pv['month']}월"),
        "baseline_ko": BASELINE_KO, "events": pv.get("events"), "plan": pv["plan"],
        "source": "sim.season.preview (default plan, events=[]) + ontology/criteria.csv, edges.csv + research/hero_base.yaml",
        "pnl": {"revenue": revenue, "cost": cost, "op": ex["op"], "op_margin": ex["op_margin"],
                "lines": {k: ex[k] for k, _ in PNL_LINES},
                "lines_ko": {k: crit[cid]["name_ko"] for k, cid in PNL_LINES}},
        "review": {"reviewed": sum(1 for k, v in hero.items() if not k.startswith("_") and v.get("method") != "derived" and v.get("reviewed_by")),
                   "total": sum(1 for k, v in hero.items() if not k.startswith("_") and v.get("method") != "derived")},
        "stops": stops,
    }


def dumps(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--engines", default=str(ENGINES))
    a = ap.parse_args()
    text = dumps(build())
    if a.check:
        ok = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("tour.json up to date" if ok else "tour.json is stale: run python -m sim.tour")
        sys.exit(0 if ok else 1)
    OUT.write_text(text, encoding="utf-8")
    print("wrote", OUT)
    eng = Path(a.engines)
    if eng.is_dir():
        (eng / "tour.json").write_text(text, encoding="utf-8")
        print("wrote", eng / "tour.json")


if __name__ == "__main__":
    main()
