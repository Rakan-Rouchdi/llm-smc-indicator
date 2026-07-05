# SMC LLM Trade Setup Validator

Phase 1 scaffold for the LLM-powered Smart Money Concepts TradingView workflow.

The MVP is decision support only. It does not place trades, connect to brokers, or create TradingView alerts automatically.

## Phase 1 Contents

- Top-level PRD copy in `docs/PRD.md`
- JSON schemas in `schemas/`
- Example payloads in `examples/`
- FastAPI backend skeleton in `backend/app/`
- Pydantic models for TradingView setup alerts and LLM trade decisions
- SQLite database setup with SQLAlchemy models
- Deterministic validator for LLM outputs
- Mock LLM provider
- Initial pytest coverage for schemas and validator rules

## Run Backend Locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn app.main:app --reload
```

Health check:

```bash
curl http://localhost:8000/health
```

## Run Tests

```bash
cd backend
source .venv/bin/activate
pytest
```

## Environment

Copy `backend/.env.example` to `backend/.env` for local overrides. By default, the backend uses the mock LLM provider when no `OPENAI_API_KEY` is configured.

## TradingView

TradingView MCP, Pine compilation, chart validation, and alert configuration are not part of Phase 1. Alerts must not be created without explicit confirmation.
