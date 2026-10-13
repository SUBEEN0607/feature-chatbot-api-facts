"""Guardrails of agents/llm.py. The real `claude` CLI is never invoked: claude_cli tests run a fake
`claude` script on a PATH that does not contain the real one."""
import pytest

def ctx(llm, session="s1"):
    return llm.RequestContext(session_id=session)


def test_default_backend_is_mock(fresh_llm, monkeypatch):
    monkeypatch.delenv("LLM_BACKEND", raising=False)
    r = fresh_llm.complete("hello", ctx=ctx(fresh_llm))
    assert r.backend == "mock" and r.text.startswith("[mock")


def test_only_api_origin(fresh_llm):
    with pytest.raises(fresh_llm.LLMRefused):
        fresh_llm.complete("x", ctx=fresh_llm.RequestContext(session_id="s", origin="script"))
    with pytest.raises(fresh_llm.LLMRefused):
        fresh_llm.complete("x", ctx="not-a-context")


def test_one_call_per_request(fresh_llm):
    c = ctx(fresh_llm)
    fresh_llm.complete("first", ctx=c)
    with pytest.raises(fresh_llm.LLMRefused, match="one LLM call per API request"):
        fresh_llm.complete("second", ctx=c)


def test_session_cap(fresh_llm, monkeypatch, fake_claude):
    fake_claude()
    monkeypatch.setenv("LLM_BACKEND", "claude_cli")
    monkeypatch.setenv("LLM_SESSION_CAP", "2")
    fresh_llm.complete("a", ctx=ctx(fresh_llm))
    fresh_llm.complete("b", ctx=ctx(fresh_llm))
    with pytest.raises(fresh_llm.LLMCapExceeded):
        fresh_llm.complete("c", ctx=ctx(fresh_llm))
    assert fresh_llm.complete("c", ctx=ctx(fresh_llm, "other-session")).calls_used == 1


def test_default_cap_is_30(fresh_llm):
    assert fresh_llm.session_cap() == 30


def test_rate_limit(fresh_llm, monkeypatch, fake_claude):
    fake_claude()
    monkeypatch.setenv("LLM_BACKEND", "claude_cli")
    monkeypatch.setenv("LLM_RATE_PER_MIN", "2")
    fresh_llm.complete("a", ctx=ctx(fresh_llm, "x"))
    fresh_llm.complete("b", ctx=ctx(fresh_llm, "y"))
    with pytest.raises(fresh_llm.LLMCapExceeded, match="last minute"):
        fresh_llm.complete("c", ctx=ctx(fresh_llm, "z"))


def test_cache_before_call_and_cap(fresh_llm, monkeypatch, tmp_path, fake_claude):
    fake_claude()
    monkeypatch.setenv("LLM_BACKEND", "claude_cli")
    monkeypatch.setenv("LLM_SESSION_CAP", "1")
    r1 = fresh_llm.complete("same prompt", ctx=ctx(fresh_llm))
    key = fresh_llm.cache_key("opus", "same prompt")
    assert (tmp_path / "cache" / f"{key}.json").exists()
    r2 = fresh_llm.complete("same prompt", ctx=ctx(fresh_llm))   # cap reached, but cached
    assert r2.cached and r2.text == r1.text and r2.calls_used == 1
    with pytest.raises(fresh_llm.LLMCapExceeded):
        fresh_llm.complete("new prompt", ctx=ctx(fresh_llm))


def test_claude_cli_wiring_with_fake(fresh_llm, fake_claude, monkeypatch, tmp_path):
    log = fake_claude()
    monkeypatch.setenv("LLM_BACKEND", "claude_cli")
    r = fresh_llm.complete("PROMPT-ON-STDIN 한국어", ctx=ctx(fresh_llm))
    assert r.text == "FAKE-ANSWER model=opus" and r.model == "opus" and not r.cached
    calls = log.read_text()
    lines = calls.splitlines()
    assert lines[0] == f"CWD={(tmp_path / 'llm-cwd').resolve()}" and lines[1] == "SAFE=1"
    args = [l[1:-1] for l in lines[2:] if l.startswith("[")]
    assert args == ["-p", "--model", "opus", "--safe-mode", "--setting-sources", "project", "--strict-mcp-config",
                    "--tools", "", "--disable-slash-commands", "--no-session-persistence", "--no-chrome",
                    "--system-prompt", fresh_llm.CLAUDE_FLAGS[-1]]
    assert "--bare" not in args and "PROMPT-ON-STDIN 한국어" in calls
    r2 = fresh_llm.complete("PROMPT-ON-STDIN 한국어", ctx=ctx(fresh_llm))   # cached: no second process
    assert r2.cached and log.read_text().count("---") == 1


