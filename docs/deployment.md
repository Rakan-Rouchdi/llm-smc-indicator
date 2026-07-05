# Deployment Notes

Phase 1 is local-only.

Do not expose the dashboard or webhook publicly without authentication, TLS, secret rotation, and deployment hardening.

Use SQLite for local MVP work. A future deployment can migrate the SQLAlchemy models to Postgres.
