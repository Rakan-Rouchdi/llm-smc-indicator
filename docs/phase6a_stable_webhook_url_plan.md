# Phase 6A Stable Webhook URL Plan

Date: 2026-07-30

## Recommendation

Replace the current TryCloudflare quick tunnel with a remotely managed
Cloudflare named tunnel and a dedicated hostname such as:

```text
https://smc-webhook.<owned-domain>
```

This is the smallest infrastructure change because FastAPI, SQLite, the live
OpenAI provider, deterministic validation, and the dashboard can continue
running on this Mac.

No tunnel, DNS record, credential, permanent config, or TradingView alert was
created or changed during Phase 6A.

## Why Quick Tunnels Break

`cloudflared tunnel --url http://localhost:8003` creates a random
`trycloudflare.com` hostname tied to that quick-tunnel session. Cloudflare
documents quick tunnels as development/testing infrastructure with no uptime
SLA. A restart can assign a different hostname, leaving TradingView configured
with a dead domain.

A named tunnel is a persistent Cloudflare object with a stable UUID. A DNS
hostname points to that tunnel, while one or more local `cloudflared`
connectors can stop and restart without changing the public hostname.

References:

- <https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/>
- <https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/routing-to-tunnel/>

## Machine Readiness

Named tunnels are technically supported on this machine:

- `cloudflared` is installed at `/opt/homebrew/bin/cloudflared`.
- Installed version: `2026.6.1`.
- The current quick tunnel proves DNS, outbound network, and Cloudflare edge
  connectivity.
- The binary supports login, create, route, run, token, readiness, and
  macOS launch-agent installation commands.

Named-tunnel account state is not configured yet:

- no `cert.pem` account certificate
- no tunnel credential JSON
- no named-tunnel YAML config
- no tunnel token in the current environment
- `cloudflared tunnel list` cannot authenticate because the origin certificate
  is absent

This is an account/configuration gap, not a machine capability problem.

## Cloudflare and Domain Requirements

The recommended remotely managed setup needs:

1. A Cloudflare account with Zero Trust enabled.
2. A domain owned by the operator.
3. A DNS zone for that domain in Cloudflare. Full Cloudflare DNS setup is the
   simplest option.
4. A remotely managed tunnel created in the Cloudflare dashboard.
5. A published application hostname, for example
   `smc-webhook.<owned-domain>`, routed to `http://localhost:8003`.
6. A tunnel token installed securely on this Mac.

A paid Cloudflare Access plan is not required merely to publish an HTTP
application. A custom domain is required for the practical stable public
hostname in this design. The tunnel's `<UUID>.cfargotunnel.com` address is the
DNS target, not the TradingView-facing application hostname.

If no domain is available, continue using the quick tunnel temporarily or
choose a managed host such as Render. A quick tunnel cannot be converted into
a stable hostname.

## Proposed Cloudflare Setup

Use the Cloudflare dashboard for a remotely managed tunnel:

1. Open **Networking > Tunnels** in Cloudflare Zero Trust.
2. Create one tunnel named `llm-smc-indicator`.
3. Add one published application route:
   - Hostname: `smc-webhook.<owned-domain>`
   - Service type: HTTP
   - Service URL: `http://localhost:8003`
4. Store the generated connector token outside this repository in a
   permission-restricted file.
5. Start it with:

   ```bash
   export CLOUDFLARED_TOKEN_FILE="$HOME/.cloudflared/llm-smc-indicator.token"
   scripts/start_cloudflare_named_tunnel.sh
   ```

The helper also supports `TUNNEL_TOKEN` for a session-only environment value,
or a locally managed `config.yml`. It deliberately refuses to create a tunnel,
DNS record, token, or config.

For a locally managed alternative, `cloudflared tunnel login` creates an
account-wide `cert.pem`, after which `cloudflared tunnel create`, `route dns`,
and a YAML ingress config can be used. The remotely managed method is
preferred because the connector only needs a tunnel-scoped token rather than
an account-wide management certificate.

Cloudflare credential scopes are documented here:

- <https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/local-management/tunnel-permissions/>

## Local Backend Operation

FastAPI remains bound to loopback:

```bash
export MVP_PORT=8003
scripts/start_backend.sh
```

The named connector forwards the stable hostname to
`http://localhost:8003`. The Mac, backend, Internet connection, and
`cloudflared` connector still need to remain online. The stable hostname
removes URL churn; it does not make a powered-off Mac available.

After configuration:

```bash
export MVP_PUBLIC_BASE_URL="https://smc-webhook.<owned-domain>"
scripts/check_live_mvp_health.sh
```

The health helper prints only endpoint status codes, not webhook secrets.

## TradingView Cutover

After the named tunnel passes local sample and public health tests, update the
existing alert in place:

```text
https://smc-webhook.<owned-domain>/webhooks/tradingview?secret=<redacted>
```

Keep:

- Alert ID `5262922741` if TradingView preserves it during editing
- Condition: `SMC LLM Candidate Detector -> Any alert() function call`
- Message: script-generated `alert()` payload
- JSON payload input: enabled
- Test webhook input: disabled

List alerts before and after the edit and require exactly one matching active
alert. This cutover requires separate explicit approval.

## Secret Handling

- Keep `OPENAI_API_KEY` and `WEBHOOK_SECRET` only in the gitignored
  `backend/.env` or a future secret manager.
- Never put secrets in Pine, source, tests, documentation, screenshots, or
  Git.
- Treat the Cloudflare connector token as a secret. Store it outside the repo,
  restrict file permissions to the current user, and do not pass it as a
  visible command-line argument.
- Rotate `WEBHOOK_SECRET` during the approved cutover and update the backend
  and the one existing TradingView alert as a matched pair.
- Keep Cloudflare logging below debug because debug logging can include request
  paths and headers.

The webhook endpoint must remain reachable by TradingView, so an interactive
Cloudflare Access login cannot be placed in front of it. Use the application
secret, schema validation, rate limiting/WAF controls, and monitoring. The
dashboard should eventually use separate authentication or remain local-only.

## Cutover Verification

Before changing TradingView:

1. Confirm local `/health` and `/dashboard` return HTTP 200.
2. Start the named tunnel.
3. Confirm stable public `/health` and `/dashboard` return HTTP 200.
4. Send the sample Pine payload through the stable public webhook URL.
5. Confirm SQLite and `/decisions/latest` update.
6. Edit the existing TradingView alert in place.
7. Confirm exactly one active alert remains.
8. Stop the quick tunnel only after the stable path is verified.

## Rollback

If the named tunnel fails:

1. Leave or restart FastAPI on port 8003.
2. Run `scripts/start_cloudflare_tunnel.sh`.
3. Verify the new quick-tunnel public health endpoint.
4. Update the existing TradingView alert in place with the temporary hostname
   and matching secret.
5. Confirm exactly one active alert.

Do not run both URLs indefinitely or create a second TradingView alert.
Rollback restores the tested Phase 5D flow but also restores hostname churn.
