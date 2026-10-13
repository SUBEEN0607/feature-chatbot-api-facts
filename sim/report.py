"""Season report (docs/GAME-V2-SPEC.md §14): what happened, what to change, what went well, where luck decided.

Pure functions over a played season: `season` = {"seed", "mode", "months": [MonthResult, ...], "state": SeasonState}
(the API session has this shape). Counterfactuals re-run the analytic path (sim.season.step_estimate) from the
month's actual starting state with the same events and the player's later plans, and compare it with the same
analytic path for what was actually played, so the estimator's own bias cancels. In-night choices are re-played on
the month's own night (sim.season._decide_night). Every number here traces to season_table rows or to those runs.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np

from agents.ko import MINUS, eul, man_won, ro
from sim import season as S
from sim.params import ROOT

LEVER_KO = {"meat_price": "삼겹살 가격", "soju_price": "소주 가격", "meat_grade": "원육", "menu_extras": "메뉴 추가",
            "banchan": "반찬 가짓수", "staff_grilling": "직원이 구워 주기", "staff_per_shift": "교대당 알바 수",
            "close_hour": "마감 시간", "lunch": "점심 영업", "terrace": "야장", "marketing_budget": "SNS 협찬 예산",
            "review_event": "리뷰 이벤트", "group_reservations": "단체 예약", "hygiene": "청결 관리"}
ALTERNATIVES = {
    "meat_price": [16000, 17000, 18000, 19000, 20000, 21000, 22000], "soju_price": [4500, 5000, 5500, 6000],
    "meat_grade": ["imported", "domestic", "aged"],
    "menu_extras": [[], ["minari"], ["naengsam"], ["tongsam"], ["naengsam", "minari"]], "banchan": [3, 4, 5, 6, 7],
    "staff_grilling": [False, True], "staff_per_shift": [1, 2, 3], "close_hour": [23, 24, 25], "lunch": [False, True],
    "terrace": [False, True], "marketing_budget": [0, 500_000, 1_000_000], "review_event": [False, True],
    "group_reservations": [False, True], "hygiene": ["basic", "normal", "high"],
}
# where each lever's mechanism lives in research/season_params.yaml (for the 근거/가정 share)
LEVER_PARAMS = {
    "meat_price": ["satisfaction.expected_price", "satisfaction.price_over_weight", "meat_grade.door_weight"],
    "soju_price": ["satisfaction.expected_soju", "satisfaction.soju_over_weight"], "meat_grade": ["meat_grade"],
    "menu_extras": ["menu_extras"], "banchan": ["banchan"], "staff_grilling": ["staff_grilling"],
    "staff_per_shift": ["staff", "fatigue"], "close_hour": ["hours"], "lunch": ["lunch"], "terrace": ["terrace"],
    "marketing_budget": ["marketing.awareness_per_million", "marketing.expectation_per_million"],
    "review_event": ["marketing.review_event_prob_mult", "marketing.review_event_star_bias", "marketing.review_event_share"],
    "group_reservations": ["groups"], "hygiene": ["hygiene"],
}
DOWNSIDE = {"meat_price": "올리면 손님이 줄고 '비싸다'가 늘어난다", "soju_price": "올리면 병 수와 손님이 줄어든다",
            "meat_grade": "좋은 고기일수록 원가가 오르고 숙성은 편차가 생긴다", "menu_extras": "원가, 준비 시간, 폐기가 늘어난다",
            "banchan": "가짓수만큼 원가가 든다", "staff_grilling": "테이블마다 직원 시간이 들고 피로가 오른다",
            "staff_per_shift": "줄이면 서비스가 느려지고 피로·퇴사 위험이, 늘리면 인건비가 오른다",
            "close_hour": "늦게 닫으면 인건비·공과금·피로가 늘어난다", "lunch": "알바 시간, 공과금, 피로가 늘어난다",
            "terrace": "비 오면 소용없고 소음 민원 위험이 있다", "marketing_budget": "비용이 들고 기대가 높아져 만족이 떨어질 수 있다",
            "review_event": "리뷰당 음료 비용, 부풀려진 별점을 의심하는 손님", "group_reservations": "예약석이 워크인을 막고 노쇼가 생긴다",
            "hygiene": "철저할수록 인건비, 느슨할수록 위생점검 위험"}


# --- helpers ----------------------------------------------------------------------------------------------------
def _won(x: float) -> str:
    return man_won(x, plus=True)


def _value_ko(lever: str, x) -> str:
    if lever in ("meat_price", "soju_price"):
        return f"{x:,}원"
    if lever == "meat_grade":
        return {"imported": "수입 냉동", "domestic": "국내산 냉장", "aged": "숙성"}[x]
    if lever == "menu_extras":
        names = {"naengsam": "냉삼", "tongsam": "통삼겹", "minari": "미나리"}
        return "·".join(names[v] for v in x) if x else "추가 메뉴 없음"
    if lever == "banchan":
        return f"반찬 {x}가지"
    if lever == "staff_per_shift":
        return f"알바 {x}명"
    if lever == "close_hour":
        return f"{x % 24:02d}시 마감"
    if lever == "marketing_budget":
        return man_won(x)
    if lever == "hygiene":
        return {"basic": "기본", "normal": "보통", "high": "철저"}[x]
    return "켬" if x else "끔"


def _confidence(lever: str) -> dict:
    """Share of the lever's mechanism values that carry a source id (vs 가정)."""
    P = S.data()["P"]
    tags = []

    def walk(node):
        if isinstance(node, dict):
            if "tag" in node:
                tags.append(str(node["tag"]))
            for k, x in node.items():
                if k != "tag":
                    walk(x)
    for path in LEVER_PARAMS[lever]:
        node = P
        for key in path.split("."):
            node = node.get(key, {}) if isinstance(node, dict) else {}
        walk(node)
    sourced = sum(1 for t in tags if any(part.strip().startswith("S") for part in t.split(";")))
    share = sourced / len(tags) if tags else 0.0
    return {"sourced_share": round(share, 2), "tag": "근거" if share >= 0.5 else "가정", "values": len(tags)}


