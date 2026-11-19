"""Operator-triggered diagnostic on a real stored test receipt, never an approval.

Normal webhook preflight and final notification rules are untouched. The operator
must match the receipt against TradingView's log before requesting this second
stage. UNKNOWN is persisted before external I/O; an ambiguous run never retries.
"""
import json
import re
import time
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError

from app.config import AUTO_NEWS_PROVIDERS
from app.context import build_context
from app.llm_client import get_llm_provider
from app.llm_prompt import PROMPT_VERSION
from app.models import FlowProbeRecord, LLMDecisionRecord, SetupAlertRecord
from app.news import utc
from app.notification_probe import send_private_telegram_text
from app.schema_validation import validate_llm_trade_decision_schema, validate_setup_alert_schema
from app.schemas import LLMTradeDecision, SetupAlert
from app.timing import setup_timing
from app.validators import validate_llm_decision
from app.workflow import _risk_policy, _validation_policy


class FlowProbe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    test_id: UUID
    setup_id: str = Field(min_length=1, max_length=255)
    tradingview_log_verified: Literal[True]


def serialize_flow_probe(row):
    return {"test_id": row.test_id, "setup_id": row.setup_id,
            "kind": "OPERATOR_LINKED_FLOW_TEST", "status": row.status,
            "final_action": "NO_TRADE", "eligible_for_outcomes": False,
            "last_error": row.last_error, "created_at": row.created_at,
            "finished_at": row.finished_at,
            "result": json.loads(row.result_json) if row.result_json else None,
            "note": "Diagnostic only. SENT means Telegram API acceptance, not phone receipt."}


def _configuration_ready(settings):
    return (settings.require_verified_news and settings.news_provider in {"manual", *AUTO_NEWS_PROVIDERS}
            and settings.llm_provider == "openai" and settings.openai_api_key is not None
            and settings.enable_notifications and not settings.notification_webhook_url
            and settings.telegram_bot_token and settings.telegram_chat_id)


def _fresh_test(setup, record, settings, now):
    age = setup_timing(setup, now)["age_minutes"]
    receipt_age = (now - utc(record.received_at)).total_seconds()
    return (setup.diagnostics.get("test_mode") is True
            and re.fullmatch(r"CME_MINI_DL:NQ1!_5_TEST_\d+_\d+", setup.setup_id) is not None
            and setup.setup_id == record.setup_id
            and setup.symbol == "CME_MINI_DL:NQ1!" and setup.timeframe == "5"
            and 0 <= age <= settings.max_setup_age_minutes and 0 <= receipt_age <= 900)


def _clear(context):
    news = context.get("news", {})
    return (news.get("status") == "CLEAR" and news.get("blackout_active") is False
            and context.get("news_blackout_active") is False)


