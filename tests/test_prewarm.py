"""agents/prewarm.py lists prompts and never sends; its prompts are byte-identical to what /chat sends."""
import pytest
from fastapi.testclient import TestClient

from agents import llm, prewarm


@pytest.fixture
def no_calls(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("prewarm must never call the LLM")
    monkeypatch.setattr(llm, "complete", boom)
    monkeypatch.setattr(llm, "_claude_cli", boom)


def test_requires_dry_run(no_calls, capsys):
    assert prewarm.main([]) == 2
    assert "never sends" in capsys.readouterr().err


def test_dry_run_lists_without_sending(loaded, no_calls, capsys):
    assert prewarm.main(["--dry-run"]) == 0
    out = capsys.readouterr()
    assert "Nothing was sent" in out.err and "SH03" in out.out


def test_plan_shape_and_model_guard(loaded, no_calls):
    rows = prewarm.plan()
    assert len(prewarm.QUESTIONS) == 20 and len(rows) >= 20
    assert {r["n"] for r in rows} == set(range(1, 21))
    assert all(r["model"] == "opus" and len(r["cache_key"]) == 64 for r in rows)
    shocked = [r for r in rows if r["shock"]]
    assert {r["action"] for r in shocked} >= {"absorb"}
    with pytest.raises(llm.LLMRefused):
        prewarm.plan("sonnet")


def test_prompts_match_what_chat_sends(loaded, monkeypatch, fresh_llm):
    from api import main
    rows = prewarm.plan()
    sent = []
    real = llm.complete

    def spy(prompt, **kw):
        sent.append(prompt)
        return real(prompt, **kw)
    monkeypatch.setattr(llm, "complete", spy)
    with TestClient(main.app) as c:
        for r in (rows[0], next(x for x in rows if x["shock"] == "SH03" and x["action"] == "absorb")):
            assert c.post("/chat", json=r["request"]).status_code == 200
            assert sent[-1] == r["prompt"], "prewarm prompt differs from the /chat prompt: cache would miss"
