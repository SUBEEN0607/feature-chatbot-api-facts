"""Game endpoints: precomputed runs, action simulate, owner decide, persona chat with context, CORS."""
import json
import re

import pytest
from fastapi.testclient import TestClient

from api import game, main, sim_bridge
from agents import chat as chat_agent
from agents import owner as owner_agent


def _kpis(op, covers=900, walk=10):
    t = {"op": {"p10": op * 0.8, "p50": op, "p90": op * 1.2}, "revenue": {"p10": 1, "p50": 27_000_000, "p90": 2},
         "covers": {"p10": 1, "p50": covers, "p90": 2}, "walkaways": {"p10": 0, "p50": walk, "p90": 1},
         "avg_wait_min": {"p10": 0, "p50": 3, "p90": 5}}
    return t


@pytest.fixture
def runs_dir(tmp_path, monkeypatch):
    """Precomputed runs for SH03: every menu action, reprice best."""
    d = tmp_path / "runs"
    menu = owner_agent.action_menu()
    for a in menu:
        op = 3_100_000 if a == "reprice" else 2_000_000
        (d / "SH03").mkdir(parents=True, exist_ok=True)
        (d / "SH03" / f"{a}.json").write_text(json.dumps({
            "shock": {"id": "SH03"}, "action": {"id": a, "args": {"pct": 0.05} if a == "reprice" else {}},
            "base": _kpis(2_600_000), "reacted": _kpis(op)}))
    monkeypatch.setenv("RUNS_DIR", str(d))
    return d


@pytest.fixture(scope="module")
def client(loaded):
    with TestClient(main.app) as c:
        yield c


def test_runs_index_and_file(client, runs_dir):
    idx = client.get("/runs").json()
    assert set(idx["shocks"]["SH03"]) == set(owner_agent.action_menu()) and idx["files"] == len(owner_agent.action_menu())
    r = client.get("/runs/SH03/reprice").json()
    assert r["reacted"]["op"]["p50"] == 3_100_000
    assert client.get("/runs/SH03/nothing").status_code == 404
    assert client.get("/runs/SH03/..%2F..%2Fsecrets").status_code in (404, 422)


def test_runs_index_empty_dir(client, tmp_path, monkeypatch):
    monkeypatch.setenv("RUNS_DIR", str(tmp_path / "none"))
    assert client.get("/runs").json()["files"] == 0


def test_owner_decide_rule_on_precomputed(client, runs_dir, fresh_llm):
    d = client.post("/owner/decide", json={"shock_id": "SH03", "allow_low_confidence": True}).json()
    assert d["action"] == "reprice" and d["method"] == "rule" and d["backend"] == "mock"
    assert d["args"] == {"pct": 0.05} and "310만원" in d["reason"] and "200만원" in d["reason"]
    assert all(c["source"] == "precomputed" for c in d["candidates"])
    assert client.post("/owner/decide", json={"shock_id": "SH99"}).status_code == 404


def test_owner_decide_llm_invalid_falls_back_to_rule(client, runs_dir, fresh_llm, fake_claude, monkeypatch):
    fake_claude('echo "제 생각엔 가격을 올리는 게 좋겠어요"')      # prose, not JSON
    monkeypatch.setenv("LLM_BACKEND", "claude_cli")
    d = client.post("/owner/decide", json={"shock_id": "SH03", "allow_low_confidence": True}).json()
    assert d["action"] == "reprice" and d["method"] == "llm_invalid_rule_fallback" and "llm_error" in d


def test_owner_decide_llm_valid(client, runs_dir, fresh_llm, fake_claude, monkeypatch):
    fake_claude("""echo '{"action": "absorb", "args": {}, "reason": "단골이 많아 버팁니다 [S31]"}'""")
    monkeypatch.setenv("LLM_BACKEND", "claude_cli")
    d = client.post("/owner/decide", json={"shock_id": "SH03"}).json()
    assert d["action"] == "absorb" and d["method"] == "llm" and d["fallback"] is False


def test_owner_decide_live_when_no_files(client, fresh_llm, tmp_path, monkeypatch):
    monkeypatch.setenv("RUNS_DIR", str(tmp_path / "empty"))
    monkeypatch.setattr(game, "LIVE_RUNS", 8)
    game._live.cache_clear()
    d = client.post("/owner/decide", json={"shock_id": "SH09", "allow_low_confidence": True}).json()
    assert d["action"] in owner_agent.action_menu() and d["method"] == "rule"
    best = max(c["op_p50"] for c in d["candidates"])
    assert next(c for c in d["candidates"] if c["action"] == d["action"])["op_p50"] == best
    assert all(c["source"] == "live" for c in d["candidates"])


