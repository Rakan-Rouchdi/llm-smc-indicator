#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${MVP_PORT:-8003}"
URL="${MVP_WEBHOOK_URL:-http://127.0.0.1:$PORT/webhooks/tradingview}"
PAYLOAD="${MVP_SAMPLE_PAYLOAD:-$PROJECT_ROOT/examples/pine_alert_payload_example.json}"

if [[ -z "${WEBHOOK_SECRET:-}" ]]; then
  echo "WEBHOOK_SECRET must match the running backend for this local test." >&2
  exit 1
fi

exec "$PROJECT_ROOT/backend/.venv/bin/python" \
  "$PROJECT_ROOT/backend/scripts/send_sample_webhook.py" \
  --url "$URL" \
  --secret "$WEBHOOK_SECRET" \
  --payload "$PAYLOAD"
