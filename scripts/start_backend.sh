#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${MVP_PORT:-8003}"
ENV_FILE="${MVP_ENV_FILE:-$PROJECT_ROOT/backend/.env}"
VENV_UVICORN="$PROJECT_ROOT/backend/.venv/bin/uvicorn"

if [[ ! -x "$VENV_UVICORN" ]]; then
  echo "Missing backend virtual environment. Follow docs/restart_live_mvp.md." >&2
  exit 1
fi

if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT is already in use. Set MVP_PORT to another port or stop that process." >&2
  exit 1
fi

if [[ -z "${WEBHOOK_SECRET:-}" && ! -f "$ENV_FILE" ]]; then
  echo "Set WEBHOOK_SECRET or create the gitignored backend/.env file first." >&2
  exit 1
fi

export APP_PORT="$PORT"
export DATABASE_URL="${DATABASE_URL:-sqlite:///$PROJECT_ROOT/smc_llm.db}"
export PYTHONPATH="$PROJECT_ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"

echo "Starting SMC LLM MVP on http://127.0.0.1:$PORT"
if [[ "$DATABASE_URL" == sqlite:///* ]]; then
  echo "SQLite: ${DATABASE_URL#sqlite:///}"
else
  echo "Database: configured by DATABASE_URL"
fi

if [[ -f "$ENV_FILE" ]]; then
  exec "$VENV_UVICORN" app.main:app \
    --host 127.0.0.1 \
    --port "$PORT" \
    --env-file "$ENV_FILE"
else
  exec "$VENV_UVICORN" app.main:app \
    --host 127.0.0.1 \
    --port "$PORT"
fi
