"""Concurrent requests on ONE season (CI: game_v2 free lost the 평소 comparison). The web client fires the shadow
(평소 plan) play without waiting, so two /play on the same season can overlap: both read the same state, both
simulate the same month, and both append it. Each state-mutating season endpoint must hold a per-season lock, and a
client that says which month it means (month_index) must never advance a season twice."""
import threading
import time

import pytest
from fastapi.testclient import TestClient

from agents import persona


@pytest.fixture(scope="module")
def client(loaded):
    from api import main
    with TestClient(main.app) as c:
        yield c


def _slow_render(monkeypatch, delay=0.15):
    """Widen the read-simulate-write window the way a slow machine does (persona text runs between the read and the write)."""
    real = persona.render_month

    def slow(*a, **kw):
        time.sleep(delay)
        return real(*a, **kw)
    monkeypatch.setattr(persona, "render_month", slow)


def _fire(client, reqs):
    """POST every (url, body) at once from its own thread; responses in request order."""
    out = [None] * len(reqs)
    gate = threading.Barrier(len(reqs))

    def go(i):
        gate.wait()
        out[i] = client.post(reqs[i][0], json=reqs[i][1])
    ts = [threading.Thread(target=go, args=(i,)) for i in range(len(reqs))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    return out


def _consistent(g: dict):
    months = g["months"]
    assert len({m["month"] for m in months}) == len(months), f"a month was stored twice: {[m['month'] for m in months]}"
    if months:
        st = {k: v for k, v in g["state"].items() if k not in ("month_events", "pending_start")}
        assert st == months[-1]["state_after"], "stored months and the season state disagree"


def test_concurrent_plays_never_duplicate_a_month(client, fresh_llm, monkeypatch):
    _slow_render(monkeypatch)
    s = client.post("/season", json={"mode": "sandbox", "seed": 31}).json()
    rs = _fire(client, [(f"/season/{s['id']}/play", {"plan": {}})] * 3)
    assert all(r.status_code == 200 for r in rs), [r.text for r in rs]
    g = client.get(f"/season/{s['id']}").json()
    _consistent(g)
    assert g["months_played"] == 3
    assert len({r.json()["month"] for r in rs}) == 3, "two concurrent plays returned the same month"


def test_month_index_plays_each_month_once(client, fresh_llm, monkeypatch):
    """The shadow client sends month_index: two copies of one request advance the season once; the second returns the
    month already played (same numbers), and a request for a month that is not open is refused."""
    _slow_render(monkeypatch)
    s = client.post("/season", json={"mode": "sandbox", "seed": 32}).json()
    events = [e["id"] for e in s["state"]["month_events"]]
    body = {"plan": {}, "events": events, "month_index": 0}
    rs = _fire(client, [(f"/season/{s['id']}/play", body)] * 2)
    assert [r.status_code for r in rs] == [200, 200], [r.text for r in rs]
    a, b = (r.json() for r in rs)
    assert a["month"] == b["month"] and a["state_after"] == b["state_after"]
    assert sum(bool(r.json().get("replayed")) for r in rs) == 1
    g = client.get(f"/season/{s['id']}").json()
    assert g["months_played"] == 1
    _consistent(g)
    stale = client.post(f"/season/{s['id']}/play", json={"plan": {}, "month_index": 3})
    assert stale.status_code == 409 and stale.json()["detail"]["months_played"] == 1
    other = client.post(f"/season/{s['id']}/play", json={"plan": {"meat_price": 99000}, "events": events, "month_index": 0})
    assert other.status_code == 409, "a different request for a played month must not pass as a replay"
    assert client.post(f"/season/{s['id']}/start_month", json={"plan": {}, "month_index": 0}).status_code == 409
    assert client.get(f"/season/{s['id']}").json()["months_played"] == 1


def test_concurrent_start_month_and_play(client, fresh_llm, monkeypatch):
    """start_month and play on one season interleave as whole requests, never half of each."""
    _slow_render(monkeypatch)
    s = client.post("/season", json={"mode": "sandbox", "seed": 33}).json()
    play, start = f"/season/{s['id']}/play", f"/season/{s['id']}/start_month"
    for _ in range(2):
        rs = _fire(client, [(start, {"plan": {}}), (play, {"plan": {}}), (start, {"plan": {}}), (play, {"plan": {}})])
        assert all(r.status_code in (200, 501) for r in rs), [r.text for r in rs]
    g = client.get(f"/season/{s['id']}").json()
    assert g["months_played"] == 4
    _consistent(g)


def test_plays_without_month_index_still_work(client, fresh_llm):
    """Guided/offline tooling and the engine clients send no month_index: unchanged behaviour."""
    s = client.post("/season", json={"mode": "free", "seed": 34}).json()
    for _ in range(2):
        r = client.post(f"/season/{s['id']}/play", json={"plan": {}})
        assert r.status_code == 200 and "replayed" not in r.json()
    assert client.get(f"/season/{s['id']}").json()["months_played"] == 2
