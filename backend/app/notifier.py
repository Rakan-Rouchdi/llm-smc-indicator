"""Final-decision outbox. Ambiguous delivery is held, never blindly replayed."""
import hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select, update

from app.config import AUTO_NEWS_PROVIDERS
from app.database import SessionLocal
from app.models import LLMDecisionRecord, NotificationRecord, SetupAlertRecord
from app.news import calendar_context, utc
from app.schemas import LLMTradeDecision, SetupAlert
from app.timing import setup_timing


def destination(settings):
    if not settings.enable_notifications:
        return None
    if settings.notification_webhook_url:
        url = settings.notification_webhook_url
        try:
            parsed = urlsplit(url)
        except ValueError:
            return None
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return None
        channel, identity = "webhook", url
    elif settings.telegram_bot_token and settings.telegram_chat_id:
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        channel, identity = "telegram", url + settings.telegram_chat_id
    else:
        return None
    return channel, url, hashlib.sha256(identity.encode()).hexdigest()


def enqueue_notification(db, setup, decision, settings, context):
    target = destination(settings)
    if (not target or decision.validator_status != "APPROVED"
            or decision.final_action not in {"BUY", "SELL"}
            or decision.model.startswith(("mock", "deterministic"))
            or setup.diagnostics.get("test_mode") is True
            or context.get("news", {}).get("status") != "CLEAR"):
        return
    db.add(NotificationRecord(decision_id=decision.id, channel=target[0], destination_hash=target[2]))


def telegram_text(payload):
    return (f"SMC reviewed candidate: {payload['action']} {payload['symbol']} ({payload['timeframe']}m)\n"
            f"Setup quality: {payload['confidence']}/100 (not a win probability)\n"
            f"Entry (unfilled): {payload['entry']}\nSL: {payload['stop_loss']}\n"
            f"TP1: {payload['take_profit']} | RR: {payload['risk_reward']}\n"
            f"Reason: {payload['reason']}\nSetup: {payload['setup_id']}\n"
            "Decision support only. Human review required; no order placed.")


def send_message(target, payload, settings):
    body = payload if target[0] == "webhook" else {
        "chat_id": settings.telegram_chat_id, "text": telegram_text(payload),
    }
    with httpx.Client(timeout=settings.notification_timeout_seconds, follow_redirects=False, trust_env=False) as client:
        response = client.post(target[1], json=body,
                               headers={"Idempotency-Key": f"smc-decision-{payload['decision_id']}"})
        if target[0] == "telegram" and response.is_success and response.json().get("ok") is not True:
            return 502
        return response.status_code


def suppression_reason(db, row, decision, setup, output, target, settings, now):
    if target is None:
        return "Notification delivery disabled or unconfigured"
    if target[2] != row.destination_hash:
        return "Notification destination changed"
    if (decision.validator_status != "APPROVED" or decision.final_action not in {"BUY", "SELL"}
            or output.action.value != decision.final_action or output.setup_id != setup.setup_id):
        return "Decision is not an approved matching trade candidate"
    if decision.model.startswith(("mock", "deterministic")) or setup.diagnostics.get("test_mode") is True:
        return "Test or fallback decision cannot be notified"
    if not 0 <= setup_timing(setup, now)["age_minutes"] <= settings.max_setup_age_minutes:
        return "Setup is stale or has not closed"
    if output.expires_at and (output.expires_at.tzinfo is None or utc(output.expires_at) <= now):
        return "Decision expiry is invalid or elapsed"
    # Reuse the same provider-matched, bounded snapshot as final validation.
    # A successful fetch alone is not evidence that a calendar remains CLEAR.
    if settings.news_provider not in {"manual", *AUTO_NEWS_PROVIDERS}:
        return "Verified news provider required"
    state = calendar_context(db, setup.root_symbol.value, now, settings)["status"]
    if state != "CLEAR":
        return f"News safety gate: {state}"
    return None


def deliver_one(settings, sender=send_message):
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        # A crash after sending cannot prove whether the destination accepted it.
        db.execute(update(NotificationRecord).where(
            NotificationRecord.status == "PROCESSING", NotificationRecord.lease_until <= now,
        ).values(status="UNKNOWN", last_error="Delivery requires reconciliation", lease_until=None))
        db.commit()
        row_id = db.scalar(select(NotificationRecord.id).where(
            NotificationRecord.status == "QUEUED", NotificationRecord.available_at <= now,
        ).order_by(NotificationRecord.id).limit(1))
        if row_id is None:
            return False
        claimed = db.execute(update(NotificationRecord).where(
            NotificationRecord.id == row_id, NotificationRecord.status == "QUEUED",
        ).values(status="PROCESSING", attempts=NotificationRecord.attempts + 1,
                 lease_until=now + timedelta(seconds=60)))
        db.commit()
        if claimed.rowcount != 1:
            return False
        row = db.get(NotificationRecord, row_id)
        decision = db.get(LLMDecisionRecord, row.decision_id)
        target = destination(settings)
        try:
            source = db.query(SetupAlertRecord).filter_by(setup_id=decision.setup_id).one_or_none() if decision else None
            if source is None:
                reason = "Stored decision or setup missing"
            else:
                setup = SetupAlert.model_validate_json(source.payload_json)
                output = LLMTradeDecision.model_validate_json(decision.raw_output_json)
                reason = suppression_reason(db, row, decision, setup, output, target, settings, now)
        except (ValueError, TypeError, OverflowError):
            reason = "Stored payload or timing invalid"
        if reason:
            row.status, row.last_error, row.lease_until = "SUPPRESSED", reason, None
            db.commit()
            return True
        payload = {"decision_id": decision.id, "setup_id": decision.setup_id,
                   "symbol": setup.symbol, "timeframe": setup.timeframe,
                   "action": decision.final_action, "confidence": decision.confidence,
                   "entry": decision.entry_preferred, "stop_loss": decision.stop_loss,
                   "take_profit": decision.take_profit_1, "risk_reward": decision.risk_reward,
                   "model": decision.model, "reason": decision.reason_summary,
                   "entry_status": "PENDING_HUMAN_REVIEW", "created_at": decision.created_at.isoformat(),
                   "confidence_meaning": "Setup quality, not win probability", "orders_placed": False}
        db.commit()
        try:
            status = sender(target, payload, settings)
            row.status = "SENT" if 200 <= status < 300 else (
                "QUEUED" if (status == 429 or status >= 500) and row.attempts < 3 else "FAILED")
            row.last_error = None if row.status == "SENT" else f"HTTP_{status}"
            row.available_at = now + timedelta(seconds=10 * row.attempts)
        except Exception as exc:
            row.status, row.last_error = "UNKNOWN", type(exc).__name__
        row.lease_until = None
        db.commit()
        return True
