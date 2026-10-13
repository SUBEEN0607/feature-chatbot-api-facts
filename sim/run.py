"""CLI: base vs shock Monte Carlo.

  python -m sim.run --shock SH03 --runs 200 --out out/sh03     # one shock
  python -m sim.run --shock none --runs 200 --out out/base     # base only
  python -m sim.run --shock all  --runs 200 --out out/all      # every shock + summary.json

Writes kpis.json (base vs shock, p10/p50/p90 per KPI) and events.json (one logged Saturday night,
base and shocked, same seed) per shock. Base and shock share seeds (common random numbers).
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from sim.engine import KPIS, driver_p50, monte_carlo, sample_night, summarize
from sim.params import SIM_ASSUMPTIONS, load_params, load_profile
from sim.shocks import apply_shock, describe, load_shocks


def _night_json(r: dict) -> dict:
    return {"dow": r["dow"], "terrace_open": r["terrace_open"], "tables_available": r["tables_available"],
            "open_clock": "17:00", "events": r["events"]}


def run(shock: str | None, action: str = "absorb", action_args: dict | None = None, runs: int = 200,
        seed: int = 42) -> dict:
    """Shock, then one owner action from sim.owner_actions.MENU, then rerun (same seeds as base).
    shock=None means no shock (the action alone). Returns base / shocked / reacted KPI bands."""
    from sim.owner_actions import MENU, apply_action

    if action not in MENU:
        raise ValueError(f"unknown action {action!r}; choose from {sorted(MENU)}")
    args = dict(action_args) if action_args else dict(MENU[action]["default_args"])
    params, profile, shocks = load_params(), load_profile(), load_shocks()
    if shock is not None and shock not in shocks:
        raise KeyError(shock)
    sh = shocks.get(shock) if shock else None

    def shocked_fn(p, rng):
        return apply_shock(p, sh, rng) if sh else p

    base_m = monte_carlo(params, profile, runs, seed)
    shock_m = monte_carlo(params, profile, runs, seed, param_fn=shocked_fn)
    react_m = monte_carlo(params, profile, runs, seed, param_fn=lambda p, rng: apply_action(shocked_fn(p, rng), action, **args))
    base, shocked, reacted = summarize(base_m), summarize(shock_m), summarize(react_m)
    return {"meta": {"runs": runs, "seed": seed, "illustrative": True, "source": "sim.run.run"},
            "shock": {"id": shock, "driver": sh["driver"] if sh else None, "params": sh["params"] if sh else []},
            "action": {"id": action, "args": args},
            "base": base, "shocked": shocked, "reacted": reacted,
            "delta_p50": {k: reacted[k]["p50"] - base[k]["p50"] for k in KPIS},
            "drivers": {"base": driver_p50(base_m), "shocked": driver_p50(shock_m), "reacted": driver_p50(react_m)}}


def run_one(params, profile, base_summary, shock_id, shock, runs, seed, out: Path) -> dict:
    t = time.time()
    months = monte_carlo(params, profile, runs, seed, param_fn=lambda p, rng: apply_shock(p, shock, rng))
    shocked = summarize(months)
    elapsed = time.time() - t
    base_night = sample_night(params, profile, seed)
    shock_night = sample_night(apply_shock(params, shock), profile, seed)
    kpis = {
        "meta": {"runs": runs, "seed": seed, "shock": shock_id, "runtime_s_shock_runs": round(elapsed, 2),
                 "illustrative": True, "params": "research/hero_base.yaml", "shocks": "research/shocks.yaml"},
        "shock": {"id": shock_id, "driver": shock["driver"], "params": shock["params"], "description": describe(shock_id, shock)},
        "base": base_summary, "shocked": shocked,
        "delta_p50": {k: shocked[k]["p50"] - base_summary[k]["p50"] for k in KPIS},
    }
    out.mkdir(parents=True, exist_ok=True)
    json.dump(kpis, open(out / "kpis.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"schema": "docs/EVENT_LOG.md", "seed": seed, "base": _night_json(base_night),
               "shocked": _night_json(shock_night)},
              open(out / "events.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return kpis


def main() -> None:
    ap = argparse.ArgumentParser(description="Hero-store simulation: base vs shock")
    ap.add_argument("--shock", default="none", help="shock id (e.g. SH03), 'none', or 'all'")
    ap.add_argument("--runs", type=int, default=200)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="out")
    args = ap.parse_args()

    params, profile, shocks = load_params(), load_profile(), load_shocks()
    out = Path(args.out)
    t = time.time()
    base_summary = summarize(monte_carlo(params, profile, args.runs, args.seed))
    base_s = time.time() - t
    print(f"base: {args.runs} runs in {base_s:.2f}s | 상권 {profile['trdar']} quarters {profile['quarters']}")

    if args.shock == "none":
        out.mkdir(parents=True, exist_ok=True)
        night = sample_night(params, profile, args.seed)
        json.dump({"meta": {"runs": args.runs, "seed": args.seed, "runtime_s_base_runs": round(base_s, 2),
                            "illustrative": True, "sim_assumptions": SIM_ASSUMPTIONS}, "base": base_summary},
                  open(out / "kpis.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        json.dump({"schema": "docs/EVENT_LOG.md", "seed": args.seed, "base": _night_json(night), "shocked": None},
                  open(out / "events.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        _print_row("base", base_summary, base_summary)
        return

    ids = sorted(shocks) if args.shock == "all" else [args.shock]
    unknown = [i for i in ids if i not in shocks]
    if unknown:
        raise SystemExit(f"unknown shock {unknown}; available: {sorted(shocks)}")
    summary = {}
    _print_row("base", base_summary, base_summary)
    for sid in ids:
        print(describe(sid, shocks[sid]))
        k = run_one(params, profile, base_summary, sid, shocks[sid], args.runs, args.seed,
                    out / sid if args.shock == "all" else out)
        summary[sid] = {m: k["shocked"][m]["p50"] for m in KPIS}
        _print_row(sid, k["shocked"], base_summary)
    if args.shock == "all":
        json.dump({"base": {m: base_summary[m]["p50"] for m in KPIS}, "shocks_p50": summary,
                   "runs": args.runs, "seed": args.seed, "base_runtime_s": round(base_s, 2)},
                  open(out / "summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def _print_row(label: str, s: dict, base: dict) -> None:
    def d(k):
        return s[k]["p50"] - base[k]["p50"]
    print(f"  {label:5s} revenue p50 ₩{s['revenue']['p50']:>12,.0f} ({d('revenue'):+,.0f}) | "
          f"OP p50 ₩{s['op']['p50']:>11,.0f} ({d('op'):+,.0f}) | margin {s['op_margin']['p50']:.1%} | "
          f"walk-aways p50 {s['walkaways']['p50']:.0f} | covers p50 {s['covers']['p50']:.0f} "
          f"[p10 {s['covers']['p10']:.0f}, p90 {s['covers']['p90']:.0f}]")


if __name__ == "__main__":
    np.seterr(all="raise")
    main()
