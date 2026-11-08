import json
from datetime import datetime, timedelta, timezone

import pytest

from app.config import get_settings
from app.database import SessionLocal
from app.llm_client import MockLLMProvider
from app.models import NotificationRecord
from app.news import replace_calendar
from app.notifier import deliver_one
from app.schemas import CalendarUpdate
from app.workflow import process_tradingview_alert


@pytest.fixture
def notification_setup(client, fresh_setup_payload, monkeypatch):
    class RecordedLiveResponse(MockLLMProvider):
        model_name = "fixture-live-response"
    monkeypatch.setattr("app.workflow.get_llm_provider", lambda _: RecordedLiveResponse())
    settings = get_settings().model_copy(update={"enable_notifications": True,
        "notification_webhook_url": "https://example.test/notify", "news_provider": "manual"})
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        replace_calendar(db, CalendarUpdate(source="Synthetic test calendar", coverage_start=now - timedelta(hours=1),
                         coverage_end=now + timedelta(hours=1), events=[]), now)
    return fresh_setup_payload, settings


def process(payload, settings):
    with SessionLocal() as db:
        return process_tradingview_alert(payload, db, settings, context_override={"news": {"status": "CLEAR"}})


def test_outbox_is_transactional_deduplicated_and_delivered_once(notification_setup):
    payload, settings = notification_setup
    result = process(payload, settings)
    assert process(payload, settings)["duplicate"]
    calls = []
    def sender(target, body, config):
        calls.append(body)
        return 200
    assert deliver_one(settings, sender)
    assert not deliver_one(settings, sender)
    assert len(calls) == 1
    assert calls[0]["entry_status"] == "PENDING_HUMAN_REVIEW"
    with SessionLocal() as db:
        assert db.query(NotificationRecord).one().status == "SENT"


@pytest.mark.parametrize("condition", ["test", "mock", "rejected", "unverified"])
def test_non_live_decisions_never_enqueued(notification_setup, condition, monkeypatch):
    payload, settings = notification_setup
    context = {"news": {"status": "CLEAR"}}
    if condition == "test":
        payload["diagnostics"]["test_mode"] = True
    elif condition == "mock":
        monkeypatch.setattr("app.workflow.get_llm_provider", lambda _: MockLLMProvider())
    elif condition == "rejected":
        payload["features"]["consolidation"]["active"] = True
    else:
        context["news"]["status"] = "UNKNOWN"
    with SessionLocal() as db:
        process_tradingview_alert(payload, db, settings, context_override=context)
        assert db.query(NotificationRecord).count() == 0


@pytest.mark.parametrize("cause", ["expired", "destination", "blackout", "calendar_stale"])
def test_recheck_before_delivery(notification_setup, cause):
    from app.models import LLMDecisionRecord, CalendarCoverageRecord, NewsEventRecord
    payload, settings = notification_setup
    process(payload, settings)
    with SessionLocal() as db:
        if cause == "expired":
            row = db.query(LLMDecisionRecord).one()
            output = json.loads(row.raw_output_json)
            output["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
            row.raw_output_json = json.dumps(output)
        elif cause == "destination":
            settings.notification_webhook_url = "https://other.example.test/notify"
        elif cause == "calendar_stale":
            db.get(CalendarCoverageRecord, 1).verified_at = datetime.now(timezone.utc) - timedelta(days=2)
        else:
            db.add(NewsEventRecord(event_id="synthetic", title="Synthetic blackout", impact="HIGH",
                                  event_time=datetime.now(timezone.utc), symbols_json='["ES"]'))
        db.commit()
    assert deliver_one(settings, lambda *_: pytest.fail("Unsafe notification"))
    with SessionLocal() as db:
        assert db.query(NotificationRecord).one().status == "SUPPRESSED"


def test_unknown_send_is_not_blindly_retried(notification_setup):
    payload, settings = notification_setup
    process(payload, settings)
    def timeout(*_):
        raise TimeoutError("secret-must-not-appear")
    assert deliver_one(settings, timeout)
    assert not deliver_one(settings, lambda *_: pytest.fail("Must not retry ambiguous send"))
    with SessionLocal() as db:
        row = db.query(NotificationRecord).one()
        assert row.status == "UNKNOWN" and row.last_error == "TimeoutError"


def test_retry_limit(notification_setup):
    payload, settings = notification_setup
    process(payload, settings)
    for _ in range(3):
        assert deliver_one(settings, lambda *_: 429)
        with SessionLocal() as db:
            db.query(NotificationRecord).update({"available_at": datetime.now(timezone.utc) - timedelta(seconds=1)})
            db.commit()
    assert not deliver_one(settings, lambda *_: pytest.fail("Retries exhausted"))
    with SessionLocal() as db:
        assert db.query(NotificationRecord).one().status == "FAILED"


def test_crashed_send_lease_becomes_unknown(notification_setup):
    payload, settings = notification_setup
    process(payload, settings)
    with SessionLocal() as db:
        row = db.query(NotificationRecord).one()
        row.status, row.lease_until = "PROCESSING", datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    assert not deliver_one(settings, lambda *_: pytest.fail("Ambiguous delivery"))
    with SessionLocal() as db:
        assert db.query(NotificationRecord).one().status == "UNKNOWN"
