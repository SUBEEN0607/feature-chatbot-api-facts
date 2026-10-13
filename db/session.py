"""Engine + session from DATABASE_URL (default: local SQLite file data/twin.db)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from .models import Base

REPO = Path(__file__).resolve().parents[1]
DEFAULT_URL = f"sqlite:///{REPO / 'data' / 'twin.db'}"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_URL)


@lru_cache(maxsize=None)
def get_engine(url: str | None = None):
    url = url or database_url()
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    engine = create_engine(url, future=True)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):  # SQLite ignores foreign keys unless asked
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
    return engine


def init_db(engine=None):
    engine = engine or get_engine()
    if engine.dialect.name == "postgresql":
        with engine.begin() as c:
            c.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    return engine


def session_factory(engine=None):
    return sessionmaker(bind=engine or get_engine(), expire_on_commit=False, future=True)
