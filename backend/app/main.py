import secrets as stdlib_secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.config import Settings, get_settings
from app.auth import require_dashboard_auth
from app.dashboard import router as dashboard_router
from app.database import get_db, init_db
from app.models import DecisionJobRecord, LLMDecisionRecord, SetupAlertRecord
from app.logging_config import protect_access_logs
from app.schemas import SetupAlert
from app.worker import DecisionWorker
from app.schema_validation import format_schema_error, validate_setup_alert_schema
from app.schemas import OutcomeUpdate
from app.workflow import (
    get_latest_decision_record,
    accept_tradingview_alert,
    record_outcome,
    serialize_decision,
    serialize_outcome,
    serialize_setup,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]

@asynccontextmanager
async def lifespan(app: FastAPI):
    protect_access_logs()
    init_db()
    worker = DecisionWorker(get_settings()) if get_settings().decision_worker_enabled else None
    app.state.decision_worker = worker
    if worker is not None:
        worker.start()
    try:
        yield
    finally:
        if worker is not None:
            await run_in_threadpool(worker.stop)


app = FastAPI(title="SMC LLM Trade Setup Validator", version="0.4.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BACKEND_ROOT / "static")), name="static")
app.include_router(dashboard_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.head("/health")
def health_head() -> None:
    """Support monitoring services that probe health endpoints with HEAD."""
    return None


def _authenticate(
    header_secret: str | None,
    query_secret: str | None,
    settings: Settings,
) -> None:
    provided_secret = header_secret or query_secret
    if not provided_secret or not stdlib_secrets.compare_digest(
        provided_secret,
        settings.webhook_secret,
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")


async def _read_json_object(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Webhook payload must be a JSON object")
    return payload


@app.get("/setups", dependencies=[Depends(require_dashboard_auth)])
def list_setups(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, object]:
    records = (
        db.query(SetupAlertRecord)
        .order_by(SetupAlertRecord.received_at.desc(), SetupAlertRecord.id.desc())
        .limit(limit)
        .all()
    )
    return {"setups": [serialize_setup(record) for record in records]}


@app.get("/setups/{setup_identifier}", dependencies=[Depends(require_dashboard_auth)])
def get_setup(setup_identifier: str, db: Annotated[Session, Depends(get_db)]) -> dict[str, object]:
    query = db.query(SetupAlertRecord)
    record = None
    if setup_identifier.isdigit():
        record = query.filter(SetupAlertRecord.id == int(setup_identifier)).one_or_none()
    if record is None:
        record = query.filter(SetupAlertRecord.setup_id == setup_identifier).one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Setup not found")

    decisions = (
        db.query(LLMDecisionRecord)
        .filter(LLMDecisionRecord.setup_id == record.setup_id)
        .order_by(LLMDecisionRecord.created_at.desc(), LLMDecisionRecord.id.desc())
        .all()
    )
    return {
        "setup": serialize_setup(record),
        "decisions": [serialize_decision(decision) for decision in decisions],
        "job": _job_status(db.get(DecisionJobRecord, record.setup_id)),
    }


@app.get("/decisions/latest", dependencies=[Depends(require_dashboard_auth)])
def latest_decision(db: Annotated[Session, Depends(get_db)]) -> dict[str, object]:
    record = get_latest_decision_record(db)
    if record is None:
        raise HTTPException(status_code=404, detail="No decisions recorded")
    return {"decision": serialize_decision(record)}


@app.post("/setups/{setup_id}/outcome", dependencies=[Depends(require_dashboard_auth)])
def mark_outcome(
    setup_id: str,
    outcome: OutcomeUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    setup = db.query(SetupAlertRecord).filter(SetupAlertRecord.setup_id == setup_id).one_or_none()
    if setup is None:
        raise HTTPException(status_code=404, detail="Setup not found")

    record = record_outcome(setup_id, outcome, db)
    return {"status": "recorded", "outcome": serialize_outcome(record)}


def _job_status(job: DecisionJobRecord | None) -> dict[str, object] | None:
    if job is None:
        return None
    return {"status": job.status, "attempts": job.attempts, "last_error": job.last_error}


@app.get("/status", dependencies=[Depends(require_dashboard_auth)])
def system_status(request: Request, db: Annotated[Session, Depends(get_db)]) -> dict[str, object]:
    db.execute(text("SELECT 1"))
    worker = getattr(request.app.state, "decision_worker", None)
    counts = dict(db.execute(select(DecisionJobRecord.status, func.count()).group_by(DecisionJobRecord.status)).all())
    latest = get_latest_decision_record(db)
    return {
        "database": "ok", "worker_alive": bool(worker and worker.thread.is_alive()),
        "jobs": counts,
        "latest_decision": {"setup_id": latest.setup_id, "model": latest.model,
                            "created_at": latest.created_at.isoformat()} if latest else None,
    }


@app.post("/webhook/tradingview")
@app.post("/webhooks/tradingview")
async def tradingview_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    x_webhook_secret: Annotated[str | None, Header(alias="X-Webhook-Secret")] = None,
    secret: Annotated[str | None, Query()] = None,
) -> JSONResponse:
    _authenticate(x_webhook_secret, secret, settings)

    payload = await _read_json_object(request)
    try:
        validate_setup_alert_schema(payload)
        SetupAlert.model_validate(payload)
    except JsonSchemaValidationError as exc:
        raise HTTPException(status_code=422, detail=format_schema_error(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Setup payload failed model validation") from exc

    acknowledgement = await run_in_threadpool(accept_tradingview_alert, payload, db)
    worker = getattr(request.app.state, "decision_worker", None)
    if worker is not None:
        worker.notify()
    return JSONResponse(acknowledgement, status_code=200 if acknowledgement["duplicate"] else 202)
