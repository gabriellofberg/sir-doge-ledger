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
  echo "Serving on http://127.0.0.1:${BACKEND_PORT}/?token=${TOKEN}"
  exec uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port "$BACKEND_PORT"
fi

echo "Backend  http://127.0.0.1:${BACKEND_PORT}/api/health"
echo "Frontend http://127.0.0.1:${FRONTEND_PORT}/?token=${TOKEN}"
echo "Open the frontend URL above to authenticate this browser session."

uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port "$BACKEND_PORT" --reload &
BACKEND_PID=$!
cd frontend && npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT"
