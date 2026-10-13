"""Precompute every shock × owner action (plus base) so the demo runs fully offline.

  python -m sim.precompute [--runs 200] [--seed 42] [--out web/public/runs] [--season | --season-only]

Writes:
  index.json             menus, labels, base KPIs, and an OP matrix (shock × action) for the choice cards
  base.json              base KPI bands, driver-tree values (sim p50 + Excel P&L), one logged Saturday night
  <shock>/<action>.json  base / shocked / reacted KPI bands, headlines, driver values, what moved, one night
  season/index.json, season/<state>.json   (--season) every lasting-choice state × shock, for 6-month seasons
Seeded and deterministic: the same inputs give byte-identical files. No LLM calls.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from sim import season_v1 as S
from sim.engine import KPIS, driver_p50, monte_carlo, sample_night, summarize
from sim.evidence import ACTION_MECHANISMS, SHOCK_MECHANISMS, evidence
from sim.labels import SEGMENT_LABELS, SHOCK_IF, SHOCK_LABELS, headline
from sim.owner_actions import MENU, apply_action
from sim.params import ROOT, load_params, load_profile
from sim.shocks import apply_shock, load_shocks

EXCEL = {  # driver node -> workbook P&L key (hero_base.yaml _pnl_base) or a parameter
    "drv_operating_profit": "op", "drv_revenue": "rev", "drv_total_cost": "cost", "drv_covers": "covers_day",
    "drv_ticket": "ticket", "drv_arrival_rate": "arrivals_day", "drv_seats": "seats", "drv_food_cost": "food",
    "drv_labor_cost": "labor", "drv_rent": "rent", "drv_mgmt_cost": "mgmt", "drv_fees": "fees",
    "cst_alcohol_meat_ratio": "alc_meat_ratio", "cst_order_volume": "order_kg", "lbl_revpash": "revpash",
}
OP_PARTS = [("drv_revenue", 1), ("drv_food_cost", -1), ("drv_labor_cost", -1), ("drv_rent", -1),
            ("drv_mgmt_cost", -1), ("drv_fees", -1)]
DRIVER_KO = {"drv_revenue": "매출", "drv_food_cost": "식재료비", "drv_labor_cost": "인건비", "drv_rent": "임차료",
             "drv_mgmt_cost": "관리비", "drv_fees": "수수료"}


def rnd(x):
    if isinstance(x, float):
        return round(x, 4) if abs(x) < 1000 else round(x)
    if isinstance(x, dict):
        return {k: rnd(v) for k, v in x.items()}
    if isinstance(x, list):
        return [rnd(v) for v in x]
    return x


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rnd(obj), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def night_json(r: dict) -> dict:
    return {"dow": r["dow"], "terrace_open": r["terrace_open"], "tables_available": r["tables_available"],
            "open_clock": "17:00", "events": r["events"]}


def moved(before: dict, after: dict) -> list[dict]:
    """Which OP line moved most (p50 differences; signed contribution to OP)."""
    out = [{"driver": d, "label": DRIVER_KO[d], "op_effect": sign * (after[d] - before[d])} for d, sign in OP_PARTS]
    return sorted(out, key=lambda x: -abs(x["op_effect"]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=200)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=str(ROOT / "web" / "public" / "runs"))
    ap.add_argument("--season", action="store_true", help="also write the season grid (48 states × shocks)")
    ap.add_argument("--season-only", action="store_true", help="write only the season grid")
    args = ap.parse_args()
    out = Path(args.out)
    t0 = time.time()
    params, profile, shocks = load_params(), load_profile(), load_shocks()
    # game.exclude (industry yaml): shocks / actions left out of the demo (still available to sim.run and tests)
    excluded = set(profile.get("game", {}).get("exclude", []))
    shocks = {k: v for k, v in shocks.items() if k not in excluded}
    menu = {k: v for k, v in MENU.items() if k not in excluded}
    meta = {"runs": args.runs, "seed": args.seed, "illustrative": True, "generated_by": "python -m sim.precompute",
            "flags": profile.get("game", {})}
    if args.season_only:
        season(params, profile, shocks, menu, out, args, meta, t0)
        return

    base_m = monte_carlo(params, profile, args.runs, args.seed)
    base, base_drv = summarize(base_m), driver_p50(base_m)
    excel = {n: params["_pnl"][k] for n, k in EXCEL.items()}
    excel["drv_dwell_time"] = params["drv_dwell_time"]
    excel["drv_balk_rate"] = params["drv_balk_rate"]
    mix = {s: float(sum(m["covers_by_segment"][s] for m in base_m) / sum(m["covers"] for m in base_m))
           for s in SEGMENT_LABELS}
    dump(out / "base.json", {"meta": meta, "kpis": base, "drivers": base_drv, "excel": excel,
                             "segment_cover_share": mix, "segments": SEGMENT_LABELS,
                             "headline": headline(None, None, base["op"]["p50"], base["op"]["p50"]),
                             "night": night_json(sample_night(params, profile, args.seed))})

    matrix = {}
    for sid in sorted(shocks):
        sh = shocks[sid]
        shock_m = monte_carlo(params, profile, args.runs, args.seed, param_fn=lambda p, rng, sh=sh: apply_shock(p, sh, rng))
        shocked, shock_drv = summarize(shock_m), driver_p50(shock_m)
        matrix[sid] = {}
        for aid, spec in menu.items():
            a_args = spec["default_args"]
            react_m = monte_carlo(params, profile, args.runs, args.seed,
                                  param_fn=lambda p, rng, sh=sh, aid=aid, a_args=a_args: apply_action(apply_shock(p, sh, rng), aid, **a_args))
            reacted, react_drv = summarize(react_m), driver_p50(react_m)
            night_params = apply_action(apply_shock(params, sh), aid, **a_args)
            op0, op1, op2 = base["op"]["p50"], shocked["op"]["p50"], reacted["op"]["p50"]
            run = {
                "meta": meta,
                "shock": {"id": sid, "label": SHOCK_LABELS[sid], "if": SHOCK_IF[sid], "driver": sh["driver"], "params": sh["params"]},
                "action": {"id": aid, "label": spec["label"], "phrase": spec["phrase"], "description": spec["description_ko"], "args": a_args},
                "base": base, "shocked": shocked, "reacted": reacted,
                "delta_p50": {k: reacted[k]["p50"] - base[k]["p50"] for k in KPIS},
                "delta_vs_shock_p50": {k: reacted[k]["p50"] - shocked[k]["p50"] for k in KPIS},
                "shock_headline": headline(sid, None, op0, op1),
                "headline": headline(sid, spec["phrase"], op0, op2),
                "drivers": {"base": base_drv, "shocked": shock_drv, "reacted": react_drv},
                "moved": {"shock": moved(base_drv, shock_drv), "choice": moved(shock_drv, react_drv)},
                "night": night_json(sample_night(night_params, profile, args.seed)),
            }
            dump(out / sid / f"{aid}.json", run)
            matrix[sid][aid] = {"op_p50": op2, "revenue_p50": reacted["revenue"]["p50"], "covers_p50": reacted["covers"]["p50"],
                                "walkaways_p50": reacted["walkaways"]["p50"], "op_vs_base": op2 - op0, "op_vs_shock": op2 - op1,
                                "headline": run["headline"]}
        matrix[sid]["_shock"] = {"op_p50": shocked["op"]["p50"], "op_vs_base": shocked["op"]["p50"] - base["op"]["p50"],
                                 "headline": headline(sid, None, base["op"]["p50"], shocked["op"]["p50"])}
        print(f"{sid} done ({time.time() - t0:.0f}s)")

    dump(out / "index.json", {
        "meta": meta,
        "base": {k: base[k]["p50"] for k in KPIS},
        "shocks": {sid: {"label": SHOCK_LABELS[sid], "if": SHOCK_IF[sid], "driver": shocks[sid]["driver"],
                         "params": shocks[sid]["params"], "evidence": evidence(SHOCK_MECHANISMS.get(sid, []))}
                   for sid in sorted(shocks)},
        "actions": {aid: {"label": s["label"], "phrase": s["phrase"], "description": s["description_ko"],
                          "args": s["default_args"], "evidence": evidence(ACTION_MECHANISMS[aid])} for aid, s in menu.items()},
        "matrix": matrix,
        "files": {sid: sorted(menu) for sid in sorted(shocks)},
        "excluded": sorted(excluded),
    })
    print(f"wrote {out} ({len(shocks)} shocks × {len(menu)} actions + base) in {time.time() - t0:.0f}s")
    if args.season:
        season(params, profile, shocks, menu, out, args, meta, t0)


SEASON_KPIS = ["revenue", "op", "op_margin", "covers", "ticket", "walkaways", "avg_wait_min", "table_utilization",
               "cogs", "labor_hours", "revpash", "alcohol_share", "arrivals"]


def season(params, profile, shocks, menu, out: Path, args, meta: dict, t0: float) -> None:
    """Every lasting-choice state × shock (sim.season); a month's outcome is grid[state after choice][shock]."""
    states = S.all_states(set(MENU) - set(menu))
    for i, st in enumerate(states):
        p_state = S.apply_state(params, st)
        cells = {}
        for sid in sorted(shocks):
            sh = shocks[sid]
            m = monte_carlo(p_state, profile, args.runs, args.seed, param_fn=lambda p, rng, sh=sh: apply_shock(p, sh, rng))
            band = summarize(m, SEASON_KPIS)
            cells[sid] = {"kpis": band, "drivers": driver_p50(m)}
        dump(out / "season" / f"{S.key(st)}.json", {"state": st, "key": S.key(st), "describe": S.describe(st), "shocks": cells})
        print(f"season state {i + 1}/{len(states)} {S.key(st)} ({time.time() - t0:.0f}s)")
    dump(out / "season" / "index.json", {
        "meta": {**meta, "months": profile.get("game", {}).get("season_months", 6),
                 "carry_state": profile.get("game", {}).get("carry_state", True)},
        "levers": S.LEVERS, "base_state": S.key(S.BASE_STATE), "states": [S.key(st) for st in states],
        "transitions": {S.key(st): {a: S.key(S.transition(st, a)) for a in menu} for st in states},
        "lever_labels": {lv: {str(k): v for k, v in d.items()} for lv, d in S.LEVER_LABELS.items()},
    })


if __name__ == "__main__":
    main()
