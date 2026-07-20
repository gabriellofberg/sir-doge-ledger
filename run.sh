#!/usr/bin/env bash
# SirDoge Ledger — local start script
#   ./run.sh        Development: backend + Vite
#   ./run.sh prod   Build frontend, single port

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

# Always-on local API token (stricter than HomeSec dev mode)
TOKEN=$(python -c "from app.services.auth import ensure_token; print(ensure_token())")
TOKEN_HINT=$(python -c "from app.services.auth import token_hint; print(token_hint('$TOKEN'))")
TOKEN_FILE=$(python -c "from app.services.auth import TOKEN_FILE; print(TOKEN_FILE)")

open_browser() {
  local url="$1"
  python -c "
import threading, time, webbrowser
def open_url():
    time.sleep(2)
    webbrowser.open('$url')
threading.Thread(target=open_url, daemon=True).start()
" &
}

cleanup() {
  if [ -n "${BACKEND_PID:-}" ]; then
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if [ "$MODE" = "prod" ]; then
  export SIR_DOGE_PROD=1
  echo "Building frontend..."
  (cd frontend && npm run build)
  FRONTEND_URL="http://127.0.0.1:${BACKEND_PORT}/"
  echo "Serving on ${FRONTEND_URL}"
  echo "Token hint: ${TOKEN_HINT}  (full token: ${TOKEN_FILE})"
  echo "Opening browser to sign in…"
  open_browser "http://127.0.0.1:${BACKEND_PORT}/?token=${TOKEN}"
  exec uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port "$BACKEND_PORT"
fi

FRONTEND_URL="http://127.0.0.1:${FRONTEND_PORT}/"
echo "Backend  http://127.0.0.1:${BACKEND_PORT}/api/health"
echo "Frontend ${FRONTEND_URL}"
echo "Token hint: ${TOKEN_HINT}  (full token: ${TOKEN_FILE})"
echo "Opening browser to sign in…"

open_browser "http://127.0.0.1:${FRONTEND_PORT}/?token=${TOKEN}"

uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port "$BACKEND_PORT" --reload &
BACKEND_PID=$!
cd frontend && npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT"
