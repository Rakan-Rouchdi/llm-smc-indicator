"""Operator-only transport test, never a trading decision or approval."""

from datetime import datetime, timezone
from uuid import UUID

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import IntegrityError

from app.models import NotificationProbeRecord


class NotificationProbe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    test_id: UUID


def send_telegram_probe(settings, test_id):
    base = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
    chat_id = str(settings.telegram_chat_id)
    with httpx.Client(timeout=settings.notification_timeout_seconds,
                      follow_redirects=False, trust_env=False) as client:
        response = client.post(base + "/getChat", json={"chat_id": chat_id})
        if not response.is_success:
            return "FAILED", f"PRIVATE_CHAT_HTTP_{response.status_code}"
        body = response.json()
        chat = body.get("result", {}) if isinstance(body, dict) else {}
        if (not isinstance(body, dict) or body.get("ok") is not True or not isinstance(chat, dict)
                or chat.get("type") != "private" or str(chat.get("id")) != chat_id):
            return "FAILED", "PRIVATE_CHAT_REQUIRED"
        text = ("SMC NOTIFICATION DELIVERY TEST\n"
                "Connectivity check only, not a BUY/SELL signal.\n"
                "No setup, approval or order was created.\n"
                "News freshness and blackout checks remain enabled for trading candidates.\n"
                f"Test reference: {test_id}")
        response = client.post(base + "/sendMessage", json={
            "chat_id": chat_id, "text": text, "protect_content": True,
        })
        if not response.is_success:
            return "FAILED", f"SEND_HTTP_{response.status_code}"
        body = response.json()
        message = body.get("result", {}) if isinstance(body, dict) else {}
        chat = message.get("chat", {}) if isinstance(message, dict) else {}
        if (not isinstance(body, dict) or body.get("ok") is not True or not isinstance(chat, dict)
                or chat.get("type") != "private" or str(chat.get("id")) != chat_id):
            return "UNKNOWN", "UNCONFIRMED_SEND_RESPONSE"
        return "SENT", None


def serialize_probe(row):
    return {"test_id": row.test_id, "status": row.status, "last_error": row.last_error,
            "created_at": row.created_at, "kind": "TRANSPORT_TEST_ONLY",
            "note": "SENT means Telegram accepted the message, not that a person read it."}


def run_probe(db, settings, test_id, sender=None, now=None):
    sender = sender or send_telegram_probe
    test_id = str(test_id)
    if not settings.dashboard_username or not settings.dashboard_password:
        raise HTTPException(503, "Dashboard authentication must be configured for notification tests")
    existing = db.get(NotificationProbeRecord, test_id)
    if existing:
        return serialize_probe(existing)
    if not settings.require_verified_news:
        raise HTTPException(409, "Verified-news blocking must remain enabled")
    if settings.notification_webhook_url or not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise HTTPException(409, "Configure a Telegram-only destination first")
    now = now or datetime.now(timezone.utc)
    row = NotificationProbeRecord(test_id=test_id, minute_bucket=int(now.timestamp() // 60),
                                  created_at=now, status="UNKNOWN")
    db.add(row)
    try:
        # Persist the attempt before network I/O. Reusing an ID never resends,
        # even after an ambiguous timeout, process crash or concurrent request.
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.get(NotificationProbeRecord, test_id)
        if existing:
            return serialize_probe(existing)
        raise HTTPException(429, "One notification test per UTC minute") from None
    try:
        row.status, row.last_error = sender(settings, test_id)
    except Exception as exc:
        row.status, row.last_error = "UNKNOWN", type(exc).__name__
    db.commit()
    return serialize_probe(row)