def run_flow_probe(db, settings, request, *, clock=None, sender=None):
    clock = clock or (lambda: datetime.now(timezone.utc))
    sender = sender or send_private_telegram_text
    if not settings.dashboard_username or not settings.dashboard_password:
        raise HTTPException(503, "Dashboard authentication must be configured")
    test_id = str(request.test_id)
    existing = db.get(FlowProbeRecord, test_id)
    if existing:
        if existing.setup_id != request.setup_id:
            raise HTTPException(409, "Test reference already belongs to another receipt")
        return serialize_flow_probe(existing)
    if not _configuration_ready(settings):
        raise HTTPException(409, "Live OpenAI, private Telegram and verified-news gates are required")
    record = db.query(SetupAlertRecord).filter_by(setup_id=request.setup_id).one_or_none()
    if record is None:
        raise HTTPException(404, "Stored receipt not found")
    # Never relabel a natural approval, pending job or historical sample as a test.
    decision = db.query(LLMDecisionRecord).filter_by(setup_id=request.setup_id).order_by(
        LLMDecisionRecord.id.desc()).first()
    if (record.status != "PROCESSED" or decision is None or decision.final_action != "NO_TRADE"
            or decision.validator_status != "REJECTED"):
        raise HTTPException(409, "Receipt must already have a rejected NO_TRADE decision")
    now = clock()
    try:
        payload = json.loads(record.payload_json)
        validate_setup_alert_schema(payload)
        setup = SetupAlert.model_validate(payload)
        fresh = _fresh_test(setup, record, settings, now)
    except Exception:
        raise HTTPException(409, "Stored test payload or timing is invalid") from None
    if not fresh:
        raise HTTPException(409, "Only a recent NQ 5m test receipt is eligible")
    row = FlowProbeRecord(test_id=test_id, setup_id=setup.setup_id,
                          minute_bucket=int(now.timestamp() // 60), created_at=now, status="UNKNOWN")
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.get(FlowProbeRecord, test_id)
        if existing and existing.setup_id == request.setup_id:
            return serialize_flow_probe(existing)
        raise HTTPException(409, "One run per receipt and per UTC minute; reconcile existing tests") from None

    evidence = {"tradingview_log_verified_by_operator": True, "schema_valid": False,
                "production_decision_id": decision.id, "production_final_action": "NO_TRADE"}
    stage = "MODEL"
    try:
        context = build_context(setup.root_symbol.value, current_time=clock())
        evidence["news_before"] = context.get("news")
        if not _clear(context):
            row.status, row.last_error = "BLOCKED", "NEWS_NOT_CLEAR"
        else:
            llm_input = {"schema_version": "1.0", "prompt_version": PROMPT_VERSION,
                         "setup_alert": setup.model_dump(mode="json"), "context": context,
                         "risk_policy": _risk_policy(settings), "setup_timing": setup_timing(setup, clock()),
                         "diagnostic": {"test_only": True, "final_action_forced": "NO_TRADE",
                                        "note": "Review supplied evidence; never invent confluences or an approval."}}
            evidence["llm_input"] = llm_input
            provider = get_llm_provider(settings)
            started = time.perf_counter()
            output = provider.decide(llm_input)
            evidence["provider_ms"] = round((time.perf_counter() - started) * 1000, 2)
            evidence["model"] = provider.model_name
            if provider.model_name != settings.openai_model or getattr(provider, "used_fallback", False):
                row.status, row.last_error = "FAILED", "LIVE_PROVIDER_UNAVAILABLE"
            else:
                raw = output.model_dump(mode="json", by_alias=True)
                validate_llm_trade_decision_schema(raw)
                output = LLMTradeDecision.model_validate(raw)
                if output.setup_id != setup.setup_id:
                    raise ValueError("Mismatched setup")
                evidence["schema_valid"], evidence["llm_output"] = True, raw
                context = build_context(setup.root_symbol.value, current_time=clock())
                result = validate_llm_decision(setup, output, context, _validation_policy(settings), clock())
                evidence["validator"] = result.model_dump()
                evidence["news_after"] = context.get("news")
                # Even a model BUY or an unexpected validator approval cannot enter
                # the production outbox or evaluation tables through this diagnostic.
                if not _clear(context) or not _fresh_test(setup, record, settings, clock()):
                    row.status, row.last_error = "BLOCKED", "NEWS_OR_RECEIPT_NO_LONGER_FRESH"
                else:
                    row.result_json = json.dumps(evidence, default=str)
                    db.commit()
                    stage = "TELEGRAM"
                    text = ("SMC END-TO-END DELIVERY TEST\n"
                            "Diagnostic only, not a BUY/SELL signal. No order placed.\n"
                            f"Stored TradingView test: {setup.setup_id}\n"
                            f"Live model: {provider.model_name}; JSON schema: valid\n"
                            f"Deterministic validator: {result.validator_status}\n"
                            "Final trading action: NO_TRADE (test only). Excluded from outcomes.\n"
                            "Verified news was CLEAR before model review and before this message.\n"
                            f"Test reference: {test_id}")
                    row.status, row.last_error = sender(settings, text)
    except Exception as exc:
        # Exception messages can contain URLs/tokens. Ambiguous sends never retry.
        row.status = "UNKNOWN" if stage == "TELEGRAM" else "FAILED"
        row.last_error = type(exc).__name__
    row.result_json = json.dumps(evidence, default=str)
    row.finished_at = clock()
    db.commit()
    return serialize_flow_probe(row)
