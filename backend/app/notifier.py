"""Final-decision outbox. Ambiguous delivery is held, never blindly replayed."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select, update

from app.database import SessionLocal
from app.models import LLMDecisionRecord, NotificationRecord, SetupAlertRecord
from app.news import calendar_context, utc
from app.schemas import SetupAlert
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


def send_message(target, payload, settings):
    body = payload if target[0] == "webhook" else {
        "chat_id": settings.telegram_chat_id, "text": json.dumps(payload),
    }
    with httpx.Client(timeout=settings.notification_timeout_seconds, follow_redirects=False, trust_env=False) as client:
        response = client.post(target[1], json=body,
                               headers={"Idempotency-Key": f"smc-decision-{payload['decision_id']}"})
        if target[0] == "telegram" and response.is_success and response.json().get("ok") is not True:
            return 502
        return response.status_code


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
        source = db.query(SetupAlertRecord).filter_by(setup_id=decision.setup_id).one()
        setup = SetupAlert.model_validate_json(source.payload_json)
        output = json.loads(decision.raw_output_json)
        target = destination(settings)
        expiry = output.get("expires_at")
        valid = (target and target[2] == row.destination_hash
                 and decision.validator_status == "APPROVED" and decision.final_action in {"BUY", "SELL"}
                 and not decision.model.startswith(("mock", "deterministic"))
                 and setup.diagnostics.get("test_mode") is not True
                 and 0 <= setup_timing(setup, now)["age_minutes"] <= settings.max_setup_age_minutes
                 and (not expiry or utc(datetime.fromisoformat(expiry.replace("Z", "+00:00"))) > now)
                 and settings.news_provider == "manual"
                 and calendar_context(db, setup.root_symbol.value, now, settings)["status"] == "CLEAR")
        if not valid:
            row.status, row.last_error, row.lease_until = "SUPPRESSED", "Safety checks no longer pass", None
            db.commit()
            return True
        payload = {"decision_id": decision.id, "setup_id": decision.setup_id,
                   "action": decision.final_action, "confidence": decision.confidence,
                   "entry": decision.entry_preferred, "stop_loss": decision.stop_loss,
                   "take_profit": decision.take_profit_1, "risk_reward": decision.risk_reward,
                   "model": decision.model, "reason": decision.reason_summary,
                   "entry_status": "PENDING_HUMAN_REVIEW", "created_at": decision.created_at.isoformat()}
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
