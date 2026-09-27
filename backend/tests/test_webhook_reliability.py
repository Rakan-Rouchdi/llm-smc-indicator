import logging
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from app.config import get_settings
from app.database import SessionLocal
from app.llm_client import MockLLMProvider
from app.logging_config import RemoveQueryString
from app.models import DecisionJobRecord, LLMDecisionRecord, SetupAlertRecord
from app.schemas import LLMTradeDecision, SetupAlert
from app.timing import setup_timing
from app.validators import validate_llm_decision
from app.worker import DecisionWorker


HEADERS = {"X-Webhook-Secret": "test-secret"}


def test_ack_is_durable_and_does_not_wait_for_slow_llm(client, fresh_setup_payload, monkeypatch):
    entered, release = threading.Event(), threading.Event()

    class SlowProvider(MockLLMProvider):
        def decide(self, llm_input):
            entered.set()
            assert release.wait(timeout=5)
            return super().decide(llm_input)

    monkeypatch.setattr("app.workflow.get_llm_provider", lambda settings: SlowProvider())
    worker = DecisionWorker(get_settings())
    client.app.state.decision_worker = worker
    worker.start()
    try:
        started = time.monotonic()
        response = client.post("/webhooks/tradingview", json=fresh_setup_payload, headers=HEADERS)
        assert response.status_code == 202
        assert time.monotonic() - started < 1
        assert entered.wait(timeout=2)
        assert not release.is_set()
        assert client.get("/health").status_code == 200
        with SessionLocal() as db:
            assert db.query(SetupAlertRecord).count() == 1
            assert db.query(DecisionJobRecord).count() == 1
            assert db.query(LLMDecisionRecord).count() == 0
        duplicate = client.post("/webhooks/tradingview", json=fresh_setup_payload, headers=HEADERS)
        assert duplicate.status_code == 200
        assert duplicate.json()["duplicate"] is True
    finally:
        release.set()
        worker.stop()
        client.app.state.decision_worker = None
    with SessionLocal() as db:
        assert db.query(LLMDecisionRecord).count() == 1
        assert db.query(DecisionJobRecord).one().status == "DONE"


def test_queued_receipt_survives_new_worker_instance(client, fresh_setup_payload):
    assert client.post("/webhook/tradingview", json=fresh_setup_payload, headers=HEADERS).status_code == 202
    with SessionLocal() as db:
        assert db.query(LLMDecisionRecord).count() == 0
    assert DecisionWorker(get_settings()).run_once()
    assert not DecisionWorker(get_settings()).run_once()
    result = client.get(f"/setups/{fresh_setup_payload['setup_id']}").json()
    assert result["job"] == {"status": "DONE", "attempts": 1, "last_error": None}
    assert len(result["decisions"]) == 1


def test_expired_worker_lease_is_recovered(client, fresh_setup_payload):
    client.post("/webhook/tradingview", json=fresh_setup_payload, headers=HEADERS)
    with SessionLocal() as db:
        job = db.query(DecisionJobRecord).one()
        job.status = "PROCESSING"
        job.lease_token = "crashed-worker"
        job.lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    assert DecisionWorker(get_settings()).run_once()
    assert client.get("/decisions/latest").status_code == 200


def test_worker_failure_is_bounded_and_visible_without_secret_details(client, fresh_setup_payload, monkeypatch):
    def fail(settings):
        raise RuntimeError("credential-detail-must-not-be-stored")

    monkeypatch.setattr("app.workflow.get_llm_provider", fail)
    client.post("/webhook/tradingview", json=fresh_setup_payload, headers=HEADERS)
    worker = DecisionWorker(get_settings())
    for _ in range(3):
        with SessionLocal() as db:
            db.query(DecisionJobRecord).update({"available_at": datetime.now(timezone.utc) - timedelta(seconds=1)})
            db.commit()
        assert worker.run_once()
    assert not worker.run_once()
    result = client.get(f"/setups/{fresh_setup_payload['setup_id']}").json()
    assert result["job"] == {"status": "FAILED", "attempts": 3, "last_error": "RuntimeError"}
    assert result["setup"]["status"] == "FAILED"
    assert result["decisions"] == []
    dashboard = client.get("/dashboard")
    assert "RuntimeError" in dashboard.text
    assert "credential-detail-must-not-be-stored" not in dashboard.text


