from pathlib import Path

import pytest

from rag.embed import get_embedder
from rag.ingest import ingest, md_chunks
from rag.retrieve import retrieve


def test_md_chunks_keep_section_path():
    text = "# Title\nintro " + "x" * 50 + "\n## Part A\n" + "a" * 2000 + "\n## Part B\nshort but long enough " * 3
    ch = md_chunks(text)
    assert ch[0][0] == "Title"
    a = [c for s, c in ch if s == "Title > Part A"]
    assert len(a) >= 2 and all(len(c) <= 900 for c in a)


def test_ingest_is_idempotent(loaded):
    ingest(loaded["engine"], get_embedder("hash"))   # catch up with docs edited since the session load
    r = ingest(loaded["engine"], get_embedder("hash"))
    assert r["chunks"] > 50 and r["embedded_now"] == 0


def test_retrieve_returns_source_ids(loaded):
    hits = retrieve("Why Restaurants Fail Parsa", k=5, engine=loaded["engine"], embedder=get_embedder("hash"))
    assert len(hits) == 5 and hits[0]["score"] >= hits[-1]["score"]
    assert {"S01", "S02"} & {h["source_id"] for h in hits}


E5_CACHED = (Path.home() / ".cache/huggingface/hub/models--intfloat--multilingual-e5-small").exists()


@pytest.mark.skipif(not E5_CACHED, reason="e5 model not downloaded")
def test_e5_korean_query(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")   # cached model only; no network in tests
    from db.session import get_engine
    eng = get_engine(f"sqlite:///{tmp_path / 'e5.db'}")
    from db.session import init_db
    init_db(eng)
    ingest(eng, get_embedder("e5"))
    hits = retrieve("인허가 데이터 좌표계 변환", k=5, engine=eng, embedder=get_embedder("e5"))
    assert any(k in h["text"] for h in hits[:3] for k in ("5174", "LOCALDATA", "인허가"))


def test_postgres_query_compiles():
    """No Postgres here (Docker is off); at least prove the pgvector query renders for the pg dialect."""
    import numpy as np
    from sqlalchemy.dialects import postgresql

    from rag.retrieve import pg_query
    sql = str(pg_query(np.zeros(384), "m", 5).compile(dialect=postgresql.dialect()))
    assert "<=>" in sql and "ORDER BY" in sql and "LIMIT" in sql
