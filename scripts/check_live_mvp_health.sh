#!/usr/bin/env bash
set -euo pipefail

LOCAL_BASE_URL="${MVP_BASE_URL:-http://127.0.0.1:${MVP_PORT:-8003}}"
PUBLIC_BASE_URL="${MVP_PUBLIC_BASE_URL:-}"

check_endpoint() {
  local label="$1"
  local url="$2"
  local status

  status="$(curl --silent --show-error --output /dev/null \
    --write-out '%{http_code}' --max-time 15 "$url")"
  if [[ "$status" != "200" ]]; then
    echo "$label: FAIL (HTTP $status)" >&2
    return 1
  fi
  echo "$label: OK (HTTP 200)"
}

check_endpoint "Local backend health" "$LOCAL_BASE_URL/health"
check_endpoint "Local dashboard" "$LOCAL_BASE_URL/dashboard"

if pgrep -f 'cloudflared tunnel' >/dev/null 2>&1; then
  echo "Cloudflare tunnel process: RUNNING"
else
  echo "Cloudflare tunnel process: NOT RUNNING" >&2
  exit 1
fi

if [[ -z "$PUBLIC_BASE_URL" ]]; then
  echo "Public checks: SKIPPED (set MVP_PUBLIC_BASE_URL)"
  exit 0
fi

if [[ "$PUBLIC_BASE_URL" != https://* ]]; then
  echo "MVP_PUBLIC_BASE_URL must use HTTPS." >&2
  exit 1
fi

if [[ "$PUBLIC_BASE_URL" == *'?'* || "$PUBLIC_BASE_URL" == *'#'* ]]; then
  echo "MVP_PUBLIC_BASE_URL must not contain a query string or fragment." >&2
  exit 1
fi

PUBLIC_BASE_URL="${PUBLIC_BASE_URL%/}"
check_endpoint "Public backend health" "$PUBLIC_BASE_URL/health"
check_endpoint "Public dashboard" "$PUBLIC_BASE_URL/dashboard"
