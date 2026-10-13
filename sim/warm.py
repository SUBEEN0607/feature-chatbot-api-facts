"""Prebuild the season engine's cached DES means so the first preview after a model change is instant.

  python -m sim.warm            build what is missing (about 1.5 minutes after a model change, instant otherwise)
  python -m sim.warm --check    exit 1 if the cache is missing or stale, build nothing

The cache lives in data/cache/, keyed by a hash of every input it depends on (research yaml, hero_base, sim code):
평소 (October, 2,000 DES runs) and the base plan in every other season month (800 runs each). preview() calibrates
against these; without them the first preview call computes them itself.
"""
from __future__ import annotations

import argparse
import sys
import time

from sim import season as S


def stale() -> list[str]:
    out = []
    if not S._cache_path("season_baseline", int(S.v("band.baseline_runs"))).exists():
        out.append("season_baseline")
    if not S._cache_path("season_months", int(S.v("band.month_runs"))).exists():
        out.append("season_months")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    missing = stale()
    if args.check:
        print("season cache: " + ("stale (" + ", ".join(missing) + ")" if missing else "warm"))
        return 1 if missing else 0
    if not missing:
        print("season cache: warm")
        return 0
    t = time.time()
    print(f"season cache: building {', '.join(missing)} (one time after a model change)", flush=True)
    S._baseline()
    S._month_means()
    for m in S.months():
        S._calibration(m)
    print(f"season cache: warm ({time.time() - t:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
