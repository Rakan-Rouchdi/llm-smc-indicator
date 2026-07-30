#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${MVP_BASE_URL:-http://127.0.0.1:${MVP_PORT:-8003}}"
curl --fail --silent --show-error "$BASE_URL/decisions/latest" | python3 -m json.tool
