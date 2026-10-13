"""Thin bridge to sim/ (built in parallel). Any import or interface gap raises SimUnavailable -> HTTP 501."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path


class SimUnavailable(RuntimeError):
    pass


def _load():
    try:
        import sim.run as R
        from sim.engine import KPIS, monte_carlo, summarize
        from sim.params import load_params, load_profile
        from sim.shocks import apply_shock, load_shocks
    except Exception as e:  # noqa: BLE001 - ImportError, missing names, broken module
        raise SimUnavailable(f"simulation package not importable: {type(e).__name__}: {e}") from e
    if not hasattr(R, "run_one"):
        raise SimUnavailable("sim.run has no run_one(); the bridge needs updating")
    return R, KPIS, monte_carlo, summarize, load_params, load_profile, apply_shock, load_shocks


def shock_ids() -> list[str]:
    *_, load_shocks = _load()
    return sorted(load_shocks())


def simulate(shock_id: str, runs: int, seed: int = 42) -> dict:
    """Base vs shock Monte Carlo. Returns {'kpis': ..., 'events': ...} as sim.run writes them."""
    R, KPIS, monte_carlo, summarize, load_params, load_profile, apply_shock, load_shocks = _load()
    params, profile, shocks = load_params(), load_profile(), load_shocks()
    if shock_id not in shocks:
        raise KeyError(shock_id)
    base = summarize(monte_carlo(params, profile, runs, seed))
    with tempfile.TemporaryDirectory() as d:
        kpis = R.run_one(params, profile, base, shock_id, shocks[shock_id], runs, seed, Path(d))
        ev = Path(d) / "events.json"
        events = json.loads(ev.read_text(encoding="utf-8")) if ev.exists() else None
    return {"kpis": kpis, "events": events, "kpi_names": list(KPIS)}


def simulate_reaction(shock_id: str, action: str, args: dict, runs: int, seed: int = 42) -> dict:
    """Shock plus the owner's chosen action, same seeds (second-order result)."""
    R, KPIS, monte_carlo, summarize, load_params, load_profile, apply_shock, load_shocks = _load()
    try:
        from sim.owner_actions import apply_action
    except Exception as e:  # noqa: BLE001
        raise SimUnavailable(f"sim.owner_actions.apply_action not importable: {e}") from e
    params, profile, shocks = load_params(), load_profile(), load_shocks()
    shock = shocks[shock_id]
    months = monte_carlo(params, profile, runs, seed,
                         param_fn=lambda p, rng: apply_action(apply_shock(p, shock, rng), action, **args))
    return summarize(months)


def default_args(action: str, menu: dict) -> dict:
    """Arguments used when a caller names an action without arguments: MENU[action]['default_args'] if sim
    defines them, else a moderate value inside each bound (never the extreme)."""
    spec = menu.get(action, {})
    if isinstance(spec.get("default_args"), dict):
        return dict(spec["default_args"])
    fallback = {"pct": 0.05, "delta_krw": 500, "hours": 1.0, "n": 1, "alcohol_pct": 0.1, "side_pct": 0.1}
    out = {}
    for k, b in spec.get("args", {}).items():
        v = fallback.get(k, (b[0] + b[1]) / 2)
        out[k] = min(max(v, b[0]), b[1])
    return out


def run_action(shock_id: str, action: str, action_args: dict | None, runs: int, seed: int = 42) -> dict:
    """Shock + owner action. Prefers sim.run.run(...) once sim provides it; otherwise composes the same
    result from sim's public pieces (base, shocked, reacted share seeds). Raises SimUnavailable / KeyError /
    ValueError (bad action or args)."""
    import inspect
    R, KPIS, monte_carlo, summarize, load_params, load_profile, apply_shock, load_shocks = _load()
    try:
        from sim.owner_actions import MENU, apply_action
    except Exception as e:  # noqa: BLE001
        raise SimUnavailable(f"sim.owner_actions not importable: {e}") from e
    if action not in MENU:
        raise ValueError(f"unknown action {action!r}; choose from {sorted(MENU)}")
    args = dict(action_args) if action_args else default_args(action, MENU)
    run_fn = getattr(R, "run", None)
    if callable(run_fn):
        sig = inspect.signature(run_fn).parameters
        kw = {k: v for k, v in {"shock": shock_id, "shock_id": shock_id, "action": action, "action_args": args,
                                "args": args, "runs": runs, "seed": seed}.items() if k in sig}
        if {"action"} <= set(kw) and ({"shock"} & set(kw) or {"shock_id"} & set(kw)):
            out = run_fn(**kw)
            if isinstance(out, dict):
                out.setdefault("action", {"id": action, "args": args})
                out.setdefault("source", "sim.run.run")
                return out
    shocks = load_shocks()
    if shock_id not in shocks:
        raise KeyError(shock_id)
    apply_action(load_params(), action, **args)          # validates args against MENU bounds early
    params, profile, shock = load_params(), load_profile(), shocks[shock_id]
    base = summarize(monte_carlo(params, profile, runs, seed))
    shocked = summarize(monte_carlo(params, profile, runs, seed, param_fn=lambda p, rng: apply_shock(p, shock, rng)))
    reacted = summarize(monte_carlo(params, profile, runs, seed,
                                    param_fn=lambda p, rng: apply_action(apply_shock(p, shock, rng), action, **args)))
    return {"meta": {"runs": runs, "seed": seed, "illustrative": True, "source": "api.sim_bridge (composed)"},
            "shock": {"id": shock_id, "driver": shock.get("driver"), "params": shock.get("params")},
            "action": {"id": action, "args": args},
            "base": base, "shocked": shocked, "reacted": reacted,
            "delta_p50": {k: reacted[k]["p50"] - base[k]["p50"] for k in KPIS}}