def _months(season: dict) -> list[dict]:
    return list(season.get("months") or [])


def _state_before(season: dict, i: int) -> dict:
    """The full state month i started from, with the seed it was actually played with (state_seed; guided months are
    played on a representative stream), so a replay draws the same night and decisions."""
    months = _months(season)
    if i == 0:
        st = S.new_season(int(season.get("seed", 0)), season.get("mode") or "free")
    else:
        st = copy.deepcopy(months[i - 1]["state_after"])
    if months and months[i].get("state_seed") is not None:
        st["seed"] = months[i]["state_seed"]
    return st


def _events(m: dict) -> list[str]:
    return [e["id"] if isinstance(e, dict) else e for e in m.get("events") or []]


def _path(state: dict, plans: list[dict], events: list[list[str]]) -> tuple[dict, list[dict]]:
    """Analytic months from `state` with these plans and events; returns the end state and each month's preview."""
    s, pvs = copy.deepcopy(state), []
    for plan, ev in zip(plans, events):
        if s.get("closed"):
            break
        pv, s = S.step_estimate(s, plan, ev)
        pvs.append(pv)
    return s, pvs


def _outcome(end: dict) -> dict:
    return {"cash": end["cash"], "store_value": S.season_value(end)["store_value"], "regular_share": end["regular_share"],
            "rating": end["rating"], "closed": bool(end.get("closed"))}


def _diff(a: dict, b: dict) -> dict:
    return {"cash_delta": a["cash"] - b["cash"], "store_value_delta": a["store_value"] - b["store_value"],
            "regular_share_delta": a["regular_share"] - b["regular_share"], "rating_delta": a["rating"] - b["rating"]}


