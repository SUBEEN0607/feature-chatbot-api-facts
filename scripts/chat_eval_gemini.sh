#!/usr/bin/env bash
# Opt-in: score the owner chat on the Gemini free tier with tests/chat_eval/questions.yaml.
# One real call per question (the v2 owner chat, POST /persona/{season}/ask), spaced 11 s apart, each through
# agents/llm.py (cache, rate cap, Flash-only model check). Never part of `make test`.
# Needs GEMINI_API_KEY in the environment, repo/.env or a parent .env (never printed), and a loaded DB with the
# e5 index (`make load ingest`). Usage: scripts/chat_eval_gemini.sh [out.json] [persona|chat|both]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
OUT="${1:-data/cache/chat_eval_gemini.json}"
mkdir -p "$(dirname "$OUT")"
exec .venv/bin/python -m tests.chat_eval.run --backend gemini --path "${2:-persona}" --json "$OUT"
