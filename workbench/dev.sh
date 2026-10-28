#!/usr/bin/env bash
# Sobe a API (uvicorn, porta 8000) e o front (Vite, porta 5173, /api proxied). Rodar a partir de qualquer lugar.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

API_PID=""
WEB_PID=""
LOG_PID=""
API_LOG=""
cleanup() {
  [[ -n "$LOG_PID" ]] && kill "$LOG_PID" 2>/dev/null || true
  [[ -n "$WEB_PID" ]] && kill "$WEB_PID" 2>/dev/null || true
  [[ -n "$API_PID" ]] && kill "$API_PID" 2>/dev/null || true
  [[ -n "$API_LOG" ]] && rm -f "$API_LOG"
}
trap cleanup EXIT INT TERM

case "${1:-}" in
  "") API_APP="workbench.api.app:app" ;;
  --stress) API_APP="workbench.web.scripts.fixture_api:app" ;;
  *) echo "Usage: bash workbench/dev.sh [--stress]" >&2; exit 2 ;;
esac

API_LOG="$(mktemp "${TMPDIR:-/tmp}/qc-workbench-api.XXXXXX")"
.venv/bin/uvicorn "$API_APP" --host 127.0.0.1 --port 8000 >"$API_LOG" 2>&1 &
API_PID=$!

# Só este processo pode autorizar o proxy: uma API antiga na porta não conta como pronta.
API_READY=""
for attempt in {1..150}; do
  if ! kill -0 "$API_PID" 2>/dev/null; then
    cat "$API_LOG" >&2
    exit 1
  fi
  if grep -q 'Uvicorn running on http://127.0.0.1:8000' "$API_LOG"; then
    API_READY=1
    break
  fi
  sleep 0.1
done
if [[ -z "$API_READY" ]]; then
  cat "$API_LOG" >&2
  echo "API startup timed out; frontend was not started." >&2
  exit 1
fi
tail -n +1 -f "$API_LOG" &
LOG_PID=$!

npm --prefix workbench/web run dev -- --strictPort &
WEB_PID=$!

wait "$WEB_PID"