# --- the table --------------------------------------------------------------------------------------------------
def season_table(season: dict) -> list[dict]:
    """One row per played month: events, every lever, night choices, prediction vs actual, KPIs, 평소 shadow, luck."""
    base = S.base_plan()
    rows = []
    for i, m in enumerate(_months(season)):
        k = m["draw"]["kpis"]
        sa = m["state_after"]
        plan = m["plan"]
        shadow = m["shadow"]["kpis"]["op"] if m.get("shadow") else None
        pred = m.get("prediction") or {}
        dps = {d["id"]: d for d in m.get("decision_points") or []}
        choices = [{"id": d["id"], "title_ko": dps.get(d["id"], {}).get("title_ko", d["kind"]), "option_id": d["option_id"],
                    "option_ko": next((o["label_ko"] for o in dps.get(d["id"], {}).get("options", []) if o["id"] == d["option_id"]), d["option_id"]),
                    "vs_default_op": d.get("vs_default_op")} for d in m.get("night_decisions") or []]
        rows.append({
            "month_index": m.get("month_index", i), "month": m["month"], "month_label": m["calendar"]["label"],
            "events": ", ".join(e.get("label", e.get("id")) if isinstance(e, dict) else str(e) for e in m.get("events") or []),
            "event_ids": _events(m),
            **{f"lever_{lv}": plan.get(lv) for lv in ALTERNATIVES},
            "levers_changed": ", ".join(LEVER_KO[lv] for lv in ALTERNATIVES if plan.get(lv) != base.get(lv)),
            "levers_changed_keys": [lv for lv in ALTERNATIVES if plan.get(lv) != base.get(lv)],
            "decisions": ", ".join(f"{c['title_ko']}: {c['option_ko']}" for c in choices), "night_choices": choices,
            "prediction": pred.get("predicted") if pred.get("metric", "op") == "op" else None,
            "prediction_metric": pred.get("metric"), "prediction_actual": pred.get("actual"),
            "prediction_error_pct": round(pred["abs_pct_error"] * 100, 1) if pred.get("abs_pct_error") is not None else None,
            "revenue": k["revenue"], "op": k["op"], "covers": k["covers"], "walkaways": k["walkaways"],
            "shadow_op": shadow, "net_vs_shadow": None if shadow is None else k["op"] - shadow,
            "p10_op": m["draw"]["p10"]["op"], "p50_op": m["draw"]["p50"]["op"], "p90_op": m["draw"]["p90"]["op"],
            "op_percentile": m["draw"].get("op_percentile"), "band_position": m["draw"].get("op_percentile"),
            "rating_after": sa["rating"], "rating_recent": sa.get("rating_recent", sa["rating"]),
            "regular_share": sa["regular_share"], "fatigue": sa["fatigue"], "cash_after": sa["cash"],
            "waterfall": [w for w in m.get("waterfall") or [] if w.get("kind") == "step"],
        })
    return rows


# --- counterfactuals --------------------------------------------------------------------------------------------
def _lever_candidates(season: dict, i: int) -> list[dict]:
    return _memo(season, "levers", _lever_candidates_raw, i)


def _lever_candidates_raw(season: dict, i: int) -> list[dict]:
    """For each lever: every other value in month i, re-estimated to the season end against the same path played."""
    months = _months(season)
    s0 = _state_before(season, i)
    plans = [m["plan"] for m in months[i:]]
    evs = [_events(m) for m in months[i:]]
    act_end, act_pvs = _path(s0, plans, evs)
    act = _outcome(act_end)
    out = []
    for lever, values in ALTERNATIVES.items():
        alts = []
        for alt in values:
            if alt == plans[0].get(lever):
                continue
            alt_plan = {**plans[0], lever: alt}
            end, pvs = _path(s0, [alt_plan] + plans[1:], evs)
            e0, a0 = pvs[0]["expected"], act_pvs[0]["expected"]
            alts.append({**_diff(_outcome(end), act), "to": alt, "alt_plan": alt_plan,
                         "cost": sum(max(0.0, e0[c] - a0[c]) for c in ("cogs", "labor", "mgmt"))})
        if alts:
            out.append({"lever": lever, "from": plans[0].get(lever), "alts": alts})
    return out


def _joint(season: dict, lever: str, to, idx: list[int]) -> dict:
    """The same lever change in several consecutive months at once, re-estimated to the season end."""
    months = _months(season)
    i0 = idx[0]
    s0 = _state_before(season, i0)
    plans = [m["plan"] for m in months[i0:]]
    evs = [_events(m) for m in months[i0:]]
    alt = [{**p, lever: to} if i0 + k in idx else p for k, p in enumerate(plans)]
    return _diff(_outcome(_path(s0, alt, evs)[0]), _outcome(_path(s0, plans, evs)[0]))


_MEMO: dict = {}


def _key(season: dict, *parts) -> tuple:
    months = _months(season)
    return (season.get("id"), id(season), len(months), months[-1]["state_after"]["cash"] if months else None, *parts)


def _memo(season: dict, name: str, fn, *args):
    k = _key(season, name, json.dumps(args, sort_keys=True, default=str))
    if k not in _MEMO:
        if len(_MEMO) > 512:
            _MEMO.clear()
        _MEMO[k] = fn(season, *args)
    return _MEMO[k]


def _decide(season: dict, i: int, choices: dict) -> dict:
    return _memo(season, "decide", _decide_raw, i, choices)


def _decide_raw(season: dict, i: int, choices: dict) -> dict:
    """Re-play month i's night with these choices (same seed path as play_month; the night is picked once)."""
    m = _months(season)[i]
    st = _state_before(season, i)
    events = _events(m)
    rng = S._rng(st, 2)
    plan = S._validate(m["plan"])
    closure, _ = S._hygiene_and_sickness(st, plan, events, rng)
    su = S._setup(st, plan, events, closure_days=closure, quit_now="staff_quit" in events)
    seed_draw = int(rng.integers(1 << 30))
    pick = _memo(season, "pick", lambda _s, _i: S._night_pick(su, seed_draw), i)
    return S._decide_night(st, su, seed_draw, choices, pick=tuple(pick))


