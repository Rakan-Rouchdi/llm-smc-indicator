# Session Resume Webhook Refresh

Date: 2026-07-30 local time

## Reason

The previous Cloudflare quick-tunnel domain expired while TradingView, the
backend, and `cloudflared` were stopped. TradingView's alert log confirmed that
the Pine alert fired, but delivery failed because the old domain no longer
resolved.

## Restored Runtime

- Backend: FastAPI on `127.0.0.1:8003`
- Backend health: passed locally and through the public tunnel
- Dashboard: passed locally and through the public tunnel
- Tunnel tool: `cloudflared`
- Tunnel type: Cloudflare quick tunnel
- New public URL, redacted:

```text
https://value-today-...-buildings.trycloudflare.com
```

- Webhook URL format:

```text
https://value-today-...-buildings.trycloudflare.com/webhooks/tradingview?secret=<REDACTED>
```

The webhook secret was freshly generated for this runtime session. It was not
written to the repository or documentation, and its temporary source file was
removed after the alert was created. The running backend retains the secret in
its process environment.

## TradingView Refresh

- TradingView MCP attachment: passed
- Chart state: `CME_MINI_DL:NQ1!`, `4h`
- `SMC LLM Candidate Detector` attached: yes
- `Enable alert() JSON payloads`: enabled (`in_28=true`)
- Old stale alert deleted: yes
- Old alert id: `5079887204`
- Fresh active alert count: `1`
- New alert id: `5262922741`
- Alert condition: `SMC LLM Candidate Detector -> Any alert() function call`
- Message behavior: Pine supplies the runtime `alert()` JSON; no static JSON was
  pasted into the alert message
- New alert active: yes
- New alert last fired during validation: none
- New alert expiration: `2026-08-30T16:19:27Z`

Evidence screenshot:

```text
/Users/rakanrouchdi/tradingview-mcp-jackson/screenshots/session_resume_fresh_alert_armed.png
```

## Backend Verification

- Natural TradingView webhook received during the brief monitoring window: no
- Stored setups after monitoring: `0`
- `GET /decisions/latest`: `404`, no decision recorded
- Dashboard status: healthy locally and publicly; no setup was expected because
  the replacement alert did not fire during the monitoring window

The alert is active and armed. The backend should create a setup and mock LLM
decision when the Pine indicator next emits a natural candidate alert.

## Safety

- Mock LLM, news, and Telegram providers remained active.
- No OpenAI credentials were read or used.
- No trades were placed.
- No broker connection was made.
- No replay tools were used.
- The stale alert was replaced; no duplicate alerts remain.

## Runtime Requirement

Keep the FastAPI backend and `cloudflared` processes running. Stopping either
process breaks delivery. Because this is a quick tunnel, any future tunnel
restart requires another TradingView webhook URL refresh.
