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


def test_bad_notification_destination_does_not_lose_decision(notification_setup):
    payload, settings = notification_setup
    settings.notification_webhook_url = "https://[invalid"
    assert process(payload, settings)["status"] == "processed"
    with SessionLocal() as db:
        assert db.query(NotificationRecord).count() == 0


@pytest.mark.parametrize("provider", ["manual", "forexfactory", "showmytrades"])
@pytest.mark.parametrize("state", ["clear", "blackout", "stale", "future", "expired_coverage", "wrong_provider", "missing"])
def test_delivery_rechecks_each_verified_provider(notification_setup, provider, state):
    from app.models import CalendarCoverageRecord, NewsEventRecord
    from app.news import SOURCE_PREFIXES
    payload, settings = notification_setup
    process(payload, settings)
    settings.news_provider = provider
    settings.require_verified_news = True
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        coverage = db.get(CalendarCoverageRecord, 1)
        coverage.source = SOURCE_PREFIXES.get(provider, "Manual test calendar") + " synthetic fixture"
        if state == "blackout":
            db.add(NewsEventRecord(event_id="test-news", title="Synthetic blackout", impact="HIGH",
                                  event_time=now, symbols_json='["ES"]'))
        elif state == "stale":
            coverage.verified_at = now - timedelta(hours=2 if provider == "showmytrades" else 25)
        elif state == "future":
            coverage.verified_at = now + timedelta(minutes=5)
        elif state == "expired_coverage":
            coverage.coverage_end = now - timedelta(seconds=1)
        elif state == "wrong_provider":
            coverage.source = SOURCE_PREFIXES["forexfactory" if provider != "forexfactory" else "showmytrades"]
        elif state == "missing":
            db.delete(coverage)
        db.commit()
    sent = []
    assert deliver_one(settings, lambda *args: sent.append(args) or 200)
    assert len(sent) == (1 if state == "clear" else 0)
    with SessionLocal() as db:
        row = db.query(NotificationRecord).one()
        assert row.status == ("SENT" if state == "clear" else "SUPPRESSED")
        if state != "clear":
            assert row.last_error == f"News safety gate: {'BLACKOUT' if state == 'blackout' else 'UNKNOWN'}"


@pytest.mark.parametrize("cause", ["disabled", "mock_news", "corrupt_output", "invalid_close", "naive_expiry"])
def test_delivery_fail_closed_without_ambiguous_retry(notification_setup, cause):
    from app.models import LLMDecisionRecord, SetupAlertRecord
    payload, settings = notification_setup
    process(payload, settings)
    with SessionLocal() as db:
        if cause == "disabled":
            settings.enable_notifications = False
        elif cause == "mock_news":
            settings.news_provider = "mock"
        elif cause == "corrupt_output":
            db.query(LLMDecisionRecord).one().raw_output_json = "not json"
        elif cause == "naive_expiry":
            row = db.query(LLMDecisionRecord).one()
            output = json.loads(row.raw_output_json)
            output["expires_at"] = "2099-01-01T12:00:00"
            row.raw_output_json = json.dumps(output)
        else:
            row = db.query(SetupAlertRecord).one()
            raw = json.loads(row.payload_json)
            raw["diagnostics"]["bar_close_time"] = "bad-date-secret-must-not-appear"
            row.payload_json = json.dumps(raw)
        db.commit()
    assert deliver_one(settings, lambda *_: pytest.fail("Unsafe notification"))
    assert not deliver_one(settings, lambda *_: pytest.fail("Suppressed notification retried"))
    with SessionLocal() as db:
        row = db.query(NotificationRecord).one()
        assert row.status == "SUPPRESSED"
        assert "secret-must-not-appear" not in row.last_error


@pytest.mark.parametrize("channel", ["webhook", "telegram"])
def test_real_sender_serialization_with_mock_http_transport(notification_setup, monkeypatch, channel):
    import httpx
    from app.notifier import send_message
    payload, settings = notification_setup
    if channel == "telegram":
        settings.notification_webhook_url = None
        settings.telegram_bot_token = "synthetic-token"
        settings.telegram_chat_id = "synthetic-chat"
    process(payload, settings)
    requests = []
    def transport(request):
        requests.append(request)
        return httpx.Response(200, json={"ok": True})
    original = httpx.Client
    def client(**kwargs):
        assert kwargs["follow_redirects"] is False and kwargs["trust_env"] is False
        return original(**kwargs, transport=httpx.MockTransport(transport))
    monkeypatch.setattr("app.notifier.httpx.Client", client)
    assert deliver_one(settings, send_message)
    assert len(requests) == 1
    body = json.loads(requests[0].content)
    if channel == "telegram":
        assert body["chat_id"] == "synthetic-chat"
        assert "not a win probability" in body["text"] and "no order placed" in body["text"]
        assert payload["symbol"] in body["text"]
    else:
        assert body["symbol"] == payload["symbol"] and body["orders_placed"] is False
    assert requests[0].headers["Idempotency-Key"].startswith("smc-decision-")