def _night_candidates(season: dict, i: int) -> list[dict]:
    return _memo(season, "night", _night_candidates_raw, i)


def _night_candidates_raw(season: dict, i: int) -> list[dict]:
    """For each night decision of month i: every other option, re-played on that night, then the rest of the season."""
    months = _months(season)
    m = months[i]
    if not m.get("night_decisions"):
        return []
    chosen = {d["id"]: d["option_id"] for d in m["night_decisions"]}
    dps = {d["id"]: d for d in m.get("decision_points") or []}
    try:
        actual_rows = {r["dp"]["id"]: r for r in _decide(season, i, chosen)["rows"]}
    except ValueError:   # the replay does not draw this month's decisions (a season from an older engine): skip
        return []
    after = copy.deepcopy(m["state_after"])
    rest_plans = [x["plan"] for x in months[i + 1:]]
    rest_evs = [_events(x) for x in months[i + 1:]]
    act = _outcome(_path(after, rest_plans, rest_evs)[0])
    out = []
    for dp_id, opt in chosen.items():
        dp = dps.get(dp_id)
        if not dp or dp_id not in actual_rows:
            continue
        alts = []
        for o in dp["options"]:
            if o["id"] == opt:
                continue
            alt_rows = {r["dp"]["id"]: r for r in _decide(season, i, {**chosen, dp_id: o["id"]})["rows"]}
            d_op = alt_rows[dp_id]["chosen"]["month"]["op"] - actual_rows[dp_id]["chosen"]["month"]["op"]
            d_state = {k: alt_rows[dp_id]["chosen"]["state"].get(k, 0.0) - actual_rows[dp_id]["chosen"]["state"].get(k, 0.0)
                       for k in ("fatigue", "awareness", "rating")}
            s1 = copy.deepcopy(after)
            s1["cash"] += d_op
            for k, x in d_state.items():
                s1[k] = s1[k] + x
            eff = S._dp_effect(dp, o["id"], S._setup(_state_before(season, i), m["plan"], _events(m)), 0)
            alts.append({**_diff(_outcome(_path(s1, rest_plans, rest_evs)[0]), act), "to": o["id"], "to_ko": o["label_ko"],
                         "cost": dp["monthly_count"] * (eff["labor"] + eff["other"] + eff["food"]),
                         "downside_ko": o["downside_ko"], "tag": o["tag"], "month_op_delta": d_op})
        if alts:
            out.append({"decision": dp_id, "kind": dp["kind"], "title_ko": dp["title_ko"], "from": opt,
                        "from_ko": next(o["label_ko"] for o in dp["options"] if o["id"] == opt), "alts": alts})
    return out


def _takeaway(label: str, what: str, d: dict) -> str:
    parts = [f"시즌 끝 현금 {_won(d['cash_delta'])}", f"가게 가치 {_won(d['store_value_delta'])}"]
    pp = round(d.get("regular_share_delta", 0) * 100)
    if pp:
        parts.append(f"단골 {MINUS if pp < 0 else '+'}{abs(pp)}%p")
    return f"{label}에 {what}, " + ", ".join(parts)


# --- DES re-scoring (analytic paths alone overstate levers whose cost comes through state-driven events) -------
ENDOGENOUS = ("staff_quit", "owner_sick", "noise_complaint", "aged_spoilage")   # drawn from the state the plan makes
DES_RUNS = 8          # paired seeds per path (same seeds for the alternative and for what was played)
DES_CANDIDATES = 10   # analytic top candidates re-scored with the DES
_DES_CACHE: dict = {}


def _des_path(job: tuple) -> dict:
    """One DES season path: from s0, these plans, the month's outside events fixed and the plan-driven events
    redrawn from each run's own state (fatigue makes quits, last month's 숙성 makes spoilage)."""
    s0, plans, exo, k = job
    s = copy.deepcopy(s0)
    s["seed"] = int(s0["seed"]) * 1000 + k
    for plan, ev in zip(plans, exo):
        if s.get("closed"):
            break
        endo = [e for e in S.draw_events(s) if e in ENDOGENOUS]
        s = S.play_month(s, plan, list(ev) + endo, lean=True)["state_after"]
    return _outcome(s)


