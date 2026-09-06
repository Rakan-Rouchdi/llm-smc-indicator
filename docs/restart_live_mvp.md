# Restart the Live MVP

The primary MVP path now runs on Render with Neon PostgreSQL. TradingView alert
`5262922741` points to the stable Render webhook, and UptimeRobot monitors the
public health endpoint every five minutes. Render selects the live OpenAI
provider through environment variables while retaining the deterministic mock
fallback. News and Telegram providers remain mocked.

## Hosted MVP (Primary)

Normal operation does not require the Mac backend or Cloudflare quick tunnel.
Check these services after a deployment or incident:

1. Render reports the web service as live.
2. Public `/health` returns HTTP 200.
3. UptimeRobot monitor `803927270` reports `Up`.
4. The dashboard prompts for Basic Auth and loads with valid credentials.
5. TradingView lists exactly one active SMC webhook alert, ID `5262922741`.
6. `/decisions/latest` shows the most recently processed decision.

The hosted webhook format is:

```text
https://<render-service>.onrender.com/webhooks/tradingview?secret=<redacted>
```

Render environment variables and the TradingView URL must use the same webhook
secret. Rotate both together and never record the value in source control.

## Local Fallback

The remaining steps restore the local FastAPI, SQLite, and Cloudflare
quick-tunnel path only when the hosted deployment is unavailable.

## Prerequisites

From the project root:

```bash
cd ~/Trading/llm-smc-indicator
test -x backend/.venv/bin/uvicorn
command -v cloudflared
```

If the virtual environment is missing:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -e 'backend[dev]'
```

## 1. Configure the Local Session

Use the same webhook secret in the backend and TradingView alert. Generate a
fresh secret without committing it:

```bash
export WEBHOOK_SECRET="$(openssl rand -hex 32)"
export MVP_PORT=8003
```

The helpers never print the secret. Do not add it to Pine, source files, docs,
screenshots, or shell scripts. A gitignored `backend/.env` can be used instead;
keep `LLM_PROVIDER=mock` unless following the controlled OpenAI procedure.

## 2. Start the Backend

In terminal one:

```bash
scripts/start_backend.sh
```

The helper launches from the project root and explicitly uses
`~/Trading/llm-smc-indicator/smc_llm.db`. This avoids accidentally creating a
second SQLite database under `backend/`.

Verify it:

```bash
scripts/check_backend_health.sh
open http://127.0.0.1:8003/dashboard
scripts/check_latest_decision.sh
backend/.venv/bin/python backend/scripts/check_mvp_status.py
```

## 3. Start the Quick Tunnel

In terminal two:

```bash
export MVP_PORT=8003
scripts/start_cloudflare_tunnel.sh
```

Copy the generated HTTPS hostname privately. A quick tunnel is tied to the
running `cloudflared` process and receives a random `trycloudflare.com`
hostname. Stopping or restarting it invalidates the old hostname.

Verify the public routes without placing the full URL in documentation:

```bash
curl --fail https://<active-host>/health
open https://<active-host>/dashboard
```

## 4. Switch the TradingView Alert to the Local Fallback

The existing alert must point to:

```text
https://<active-host>/webhooks/tradingview?secret=<current-secret>
```

Edit the existing alert named `SMC LLM Candidate Detector webhook`. Keep:

- Condition: `SMC LLM Candidate Detector -> Any alert() function call`
- Message: script-generated `alert()` message; leave the message field empty
- Webhook: enabled
- `Enable alert() JSON payloads`: enabled
- `Enable test webhook alert`: disabled except during an approved delivery test

Do not create another alert. Check the alert list first and edit alert
`5262922741` while it exists. If TradingView cannot edit the webhook URL
in-place, delete the stale alert before creating one replacement, then verify
that exactly one matching active alert remains.

## 5. Local Sample Test

This sends `examples/pine_alert_payload_example.json` to the local backend:

```bash
scripts/send_sample_webhook.sh
```

The sender refreshes `bar_time` and appends a unique suffix to `setup_id`, so
the checked-in sample can be submitted repeatedly. Pass `--preserve-payload`
directly to `backend/scripts/send_sample_webhook.py` only when testing the exact
file contents.

Then run:

```bash
scripts/check_latest_decision.sh
backend/.venv/bin/python backend/scripts/check_mvp_status.py
```

## Shutdown and Recovery

Stop FastAPI or `cloudflared` with `Ctrl-C` in their terminals. If only FastAPI
restarts with the same port and secret, the alert URL remains valid. If
`cloudflared` restarts, its quick-tunnel hostname changes and the existing
TradingView alert must be refreshed.

Never run two tunnel processes for the same alert during recovery. Confirm the
backend, tunnel, and current alert URL as one matched set.

After Render recovers, validate its health and edit the same alert back to the
stable Render URL. Never create a second webhook alert during failover.
