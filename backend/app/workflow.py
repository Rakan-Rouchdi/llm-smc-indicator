import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings
from app.context import build_context
from app.llm_client import get_llm_provider
from app.llm_prompt import PROMPT_VERSION
from app.models import LLMDecisionRecord, OutcomeRecord, SetupAlertRecord
from app.schemas import LLMTradeDecision, OutcomeUpdate, SetupAlert
from app.validators import ValidationPolicy, ValidatorResult, validate_llm_decision


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, default=str, separators=(",", ":"))


def _json_loads(payload: str | None) -> Any:
    if not payload:
        return None
    return json.loads(payload)


def _risk_policy(settings: Settings) -> dict[str, Any]:
    return {
        "min_confidence_for_trade": settings.llm_confidence_approve_threshold,
        "min_risk_reward": 1.5,
        "max_setup_age_minutes": settings.max_setup_age_minutes,
        "no_trade_during_blackout": True,
        "no_trade_when_consolidation": True,
    }


def _validation_policy(settings: Settings) -> ValidationPolicy:
    return ValidationPolicy(
        min_confidence_for_trade=settings.llm_confidence_approve_threshold,
        min_risk_reward=1.5,
        max_setup_age_minutes=settings.max_setup_age_minutes,
    )


def _final_decision_payload(decision: LLMTradeDecision, result: ValidatorResult) -> dict[str, Any]:
    return {
        "setup_id": decision.setup_id,
        "raw_llm_action": decision.action.value,
        "action": result.final_action.value,
        "confidence": result.final_confidence,
        "entry": decision.entry.model_dump(mode="json", by_alias=True),
        "stop_loss": decision.stop_loss,
        "take_profit": decision.take_profit.model_dump(mode="json"),
        "risk_reward": decision.risk_reward,
        "reasoning": decision.reason_summary,
        "confluence_summary": decision.confluence_notes,
        "validation_status": result.validator_status,
        "rejection_reason": "; ".join(result.rejections) if result.rejections else None,
        "warnings": result.warnings,
    }


def serialize_setup(record: SetupAlertRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "setup_id": record.setup_id,
        "received_at": record.received_at.isoformat() if record.received_at else None,
        "symbol": record.symbol,
        "timeframe": record.timeframe,
        "bar_time": record.bar_time.isoformat() if record.bar_time else None,
        "direction": record.direction,
        "rule_score": record.rule_score,
        "status": record.status,
        "raw_payload": _json_loads(record.payload_json),
        "parsed_setup": _json_loads(record.parsed_setup_json),
        "enriched_context": _json_loads(record.enriched_context_json),
    }


def serialize_decision(record: LLMDecisionRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "setup_id": record.setup_id,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "model": record.model,
        "prompt_version": record.prompt_version,
        "llm_decision": _json_loads(record.raw_output_json),
        "validator_result": _json_loads(record.validator_result_json),
        "validator_status": record.validator_status,
        "final_action": record.final_action,
        "confidence": record.confidence,
        "entry_preferred": record.entry_preferred,
        "stop_loss": record.stop_loss,
        "take_profit_1": record.take_profit_1,
        "take_profit_2": record.take_profit_2,
        "risk_reward": record.risk_reward,
        "reason_summary": record.reason_summary,
        "blocking_conditions": _json_loads(record.blocking_conditions_json) or [],
        "validation_rejection_reason": record.validation_rejection_reason,
        "llm_input": _json_loads(record.raw_input_json),
    }


def get_latest_decision_record(db: Session) -> LLMDecisionRecord | None:
    return db.query(LLMDecisionRecord).order_by(LLMDecisionRecord.created_at.desc(), LLMDecisionRecord.id.desc()).first()


