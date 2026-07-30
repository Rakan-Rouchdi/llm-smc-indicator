# Live MVP Monitoring

Use this checklist after startup, after any tunnel restart, and when TradingView
reports a failed webhook.

## Automated Local Check

```bash
backend/.venv/bin/python backend/scripts/check_mvp_status.py
```

Success requires:

- `GET /health` returns HTTP `200`
- `GET /decisions/latest` returns HTTP `200`
- `GET /dashboard` returns HTTP `200`
- the configured SQLite database contains at least one setup and decision

## Runtime Checklist

- Backend process: `lsof -nP -iTCP:8003 -sTCP:LISTEN`
- Backend health: `scripts/check_backend_health.sh`
- Tunnel process: `pgrep -af 'cloudflared tunnel'`
- Public health: `curl --fail https://<active-host>/health`
- Dashboard: open `http://127.0.0.1:8003/dashboard`
- Latest decision: `scripts/check_latest_decision.sh`
- TradingView alert: exactly one active
  `SMC LLM Candidate Detector webhook` alert
- Alert condition: `Any alert() function call`
- Alert input: JSON payloads enabled; test webhook mode disabled
- Webhook URL: current tunnel hostname and current secret
- TradingView alert log: no domain lookup, timeout, HTTP `400`, or HTTP `401`
  errors
- FastAPI log: successful webhook requests return HTTP `200`

## SQLite Checks

The operational database is `smc_llm.db` in the project root.

```bash
sqlite3 smc_llm.db \
  "SELECT COUNT(*) AS setups FROM setup_alerts;
   SELECT COUNT(*) AS decisions FROM llm_decisions;"
```

Latest stored decision:

```bash
sqlite3 -header -column smc_llm.db \
  "SELECT setup_id, final_action, validator_status, confidence, created_at
   FROM llm_decisions
   ORDER BY created_at DESC, id DESC
   LIMIT 1;"
```

## Failure Triage

`Could not find this domain` means the quick-tunnel hostname is stale. Start a
new tunnel and update the existing TradingView alert.

HTTP `401` means the query secret and backend secret differ. Rotate them as one
pair without exposing either value.

HTTP `400` means the request reached FastAPI but failed JSON, schema, or
Pydantic validation. Inspect the backend validation response and Pine alert
payload. Do not weaken schema validation.

No new decision with HTTP `200` health usually means no alert fired, the alert
is paused, or its URL is stale. Compare TradingView's alert log time with the
FastAPI access log and the latest SQLite `received_at`.
