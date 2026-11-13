"""Safe receipt timing and operator-observed alert state; no secrets in metrics."""
import json
import logging
import math
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone

from sqlalchemy import func, select, text

from app.models import AlertObservationRecord, DecisionJobRecord, NotificationRecord, SetupAlertRecord
from app.news import calendar_context, utc
from app.news_refresh import refresh_status
from app.notifier import destination
from app.workflow import get_latest_decision_record
from app.outcome_tracking import outcome_feed_status

logger = logging.getLogger(__name__)
_receipts = deque(maxlen=500)
_lock = threading.Lock()


class ReceiptTimingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") not in {"/webhook/tradingview", "/webhooks/tradingview"}:
            return await self.app(scope, receive, send)
        start = time.perf_counter()
        metrics = {"request_id": uuid.uuid4().hex, "status": 500}
        scope["receipt_timings"] = metrics

        async def measured_send(message):
            if message["type"] == "http.response.start":
                metrics["status"] = message["status"]
                message.setdefault("headers", []).append((b"x-request-id", metrics["request_id"].encode()))
            await send(message)

        try:
            await self.app(scope, receive, measured_send)
        finally:
            metrics["application_ms"] = round((time.perf_counter() - start) * 1000, 2)
            metrics["at"] = datetime.now(timezone.utc).isoformat()
            with _lock:
                _receipts.append(dict(metrics))
            logger.info("webhook_receipt %s", json.dumps(metrics))


def receipt_summary():
    with _lock:
        rows = list(_receipts)
    times = sorted(r["application_ms"] for r in rows if r["status"] in {200, 202})
    return {"scope": "last 500 requests in this process; excludes proxy/network time",
            "count": len(rows), "accepted": len(times), "errors": len(rows) - len(times),
            "accepted_p95_ms": times[math.ceil(.95 * len(times)) - 1] if times else None,
            "accepted_over_3s": sum(t >= 3000 for t in times), "latest": rows[-1] if rows else None}


def alert_status(db, settings, now):
    row = db.get(AlertObservationRecord, 1)
    if not row:
        return {"status": "UNKNOWN", "source": "operator observation; not a live TradingView poll"}
    remaining = (utc(row.expires_at) - now).total_seconds()
    age = (now - utc(row.observed_at)).total_seconds()
    status = "EXPIRED" if remaining <= 0 else "STOPPED" if not row.active else (
        "UNKNOWN" if age < 0 or age > settings.alert_observation_max_hours * 3600 else
        "EXPIRING" if remaining <= 7 * 86400 else "ACTIVE")
    return {"status": status, "alert_id": row.alert_id, "symbol": row.symbol, "timeframe": row.timeframe,
            "expires_at": utc(row.expires_at).isoformat(), "observed_at": utc(row.observed_at).isoformat(),
            "source": "operator observation; not a live TradingView poll"}


def operational_status(db, settings, worker=None, now=None):
    now = now or datetime.now(timezone.utc)
    db.execute(text("SELECT 1"))
    counts = dict(db.execute(select(DecisionJobRecord.status, func.count()).group_by(DecisionJobRecord.status)).all())
    notifications = dict(db.execute(select(NotificationRecord.status, func.count()).group_by(NotificationRecord.status)).all())
    oldest = db.scalar(select(func.min(DecisionJobRecord.available_at)).where(
        DecisionJobRecord.status.in_(["QUEUED", "PROCESSING"])))
    age = max(0, (now - utc(oldest)).total_seconds()) if oldest else 0
    latest = get_latest_decision_record(db)
    recent = db.query(SetupAlertRecord).order_by(SetupAlertRecord.received_at.desc(), SetupAlertRecord.id.desc()).limit(200).all()
    natural = next((row for row in recent if json.loads(row.payload_json).get("diagnostics", {}).get("test_mode") is not True), None)
    alert = alert_status(db, settings, now)
    news = {symbol: calendar_context(db, symbol, now, settings)["status"]
            if settings.news_provider != "mock" else "UNVERIFIED" for symbol in ("ES", "NQ")}
    alive = bool(worker and worker.thread.is_alive())
    ready = alive and not counts.get("FAILED", 0) and age <= settings.max_setup_age_minutes * 60
    return {"database": "ok", "worker_alive": alive, "service_ready": ready,
            "outcome_tracking": outcome_feed_status(db, settings),
            "armed": ready and alert["status"] in {"ACTIVE", "EXPIRING"} and all(v == "CLEAR" for v in news.values()),
            "jobs": counts, "oldest_pending_seconds": round(age, 1), "notifications": notifications,
            "notification_delivery": "DISABLED" if not settings.enable_notifications else "CONFIGURED" if destination(settings) else "NOT_CONFIGURED",
            "latest_natural_receipt": {"setup_id": natural.setup_id, "received_at": utc(natural.received_at).isoformat()} if natural else None,
            "natural_receipt_scope": "Newest 200 receipts; delivery tests excluded",
            "alert": alert, "news": news, "news_refresh": refresh_status(db, settings), "receipts": receipt_summary(),
            "provider": settings.llm_provider, "configured_model": settings.openai_model if settings.llm_provider == "openai" else "mock",
            "latest_decision": {"setup_id": latest.setup_id, "model": latest.model,
                                "action": latest.final_action, "validator_status": latest.validator_status,
                                "created_at": utc(latest.created_at).isoformat(),
                                "historical": (now - utc(latest.created_at)).total_seconds() > settings.max_setup_age_minutes * 60}
            if latest else None}
