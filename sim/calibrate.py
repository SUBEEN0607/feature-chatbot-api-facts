"""Compare the simulated base month with the workbook P&L and report the walk-away rate the P&L should use.

  python -m sim.calibrate [--runs 200]

drv_balk_rate in the workbook sets how many parties arrive (arrivals = P&L covers ÷ (1 − balk) ÷ party size).
The simulation measures the actual walk-away share; when the two differ, the sim over- or under-shoots the
P&L covers. Copy the printed balk rate into HERO in research/build_workbook.py and rebuild.
"""
from __future__ import annotations

import argparse

import numpy as np

from sim.engine import monte_carlo
from sim.params import load_params, load_profile


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=200)
    args = ap.parse_args()
    p, prof = load_params(), load_profile()
    m = monte_carlo(p, prof, args.runs, 42)
    med = lambda k: float(np.median([x[k] for x in m]))  # noqa: E731
    pnl = p["_pnl"]
    print(f"walk-away share (persons): sim {med('balk_rate'):.4f} | workbook drv_balk_rate {p['drv_balk_rate']}")
    for label, sk, pk in (("covers/month", "covers", "covers_month"), ("revenue", "revenue", "rev"), ("OP", "op", "op")):
        print(f"{label:13s} sim p50 {med(sk):>14,.0f} | P&L {pnl[pk]:>14,.0f} | gap {med(sk) / pnl[pk] - 1:+.1%}")
    print(f"OP margin     sim p50 {med('op_margin'):.2%} | P&L {pnl['op'] / pnl['rev']:.2%}")


if __name__ == "__main__":
    main()
