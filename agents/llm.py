"""The ONE LLM adapter. Every model call in this repo goes through `complete()`.

Guardrails (decision 2026-09-30; enforced here in code, not by convention):
  1. Origin: `complete()` needs a RequestContext that only the API layer creates, one per HTTP request,
     and each request may make ONE call. There is no batch helper; a loop inside a request is refused.
     Command-line tools (origin 'cli') may only use the offline mock backend.
  2. Session cap: at most LLM_SESSION_CAP real-model calls per session id (default 30).
  3. Rate: at most LLM_RATE_PER_MIN real-model calls per rolling minute in this process (default 6),
     which stops a client-side loop hammering the API. The offline mock is exempt from 2 and 3.
  4. Cache: an on-disk cache keyed by sha256(model + prompt) is checked BEFORE the cap and the call.
  5. Model: the claude_cli backend only runs a model whose name contains 'opus' (haiku/sonnet refused); the gemini
     backend only runs a free-tier Flash / Flash-Lite text model (pro, image, tts refused).
  6. Backend: LLM_BACKEND selects it; the default is `mock`, so nothing is ever called by accident.

Backends:
  mock        deterministic, offline (tests, teammates without keys)
  claude_cli  `claude -p --model <opus>` + isolation flags, prompt on stdin, run from an empty dir
              outside every repo (see CLAUDE_FLAGS); Keonhee's Mac only, demo clicks only
  gemini      Google AI Studio free tier over REST (default gemini-3.1-flash-lite, thinking off), key GEMINI_API_KEY
              from the environment or a .env; calls spaced by GEMINI_MIN_INTERVAL_S, retried on 429/5xx with
              backoff capped at 8 s inside GEMINI_TIMEOUT_S, then GEMINI_FALLBACK_MODEL once (see _gemini)
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKENDS = ("mock", "claude_cli", "gemini")


class LLMGuardError(RuntimeError):
    """A guardrail refused the call."""


class LLMCapExceeded(LLMGuardError):
    pass


class LLMRefused(LLMGuardError):
    pass


class LLMBackendError(RuntimeError):
    pass


@dataclass(frozen=True)
class RequestContext:
    session_id: str
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    origin: str = "api"


@dataclass
class LLMResult:
    text: str
    backend: str
    model: str
    cached: bool
    calls_used: int
    cap: int


# --- process state (guarded by _lock) ---
_lock = threading.Lock()
_session_calls: dict[str, int] = {}
_used_requests: set[str] = set()
_recent: deque[float] = deque()


def reset_state() -> None:
    """Tests only."""
    with _lock:
        _session_calls.clear()
        _used_requests.clear()
        _recent.clear()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def session_cap() -> int:
    return _env_int("LLM_SESSION_CAP", 30)


def cache_dir() -> Path:
    return Path(os.environ.get("LLM_CACHE_DIR", REPO / "data" / "llm_cache"))


def default_model(backend: str) -> str:
    return os.environ.get("LLM_MODEL") or {"claude_cli": "opus", "gemini": "gemini-3.1-flash-lite"}.get(backend, "mock")


def cache_key(model: str, prompt: str) -> str:
    return hashlib.sha256(f"{model}\n{prompt}".encode("utf-8")).hexdigest()


def _cache_get(key: str) -> str | None:
    p = cache_dir() / f"{key}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))["text"]
        except (json.JSONDecodeError, KeyError):
            return None
    return None


def _cache_put(key: str, model: str, text: str) -> None:
    d = cache_dir()
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f"{key}.tmp"
    tmp.write_text(json.dumps({"model": model, "text": text, "ts": time.time()}, ensure_ascii=False),
                   encoding="utf-8")
    tmp.replace(d / f"{key}.json")


def check_model(backend: str, model: str) -> None:
    if backend == "claude_cli":
        m = model.lower()
        if "opus" not in m or "haiku" in m or "sonnet" in m:
            raise LLMRefused(f"claude_cli only runs an Opus model; refused {model!r}")
    if backend == "gemini":
        m = model.lower()
        if not m.startswith("gemini-") or "flash" not in m or any(x in m for x in ("pro", "image", "tts", "live")):
            raise LLMRefused(f"gemini runs a free-tier Flash or Flash-Lite text model only; refused {model!r}")


def complete(prompt: str, *, ctx: RequestContext, backend: str | None = None, model: str | None = None,
             mock_text: str | None = None) -> LLMResult:
    """One model call for one API request. Raises LLMGuardError subclasses when a guardrail refuses.
    `mock_text` is what the mock backend returns (a deterministic template built from real numbers);
    real backends ignore it."""
    if not isinstance(ctx, RequestContext) or ctx.origin not in ("api", "cli"):
        raise LLMRefused("LLM calls are only allowed from an API request (RequestContext origin='api')")
    backend = backend or os.environ.get("LLM_BACKEND", "mock")
    if backend not in BACKENDS:
        raise LLMRefused(f"unknown LLM backend {backend!r}; choose from {BACKENDS}")
    if ctx.origin == "cli" and backend != "mock":
        # command-line tools may loop over many items; only the offline mock may run there
        raise LLMRefused("from the command line only the mock backend runs; draft one item per API request "
                         "(e.g. POST /review/drafts/{criterion_id}) to use a real model")
    model = model or default_model(backend)
    check_model(backend, model)
    cap = session_cap()

    with _lock:
        if ctx.request_id in _used_requests:
            raise LLMRefused("one LLM call per API request; this request already made one")
        _used_requests.add(ctx.request_id)

    # mock answers are templates over live numbers: key on the template output too, so a template change
    # never serves a stale cached sentence (real backends key on model + prompt only)
    key = cache_key(model, prompt if (backend != "mock" or mock_text is None) else f"{prompt}\n<mock>{mock_text}")
    hit = _cache_get(key)
    if hit is not None:
        return LLMResult(hit, backend, model, True, _session_calls.get(ctx.session_id, 0), cap)

    if backend == "mock":   # offline and free: caps protect real model calls only, so a demo on the
        # mock backend never hits 429 when someone clicks through many preset questions
        text = mock_text if mock_text is not None else _mock(prompt, model)
        _cache_put(key, model, text)
        return LLMResult(text, backend, model, False, _session_calls.get(ctx.session_id, 0), cap)

    with _lock:
        used = _session_calls.get(ctx.session_id, 0)
        if used >= cap:
            raise LLMCapExceeded(f"session {ctx.session_id!r} used its {cap} LLM calls (LLM_SESSION_CAP)")
        now = time.time()
        while _recent and now - _recent[0] > 60:
            _recent.popleft()
        per_min = _env_int("LLM_RATE_PER_MIN", 6)
        if len(_recent) >= per_min:
            raise LLMCapExceeded(f"more than {per_min} LLM calls in the last minute (LLM_RATE_PER_MIN)")
        _session_calls[ctx.session_id] = used + 1   # counted before the call: a failed call still counts
        _recent.append(now)

    text = mock_text if (backend == "mock" and mock_text is not None) else _BACKEND_FN[backend](prompt, model)
    _cache_put(key, model, text)
    return LLMResult(text, backend, model, False, used + 1, cap)


# --- backends ---

def _mock(prompt: str, model: str) -> str:
    if "RESPOND_WITH_OWNER_ACTION_JSON" in prompt:
        return json.dumps({"action": "absorb", "args": {},
                           "reason": "mock 백엔드: 실제 모델 없이 고정 응답 (테스트용)"}, ensure_ascii=False)
    h = hashlib.sha256(prompt.encode()).hexdigest()[:8]
    return f"[mock {h}] 실제 모델이 연결되지 않은 테스트 응답입니다. 아래 근거 문서를 참고하세요."


# Isolation for `claude -p` (checked against `claude --help`, Claude Code 2.1.285). Launched from inside a
# repo, `claude` would load that repo's CLAUDE.md/memory and fire the user's hooks, so it runs from an
# empty directory outside every repo with customizations off:
#   --safe-mode                  CLAUDE.md, skills, plugins, hooks, MCP servers, custom agents all off
#   --setting-sources project    only project settings, and the cwd has none (user settings/hooks skipped)
#   --strict-mcp-config          no --mcp-config given, so no MCP servers
#   --tools ""                   no tools at all: personas only return text
#   --disable-slash-commands     no skills
#   --no-session-persistence     nothing saved to disk or resumable
#   --no-chrome                  no browser integration
#   --system-prompt              a short text-only prompt instead of the coding-agent default
# Not used: --bare (reads only ANTHROPIC_API_KEY, i.e. the paid API, never the subscription login) and
# max-turns (no such flag in this version; with no tools there is only one turn anyway).
CLAUDE_FLAGS = [
    "--safe-mode", "--setting-sources", "project", "--strict-mcp-config", "--tools", "",
    "--disable-slash-commands", "--no-session-persistence", "--no-chrome",
    "--system-prompt", "You answer in plain text only. You have no tools. Follow the user's instructions.",
]


def claude_cwd() -> Path:
    """Empty working dir outside every repo, created on demand. Refused if it would pick up project context."""
    d = Path(os.environ.get("LLM_CLAUDE_CWD", Path.home() / ".cache" / "team-gogi-llm")).expanduser().resolve()
    home = Path.home().resolve()
    for p in [d, *d.parents]:
        if p == REPO or (p / ".git").exists() or (p / "CLAUDE.md").exists() or (p / "CLAUDE.local.md").exists() \
                or (p != home and (p / ".claude").exists()):
            raise LLMRefused(f"claude_cli cwd {d} sits under {p}, which has repo/Claude project context")
    d.mkdir(parents=True, exist_ok=True)
    found = [n for n in (".mcp.json", ".claude", "CLAUDE.md", "CLAUDE.local.md", ".git") if (d / n).exists()]
    if found:
        raise LLMRefused(f"claude_cli cwd {d} contains project context: {found}")
    return d


def _claude_cli(prompt: str, model: str) -> str:
    exe = shutil.which("claude")
    if not exe:
        raise LLMBackendError("`claude` CLI not found on PATH")
    cwd = claude_cwd()
    env = {**os.environ, "CLAUDE_CODE_SAFE_MODE": "1"}
    try:
        r = subprocess.run([exe, "-p", "--model", model, *CLAUDE_FLAGS], input=prompt, text=True,
                           capture_output=True, cwd=cwd, env=env, timeout=_env_int("LLM_TIMEOUT_S", 120))
    except subprocess.TimeoutExpired as e:
        raise LLMBackendError(f"claude CLI timed out after {e.timeout}s") from e
    if r.returncode != 0:
        raise LLMBackendError(f"claude CLI exit {r.returncode}: {r.stderr.strip()[:300]}")
    out = r.stdout.strip()
    if not out:
        raise LLMBackendError("claude CLI returned empty output")
    return out


# Gemini free tier (Google AI Studio key). Model names checked against GET /v1beta/models on 2026-10-05; the free
# tier covers Flash and Flash-Lite only, so check_model refuses anything else. Default gemini-3.1-flash-lite: on
# 2026-10-05 it answered every eval question (median 2.5 s) while gemini-2.5-flash returned 503 "high demand" on a
# third of the calls (median 15 s) and then hit its free daily request quota. Each model has its own daily quota,
# reset at midnight Pacific (16:00 KST). The key is read like
# SEOUL_API_KEY (pipelines/common.py): environment, then repo/.env, then the nearest parent .env. It travels in a
# header, never in the URL, and is never logged or put in an error message.
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_gemini_lock = threading.Lock()
_gemini_last = [0.0]


def gemini_key() -> str | None:
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key
    for d in [REPO, *REPO.parents]:
        f = d / ".env"
        if f.is_file():
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("GEMINI_API_KEY="):
                    v = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if v:
                        return v
    return None


def _gemini_throttle() -> None:
    """Space real calls by GEMINI_MIN_INTERVAL_S (default 4 s, under the free tier's per-minute limit)."""
    gap = float(os.environ.get("GEMINI_MIN_INTERVAL_S", "4"))
    with _gemini_lock:
        wait = _gemini_last[0] + gap - time.time()
        if wait > 0:
            time.sleep(wait)
        _gemini_last[0] = time.time()


def _gemini_post(url: str, body: bytes, key: str, timeout: float) -> dict:
    import urllib.request
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _gemini(prompt: str, model: str) -> str:
    """One answer. Retries 429/5xx with backoff (2 s, then 4 s, capped at 8 s) inside GEMINI_TIMEOUT_S (default 15 s,
    so the chat's template fallback still answers inside the web's 30 s ask timeout); on the last failure of an
    overloaded model it tries GEMINI_FALLBACK_MODEL once (default gemini-2.5-flash, a separate daily quota). A quota
    used up for the day fails fast with the API message."""
    import urllib.error

    key = gemini_key()
    if not key:
        raise LLMBackendError("GEMINI_API_KEY is not set (environment, repo/.env or a parent .env)")
    body = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024,
                             "thinkingConfig": {"thinkingBudget": _env_int("GEMINI_THINKING_BUDGET", 0)}},
    }).encode("utf-8")
    deadline = time.time() + _env_int("GEMINI_TIMEOUT_S", 15)
    retries = _env_int("GEMINI_RETRIES", 1)
    fallback = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash")
    plan = [(model, a) for a in range(retries + 1)]
    if fallback and fallback != model:
        check_model("gemini", fallback)
        plan.append((fallback, 0))
    err = "no attempt"
    for i, (m, attempt) in enumerate(plan):
        last = i == len(plan) - 1
        _gemini_throttle()
        try:
            data = _gemini_post(GEMINI_URL.format(model=m), body, key, max(3.0, deadline - time.time()))
        except urllib.error.HTTPError as e:
            msg, quota = "", ""
            try:
                er = json.loads(e.read().decode("utf-8")).get("error", {})
                msg = er.get("message", "")[:160]
                quota = " ".join(v.get("quotaId", "") for d in er.get("details") or [] for v in d.get("violations") or [])
            except (ValueError, AttributeError):
                pass
            err = f"gemini HTTP {e.code} ({m}): {msg}" + (f" [{quota[:120]}]" if quota else "")
            quota_gone = e.code == 429 and ("perday" in quota.lower() or "per day" in msg.lower())
            delay = 0.0 if plan[min(i + 1, len(plan) - 1)][0] != m else min(8.0, 2.0 * (2 ** attempt))
            if e.code not in (429, 500, 503) or quota_gone or last or time.time() + delay > deadline:
                raise LLMBackendError(err) from None
            time.sleep(delay)
            continue
        except (urllib.error.URLError, TimeoutError) as e:
            err = f"gemini unreachable ({m}): {type(e).__name__}"
            if last or time.time() + 2 > deadline:
                raise LLMBackendError(err) from None
            time.sleep(2.0)
            continue
        cands = data.get("candidates") or []
        parts = ((cands[0].get("content") or {}).get("parts") or []) if cands else []
        out = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
        if out:
            return out
        reason = (cands[0].get("finishReason") if cands else None) or (data.get("promptFeedback") or {}).get("blockReason")
        raise LLMBackendError(f"gemini returned no text ({reason or 'empty'})")
    raise LLMBackendError(err)


_BACKEND_FN = {"mock": _mock, "claude_cli": _claude_cli, "gemini": _gemini}
