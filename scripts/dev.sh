#!/usr/bin/env bash
# One-command local run without Docker (macOS / Linux / WSL).
#   scripts/dev.sh               set up .venv, load DB + RAG, start API :8000 and web :5173
#   API_PORT=8100 WEB_PORT=5273 scripts/dev.sh   other ports (e.g. while a demo holds 8000/5173)
#   scripts/dev.sh --no-web      API only
#   scripts/dev.sh --no-load     skip db.load / rag.ingest (fast restart)
# Ctrl-C stops both servers. Nothing opens a browser; visit http://localhost:5173 yourself.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
WEB=1; LOAD=1
for a in "$@"; do
  case "$a" in
    --no-web) WEB=0 ;;
    --no-load) LOAD=0 ;;
    -h|--help) sed -n '2,6p' "$0"; exit 0 ;;
    *) echo "unknown option $a" >&2; exit 2 ;;
  esac
done
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"
# the web app calls the API at VITE_API_BASE; the API allows the web origin in CORS_ORIGINS
export VITE_API_BASE="${VITE_API_BASE:-http://localhost:${API_PORT}}"
export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:${WEB_PORT},http://127.0.0.1:${WEB_PORT}}"
export LLM_BACKEND="${LLM_BACKEND:-mock}"
export BROWSER=none   # vite never opens a browser
# offline demo guard: once the e5 embedder is in the Hugging Face cache, never ask the Hub again (no Wi-Fi needed,
# no hang on a captive portal). First run, no cache: stay online so the model downloads. Set either var to override.
HF_CACHE="${HF_HUB_CACHE:-${HF_HOME:-$HOME/.cache/huggingface}/hub}"
if [ -z "${HF_HUB_OFFLINE:-}" ] && ls "$HF_CACHE"/models--intfloat--multilingual-e5-small/snapshots/*/config.json >/dev/null 2>&1; then
  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
fi

say() { printf '\033[1m[dev]\033[0m %s\n' "$*"; }

# 1. Python env
if [ ! -x .venv/bin/python ]; then
  if command -v uv >/dev/null 2>&1; then
    say "creating .venv with uv (Python 3.12)"; uv venv --python 3.12 .venv
  else
    PY=""
    for c in python3.12 python3.11 python3; do command -v "$c" >/dev/null 2>&1 && { PY="$c"; break; }; done
    [ -n "$PY" ] || { echo "no python3 found" >&2; exit 1; }
    say "creating .venv with $PY"; "$PY" -m venv .venv
  fi
fi
REQ_HASH="$(shasum -a 256 requirements.txt 2>/dev/null | cut -c1-16 || sha256sum requirements.txt | cut -c1-16)"
if [ "$(cat .venv/.req-hash 2>/dev/null || true)" != "$REQ_HASH" ]; then
  say "installing requirements (first run pulls torch for local embeddings)"
  if command -v uv >/dev/null 2>&1; then uv pip install --python .venv/bin/python -r requirements.txt
  else .venv/bin/python -m pip install -q --upgrade pip && .venv/bin/python -m pip install -q -r requirements.txt; fi
  echo "$REQ_HASH" > .venv/.req-hash
fi

# 2. Database + RAG (idempotent)
if [ "$LOAD" = 1 ]; then
  say "loading DB (${DATABASE_URL:-sqlite:///data/twin.db})"
  .venv/bin/python -m db.load
  say "embedding RAG corpus (${RAG_EMBEDDER:-e5})"
  .venv/bin/python -m rag.ingest
fi

# 3. Season preview cache: the first preview after a model change would otherwise spend ~1.5 min building it
if ! .venv/bin/python -m sim.warm --check >/dev/null 2>&1; then
  say "building the season preview cache (one time after a model change)"
  .venv/bin/python -m sim.warm
fi

# 4. Servers (each in its own process group, so stopping also stops npm's vite child)
set -m
PIDS=()
cleanup() {
  trap - EXIT INT TERM
  say "stopping"
  for p in "${PIDS[@]:-}"; do [ -n "$p" ] && { kill -- "-$p" 2>/dev/null || kill "$p" 2>/dev/null || true; }; done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

say "API  http://localhost:${API_PORT}/docs  (LLM_BACKEND=${LLM_BACKEND}, HF_HUB_OFFLINE=${HF_HUB_OFFLINE:-0})"
.venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port "$API_PORT" &
PIDS+=($!)

if [ "$WEB" = 1 ] && [ -f web/package.json ]; then
  if command -v npm >/dev/null 2>&1; then
    [ -d web/node_modules ] || { say "npm install (web)"; (cd web && npm install --no-fund --no-audit); }
    say "web  http://localhost:${WEB_PORT}"
    (cd web && exec npm run dev -- --host 127.0.0.1 --port "$WEB_PORT" --strictPort) &
    PIDS+=($!)
  else
    say "npm not found: skipping web (install Node.js 20+)"
  fi
fi
wait -n 2>/dev/null || wait
