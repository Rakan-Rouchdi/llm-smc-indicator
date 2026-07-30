#!/usr/bin/env bash
set -euo pipefail

PORT="${MVP_PORT:-8003}"
BASE_URL="http://127.0.0.1:$PORT"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared is not installed. Install it explicitly before using this helper." >&2
  exit 1
fi

curl --fail --silent --show-error "$BASE_URL/health" >/dev/null
echo "Starting a temporary Cloudflare quick tunnel for $BASE_URL"
echo "Its public hostname will change whenever this process restarts."
exec cloudflared tunnel --url "$BASE_URL"