def process_tradingview_alert(
    payload: dict[str, Any],
    db: Session,
    settings: Settings,
    *,
    current_time: datetime | None = None,
    context_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    setup_alert = SetupAlert.model_validate(payload)

    existing = (
        db.query(SetupAlertRecord)
        .filter(SetupAlertRecord.setup_id == setup_alert.setup_id)
        .one_or_none()
    )
    if existing is not None:
        decision = (
            db.query(LLMDecisionRecord)
            .filter(LLMDecisionRecord.setup_id == setup_alert.setup_id)
            .order_by(LLMDecisionRecord.created_at.desc(), LLMDecisionRecord.id.desc())
            .first()
        )
        return {
            "status": "duplicate",
            "duplicate": True,
            "setup": serialize_setup(existing),
            "decision": serialize_decision(decision) if decision else None,
        }

    decision_time = current_time or datetime.now(timezone.utc)
    context = context_override or build_context(setup_alert.root_symbol.value, current_time=decision_time)

    setup_record = SetupAlertRecord(
        setup_id=setup_alert.setup_id,
        symbol=setup_alert.symbol,
        timeframe=setup_alert.timeframe,
        bar_time=setup_alert.bar_time,
        direction=setup_alert.direction.value,
        rule_score=setup_alert.rule_score,
        payload_json=_json_dumps(payload),
        parsed_setup_json=setup_alert.model_dump_json(),
        enriched_context_json=_json_dumps(context),
        status="ACCEPTED",
    )
    db.add(setup_record)
    db.flush()

    llm_input = {
        "schema_version": "1.0",
        "prompt_version": PROMPT_VERSION,
        "setup_alert": setup_alert.model_dump(mode="json"),
        "context": context,
        "risk_policy": _risk_policy(settings),
    }

    provider = get_llm_provider(settings)
    llm_decision = provider.decide(llm_input)
    validator_result = validate_llm_decision(
        setup_alert=setup_alert,
        decision=llm_decision,
        context=context,
        policy=_validation_policy(settings),
        current_time=decision_time,
    )

    rejection_reason = "; ".join(validator_result.rejections) if validator_result.rejections else None
    decision_record = LLMDecisionRecord(
        setup_id=setup_alert.setup_id,
        model=provider.model_name,
        prompt_version=PROMPT_VERSION,
        raw_input_json=_json_dumps(llm_input),
        raw_output_json=llm_decision.model_dump_json(by_alias=True),
        validator_status=validator_result.validator_status,
        final_action=validator_result.final_action.value,
        confidence=validator_result.final_confidence,
        entry_preferred=llm_decision.entry.preferred,
        stop_loss=llm_decision.stop_loss,
        take_profit_1=llm_decision.take_profit.tp1,
        take_profit_2=llm_decision.take_profit.tp2,
        risk_reward=llm_decision.risk_reward,
        reason_summary=llm_decision.reason_summary,
        blocking_conditions_json=_json_dumps(validator_result.rejections),
        validator_result_json=_json_dumps(validator_result.model_dump()),
        validation_rejection_reason=rejection_reason,
    )
    db.add(decision_record)
    setup_record.status = "PROCESSED"
    db.commit()
    db.refresh(setup_record)
    db.refresh(decision_record)

    return {
        "status": "processed",
        "duplicate": False,
        "setup": serialize_setup(setup_record),
        "llm_decision": llm_decision.model_dump(mode="json", by_alias=True),
        "validator": validator_result.model_dump(),
        "final_decision": _final_decision_payload(llm_decision, validator_result),
    }


def record_outcome(setup_id: str, payload: OutcomeUpdate, db: Session) -> OutcomeRecord:
    record = OutcomeRecord(
        setup_id=setup_id,
        outcome=payload.outcome.value,
        hit_target=payload.hit_target,
        mfe_points=payload.mfe_points,
        mae_points=payload.mae_points,
        notes=payload.notes,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def serialize_outcome(record: OutcomeRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "setup_id": record.setup_id,
        "recorded_at": record.recorded_at.isoformat() if record.recorded_at else None,
        "outcome": record.outcome,
        "hit_target": record.hit_target,
        "mfe_points": record.mfe_points,
        "mae_points": record.mae_points,
        "notes": record.notes,
    }