@pytest.mark.parametrize("minutes", [5, 15, 60, 240])
def test_freshness_is_measured_from_bar_close(minutes, valid_setup_payload, valid_buy_decision_payload):
    opened = datetime(2026, 9, 24, 14, tzinfo=timezone.utc)
    valid_setup_payload.update(timeframe=str(minutes), bar_time=opened.isoformat())
    setup = SetupAlert.model_validate(valid_setup_payload)
    decision = LLMTradeDecision.model_validate(valid_buy_decision_payload)
    now = opened + timedelta(minutes=minutes + 10)
    assert setup_timing(setup, now)["age_minutes"] == 10
    result = validate_llm_decision(setup, decision, current_time=now)
    assert result.validator_status == "APPROVED"
    stale = validate_llm_decision(setup, decision, current_time=now + timedelta(minutes=6))
    assert "Setup is stale" in stale.rejections


def test_future_or_unknown_close_cannot_bypass_freshness(valid_setup_payload, valid_buy_decision_payload):
    valid_setup_payload.update(timeframe="240", bar_time="2026-09-24T14:00:00Z")
    setup = SetupAlert.model_validate(valid_setup_payload)
    decision = LLMTradeDecision.model_validate(valid_buy_decision_payload)
    before_close = datetime(2026, 9, 24, 17, tzinfo=timezone.utc)
    result = validate_llm_decision(setup, decision, current_time=before_close)
    assert result.validator_status == "REJECTED"
    assert "Setup candle has not closed or its timestamp is inconsistent" in result.rejections
    setup.timeframe = "D"
    assert "Setup timing could not be validated" in validate_llm_decision(setup, decision, current_time=before_close).rejections


def test_explicit_shortened_session_close_is_supported(valid_setup_payload):
    valid_setup_payload.update(timeframe="240", bar_time="2026-09-24T18:00:00Z")
    valid_setup_payload["diagnostics"]["bar_close_time"] = "2026-09-24T21:00:00Z"
    timing = setup_timing(SetupAlert.model_validate(valid_setup_payload), datetime(2026, 9, 24, 21, 10, tzinfo=timezone.utc))
    assert timing["age_minutes"] == 10
    assert timing["basis"] == "explicit_bar_close_time"


def test_data_routes_and_outcomes_require_dashboard_auth(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DASHBOARD_USERNAME", "operator")
    monkeypatch.setenv("DASHBOARD_PASSWORD", "test-dashboard-password")
    get_settings.cache_clear()
    for path in ["/", "/dashboard", "/dashboard/setups/1", "/setups", "/setups/1", "/decisions/latest", "/status"]:
        assert client.get(path).status_code == 401
    assert client.post("/setups/x/outcome", json={"outcome": "WIN"}).status_code == 401
    assert client.get("/health").status_code == 200
    assert client.get("/status", auth=("operator", "test-dashboard-password")).status_code == 200


def test_access_log_removes_webhook_query_secret():
    record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                               ("127.0.0.1", "POST", "/webhooks/tradingview?secret=private-test-value", "1.1", 202), None)
    assert RemoveQueryString().filter(record)
    assert "private-test-value" not in record.getMessage()
    assert "/webhooks/tradingview" in record.getMessage()


def test_pending_setup_does_not_display_previous_setups_decision(client, fresh_setup_payload):
    client.post("/webhook/tradingview", json=fresh_setup_payload, headers=HEADERS)
    DecisionWorker(get_settings()).run_once()
    fresh_setup_payload["setup_id"] += "_next"
    client.post("/webhook/tradingview", json=fresh_setup_payload, headers=HEADERS)
    dashboard = client.get("/dashboard").text
    assert "QUEUED: no decision recorded for this setup." in dashboard
    assert "mock-llm-deterministic" not in dashboard
