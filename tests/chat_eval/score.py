"""Scoring for the owner-chat eval (questions.yaml). Pure functions: no network, no database."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from agents.ko import man_won

HERE = Path(__file__).resolve().parent
DIGIT = re.compile(r"\d")


def load(path: Path | None = None) -> list[dict]:
    return yaml.safe_load((path or HERE / "questions.yaml").read_text(encoding="utf-8"))["questions"]


def norm(s: str) -> str:
    """Spaces, commas and the UI minus removed: '2,613만 원' -> '2613만원'."""
    return re.sub(r"[\s,−]", "", s or "")


def season_values(season: dict) -> dict[str, list[str]]:
    """Spellings of the eval season's numbers (after one played month) as the chat may write them."""
    last = (season.get("months") or [{}])[-1]
    k = (last.get("draw") or {}).get("kpis") or {}
    st = season.get("state") or {}
    vals = {"last.op": k.get("op"), "last.revenue": k.get("revenue"), "last.covers": k.get("covers"),
            "cash": st.get("cash")}
    out = {}
    for name, v in vals.items():
        if v is None:
            continue
        if name == "last.covers":
            out[name] = [f"{round(v)}명"]
        else:
            out[name] = [norm(man_won(abs(v)))[:-1]]    # '95만' (no trailing 원, so '95만 원' and '95만원' match)
    return out


def score_answer(item: dict, answer: str, season_vals: dict[str, list[str]] | None = None) -> dict:
    """{'pass': bool, 'why': [...]} for one answer."""
    a, why = norm(answer), []
    sv = season_vals or {}
    groups = [list(g) for g in item.get("expect") or []]
    if groups and item.get("accept_season"):
        groups[0] += [s for name in item["accept_season"] for s in sv.get(name, [])]
    for g in item.get("expect_season") or []:
        groups.append([s for name in g for s in sv.get(name, [])] or ["<season value missing>"])
    for g in groups:
        if not any(norm(s) in a for s in g):
            why.append(f"missing one of {g}")
    for s in item.get("forbid") or []:
        if norm(s) in a:
            why.append(f"forbidden {s!r}")
    if item.get("no_numbers") and DIGIT.search(answer or ""):
        why.append("has a number (off-topic answers must not)")
    return {"pass": not why, "why": why}


def retrieval_hit(item: dict, hits: list[dict]) -> bool | None:
    """True when a gold document or source id is among the retrieved chunks; None when the item has no gold."""
    gold = item.get("gold")
    if not gold:
        return None
    for h in hits:
        for g in gold:
            if h.get("source_id") == g or h["doc_id"] == g or h["doc_id"].startswith(g + "#") \
                    or (g.endswith(".md") and h["doc_id"] == g):
                return True
    return False