def _run_jobs(jobs: list[tuple]) -> list[dict]:
    keys = [json.dumps([j[0]["seed"], j[0]["month_index"], j[0]["cash"], j[1], j[2], j[3]], sort_keys=True, default=str)
            for j in jobs]
    todo = [(k, j) for k, j in zip(keys, jobs) if k not in _DES_CACHE]
    uniq = dict(todo)
    if uniq:
        items = list(uniq.items())
        try:   # paths are independent: run them on a forked pool, serial if that is not possible
            import multiprocessing as mp
            from concurrent.futures import ProcessPoolExecutor
            with ProcessPoolExecutor(max_workers=min(12, (mp.cpu_count() or 2)), mp_context=mp.get_context("fork")) as ex:
                outs = list(ex.map(_des_path, [j for _, j in items], chunksize=4))
        except Exception:   # noqa: BLE001
            outs = [_des_path(j) for _, j in items]
        for (k, _), o in zip(items, outs):
            _DES_CACHE[k] = o
        if len(_DES_CACHE) > 5000:
            _DES_CACHE.clear()
            for (k, _), o in zip(items, outs):
                _DES_CACHE[k] = o
    return [_DES_CACHE[k] for k in keys]


def _exo(m: dict) -> list[str]:
    return [e for e in _events(m) if e not in ENDOGENOUS]


def _des_rescore(season: dict) -> dict:
    return _memo(season, "des", _des_rescore_raw)


def _des_rescore_raw(season: dict) -> dict:
    """Re-score the analytic top lever candidates with paired DES paths; keep those where both agree (same sign,
    within 2x on 가게 가치), with the DES numbers; flag the rest."""
    months = _months(season)
    cands = [x for x in _merge_runs(season, _items(season, "value")) if x["kind"] == "lever" and x["store_value_delta"] > 0]
    for x in cands:
        x["store_value_per_month"] = x["store_value_delta"] / len(x.get("month_indices") or [x["month_index"]])
    cands.sort(key=lambda x: (-x["store_value_per_month"], x["i"], x["lever"]))
    cands = cands[:DES_CANDIDATES]
    jobs, plan_of = [], []
    for x in cands:
        i0 = x["i"]
        idx = [i0 + d for d in range(len(x.get("month_indices") or [0]))]
        s0 = _state_before(season, i0)
        act = [m["plan"] for m in months[i0:]]
        alt = [{**p, x["lever"]: x["to"]} if i0 + d in idx else p for d, p in enumerate(act)]
        exo = [_exo(m) for m in months[i0:]]
        for k in range(DES_RUNS):
            jobs += [(s0, act, exo, k), (s0, alt, exo, k)]
        plan_of.append(x)
    outs = _run_jobs(jobs)
    kept, flagged = [], []
    for n, x in enumerate(cands):
        pairs = [(outs[2 * (n * DES_RUNS + k)], outs[2 * (n * DES_RUNS + k) + 1]) for k in range(DES_RUNS)]
        d_cash = [b["cash"] - a["cash"] for a, b in pairs]
        d_val = [b["store_value"] - a["store_value"] for a, b in pairs]
        d_reg = [b["regular_share"] - a["regular_share"] for a, b in pairs]
        des = {"cash_delta": float(np.mean(d_cash)), "store_value_delta": float(np.mean(d_val)),
               "regular_share_delta": float(np.mean(d_reg)), "runs": DES_RUNS,
               "store_value_se": float(np.std(d_val) / np.sqrt(DES_RUNS))}
        ana = {k: x[k] for k in ("cash_delta", "store_value_delta", "regular_share_delta")}
        a_v, d_v = ana["store_value_delta"], des["store_value_delta"]
        agree = d_v > 0 and 0.5 <= a_v / d_v <= 2.0
        y = {**x, "analytic": ana, "des": des, "agree": agree}
        if agree:
            y.update({"cash_delta": des["cash_delta"], "store_value_delta": d_v, "regular_share_delta": des["regular_share_delta"],
                      "basis": x["basis"] + f"; 시뮬레이션 {DES_RUNS}회 재실행으로 확인 (가게 가치 ±{des['store_value_se'] / 1e4:,.0f}만원)"})
            kept.append(y)
        else:
            flagged.append(y)
    return {"kept": kept, "flagged": flagged}


def warm(season: dict) -> None:
    """Precompute the report (DES re-scoring is the slow part); call in the background after the last month."""
    improvements(season)
    cash_only(season)
    good_decisions(season)


