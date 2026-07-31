# Stable Deployment Options

The current Cloudflare quick tunnel is suitable for proof-of-delivery testing,
but its random hostname changes whenever `cloudflared` restarts. The next
operational improvement should remove that URL churn before enabling a live LLM
provider.

## Comparison

| Option | Operational fit | Persistence | Main tradeoff |
| --- | --- | --- | --- |
| Cloudflare named tunnel | Smallest change; keeps FastAPI and SQLite on the Mac while assigning a stable hostname | Existing local SQLite remains unchanged | The Mac, backend, network, and tunnel service must stay online |
| Render | Simple managed FastAPI web service with TLS, health checks, and Git-based deploys | Use managed Postgres or a paid persistent disk; default filesystem is ephemeral | Requires application deployment and database migration/configuration |
| Railway | Straightforward FastAPI deployment from GitHub or CLI with a generated public domain | Add Railway Postgres or a volume | Introduces hosted-service configuration and usage-based operations |
| Fly.io | Good control over regions, Machines, health checks, and Docker deployment | SQLite requires a Fly Volume; volumes are local to a Machine | More infrastructure configuration than Render or Railway |
| VPS | Maximum control and a stable IP/domain; can run FastAPI, a reverse proxy, and SQLite/Postgres | Fully controlled disk and backup policy | You own patching, TLS, firewalling, monitoring, backups, and process supervision |

## Recommendation

Use a **Cloudflare named tunnel** next. It is the smallest stable step for this
MVP because it preserves the already validated local backend and SQLite flow
while replacing the expiring quick-tunnel hostname with a stable hostname.
Run both FastAPI and `cloudflared` as supervised macOS services, add uptime
monitoring, and rotate the webhook secret during the cutover.

The machine-readiness audit, account/domain prerequisites, guarded helper
scripts, cutover procedure, and rollback plan are documented in
`docs/phase6a_stable_webhook_url_plan.md`.

This recommendation assumes the Mac can remain online. If unattended uptime is
required independently of the Mac, choose **Render with managed Postgres** as
the next simplest hosted architecture. Do not rely on Render's default
filesystem for SQLite because it is ephemeral.

## Provider Notes

- Cloudflare documents that quick-tunnel hostnames change on restart, while
  named tunnels bind a stable hostname. Cloudflare recommends remotely managed
  tunnels for most use cases:
  <https://developers.cloudflare.com/tunnel/advanced/local-management/>
- Render provides a FastAPI deployment path and HTTPS web services. Persistent
  disks are paid and single-service; Render recommends a managed datastore when
  suitable:
  <https://render.com/docs/deploy-fastapi> and
  <https://render.com/docs/disks>
- Railway supports FastAPI deployment through GitHub, CLI, or Docker and can
  generate a public service domain:
  <https://docs.railway.com/guides/fastapi>
- Fly.io supports FastAPI deployments and persistent volumes. SQLite must live
  on a mounted volume, and volumes are tied to Machines:
  <https://fly.io/docs/python/> and
  <https://fly.io/docs/volumes/overview/>

## Before Any Hosted Cutover

- Keep `LLM_PROVIDER=mock` for the infrastructure migration.
- Move secrets into the provider's secret manager.
- Replace SQLite with managed Postgres for multi-instance hosting.
- Add proper migrations, rate limiting, authenticated dashboard access, log
  retention, backups, and uptime alerts.
- Test the public webhook with a sample payload before editing TradingView.
- Edit or replace the existing alert so exactly one active webhook alert
  remains.
