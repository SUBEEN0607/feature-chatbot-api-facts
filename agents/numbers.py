"""No-invented-number check for generated Korean text.

Every number in a generated sentence must come from the inputs it was built from (state values, month
result, hero attributes, review facts). `pool(*inputs)` collects every number in the inputs in the spellings
the templates use (plain, comma, 만원, percent of a ratio, rounded); `invented(text, pool)` returns the
numbers in `text` that are not in the pool. Used at runtime to reject LLM output and in tests on all text.
"""
from __future__ import annotations

import re

NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _spellings(v: float) -> set[str]:
    out = set()
    for x in (v, round(v), round(v, 1), round(v, 2)):
        out.add(f"{x:g}" if isinstance(x, float) else str(x))
        if float(x).is_integer():
            out.add(str(int(x)))
    if abs(v) >= 1e4:                       # 만원 forms: 1,223,984 -> 122
        out |= {str(round(v / 1e4)), str(int(v // 1e4)), f"{v / 1e4:.1f}".rstrip("0").rstrip(".")}
    if abs(v) >= 1e8:                       # 억 forms
        out |= {str(round(v / 1e8)), f"{v / 1e8:.1f}".rstrip("0").rstrip(".")}
    if 0 < abs(v) <= 1:                     # ratios shown as percent
        out |= {str(round(v * 100)), f"{v * 100:.1f}".rstrip("0").rstrip("."), f"{v * 100:.2f}".rstrip("0").rstrip(".")}
    return {s.lstrip("-") for s in out}


def pool(*inputs) -> set[str]:
    found: set[str] = set()

    def walk(o):
        if isinstance(o, bool) or o is None:
            return
        if isinstance(o, (int, float)):
            found.update(_spellings(float(o)))
        elif isinstance(o, str):
            for n in NUM.findall(o):
                n = n.replace(",", "")
                found.add(n)
                try:
                    found.update(_spellings(float(n)))
                except ValueError:
                    pass
        elif isinstance(o, dict):
            for k, v in o.items():
                walk(k)
                walk(v)
        elif isinstance(o, (list, tuple, set)):
            for v in o:
                walk(v)
    for i in inputs:
        walk(i)
    return found


def _norm(n: str) -> str:
    """'4.20' -> '4.2', '63.0' -> '63', '1,200' -> '1200' (table formatting is not a new number)."""
    n = n.replace(",", "")
    return n.rstrip("0").rstrip(".") if "." in n else n


def invented(text: str, allowed: set[str]) -> list[str]:
    return [n for n in NUM.findall(text or "") if n.replace(",", "") not in allowed and _norm(n) not in allowed]
