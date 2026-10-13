"""Game-side helpers: precomputed runs (web/public/runs/<shock>/<action>.json), outcome extraction, and
live fallbacks when a precomputed file is missing."""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

from . import sim_bridge

REPO = Path(__file__).resolve().parents[1]
SAFE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
LIVE_RUNS = int(os.environ.get("LIVE_RUNS", 100))


def runs_dir() -> Path:
    return Path(os.environ.get("RUNS_DIR", REPO / "web" / "public" / "runs"))


def run_index() -> dict:
    """{'shocks': {shock: [actions...]}, 'files': n}; merges runs/index.json if sim wrote one."""
    d = runs_dir()
    shocks: dict[str, list[str]] = {}
    if d.exists():
        for sd in sorted(p for p in d.iterdir() if p.is_dir() and SAFE.match(p.name)):
            acts = sorted(f.stem for f in sd.glob("*.json") if SAFE.match(f.stem))
            if acts:
                shocks[sd.name] = acts
    out = {"runs_dir": str(d.relative_to(REPO)) if d.is_relative_to(REPO) else str(d),
           "shocks": shocks, "files": sum(len(v) for v in shocks.values())}
    idx = d / "index.json"
    if idx.exists():
        try:
            out["index"] = json.loads(idx.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            out["index_error"] = "index.json is not valid JSON"
    return out


def load_run(shock: str, action: str) -> dict | None:
    if not (SAFE.match(shock) and SAFE.match(action)):
        raise ValueError("bad shock or action id")
    p = runs_dir() / shock / f"{action}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


OUTCOME_KEYS = ("reacted", "reaction", "result", "shocked")   # first present wins: the post-action outcome


def outcome(run: dict) -> dict | None:
    """KPI table (kpi -> {p10,p50,p90}) describing the world after shock + action."""
    for k in OUTCOME_KEYS:
        v = run.get(k)
        if isinstance(v, dict) and isinstance(v.get("op"), dict):
            return v
    v = run.get("kpis")
    if isinstance(v, dict):
        return outcome(v)
    return run if isinstance(run.get("op"), dict) else None


def p50(table: dict | None, kpi: str) -> float | None:
    try:
        return float(table[kpi]["p50"])
    except (TypeError, KeyError, ValueError):
        return None


@lru_cache(maxsize=256)
def _live(shock: str, action: str, runs: int) -> str:
    return json.dumps(sim_bridge.run_action(shock, action, None, runs), ensure_ascii=False)


def get_run(shock: str, action: str, live_runs: int = LIVE_RUNS) -> tuple[dict, str]:
    """(run, 'precomputed' | 'live'). Live results are memoised per process."""
    r = load_run(shock, action)
    if r is not None:
        return r, "precomputed"
    return json.loads(_live(shock, action, live_runs)), "live"


def candidates(shock: str, menu: dict, precomputed_only: bool = False) -> list[dict]:
    """One row per menu action. precomputed_only skips actions with no file instead of simulating them live
    (the survey uses that: it must answer in well under a second)."""
    out = []
    for a in menu:
        if precomputed_only:
            r = load_run(shock, a)
            if r is None:
                continue
            src = "precomputed"
        else:
            r, src = get_run(shock, a)
        t = outcome(r)
        base = r.get("base") if isinstance(r.get("base"), dict) else None
        out.append({"action": a, "args": (r.get("action") or {}).get("args"), "source": src,
                    "op_p50": p50(t, "op"), "revenue_p50": p50(t, "revenue"), "covers_p50": p50(t, "covers"),
                    "walkaways_p50": p50(t, "walkaways"), "base_op_p50": p50(base, "op")})
    return out


def shock_label(shock_id: str, fallback: str | None = None) -> str:
    try:
        from sim.labels import SHOCK_LABELS
        return SHOCK_LABELS.get(shock_id) or fallback or shock_id
    except Exception:  # noqa: BLE001 - sim/ is optional for the API
        return fallback or shock_id
