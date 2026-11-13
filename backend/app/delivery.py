"""Read-only delivery evidence and bounded, explicitly unvalidated outcome counts."""

import json
import math
from collections import Counter
from datetime import datetime, timezone

from app.models import ForwardReviewRecord, LLMDecisionRecord, NotificationRecord, NotificationAttemptRecord, OutcomeRecord, SetupAlertRecord
from app.news import utc
from app.schemas import SetupAlert
from app.timing import setup_timing


def _object(value):
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def _milliseconds(value):
    return round(value, 2) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 else None


def delivery_report(db, setup, decision=None, now=None):
    now = now or datetime.now(timezone.utc)
    payload = _object(setup.payload_json)
    diagnostics = payload.get("diagnostics", {})
    report = {
        "setup_id": setup.setup_id,
        "source": "DELIVERY_TEST" if diagnostics.get("test_mode") is True else "CHART_CANDIDATE",
        "market_data": "DELAYED" if "_DL:" in setup.symbol else "NOT_VERIFIED",
        "detector_revision": diagnostics.get("detector_revision", "LEGACY_OR_UNKNOWN"),
        "received_at": utc(setup.received_at).isoformat(),
        "bar_close_time": None, "close_to_receipt_ms": None,
        "receipt_to_processing_ms": None, "provider_ms": None,
        "processing_ms_before_commit": None, "receipt_to_decision_record_ms": None,
        "decision_recorded_at": None, "timing_status": "UNKNOWN",
        "notification": {"status": "NOT_ENQUEUED", "attempts": 0, "reason": None,
                         "api_accepted_at": None, "receipt_to_api_acceptance_ms": None},
    }
    try:
        timing = setup_timing(SetupAlert.model_validate(payload), now)
        closed = datetime.fromisoformat(timing["bar_close_time"])
        elapsed = (utc(setup.received_at) - closed).total_seconds() * 1000
        report.update(bar_close_time=timing["bar_close_time"], timing_basis=timing["basis"],
                      close_to_receipt_ms=_milliseconds(elapsed),
                      timing_status="CLOCK_OR_PAYLOAD_ERROR" if elapsed < 0 else "MEASURED",
                      age_minutes=timing["age_minutes"])
    except (ValueError, TypeError, OverflowError):
        pass
    if decision is not None:
        execution = _object(decision.raw_input_json).get("execution", {})
        for field in ("receipt_to_processing_ms", "provider_ms", "processing_ms_before_commit"):
            report[field] = _milliseconds(execution.get(field))
        report["decision_recorded_at"] = utc(decision.created_at).isoformat()
        report["receipt_to_decision_record_ms"] = _milliseconds(
            (utc(decision.created_at) - utc(setup.received_at)).total_seconds() * 1000)
        row = db.query(NotificationRecord).filter_by(decision_id=decision.id).first()
        if row:
            report["notification"].update(status=row.status, attempts=row.attempts, reason=row.last_error)
            attempt = db.query(NotificationAttemptRecord).filter_by(notification_id=row.id, status="SENT").order_by(
                NotificationAttemptRecord.finished_at, NotificationAttemptRecord.id).first()
            if row.status == "SENT" and attempt:
                report["notification"].update(api_accepted_at=utc(attempt.finished_at).isoformat(),
                    receipt_to_api_acceptance_ms=_milliseconds((utc(attempt.finished_at)-utc(setup.received_at)).total_seconds()*1000))
    return report


def evaluation_summary(db, limit=500):
    """Keep test/fallback/legacy decisions out of the current forward cohort.

    Manual outcomes are annotations, not independently verified executions.
    No win-rate, P&L or prediction accuracy is inferred from these counts.
    """
    setups = db.query(SetupAlertRecord).order_by(SetupAlertRecord.received_at.desc(), SetupAlertRecord.id.desc()).limit(limit).all()
    ids = [row.setup_id for row in setups]
    decisions = {}
    outcomes = {}
    reviews = {}
    if ids:
        for row in db.query(LLMDecisionRecord).filter(LLMDecisionRecord.setup_id.in_(ids)).order_by(
                LLMDecisionRecord.created_at.desc(), LLMDecisionRecord.id.desc()):
            decisions.setdefault(row.setup_id, row)
        for row in db.query(OutcomeRecord).filter(OutcomeRecord.setup_id.in_(ids)).order_by(
                OutcomeRecord.recorded_at.desc(), OutcomeRecord.id.desc()):
            outcomes.setdefault(row.setup_id, row)
        decision_ids = [row.id for row in decisions.values()]
        if decision_ids:
            for row in db.query(ForwardReviewRecord).filter(ForwardReviewRecord.decision_id.in_(decision_ids)).order_by(
                    ForwardReviewRecord.recorded_at.desc(), ForwardReviewRecord.id.desc()):
                reviews.setdefault(row.decision_id, row)
    excluded, counts, eligible = Counter(), Counter(), 0
    for setup in setups:
        payload = _object(setup.payload_json)
        diagnostics = payload.get("diagnostics", {})
        decision = decisions.get(setup.setup_id)
        if diagnostics.get("test_mode") is True:
            excluded["delivery_test"] += 1
        elif diagnostics.get("detector_revision") != "timing_sessions_v2" or diagnostics.get("policy_version") != "strict_v1":
            excluded["legacy_revision"] += 1
        elif decision is None:
            excluded["pending_or_failed"] += 1
        elif decision.validator_status != "APPROVED" or decision.final_action not in {"BUY", "SELL"}:
            excluded["not_approved"] += 1
        elif decision.model.startswith(("mock", "deterministic")) or _object(decision.raw_input_json).get("execution", {}).get("provider_requested") != "openai":
            excluded["non_live_provider"] += 1
        else:
            eligible += 1
            outcome = reviews.get(decision.id) or outcomes.get(setup.setup_id)
            counts[outcome.outcome if outcome else "UNRECORDED"] += 1
    return {"scope": f"Newest {limit} received setups; latest decision and outcome per setup",
            "reviewed_setups": len(setups), "eligible_candidates": eligible,
            "excluded": dict(excluded), "manual_outcomes": dict(counts),
            "accuracy_status": "NOT_ESTABLISHED",
            "limitations": "Manual outcomes do not verify fills, costs or profitability. Delivery tests and legacy/fallback decisions are excluded."}
