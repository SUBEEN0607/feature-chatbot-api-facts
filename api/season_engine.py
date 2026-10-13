"""Season engine adapter: sim.season when it provides the §11 contract, else the labelled stub."""
from __future__ import annotations

import dataclasses


def engine():
    try:
        import sim.season as S
        if all(callable(getattr(S, f, None)) for f in ("new_season", "preview", "play_month")):
            return S, "sim.season"
    except Exception:  # noqa: BLE001 - sim/ is built in parallel; any import problem means "use the stub"
        pass
    from . import season_stub as S
    return S, "stub"


def to_json(o):
    """SeasonState / MonthResult may be dataclasses or objects with to_dict(); the API stores plain JSON."""
    if dataclasses.is_dataclass(o) and not isinstance(o, type):
        return to_json(dataclasses.asdict(o))
    if hasattr(o, "to_dict"):
        return to_json(o.to_dict())
    if isinstance(o, dict):
        return {str(k): to_json(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [to_json(v) for v in o]
    return o


def from_json(S, state: dict):
    """Give the engine its own state type back if it has one."""
    if hasattr(S, "SeasonState") and hasattr(S.SeasonState, "from_dict"):
        return S.SeasonState.from_dict(state)
    return state


def default_plan(S) -> dict:
    for name in ("default_plan", "base_plan"):
        fn = getattr(S, name, None)
        if callable(fn):
            return to_json(fn())
    return {}


def draw_events(S, state) -> list:
    return to_json(S.draw_events(state)) if callable(getattr(S, "draw_events", None)) else []


def event_info(S, eid: str) -> dict:
    """id, label, kind (group), effect line and source/가정 tag for one event id."""
    ev = None
    if callable(getattr(S, "data", None)):
        try:
            ev = S.data().get("EV", {}).get(eid)
        except Exception:  # noqa: BLE001
            ev = None
    if ev:
        return {"id": eid, "label": ev.get("label", eid), "kind": ev.get("group"), "effect": ev.get("mechanism"),
                "tag": ev.get("tag")}
    stub = getattr(S, "EVENTS", {}).get(eid)
    if stub:
        return {"id": eid, "label": stub[0], "kind": None, "effect": None, "tag": stub[-1]}
    return {"id": eid, "label": eid, "kind": None, "effect": None, "tag": "가정"}


def supports_choices(S) -> bool:
    import inspect
    try:
        return callable(getattr(S, "start_month", None)) and "night_choices" in inspect.signature(S.play_month).parameters
    except (TypeError, ValueError):
        return False