def _items(season: dict, mode: str) -> list[dict]:
    """Per month: each lever's and each night decision's best alternative. mode 'value': best 가게 가치 gain (only
    gains); mode 'cash_only': best cash gain among alternatives that lower 가게 가치."""
    found = []
    for i, m in enumerate(_months(season)):
        label = m["calendar"]["label"]
        for c in _lever_candidates(season, i):
            pool = ([a for a in c["alts"] if a["store_value_delta"] > 0] if mode == "value"
                    else [a for a in c["alts"] if a["cash_delta"] > 0 and a["store_value_delta"] <= 0])
            if not pool:
                continue
            a = max(pool, key=lambda x: x["store_value_delta"] if mode == "value" else x["cash_delta"])
            conf = _confidence(c["lever"])
            found.append({"kind": "lever", "key": c["lever"], "i": i, "month_index": m.get("month_index", i),
                          "month_label": label, "lever": c["lever"], "lever_ko": LEVER_KO[c["lever"]], "from": c["from"],
                          "to": a["to"], "from_ko": _value_ko(c["lever"], c["from"]), "to_ko": _value_ko(c["lever"], a["to"]),
                          "alt_plan": a["alt_plan"], "cost": a["cost"], "downside_ko": DOWNSIDE[c["lever"]],
                          "confidence": conf, "tag": conf["tag"],
                          "basis": f"분석 추정 (같은 사건, 이후 계획 그대로), 메커니즘 값 {conf['values']}개 중 근거 {conf['sourced_share']:.0%}",
                          **{k: a[k] for k in ("cash_delta", "store_value_delta", "regular_share_delta", "rating_delta")}})
        for c in _night_candidates(season, i):
            pool = ([a for a in c["alts"] if a["store_value_delta"] > 0] if mode == "value"
                    else [a for a in c["alts"] if a["cash_delta"] > 0 and a["store_value_delta"] <= 0])
            if not pool:
                continue
            a = max(pool, key=lambda x: x["store_value_delta"] if mode == "value" else x["cash_delta"])
            found.append({"kind": "night_choice", "key": f"dp:{c['kind']}", "i": i, "month_index": m.get("month_index", i),
                          "month_label": label, "lever": None, "decision": c["decision"], "decision_ko": c["title_ko"],
                          "from": c["from"], "to": a["to"], "from_ko": c["from_ko"], "to_ko": a["to_ko"],
                          "alt_plan": m["plan"], "alt_night_choices": {c["decision"]: a["to"]}, "cost": a["cost"],
                          "downside_ko": a["downside_ko"],
                          "confidence": {"sourced_share": 0.0 if a["tag"] == "가정" else 1.0, "tag": a["tag"], "values": 1},
                          "tag": a["tag"], "basis": f"그 밤을 다시 시뮬레이션 (한 달 {_won(a['month_op_delta'])}), 이후는 분석 추정",
                          **{k: a[k] for k in ("cash_delta", "store_value_delta", "regular_share_delta", "rating_delta")}})
    return found


def _merge_runs(season: dict, items: list[dict]) -> list[dict]:
    """Adjacent months with the same lever change (same from and to) become one item over the month range,
    re-estimated jointly (the change in all those months together)."""
    months = _months(season)
    levers = sorted((x for x in items if x["kind"] == "lever"), key=lambda x: (x["lever"], str(x["from"]), str(x["to"]), x["i"]))
    out, run = [x for x in items if x["kind"] != "lever"], []

    def flush():
        if not run:
            return
        if len(run) == 1:
            out.append({**run[0], "month_indices": [run[0]["month_index"]]})
        else:
            idx = [x["i"] for x in run]
            d = _joint(season, run[0]["lever"], run[0]["to"], idx)
            label = f"{months[idx[0]]['calendar']['label']}~{months[idx[-1]]['calendar']['label']}"
            out.append({**run[0], **d, "month_label": label, "month_indices": [x["month_index"] for x in run],
                        "alt_plans": {x["month_index"]: x["alt_plan"] for x in run}, "cost": sum(x["cost"] for x in run)})
    for x in levers:
        if run and (x["lever"], x["from"], x["to"]) == (run[-1]["lever"], run[-1]["from"], run[-1]["to"]) and x["i"] == run[-1]["i"] + 1:
            run.append(x)
        else:
            flush()
            run = [x]
    flush()
    return out


def _finish(x: dict) -> dict:
    if x["kind"] == "lever":
        what = f"{eul(x['lever_ko'])} {x['from_ko']}에서 {ro(x['to_ko'])} 바꿨다면"
    else:
        what = f"밤 결정 '{x['decision_ko']}'에서 '{x['from_ko']}' 대신 {eul(chr(39) + x['to_ko'] + chr(39))} 골랐다면"
    take = _takeaway(x["month_label"], what, x)
    i = x.pop("i")
    x.pop("key")
    return {"id": f"m{i}-{x['lever'] or x['decision']}", **x, "takeaway_ko": take, "why_ko": take}