@pytest.mark.parametrize("model", ["haiku", "claude-haiku-4-5", "sonnet", "claude-sonnet-5-5", "gpt-4o",
                                   "opus-sonnet-mix"])
def test_claude_cli_refuses_non_opus(fresh_llm, fake_claude, monkeypatch, model):
    log = fake_claude()
    monkeypatch.setenv("LLM_BACKEND", "claude_cli")
    with pytest.raises(fresh_llm.LLMRefused):
        fresh_llm.complete("x", ctx=ctx(fresh_llm), model=model)
    assert not log.exists(), "a refused model must never reach the subprocess"


def test_claude_cli_errors(fresh_llm, fake_claude, monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "claude_cli")
    fake_claude('echo boom >&2; exit 3')
    with pytest.raises(fresh_llm.LLMBackendError, match="exit 3"):
        fresh_llm.complete("x", ctx=ctx(fresh_llm))
    fake_claude("sleep 5")
    monkeypatch.setenv("LLM_TIMEOUT_S", "1")
    with pytest.raises(fresh_llm.LLMBackendError, match="timed out"):
        fresh_llm.complete("y", ctx=ctx(fresh_llm))


# gemini: the HTTP call (_gemini_post) is replaced in every test, so nothing reaches the network even when a
# parent .env holds a real key
def _gemini_fake(llm, monkeypatch, replies):
    """replies: list of dicts (a JSON reply) or ints (an HTTP error code), consumed in order."""
    import io
    import urllib.error
    calls = []

    def post(url, body, key, timeout):
        calls.append({"url": url, "key": key, "body": body})
        r = replies.pop(0)
        if isinstance(r, int):
            raise urllib.error.HTTPError(url, r, "err", {}, io.BytesIO(b'{"error": {"message": "busy"}}'))
        return r
    monkeypatch.setattr(llm, "_gemini_post", post)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("GEMINI_MIN_INTERVAL_S", "0")
    return calls


def _reply(text):
    return {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}]}


def test_gemini_needs_a_key(fresh_llm, monkeypatch):
    monkeypatch.setattr(fresh_llm, "gemini_key", lambda: None)
    with pytest.raises(fresh_llm.LLMBackendError, match="GEMINI_API_KEY"):
        fresh_llm.complete("x", ctx=ctx(fresh_llm), backend="gemini")


def test_gemini_answers_with_key_in_header_only(fresh_llm, monkeypatch):
    calls = _gemini_fake(fresh_llm, monkeypatch, [_reply("답입니다")])
    r = fresh_llm.complete("질문", ctx=ctx(fresh_llm), backend="gemini")
    assert (r.text, r.backend, r.model, r.calls_used) == ("답입니다", "gemini", "gemini-3.1-flash-lite", 1)
    assert calls[0]["key"] == "test-key-not-real" and "test-key-not-real" not in calls[0]["url"]
    assert "gemini-3.1-flash-lite:generateContent" in calls[0]["url"]


def test_gemini_retries_then_falls_back_and_never_leaks_the_key(fresh_llm, monkeypatch):
    calls = _gemini_fake(fresh_llm, monkeypatch, [503, _reply("두 번째에 성공")])
    assert fresh_llm.complete("a", ctx=ctx(fresh_llm, "r1"), backend="gemini").text == "두 번째에 성공"
    calls = _gemini_fake(fresh_llm, monkeypatch, [503, 503, _reply("대체 모델")])
    assert fresh_llm.complete("b", ctx=ctx(fresh_llm, "r2"), backend="gemini").text == "대체 모델"
    assert "gemini-2.5-flash:" in calls[-1]["url"]
    _gemini_fake(fresh_llm, monkeypatch, [503, 503, 503])
    with pytest.raises(fresh_llm.LLMBackendError) as e:
        fresh_llm.complete("c", ctx=ctx(fresh_llm, "r3"), backend="gemini")
    assert "503" in str(e.value) and "test-key-not-real" not in str(e.value)
    _gemini_fake(fresh_llm, monkeypatch, [400])           # not retryable: one call, then the error
    with pytest.raises(fresh_llm.LLMBackendError, match="400"):
        fresh_llm.complete("d", ctx=ctx(fresh_llm, "r4"), backend="gemini")


