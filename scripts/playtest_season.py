"""Play full 6-month v2 seasons through the API as a player and summarise which strategies win.

  .venv/bin/python scripts/playtest_season.py                  # in-process API (no server needed)
  .venv/bin/python scripts/playtest_season.py --seeds 5 --json out.json

Strategies hold one plan for the whole season. Single-lever sweeps change one lever from the base plan to
find free wins (better operating profit in every seed with no rating or fatigue cost). Uses the mock LLM
backend only.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["LLM_BACKEND"] = "mock"
# seasons go to a throwaway SQLite file, not data/twin.db (only game_session is needed for /season and /play)
_TMP = __import__("tempfile").mkdtemp(prefix="playtest-")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP}/playtest.db")

STRATEGIES = {
    "do_nothing": {},
    "cheap_meat": {"meat_grade": "imported", "meat_price": 16000, "soju_price": 4500, "banchan": 4, "hygiene": "basic"},
    "premium": {"meat_grade": "aged", "meat_price": 22000, "staff_grilling": True, "banchan": 7, "hygiene": "high",
                "menu_extras": ["minari"], "staff_per_shift": 3},
    "lean": {"staff_per_shift": 1, "close_hour": 23, "banchan": 4},
    "growth": {"marketing_budget": 1_000_000, "review_event": True, "group_reservations": True, "close_hour": 25,
               "lunch": True},
}
SWEEPS = {
    "price_up_10pct": {"meat_price": 20900}, "price_down_10pct": {"meat_price": 17100}, "soju_up_500": {"soju_price": 5500},
    "grade_imported": {"meat_grade": "imported"}, "grade_aged": {"meat_grade": "aged"},
    "extra_naengsam": {"menu_extras": ["naengsam"]}, "extra_tongsam": {"menu_extras": ["tongsam"]},
    "extra_minari": {"menu_extras": ["minari"]}, "banchan_3": {"banchan": 3}, "banchan_7": {"banchan": 7},
    "staff_grilling": {"staff_grilling": True}, "staff_1": {"staff_per_shift": 1}, "staff_3": {"staff_per_shift": 3},
    "close_23": {"close_hour": 23}, "close_25": {"close_hour": 25}, "lunch": {"lunch": True}, "terrace_off": {"terrace": False},
    "marketing_1m": {"marketing_budget": 1_000_000}, "review_event": {"review_event": True},
    "group_reservations": {"group_reservations": True}, "hygiene_basic": {"hygiene": "basic"}, "hygiene_high": {"hygiene": "high"},
}


def play(client, plan: dict, seed: int) -> dict:
    s = client.post("/season", json={"mode": "free", "seed": seed}).json()
    ops, closed_at = [], None
    for i in range(6):
        r = client.post(f"/season/{s['id']}/play", json={"plan": plan})
        if r.status_code == 409:
            break
        m = r.json()
        ops.append(m["draw"]["kpis"]["op"])
        if m["state_after"].get("closed"):
            closed_at = i + 1
            break
    end = client.get(f"/season/{s['id']}").json()["state"]
    return {"seed": seed, "ops": ops, "total_op": sum(ops), "cash": end.get("cash"), "rating": end.get("rating"),
            "fatigue": end.get("fatigue"), "closed_at": closed_at, "months": len(ops)}


def summarise(runs: list[dict]) -> dict:
    return {"mean_total_op": round(st.mean(r["total_op"] for r in runs)),
            "min_total_op": min(r["total_op"] for r in runs), "max_total_op": max(r["total_op"] for r in runs),
            "mean_end_cash": round(st.mean(r["cash"] for r in runs)),
            "mean_end_rating": round(st.mean(r["rating"] for r in runs), 3),
            "mean_end_fatigue": round(st.mean(r["fatigue"] for r in runs), 1),
            "closures": sum(r["closed_at"] is not None for r in runs), "runs": len(runs)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--json", default=None)
    ap.add_argument("--extra", default=None, help="JSON dict of extra named plans to try (e.g. a 폐업 attempt)")
    a = ap.parse_args(argv)
    from fastapi.testclient import TestClient
    from api import main as api
    seeds = list(range(1, a.seeds + 1))
    plans = {**STRATEGIES, **{f"sweep:{k}": v for k, v in SWEEPS.items()}, **(json.loads(a.extra) if a.extra else {})}
    out = {}
    with TestClient(api.app) as c:
        for name, plan in plans.items():
            runs = [play(c, plan, sd) for sd in seeds]
            out[name] = {"plan": plan, "summary": summarise(runs), "runs": runs}
            print(f"{name:28s} mean OP {out[name]['summary']['mean_total_op']:>12,}  cash {out[name]['summary']['mean_end_cash']:>12,}"
                  f"  rating {out[name]['summary']['mean_end_rating']}  fatigue {out[name]['summary']['mean_end_fatigue']}"
                  f"  closures {out[name]['summary']['closures']}", file=sys.stderr, flush=True)
    base = {r["seed"]: r for r in out["do_nothing"]["runs"]}
    free = []
    for name, d in out.items():
        if not name.startswith("sweep:"):
            continue
        better = all(r["total_op"] > base[r["seed"]]["total_op"] for r in d["runs"])
        no_cost = all(r["rating"] >= base[r["seed"]]["rating"] - 0.01 and r["fatigue"] <= base[r["seed"]]["fatigue"] + 1
                      for r in d["runs"])
        d["beats_base_every_seed"] = better
        d["no_rating_or_fatigue_cost"] = no_cost
        if better and no_cost:
            free.append(name)
    out["_free_wins"] = free
    if a.json:
        Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps({"free_wins": free, "ranking": sorted(((k, v["summary"]["mean_total_op"]) for k, v in out.items()
                                                            if not k.startswith("_")), key=lambda kv: -kv[1])},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
