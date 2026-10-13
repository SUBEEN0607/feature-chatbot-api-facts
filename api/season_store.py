"""Season sessions: in memory for speed, written to the game_session table on every change (survives restart)."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime

from db import models as M
from db.session import session_factory

_lock = threading.Lock()
_live: dict[str, dict] = {}


def _save(engine, sess: dict) -> None:
    with session_factory(engine)() as s, s.begin():
        s.merge(M.GameSession(season_id=sess["id"], mode=sess["mode"], seed=sess["seed"], engine=sess["engine"],
                              state=sess["state"], months=sess["months"], created_at=sess["created_at"],
                              updated_at=datetime.utcnow()))


def create(engine, mode: str, seed: int, engine_name: str, state: dict) -> dict:
    sess = {"id": uuid.uuid4().hex[:12], "mode": mode, "seed": seed, "engine": engine_name, "state": state,
            "months": [], "created_at": datetime.utcnow()}
    with _lock:
        _live[sess["id"]] = sess
    _save(engine, sess)
    return sess


def get(engine, season_id: str) -> dict | None:
    with _lock:
        if season_id in _live:
            return _live[season_id]
    with session_factory(engine)() as s:
        row = s.get(M.GameSession, season_id)
        if row is None:
            return None
        sess = {"id": row.season_id, "mode": row.mode, "seed": row.seed, "engine": row.engine, "state": row.state,
                "months": row.months or [], "created_at": row.created_at}
    with _lock:
        _live[season_id] = sess
    return sess


def update(engine, sess: dict) -> None:
    with _lock:
        _live[sess["id"]] = sess
    _save(engine, sess)


def forget_memory() -> None:
    """Tests: drop the in-memory copies so the next get() reads the database."""
    with _lock:
        _live.clear()
