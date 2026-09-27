import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import require_dashboard_auth
from app.database import get_db
from app.models import DecisionJobRecord, LLMDecisionRecord, SetupAlertRecord
from app.workflow import serialize_decision, serialize_setup

router = APIRouter()

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


def _pretty(payload: Any) -> str:
    if payload is None:
        return "{}"
    return json.dumps(payload, indent=2, default=str)


@router.get("/")
@router.get("/dashboard")
def index(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    _dashboard_auth: Annotated[None, Depends(require_dashboard_auth)],
):
    setup_records = (
        db.query(SetupAlertRecord)
        .order_by(SetupAlertRecord.received_at.desc(), SetupAlertRecord.id.desc())
        .limit(25)
        .all()
    )
    setup = setup_records[0] if setup_records else None
    decision = (db.query(LLMDecisionRecord).filter_by(setup_id=setup.setup_id)
                .order_by(LLMDecisionRecord.created_at.desc(), LLMDecisionRecord.id.desc()).first()) if setup else None
    job = db.get(DecisionJobRecord, setup.setup_id) if setup else None

    serialized_setup = serialize_setup(setup) if setup is not None else None
    serialized_decision = serialize_decision(decision) if decision is not None else None
    context = serialized_setup.get("enriched_context") if serialized_setup else None
    raw_payload = serialized_setup.get("raw_payload") if serialized_setup else None

    return templates.TemplateResponse(
        request,
        "index.html",
        context={
            "request": request,
            "latest_setup": serialized_setup,
            "latest_decision": serialized_decision,
            "processing_error": job.last_error if job else None,
            "news_context": context.get("news") if isinstance(context, dict) else None,
            "telegram_context": context.get("telegram") if isinstance(context, dict) else None,
            "setup_history": [serialize_setup(record) for record in setup_records],
            "raw_payload_json": _pretty(raw_payload),
            "llm_decision_json": _pretty(
                serialized_decision.get("llm_decision") if serialized_decision else None
            ),
        },
    )


@router.get("/dashboard/setups/{setup_identifier}")
def setup_detail(
    setup_identifier: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    _dashboard_auth: Annotated[None, Depends(require_dashboard_auth)],
):
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
    serialized_setup = serialize_setup(record)
    serialized_decisions = [serialize_decision(decision) for decision in decisions]
    context = serialized_setup.get("enriched_context")

    return templates.TemplateResponse(
        request,
        "setup_detail.html",
        context={
            "request": request,
            "setup": serialized_setup,
            "decisions": serialized_decisions,
            "job": db.get(DecisionJobRecord, record.setup_id),
            "news_context": context.get("news") if isinstance(context, dict) else None,
            "telegram_context": context.get("telegram") if isinstance(context, dict) else None,
            "raw_payload_json": _pretty(serialized_setup.get("raw_payload")),
        },
    )