def improvements(season: dict, top: int = 5, per_key: int = 2) -> list[dict]:
    """Ranked counterfactuals by 가게 가치 gained (cash + the 6-month forecast) per month of change, never one that
    lowers it. For each month, the best alternative of every lever and night choice, re-estimated over the rest of
    the season (same events, the player's later plans); adjacent months with the same change merge into one item.
    Lever candidates come from the analytic pass, then the top ones are re-scored with paired DES paths (plan-driven
    events redrawn) and only kept where both agree, with the DES numbers; at most `per_key` items per lever."""
    rescored = _des_rescore(season)
    nights = [x for x in _items(season, "value") if x["kind"] == "night_choice"]   # already from a re-played night
    items = [dict(x) for x in rescored["kept"]] + [{**x, "month_indices": [x["month_index"]]} for x in nights]
    items = [x for x in items if x["store_value_delta"] > 0]
    for x in items:   # a six-month change and a one-month mistake compare per month of change
        x["store_value_per_month"] = x["store_value_delta"] / len(x.get("month_indices") or [x["month_index"]])
    items.sort(key=lambda x: (-x["store_value_per_month"], x["i"], str(x["lever"] or x["decision"])))
    out, count = [], {}
    for x in items:
        if count.get(x["key"], 0) >= per_key:
            continue
        count[x["key"]] = count.get(x["key"], 0) + 1
        out.append(_finish(dict(x)))
        if len(out) == top:
            break
    return out


def uncertain(season: dict) -> list[dict]:
    """Analytic candidates the DES does not confirm (opposite sign or more than 2x apart): shown, not ranked."""
    out = []
    for x in _des_rescore(season)["flagged"]:
        y = _finish(dict(x))
        y["note_ko"] = (f"빠른 추정은 가게 가치 {_won(x['analytic']['store_value_delta'])}, 시뮬레이션 재실행은 "
                        f"{_won(x['des']['store_value_delta'])}: 결과가 엇갈려 개선안에서 뺐습니다")
        out.append(y)
    return out


def cash_only(season: dict, top: int = 3) -> list[dict]:
    """현금만 늘리는 선택 (주의): alternatives that would have raised season-end cash but lowered 가게 가치, with both
    numbers, so a cash-only recommendation is never presented as an improvement."""
    items = _merge_runs(season, _items(season, "cash_only"))
    items = [x for x in items if x["cash_delta"] > 0 and x["store_value_delta"] <= 0]
    items.sort(key=lambda x: (-x["cash_delta"], x["i"]))
    out = []
    for x in items[:top]:
        y = _finish(dict(x))
        what = (f"{eul(y['lever_ko'])} {ro(y['to_ko'])}" if y["kind"] == "lever"
                else f"'{y['decision_ko']}'에서 {eul(chr(39) + y['to_ko'] + chr(39))}")
        y["warning_ko"] = (f"{y['month_label']}에 {what} 했다면 현금은 {_won(y['cash_delta'])}이지만 가게 가치는 "
                           f"{_won(y['store_value_delta'])}. 당장 남지만 손님과 평판을 깎는 선택입니다")
        out.append(y)
    return out


def good_decisions(season: dict, top: int = 3) -> list[dict]:
    """Choices that beat the alternative on 가게 가치: a lever set away from 평소 that did better than going back to 평소
    (same analytic path), or a night choice better than every other option."""
    months = _months(season)
    base = S.base_plan()
    found = []
    for i, m in enumerate(months):
        label = m["calendar"]["label"]
        net = (m["draw"]["kpis"]["op"] - m["shadow"]["kpis"]["op"]) if m.get("shadow") else None
        for c in _lever_candidates(season, i):
            if c["from"] == base.get(c["lever"]):
                continue
            back = next((a for a in c["alts"] if a["to"] == base[c["lever"]]), None)
            if back is None or back["store_value_delta"] >= 0:
                continue
            d = {k: -back[k] for k in ("cash_delta", "store_value_delta", "regular_share_delta", "rating_delta")}
            v = _value_ko(c["lever"], c["from"])
            found.append({"month_index": m.get("month_index", i), "month_label": label, "kind": "lever", "lever": c["lever"],
                          "levers": [c["lever"]], "net_vs_shadow": net, **d,
                          "what_ko": f"{LEVER_KO[c['lever']]} {v} (평소 {_value_ko(c['lever'], base[c['lever']])})",
                          "why_ko": _takeaway(label, f"{eul(LEVER_KO[c['lever']])} {ro(v)} 한 덕분에", d)})
        for c in _night_candidates(season, i):
            best = max(c["alts"], key=lambda a: a["store_value_delta"])
            if best["store_value_delta"] < 0:   # every other option would have done worse
                d = {k: -best[k] for k in ("cash_delta", "store_value_delta", "regular_share_delta", "rating_delta")}
                found.append({"month_index": m.get("month_index", i), "month_label": label, "kind": "night_choice",
                              "decision": c["decision"], "levers": [], "net_vs_shadow": net, **d,
                              "what_ko": f"밤 결정 '{c['title_ko']}': {c['from_ko']}",
                              "why_ko": _takeaway(label, f"'{c['title_ko']}'에서 {eul(chr(39) + c['from_ko'] + chr(39))} 고른 덕분에", d)})
    found.sort(key=lambda x: (-x["store_value_delta"], x["month_label"]))
    return found[:top]