def test_simulate_with_action(client):
    r = client.post("/simulate", json={"shock_id": "SH03", "action": "reprice", "action_args": {"pct": 0.1}, "runs": 5})
    assert r.status_code == 200, r.text
    k = r.json()["kpis"]
    assert k["action"] == {"id": "reprice", "args": {"pct": 0.1}} and k["reacted"]["op"]["p50"]
    bad = client.post("/simulate", json={"shock_id": "SH03", "action": "reprice", "action_args": {"pct": 0.9}, "runs": 2})
    assert bad.status_code == 422
    assert client.post("/simulate", json={"shock_id": "SH03", "action": "fly", "runs": 2}).status_code == 422


def test_simulate_action_501(client, monkeypatch):
    def boom(*a, **k):
        raise sim_bridge.SimUnavailable("no sim")
    monkeypatch.setattr(sim_bridge, "run_action", boom)
    assert client.post("/simulate", json={"shock_id": "SH03", "action": "absorb", "runs": 2}).status_code == 501


NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


@pytest.mark.parametrize("persona", list(chat_agent.PERSONAS))
def test_chat_context_numbers_only_from_inputs(client, runs_dir, fresh_llm, persona):
    """The mock answer may only contain numbers that appear in the prompt's number blocks or the question."""
    msg = "고기 원가가 오르면 어떻게 하실 건가요?"
    r = client.post("/chat", json={"persona": persona, "message": msg, "context": {"shock": "SH03", "action": "reprice"}})
    assert r.status_code == 200, r.text
    d = r.json()
    assert set(d) >= {"answer", "sources", "backend", "cached"} and d["backend"] == "mock"
    assert any("SH03/reprice (precomputed)" in x for x in d["numbers_from"])
    # rebuild the allowed-number pool exactly as the prompt does
    from db.session import database_url, get_engine, session_factory
    with session_factory(get_engine(database_url()))() as s:
        hero = main._with_baseline(main._hero(s))
        note = main._shock_note(s, "SH03", "reprice")       # shock/action labels are inputs too
    sim, _ = main._sim_context("SH03", "reprice")
    allowed = " ".join(chat_agent.facts(hero, district=main._chat_district(s)).values()) + " ".join(chat_agent.sim_lines(sim)) + msg + note
    allowed += " ".join(c["label"] or "" for c in d["citations"])     # cited source ids (S36 ...) are not numbers
    for n in NUM.findall(d["answer"]):
        assert n in allowed, f"{persona}: number {n} not from hero/sim inputs"
    if persona == "owner":
        assert "310만원" in d["answer"]          # the reprice outcome reached the owner's answer


def test_chat_bad_context(client, fresh_llm):
    r = client.post("/chat", json={"persona": "owner", "message": "x", "context": {"shock": "../x"}})
    assert r.status_code == 422


def test_cors(client):
    ok = client.options("/runs", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = client.options("/runs", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"})
    assert bad.headers.get("access-control-allow-origin") is None


def test_owner_decide_excludes_low_confidence_by_default(client, runs_dir, fresh_llm):
    d = client.post("/owner/decide", json={"shock_id": "SH03"}).json()
    ex = {e["action"]: e for e in d["excluded"]}
    assert "cut_staff" in ex and "cut_staff_hours" in ex and d["action"] not in ex
    assert "인터뷰로 확인 필요" in ex["cut_staff"]["reason"] and ex["cut_staff"]["mechanisms"][0]["confidence"] == "L"
    assert ex["cut_staff"]["op_p50"] == 2_000_000          # outcome still shown for the UI
    assert {c["action"] for c in d["candidates"]}.isdisjoint(ex) and d["allow_low_confidence"] is False
    eligible = {c["action"]: c for c in d["candidates"]}
    assert d["action"] in eligible
    assert eligible[d["action"]]["op_p50"] == max(c["op_p50"] for c in eligible.values())


def test_owner_decide_llm_cannot_pick_excluded(client, runs_dir, fresh_llm, fake_claude, monkeypatch):
    fake_claude("""echo '{"action": "cut_staff", "args": {"n": 1}, "reason": "인건비 절감 [S31]"}'""")
    monkeypatch.setenv("LLM_BACKEND", "claude_cli")
    d = client.post("/owner/decide", json={"shock_id": "SH03"}).json()
    assert d["action"] != "cut_staff" and d["method"] == "llm_invalid_rule_fallback"


def test_confidence_gate_unit():
    menu = owner_agent.action_menu()
    cands = [{"action": a, "op_p50": 1.0} for a in ("absorb", "reprice", "cut_staff", "brand_new_action")]
    el, ex = owner_agent.confidence_gate(cands, {"mkt_price_elasticity": {"confidence": "M"}}, menu, False)
    assert [c["action"] for c in el] == ["absorb", "reprice"]           # reviewed to M: price action returns
    assert {e["action"] for e in ex} == {"cut_staff", "brand_new_action"}  # sim constant L; unmapped = excluded
    el, ex = owner_agent.confidence_gate(cands, {}, menu, True)
    assert len(el) == 4 and ex == []