def test_gemini_keeps_the_guardrails(fresh_llm, monkeypatch):
    _gemini_fake(fresh_llm, monkeypatch, [_reply("x")] * 5)
    for bad in ("gemini-2.5-pro", "gemini-2.5-flash-image", "gemini-2.5-flash-preview-tts", "gpt-4o"):
        with pytest.raises(fresh_llm.LLMRefused):
            fresh_llm.complete("q", ctx=ctx(fresh_llm), backend="gemini", model=bad)
    monkeypatch.setenv("LLM_SESSION_CAP", "1")
    fresh_llm.complete("q1", ctx=ctx(fresh_llm, "cap"), backend="gemini")
    assert fresh_llm.complete("q1", ctx=ctx(fresh_llm, "cap"), backend="gemini").cached     # cache before the cap
    with pytest.raises(fresh_llm.LLMCapExceeded):
        fresh_llm.complete("q2", ctx=ctx(fresh_llm, "cap"), backend="gemini")
    with pytest.raises(fresh_llm.LLMRefused, match="command line only the mock"):
        fresh_llm.complete("q3", ctx=fresh_llm.RequestContext(session_id="c", origin="cli"), backend="gemini")


def test_unknown_backend(fresh_llm):
    with pytest.raises(fresh_llm.LLMRefused):
        fresh_llm.complete("x", ctx=ctx(fresh_llm), backend="openai")


@pytest.mark.parametrize("where", ["repo", "repo_sub", "has_claude_md", "has_mcp_json"])
def test_claude_cli_cwd_guard(fresh_llm, fake_claude, monkeypatch, tmp_path, where):
    from .conftest import REPO
    log = fake_claude()
    monkeypatch.setenv("LLM_BACKEND", "claude_cli")
    if where == "repo":
        d = REPO
    elif where == "repo_sub":
        d = REPO / "data" / "llm_cwd_should_not_exist"
    elif where == "has_claude_md":
        (tmp_path / "proj").mkdir()
        (tmp_path / "proj" / "CLAUDE.md").write_text("x")
        d = tmp_path / "proj" / "sub"
    else:
        d = tmp_path / "busy"
        d.mkdir()
        (d / ".mcp.json").write_text("{}")
    monkeypatch.setenv("LLM_CLAUDE_CWD", str(d))
    with pytest.raises(fresh_llm.LLMRefused, match="cwd"):
        fresh_llm.complete("x", ctx=ctx(fresh_llm))
    assert not log.exists() and not (REPO / "data" / "llm_cwd_should_not_exist").exists()


def test_default_cwd_is_outside_repos(fresh_llm, monkeypatch):
    monkeypatch.delenv("LLM_CLAUDE_CWD", raising=False)
    from pathlib import Path
    from .conftest import REPO
    d = Path.home() / ".cache" / "team-gogi-llm"
    assert REPO not in d.resolve().parents and "Dev" not in d.parts


def test_mock_template_change_is_not_served_from_cache(fresh_llm):
    a = fresh_llm.complete("same", ctx=ctx(fresh_llm), mock_text="old sentence")
    b = fresh_llm.complete("same", ctx=ctx(fresh_llm), mock_text="new sentence")
    assert a.text == "old sentence" and b.text == "new sentence" and not b.cached
    c = fresh_llm.complete("same", ctx=ctx(fresh_llm), mock_text="new sentence")
    assert c.cached


def test_cli_origin_mock_only(fresh_llm, fake_claude, monkeypatch):
    log = fake_claude()
    r = fresh_llm.complete("x", ctx=fresh_llm.RequestContext(session_id="cli", origin="cli"))
    assert r.backend == "mock"
    monkeypatch.setenv("LLM_BACKEND", "claude_cli")
    with pytest.raises(fresh_llm.LLMRefused, match="command line only the mock"):
        fresh_llm.complete("y", ctx=fresh_llm.RequestContext(session_id="cli", origin="cli"))
    assert not log.exists()


def test_mock_is_exempt_from_caps(fresh_llm, monkeypatch):
    """A demo on the mock backend must survive a fast click-through of all preset questions."""
    monkeypatch.setenv("LLM_SESSION_CAP", "1")
    monkeypatch.setenv("LLM_RATE_PER_MIN", "1")
    for i in range(25):
        assert fresh_llm.complete(f"q{i}", ctx=ctx(fresh_llm)).backend == "mock"
