#!/usr/bin/env bash
# Start API + web headless (scripts/dev.sh), run the Playwright checks (v1 game + chat at #/v1, v2 free season and
# game_v2 free, the welcome tour, the no-WebGL fallback, v2 guided and game_v2 guided with the API down on GUIDED_PORT, default WEB_PORT+1), stop everything.
# Never opens a browser window. Usage: [API_PORT=8100 WEB_PORT=5273] scripts/e2e.sh [screenshot_dir]
# Defaults 8000/5173; pick other ports when a demo is already serving those (this script only stops what it started).
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"
LOG="$(mktemp -t e2e-dev.XXXXXX)"
for p in "$API_PORT" "$WEB_PORT"; do
  if lsof -nP -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "port $p is busy; set API_PORT/WEB_PORT to free ports (this script never stops other servers)" >&2; exit 2
  fi
done
API_PORT="$API_PORT" WEB_PORT="$WEB_PORT" LLM_BACKEND=mock scripts/dev.sh --no-load >"$LOG" 2>&1 &
DEV=$!
listening() { lsof -nP -iTCP:"$API_PORT" -iTCP:"$WEB_PORT" -sTCP:LISTEN >/dev/null 2>&1; }
stop() {
  kill -TERM "$DEV" 2>/dev/null || true
  for _ in $(seq 1 20); do listening || break; sleep 1; done
  if listening; then echo "WARNING: a server is still listening on $API_PORT or $WEB_PORT" >&2; fi
  rm -f "$LOG"
}
trap stop EXIT
for _ in $(seq 1 90); do
  curl -sf "http://127.0.0.1:$API_PORT/health" >/dev/null && curl -sf -o /dev/null "http://127.0.0.1:$WEB_PORT/" && break
  sleep 1
done
curl -sf "http://127.0.0.1:$API_PORT/health" >/dev/null || { echo "API did not start"; tail -20 "$LOG"; exit 1; }
RC=0
run() {  # name, command...: exit 3 from a check means "UI for it not built yet" and is reported as SKIP
  local name="$1"; shift
  "$@"; local rc=$?
  if [ $rc -eq 3 ]; then echo "SKIP $name"; elif [ $rc -ne 0 ]; then echo "FAIL $name"; RC=1; else echo "PASS $name"; fi
}
SHOTS="${1:-}"
run "v1 game + owner chat" env E2E_API_BASE="http://127.0.0.1:$API_PORT" node tests/e2e/game_chat.mjs "http://127.0.0.1:$WEB_PORT/" "$SHOTS"
run "v2 free season (contract)" node tests/e2e/v2_season.mjs free "http://127.0.0.1:$WEB_PORT/" "http://127.0.0.1:$API_PORT" "$SHOTS"
run "v2 game free (lose, win, compare)" node tests/e2e/game_v2.mjs "http://127.0.0.1:$WEB_PORT/" "$SHOTS" free
run "v2 welcome tour (skip, replay, complete free + guided)" node tests/e2e/tour.mjs "http://127.0.0.1:$WEB_PORT/" "$SHOTS"
run "v2 without WebGL (fallback note, tour, a free month)" node tests/e2e/no_webgl.mjs "http://127.0.0.1:$WEB_PORT/" "$SHOTS"

# guided mode with the API down: a second web server whose API base points at a closed port
GUIDED_PORT="${GUIDED_PORT:-$((WEB_PORT + 1))}"
if lsof -nP -iTCP:"$GUIDED_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "SKIP v2 guided (port $GUIDED_PORT busy; set GUIDED_PORT)"
else
  (cd web && VITE_API_BASE="http://127.0.0.1:9" BROWSER=none exec npx vite --host 127.0.0.1 --port "$GUIDED_PORT" --strictPort) >/dev/null 2>&1 &
  GPID=$!
  for _ in $(seq 1 30); do curl -sf -o /dev/null "http://127.0.0.1:$GUIDED_PORT/" && break; sleep 1; done
  run "v2 guided (API down, contract)" node tests/e2e/v2_season.mjs guided "http://127.0.0.1:$GUIDED_PORT/" "$SHOTS"
  run "v2 game guided (API down, full story)" node tests/e2e/game_v2.mjs "http://127.0.0.1:$GUIDED_PORT/" "$SHOTS" guided
  pkill -TERM -P "$GPID" 2>/dev/null; kill "$GPID" 2>/dev/null
  for _ in $(seq 1 10); do lsof -nP -iTCP:"$GUIDED_PORT" -sTCP:LISTEN >/dev/null 2>&1 || break; sleep 1; done
fi
exit $RC
