#!/usr/bin/env bash
set -euo pipefail

PORT="${MVP_PORT:-8003}"
BASE_URL="http://127.0.0.1:$PORT"
CONFIG_FILE="${CLOUDFLARED_CONFIG_FILE:-$HOME/.cloudflared/config.yml}"
TUNNEL_NAME="${CLOUDFLARED_TUNNEL_NAME:-}"
TOKEN_FILE="${CLOUDFLARED_TOKEN_FILE:-}"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared is not installed." >&2
  exit 1
fi

curl --fail --silent --show-error "$BASE_URL/health" >/dev/null

if [[ -n "$TOKEN_FILE" ]]; then
  if [[ ! -r "$TOKEN_FILE" ]]; then
    echo "CLOUDFLARED_TOKEN_FILE is not readable." >&2
    exit 1
  fi
  TOKEN_MODE="$(stat -f '%Lp' "$TOKEN_FILE")"
  if (( (8#$TOKEN_MODE & 077) != 0 )); then
    echo "CLOUDFLARED_TOKEN_FILE must not be accessible by group or others." >&2
    exit 1
  fi
  echo "Starting the configured Cloudflare named tunnel for $BASE_URL"
  exec cloudflared tunnel run --token-file "$TOKEN_FILE"
fi

if [[ -n "${TUNNEL_TOKEN:-}" ]]; then
  echo "Starting the configured Cloudflare named tunnel for $BASE_URL"
  exec cloudflared tunnel run
fi

if [[ -f "$CONFIG_FILE" ]]; then
  echo "Starting the configured Cloudflare named tunnel for $BASE_URL"
  if [[ -n "$TUNNEL_NAME" ]]; then
    exec cloudflared tunnel --config "$CONFIG_FILE" run "$TUNNEL_NAME"
  fi
  exec cloudflared tunnel --config "$CONFIG_FILE" run
fi

cat >&2 <<'EOF'
No named tunnel configuration was found.

Complete the Cloudflare account, domain, tunnel, and published-hostname steps
in docs/phase6a_stable_webhook_url_plan.md first. Then configure one of:

  CLOUDFLARED_TOKEN_FILE=/secure/path/to/tunnel-token
  TUNNEL_TOKEN=<session-only token>
  CLOUDFLARED_CONFIG_FILE=~/.cloudflared/config.yml

This helper does not create tunnels, DNS records, credentials, or config files.
EOF
exit 1
