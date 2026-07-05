# Codex Agent Build Brief — SMC LLM Trade Setup Validator MVP

Build the MVP repository described in `PRD.md`.

## Deliverables

1. Pine Script indicator: `pine/smc_llm_candidate_detector.pine`
2. FastAPI backend under `backend/app/`
3. Pydantic schemas matching `schemas/*.json`
4. SQLite persistence with SQLAlchemy
5. Authenticated TradingView webhook endpoint
6. LLM prompt and structured-output wrapper
7. Deterministic decision validator
8. Manual news/headline/Telegram-summary context endpoints
9. Minimal dashboard
10. Outcome logging endpoint and form
11. Tests with pytest
12. README, AGENTS.md, API docs, deployment docs, Pine manual QA docs

## Hard Constraints

- No broker execution or auto-trading.
- No traditional ML training in MVP.
- No claims of guaranteed profitability.
- Pine Script emits webhook alerts and shows provisional setup data only.
- Final LLM decision appears in dashboard/notifications. Automatic round-trip plotting inside TradingView is out of scope for MVP.
- Use confirmed bars only.
- Webhook endpoint must ack quickly and process LLM asynchronously/in background.
- Do not commit secrets.

## Expected Local Commands

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest
uvicorn app.main:app --reload
```

## Done Criteria

- Tests pass.
- Backend starts.
- Example webhook cURL stores a setup.
- Mock LLM decision appears on dashboard.
- Pine file is ready to paste into TradingView and compile.
