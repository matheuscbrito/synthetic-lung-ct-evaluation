#!/usr/bin/env bash
# Sobe a API (uvicorn, porta 8000) e o front (Vite, porta 5173, /api proxied). Rodar a partir de qualquer lugar.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

API_PID=""
WEB_PID=""
cleanup() {
  [[ -n "$WEB_PID" ]] && kill "$WEB_PID" 2>/dev/null || true
  [[ -n "$API_PID" ]] && kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

.venv/bin/uvicorn workbench.api.app:app --port 8000 &
API_PID=$!

npm --prefix workbench/web run dev &
WEB_PID=$!

wait "$WEB_PID"
