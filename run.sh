#!/usr/bin/env bash
# SirDoge Ledger — local start script
#   ./run.sh        Development: backend + Vite (open auth)
#   ./run.sh prod   Build frontend, single port (password auth)

set -euo pipefail
cd "$(dirname "$0")"

MODE="${1:-dev}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

echo "======================================================"
echo " SirDoge Ledger"
echo " Local finance & life admin — fancy Doge, no cloud."
echo "======================================================"

if [ ! -d .venv ]; then
  echo "Creating Python venv..."
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "Installing backend deps..."
pip install -q -r backend/requirements-dev.txt

if [ ! -d frontend/node_modules ]; then
  echo "Installing frontend deps..."
  (cd frontend && npm install)
fi

export PYTHONPATH="${PWD}/backend${PYTHONPATH:+:$PYTHONPATH}"

if [ "$MODE" = "prod" ]; then
  unset SIR_DOGE_DEV
  export SIR_DOGE_PROD=1
  echo "Building frontend..."
  (cd frontend && npm run build)
  echo "Serving on http://127.0.0.1:${BACKEND_PORT}/"
  echo "Set a password on first visit. Recovery key saved to ~/.local/share/sir-doge-ledger/recovery-hint.txt"
  exec uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port "$BACKEND_PORT"
fi

export SIR_DOGE_DEV=1
echo "Dev mode: no password required (SIR_DOGE_DEV=1)"
echo "Backend  http://127.0.0.1:${BACKEND_PORT}/api/health"
echo "Frontend http://127.0.0.1:${FRONTEND_PORT}/"

open_browser() {
  local url="$1"
  python -c "
import threading, time, webbrowser
def open_url():
    time.sleep(1)
    webbrowser.open('$url')
threading.Thread(target=open_url, daemon=True).start()
" &
}

wait_for_backend() {
  local url="http://127.0.0.1:${BACKEND_PORT}/api/health"
  echo "Waiting for backend..."
  for _ in $(seq 1 60); do
    if curl -sf "$url" >/dev/null 2>&1; then
      echo "Backend ready."
      return 0
    fi
    sleep 0.25
  done
  echo "Backend did not start on ${BACKEND_PORT} — check errors above." >&2
  return 1
}

cleanup() {
  if [ -n "${BACKEND_PID:-}" ]; then
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port "$BACKEND_PORT" --reload &
BACKEND_PID=$!
wait_for_backend
open_browser "http://127.0.0.1:${FRONTEND_PORT}/"
cd frontend && npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT"
