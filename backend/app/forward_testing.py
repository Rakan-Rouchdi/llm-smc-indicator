"""Read-only cohort plus append-only paper reviews; never executes or approves trades."""

from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.auth import require_dashboard_auth
from app.database import get_db
from app.delivery import _object, delivery_report
from app.models import ForwardReviewRecord, LLMDecisionRecord, SetupAlertRecord
from app.news import utc

# Start of the approved revision-19 alert, not a retrospective best-performing window.
COHORT_START = datetime(2026, 11, 13, 17, 10, 12, tzinfo=timezone.utc)
router = APIRouter(dependencies=[Depends(require_dashboard_auth)])


class ForwardReview(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    outcome: Literal["WIN", "LOSS", "EXPIRED", "UNKNOWN"]
    entry_status: Literal["TOUCHED", "NOT_TOUCHED", "UNKNOWN"]
    observed_until: AwareDatetime
    source_verified: bool
    notes: str = Field(min_length=20, max_length=2000)

    @model_validator(mode="after")
    def consistent_observation(self):
        if self.outcome in {"WIN", "LOSS"} and (self.entry_status != "TOUCHED" or not self.source_verified):
            raise ValueError("WIN/LOSS requires an observed entry touch and a checked TradingView alert log")
        if self.outcome == "EXPIRED" and self.entry_status != "NOT_TOUCHED":
            raise ValueError("EXPIRED requires no observed entry touch")
        return self


def cohort_reason(setup, decision):
    diagnostics = _object(setup.payload_json).get("diagnostics", {})
    if diagnostics.get("test_mode") is True:
        return "DELIVERY_TEST"
    if utc(setup.received_at) < COHORT_START:
        return "BEFORE_COHORT"
    if (diagnostics.get("detector_revision") != "timing_sessions_v2"
            or diagnostics.get("policy_version") != "strict_v1"):
        return "LEGACY_REVISION"
    if decision is None:
        return "PENDING_OR_FAILED"
    if decision.validator_status != "APPROVED" or decision.final_action not in {"BUY", "SELL"}:
        return "NOT_APPROVED"
    if (decision.model.startswith(("mock", "deterministic"))
            or _object(decision.raw_input_json).get("execution", {}).get("provider_requested") != "openai"):
        return "NON_LIVE_PROVIDER"
    return "ELIGIBLE_PAPER_REVIEW"


def serialize_review(row):
    return {"id": row.id, "decision_id": row.decision_id, "recorded_at": utc(row.recorded_at).isoformat(),
            "observed_until": utc(row.observed_until).isoformat(), "outcome": row.outcome,
            "entry_status": row.entry_status, "source_verified": bool(row.source_verified), "notes": row.notes}


def forward_ledger(db, limit=50, offset=0):
    # Keep blocked, test and pending records visible, avoiding approval-only survivorship bias.
    query = db.query(SetupAlertRecord).filter(SetupAlertRecord.received_at >= COHORT_START)
    total = query.count()
    setups = query.order_by(SetupAlertRecord.received_at.desc(), SetupAlertRecord.id.desc()).offset(offset).limit(limit).all()
    ids = [s.setup_id for s in setups]
    decisions = {}
    if ids:
        for d in db.query(LLMDecisionRecord).filter(LLMDecisionRecord.setup_id.in_(ids)).order_by(
                LLMDecisionRecord.created_at.desc(), LLMDecisionRecord.id.desc()):
            decisions.setdefault(d.setup_id, d)
    reviews = {}
    decision_ids = [d.id for d in decisions.values()]
    if decision_ids:
        for r in db.query(ForwardReviewRecord).filter(ForwardReviewRecord.decision_id.in_(decision_ids)).order_by(
                ForwardReviewRecord.recorded_at.desc(), ForwardReviewRecord.id.desc()):
            reviews.setdefault(r.decision_id, serialize_review(r))
    rows = []
    for s in setups:
        d = decisions.get(s.setup_id)
        rows.append({"id": s.id, "setup_id": s.setup_id, "symbol": s.symbol, "timeframe": s.timeframe,
            "received_at": utc(s.received_at).isoformat(), "status": s.status,
            "cohort_status": cohort_reason(s, d), "decision_id": d.id if d else None,
            "action": d.final_action if d else None, "model": d.model if d else None,
            "validator": d.validator_status if d else None,
            "reason": d.validation_rejection_reason or d.reason_summary if d else None,
            "entry": d.entry_preferred if d else None, "sl": d.stop_loss if d else None,
            "tp1": d.take_profit_1 if d else None,
            "delivery": delivery_report(db, s, d), "review": reviews.get(d.id) if d else None})
    return {"cohort_start": COHORT_START.isoformat(), "total_receipts": total,
            "limit": limit, "offset": offset, "rows": rows, "accuracy_status": "NOT_ESTABLISHED"}


@router.get("/forward-testing")
def ledger_api(db: Annotated[Session, Depends(get_db)], limit: int = Query(50, ge=1, le=100),
               offset: int = Query(0, ge=0)):
    return forward_ledger(db, limit, offset)


@router.get("/dashboard/forward-testing")
def ledger_page(request: Request, db: Annotated[Session, Depends(get_db)], offset: int = Query(0, ge=0)):
    from app.dashboard import templates
    return templates.TemplateResponse(request, "forward_testing.html", {"ledger": forward_ledger(db, 25, offset)})


@router.post("/forward-testing/decisions/{decision_id}/reviews")
def save_review(decision_id: int, body: ForwardReview, db: Annotated[Session, Depends(get_db)]):
    decision = db.get(LLMDecisionRecord, decision_id)
    setup = db.query(SetupAlertRecord).filter_by(setup_id=decision.setup_id).first() if decision else None
    if setup is None:
        raise HTTPException(404, "Decision not found")
    if cohort_reason(setup, decision) != "ELIGIBLE_PAPER_REVIEW":
        raise HTTPException(409, "Only current-cohort live-approved decisions accept paper reviews")
    now = datetime.now(timezone.utc)
    if not utc(decision.created_at) <= body.observed_until <= now:
        raise HTTPException(422, "Observation must fall between decision creation and now")
    if body.observed_until > utc(decision.created_at) + timedelta(hours=24):
        raise HTTPException(422, "Paper protocol uses a maximum 24-hour observation window")
    if body.outcome == "EXPIRED":
        expiry = _object(decision.raw_output_json).get("expires_at")
        try:
            expiry = datetime.fromisoformat(expiry)
            if expiry.tzinfo is None or body.observed_until < expiry:
                raise ValueError()
        except (TypeError, ValueError):
            raise HTTPException(422, "EXPIRED requires a known elapsed decision expiry")
    row = ForwardReviewRecord(decision_id=decision_id, **body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"status": "recorded", "review": serialize_review(row)}


@router.get("/forward-testing/decisions/{decision_id}/reviews")
def review_history(decision_id: int, db: Annotated[Session, Depends(get_db)]):
    return {"reviews": [serialize_review(r) for r in db.query(ForwardReviewRecord).filter_by(
        decision_id=decision_id).order_by(ForwardReviewRecord.recorded_at.desc(), ForwardReviewRecord.id.desc())]}