def luck_months(season: dict) -> list[dict]:
    """Months where the draw, not the plan, explains most of the gap to 평소: the month sits in the outer fifth of
    its own band and the draw's distance from the band median is larger than the plan's effect (median - 평소)."""
    out = []
    for r in season_table(season):
        pos = r["op_percentile"]
        if pos is None or r["shadow_op"] is None:
            continue
        luck = r["op"] - r["p50_op"]
        plan_effect = r["p50_op"] - r["shadow_op"]
        if (pos <= 0.2 or pos >= 0.8) and abs(luck) > abs(plan_effect):
            good = luck > 0
            out.append({"month_index": r["month_index"], "month_label": r["month_label"], "band_position": pos,
                        "op": r["op"], "p10_op": r["p10_op"], "p50_op": r["p50_op"], "p90_op": r["p90_op"],
                        "luck_won": luck, "plan_effect_won": plan_effect, "luck": "운이 좋았던 달" if good else "운이 나빴던 달",
                        "luck_ko": (f"{r['month_label']}은 같은 계획으로 흔히 나오는 결과보다 {_won(luck)}: "
                                    f"계획의 효과 ({_won(plan_effect)})보다 운의 몫이 컸습니다")})
    return out


def _review_counts(review: dict | None) -> dict | None:
    if review:
        return review
    path = ROOT / "web" / "public" / "data" / "hero.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("review")
    except (OSError, ValueError):
        return None


def season_summary(season: dict, review: dict | None = None) -> dict:
    """Totals vs the 평소 shadow, ending state and 가게 가치, closure reason, prediction accuracy, 검토 N/82 caveat."""
    rows = season_table(season)
    st = season.get("state") or (_months(season)[-1]["state_after"] if _months(season) else {})
    ops = [r["op"] for r in rows]
    shadows = [r["shadow_op"] for r in rows if r["shadow_op"] is not None]
    nets = [r["net_vs_shadow"] for r in rows if r["net_vs_shadow"] is not None]
    errs = [r["prediction_error_pct"] for r in rows if r["prediction_error_pct"] is not None]
    rc = _review_counts(review)
    best = max(rows, key=lambda r: r["op"]) if rows else None
    worst = min(rows, key=lambda r: r["op"]) if rows else None
    return {
        "months_played": len(rows), "total_op": float(sum(ops)), "total_shadow_op": float(sum(shadows)),
        "total_vs_shadow": float(sum(nets)), "ending_cash": st.get("cash"), "ending_rating": st.get("rating"),
        "ending_regular_share": st.get("regular_share"), "store_value": S.season_value(st)["store_value"] if st else None,
        "closed": bool(st.get("closed")), "closed_reason": st.get("closed_reason"),
        "closed_reason_ko": {"cash": "현금이 두 달 연속 0 아래 (S21; S09)", "revenue": "매출이 평소의 60% 이하로 두 달 연속 (S89)"}.get(st.get("closed_reason")),
        "best_month": best and {"month_label": best["month_label"], "op": best["op"]},
        "worst_month": worst and {"month_label": worst["month_label"], "op": worst["op"]},
        "prediction_months": len(errs), "prediction_mean_abs_error_pct": float(np.mean(errs)) if errs else None,
        "review": rc,
        "caveat_ko": (f"검토 {rc['reviewed']}/{rc['total']}: 사람이 확인한 수치는 {rc['reviewed']}개입니다. 나머지는 출처 또는 가정이고, "
                      "개선안은 분석 추정입니다." if rc else "개선안은 분석 추정이고 가정이 섞여 있습니다."),
    }
