import csv

from sqlalchemy import select

from db import models as M
from db.load import load_all, table_counts
from db.schema_sql import PATH, render
from db.session import session_factory

from .conftest import REPO


def _rows(path):
    with open(path, encoding="utf-8") as f:
        return sum(1 for _ in csv.DictReader(f))


def test_load_counts_match_inputs(loaded):
    c = table_counts(loaded["engine"])
    assert c["criterion"] == _rows(REPO / "ontology" / "criteria.csv")
    assert c["criterion_edge"] == _rows(REPO / "ontology" / "edges.csv")
    assert c["source"] == _rows(REPO / "ontology" / "sources.csv")
    assert c["store"] == _rows(REPO / "data" / "processed" / "stores_sbiz.csv")
    assert c["store_license"] == _rows(REPO / "data" / "processed" / "licenses.csv")
    assert c["hero_attribute"] > 0 and c["shock"] > 0 and c["district"] == 4


def test_load_is_idempotent(loaded):
    before = table_counts(loaded["engine"])
    load_all(loaded["engine"])
    assert table_counts(loaded["engine"]) == before


def test_values_roundtrip(loaded):
    with session_factory(loaded["engine"])() as s:
        q = s.get(M.DistrictQuarter, ("3120012", "20254"))
        assert q.stores_total == 191 and q.stores_franchise == 31
        assert abs(sum(q.shares["timeband_share"].values()) - 1) < 1e-3
        h = s.get(M.HeroAttribute, ("pork_bbq", "prd_meat_price"))
        assert h.base_num == 19000 and h.filled_by in ("AI", "formula") or h.filled_by
        d = s.get(M.HeroAttribute, ("pork_bbq", "drv_revenue"))
        assert d.method == "derived" and d.filled_by == "formula"
        assert s.scalar(select(M.Store).where(M.Store.class_code == "I20107", M.Store.trdar_code == "3120012")
                        .limit(1)) is not None


def test_embedding_roundtrip_sqlite(loaded):
    with session_factory(loaded["engine"])() as s:
        c = s.scalars(select(M.DocChunk).limit(1)).one()
        assert len(c.embedding) == M.EMBED_DIM and isinstance(c.embedding[0], float)


def test_schema_sql_is_current():
    assert PATH.read_text(encoding="utf-8") == render(), "run `python -m db.schema_sql`"
    assert "VECTOR(384)" in render()
