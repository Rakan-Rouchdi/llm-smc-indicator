# Deployment Notes

Phase 3 is local-only.

Do not expose the dashboard or webhook publicly without authentication, TLS, secret rotation, request logging, rate limiting, and deployment hardening.

Current local defaults:

- SQLite database: `backend/smc_llm.db`
- Mock LLM provider: `LLM_PROVIDER=mock`
- Mock news adapter
- Mock Telegram adapter
- Webhook secret: `WEBHOOK_SECRET`

Use SQLite for local MVP work. A future deployment can migrate the SQLAlchemy models to Postgres.

Before a live deployment:

- Replace mock news and Telegram adapters with credentialed providers.
- Replace mock LLM routing with a live provider only after explicit configuration.
- Add database migrations instead of the lightweight local SQLite column migration helper.
- Put the FastAPI service behind TLS and a real auth boundary.
- Rotate webhook secrets and never expose them in TradingView screenshots or shared logs.
- Keep TradingView alerts disabled until the exact alert payload template is approved.
