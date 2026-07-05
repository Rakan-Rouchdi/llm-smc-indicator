# Phase 4C Live TradingView Alert

Date: 2026-07-06 local time

Scope: create one real TradingView alert for the existing `SMC LLM Candidate Detector` indicator, routed through the public Cloudflare Tunnel webhook path into the local FastAPI backend. Mock LLM, mock news, and mock Telegram context remained active.

## Runtime Setup

- Backend port used: `8003`
- Backend bind address: `127.0.0.1:8003`
- Temporary secret handling: generated at runtime, used for the running backend process, and removed from `/tmp` after alert creation
- Tunnel tool used: `cloudflared`
- Tunnel type: Cloudflare quick tunnel
- Public URL, redacted: `https://opera-breed-...-art.trycloudflare.com`
- Public health check: passed
- Public dashboard check: passed

## Alert Configuration

- Requested alert name: `SMC LLM Candidate Detector webhook`
- TradingView visible alert label: `SMC LLM Candidate Detector (, 3, 3, 2, 2, 1...)`
- Alert condition: `SMC LLM Candidate Detector -> Any alert() function call`
- Symbol/timeframe at creation: `CME_MINI_DL:NQ1!`, `4h`
- Webhook: enabled
- Webhook URL format:

```text
https://opera-breed-...-art.trycloudflare.com/webhooks/tradingview?secret=<REDACTED>
```

- Message behavior: script-generated Pine `alert()` message is used. Static JSON was not pasted into the TradingView alert message field.

TradingView's current alert dialog did not expose a separate editable alert-name field without changing the message row. The alert was left with the script-generated message behavior intact so the Pine runtime JSON payload is preserved.

## TradingView Validation

- Indicator attached: yes
- Indicator input `Enable alert() JSON payloads`: confirmed enabled
- Existing alerts before creation: `0`
- Existing alerts after creation: `1`
- Alert id: `5079887204`
- Alert type: `indicator`
- Internal condition type: `pine_alert`
- Internal resolution: `240`
- Active: yes
- Last fired: none at validation time
- Expiration: `2026-08-05T22:13:43Z`

Evidence screenshots:

```text
/Users/rakanrouchdi/tradingview-mcp-jackson/screenshots/phase4c_retry_before_create.png
/Users/rakanrouchdi/tradingview-mcp-jackson/screenshots/phase4c_retry_after_create.png
/Users/rakanrouchdi/tradingview-mcp-jackson/screenshots/phase4c_retry_alerts_panel.png
```

## Webhook Receipt

- Real TradingView webhook received during validation window: no
- Reason: no natural Pine alert fired during the wait window
- `GET /decisions/latest`: `404`, `{"detail":"No decisions recorded"}`
- Local dashboard status: passed
- Public dashboard status: passed

The alert is armed. A backend decision should appear when the Pine indicator naturally emits an `alert()` payload.

## Basic-Plan Blocker Resolution

The previous Phase 4C attempt was blocked because the TradingView Basic plan did not allow enabling `Webhook URL`. After upgrading to Essential and enabling 2FA, the webhook checkbox was enabled successfully and the alert was created.

## Safety Notes

- Mock LLM was used.
- Mock news context was used.
- Mock Telegram context was used.
- No OpenAI credentials were read or used.
- No trades were placed.
- No broker connection was made.
- No replay tools were used.
- Exactly one TradingView alert was created.
- No duplicate alerts were created.

## Operational Note

The active TradingView alert points at the temporary Cloudflare quick tunnel URL above. Keep the local FastAPI backend and `cloudflared` process running for the alert to deliver webhooks. If either process stops, recreate the tunnel and update the TradingView alert webhook URL.
