from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.dashboard import router as dashboard_router
from app.database import get_db, init_db
from app.models import LLMDecisionRecord, SetupAlertRecord
from app.schema_validation import format_schema_error, validate_setup_alert_schema
from app.schemas import OutcomeUpdate
from app.workflow import (
    get_latest_decision_record,
    process_tradingview_alert,
    record_outcome,
    serialize_decision,
    serialize_outcome,
    serialize_setup,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]

app = FastAPI(title="SMC LLM Trade Setup Validator", version="0.3.0")
app.mount("/static", StaticFiles(directory=str(BACKEND_ROOT / "static")), name="static")
app.include_router(dashboard_router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _authenticate(
    header_secret: str | None,
    query_secret: str | None,
    settings: Settings,
) -> None:
    provided_secret = header_secret or query_secret
    if not provided_secret or provided_secret != settings.webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")


async def _read_json_object(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Webhook payload must be a JSON object")
    return payload


@app.get("/setups")
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


@app.get("/setups/{setup_identifier}")
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
    }


@app.get("/decisions/latest")
def latest_decision(db: Annotated[Session, Depends(get_db)]) -> dict[str, object]:
    record = get_latest_decision_record(db)
    if record is None:
        raise HTTPException(status_code=404, detail="No decisions recorded")
    return {"decision": serialize_decision(record)}


@app.post("/setups/{setup_id}/outcome")
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


@app.post("/webhook/tradingview")
@app.post("/webhooks/tradingview")
async def tradingview_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    x_webhook_secret: Annotated[str | None, Header(alias="X-Webhook-Secret")] = None,
    secret: Annotated[str | None, Query()] = None,
) -> dict[str, object]:
    _authenticate(x_webhook_secret, secret, settings)

    payload = await _read_json_object(request)
    try:
        validate_setup_alert_schema(payload)
    except JsonSchemaValidationError as exc:
        raise HTTPException(status_code=422, detail=format_schema_error(exc)) from exc

    return process_tradingview_alert(payload, db, settings)
