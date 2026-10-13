import csv

import pytest
from fastapi.testclient import TestClient

from api import main, sim_bridge
from db import models as M
from db.session import session_factory

from .conftest import REPO


@pytest.fixture(scope="module")
def client(loaded):
    with TestClient(main.app) as c:
        yield c


def _n(name):
    with open(REPO / "ontology" / name, encoding="utf-8") as f:
        return sum(1 for _ in csv.DictReader(f))


def test_health(client):
    d = client.get("/health").json()
    assert d["ok"] is True and d["db"] == "sqlite" and d["backend"] == "mock"
    assert d["rag_chunks"] > 50 and isinstance(d["cache_entries"], int)


def test_ontology(client):
    d = client.get("/ontology").json()
    assert len(d["nodes"]) == _n("criteria.csv") and len(d["edges"]) == _n("edges.csv")
    price = next(n for n in d["nodes"] if n["criterion_id"] == "prd_meat_price")
    assert price["value"]["base"] == "19000" and price["value"]["method"] == "guesstimate"


def test_sources_and_shocks(client):
    assert len(client.get("/sources").json()) == _n("sources.csv")
    assert any(s["shock_id"] == "SH03" for s in client.get("/shocks").json())


def test_district(client):
    d = client.get("/district", params={"trdar": "3120012"}).json()
    assert d["district"]["trdar_name"] == "대학로(혜화역)" and len(d["quarters"]) == 22
    assert sum(s["class_code"] == "I20107" for s in d["stores"]) == 27
    assert d["survival"]["hansik_primary"]["n"] > 0
    assert d["survival_scope"] == "wide"
    w = d["survival_wide"]
    assert w["scope"] == "wide" and w["pork_name_only"]["n"] > 0 and w["hansik_all"]["n"] > w["pork_name_only"]["n"]
    assert {"pork_name_only_vs_other_hansik", "pork_like_vs_other_hansik"} <= set(w["logrank"])
    assert {r["month"] for r in w["hansik_all"]["table"]} >= {24, 60}
    assert client.get("/district", params={"trdar": "9999999"}).status_code == 404


def test_hero(client):
    d = client.get("/hero").json()
    assert d["pnl"]["rev"] > 0 and len(d["attributes"]) > 50 and d["meta"]["illustrative"] is True


def test_chat_mock_with_citations(client, fresh_llm):
    r = client.post("/chat", json={"persona": "owner", "message": "돼지고기 원가가 오르면?", "k": 3})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["backend"] == "mock" and len(d["sources"]) == 3
    assert "19,000원" in d["answer"] and d["cached"] is False


def test_chat_unknown_persona(client, fresh_llm):
    assert client.post("/chat", json={"persona": "ceo", "message": "hi"}).status_code == 422


def test_chat_cap_returns_429(client, fresh_llm, monkeypatch, fake_claude):
    fake_claude()                                   # caps apply to real backends only; the fake stands in
    monkeypatch.setenv("LLM_BACKEND", "claude_cli")
    monkeypatch.setenv("LLM_SESSION_CAP", "1")
    h = {"X-Session-Id": "capped"}
    assert client.post("/chat", json={"persona": "staff", "message": "피크 시간은?"}, headers=h).status_code == 200
    r = client.post("/chat", json={"persona": "staff", "message": "다른 질문"}, headers=h)
    assert r.status_code == 429 and "LLM_SESSION_CAP" in r.json()["detail"]


def test_chat_refused_model_403(client, fresh_llm, monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "claude_cli")
    monkeypatch.setenv("LLM_MODEL", "sonnet")
    assert client.post("/chat", json={"persona": "owner", "message": "x"}).status_code == 403


def test_simulate_501_when_sim_missing(client, monkeypatch):
    def boom(*a, **k):
        raise sim_bridge.SimUnavailable("no sim")
    monkeypatch.setattr(sim_bridge, "simulate", boom)
    r = client.post("/simulate", json={"shock_id": "SH03", "runs": 2})
    assert r.status_code == 501 and "not available" in r.json()["detail"]


def _sim_ok():
    try:
        sim_bridge._load()
        return True
    except sim_bridge.SimUnavailable:
        return False


@pytest.mark.skipif(not _sim_ok(), reason="sim/ not importable yet")
def test_simulate_persists(client, fresh_llm, loaded):
    r = client.post("/simulate", json={"shock_id": "SH03", "runs": 3, "owner_reaction": True})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["owner_reaction"]["action"] == "absorb" and d["owner_reaction"]["backend"] == "mock"
    with session_factory(loaded["engine"])() as s:
        kpis = s.query(M.SimKpi).filter_by(run_id=d["run_id"]).all()
        assert {k.variant for k in kpis} >= {"base", "shock"}
    ev = client.get(f"/simulate/{d['run_id']}/events", params={"variant": "base"}).json()
    assert len(ev) == d["events"]["base"] and ev[0]["type"]
    assert client.post("/simulate", json={"shock_id": "NOPE", "runs": 2}).status_code == 404
