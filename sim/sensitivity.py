"""Party-size sensitivity (illustrative): the base month with a pairs-heavy party mix.

  python -m sim.sensitivity [--runs 200]

Base: per-segment 1 + Binomial(3, p) around mkt_party_size 2.8 (3-person parties are the mode).
Pairs-heavy: {1: 0.04, 2: 0.58, 3: 0.20, 4: 0.18} for every segment (mean 2.52; ~58% pairs as in the US casual-dining
reference, Kimes & Robson 2004, S72). Arrivals (parties per night) are held fixed, so fewer people come per party.
"""
from __future__ import annotations

import argparse

import numpy as np

from sim.engine import monte_carlo
from sim.params import SIM_ASSUMPTIONS, load_params, load_profile

PAIRS_HEAVY = {1: 0.04, 2: 0.58, 3: 0.20, 4: 0.18}
ROWS = [("covers", "손님 수", "{:,.0f}"), ("revenue", "월 매출", "₩{:,.0f}"), ("op", "영업이익", "₩{:,.0f}"),
        ("op_margin", "영업이익률", "{:.1%}"), ("walkaways", "돌아간 팀", "{:.0f}"),
        ("table_utilization", "테이블 가동률", "{:.1%}"), ("revpash", "RevPASH", "₩{:,.0f}")]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=200)
    args = ap.parse_args()
    p, prof = load_params(), load_profile()
    base = monte_carlo(p, prof, args.runs, 42)
    pairs = monte_carlo(p, prof, args.runs, 42, a={**SIM_ASSUMPTIONS, "party_size_categorical": PAIRS_HEAVY})
    print("| KPI (p50) | binomial, mean 2.8 | pairs-heavy, mean 2.52 | change |")
    print("|---|---|---|---|")
    for k, label, f in ROWS:
        a, b = float(np.median([m[k] for m in base])), float(np.median([m[k] for m in pairs]))
        print(f"| {label} | {f.format(a)} | {f.format(b)} | {(b / a - 1) if a else 0:+.1%} |")


if __name__ == "__main__":
    main()
