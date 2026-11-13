import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from app.config import get_settings
from app.database import SessionLocal
from app.delivery import delivery_report
from app.llm_client import MockLLMProvider
from app.models import LLMDecisionRecord, NotificationRecord, SetupAlertRecord
from app.news import replace_calendar
from app.notifier import deliver_one
from app.schemas import CalendarUpdate
from app.worker import DecisionWorker
from app.workflow import process_tradingview_alert


def test_webhook_worker_automatic_news_and_final_notification(client, fresh_setup_payload, monkeypatch):
    class RecordedResponse(MockLLMProvider):
        model_name = "fixture-live-response"
    monkeypatch.setattr("app.workflow.get_llm_provider", lambda _: RecordedResponse())
    monkeypatch.setenv("NEWS_PROVIDER", "showmytrades")
    monkeypatch.setenv("REQUIRE_VERIFIED_NEWS", "true")
    monkeypatch.setenv("ENABLE_NOTIFICATIONS", "true")
    monkeypatch.setenv("NOTIFICATION_WEBHOOK_URL", "https://example.test/notify")
    get_settings.cache_clear()
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        replace_calendar(db, CalendarUpdate(source="ShowMyTrades USD calendar; synthetic integration fixture",
            coverage_start=now-timedelta(minutes=5), coverage_end=now+timedelta(hours=1), events=[]), now)
    assert client.post("/webhooks/tradingview", headers={"X-Webhook-Secret": "test-secret"}, json=fresh_setup_payload).status_code == 202
    assert client.get("/setups/1").json()["delivery"]["provider_ms"] is None
    assert DecisionWorker(get_settings()).run_once()
    sent = []
    assert deliver_one(get_settings(), lambda target, body, _: sent.append(body) or 200)
    assert not deliver_one(get_settings(), lambda *_: pytest.fail("Duplicate notification"))
    result = client.get("/setups/1").json()
    assert result["decisions"][0]["validator_status"] == "APPROVED"
    assert result["delivery"]["notification"]["status"] == "SENT"
    assert result["delivery"]["receipt_to_processing_ms"] >= 0
    assert result["delivery"]["provider_ms"] >= 0
    assert result["delivery"]["receipt_to_decision_record_ms"] >= 0
    assert sent[0]["orders_placed"] is False
    assert "Delivery evidence" in client.get("/dashboard").text
    assert "SENT | 1 attempts" in client.get("/dashboard/setups/1").text
    with SessionLocal() as db:
        assert db.query(SetupAlertRecord).count() == db.query(LLMDecisionRecord).count() == db.query(NotificationRecord).count() == 1


def test_delivery_metrics_preserve_unknown_and_clock_errors(client, fresh_setup_payload):
    fresh_setup_payload["symbol"] = "CME_MINI_DL:ES1!"
    fresh_setup_payload["diagnostics"]["test_mode"] = True
    client.post("/webhook/tradingview?secret=test-secret", json=fresh_setup_payload)
    with SessionLocal() as db:
        row = db.query(SetupAlertRecord).one()
        row.received_at = datetime.fromisoformat(fresh_setup_payload["diagnostics"]["bar_close_time"]) - timedelta(seconds=1)
        report = delivery_report(db, row)
        assert report["timing_status"] == "CLOCK_OR_PAYLOAD_ERROR"
        assert report["close_to_receipt_ms"] is None
        assert report["source"] == "DELIVERY_TEST" and report["market_data"] == "DELAYED"
        assert report["provider_ms"] is None
        raw = json.loads(row.payload_json)
        raw["diagnostics"]["bar_close_time"] = "invalid"
        row.payload_json = json.dumps(raw)
        assert delivery_report(db, row)["timing_status"] == "UNKNOWN"


def test_evaluation_excludes_tests_fallbacks_legacy_and_duplicate_outcomes(client, fresh_setup_payload, monkeypatch):
    class RecordedResponse(MockLLMProvider):
        model_name = "fixture-live-response"
    monkeypatch.setattr("app.workflow.get_llm_provider", lambda _: RecordedResponse())
    settings = get_settings().model_copy(update={"llm_provider": "openai"})
    for case in ("eligible", "test", "legacy", "fallback", "rejected", "pending"):
        payload = deepcopy(fresh_setup_payload)
        payload["setup_id"] += "_" + case
        if case == "test":
            payload["diagnostics"]["test_mode"] = True
        if case == "rejected":
            payload["features"]["consolidation"]["active"] = True
        if case == "pending":
            client.post("/webhook/tradingview?secret=test-secret", json=payload)
        else:
            with SessionLocal() as db:
                process_tradingview_alert(payload, db, settings, context_override={"news": {"status": "CLEAR"}})
                if case == "fallback":
                    db.query(LLMDecisionRecord).filter_by(setup_id=payload["setup_id"]).one().model = "mock-openai-fallback"
                db.commit()
        # Cohort fixtures annotate stored revision metadata, not market data or live alerts.
        if case != "legacy":
            with SessionLocal() as db:
                row = db.query(SetupAlertRecord).filter_by(setup_id=payload["setup_id"]).one()
                raw = json.loads(row.payload_json)
                raw["diagnostics"]["detector_revision"] = "timing_sessions_v2"
                row.payload_json = json.dumps(raw)
                db.commit()
    eligible_id = fresh_setup_payload["setup_id"] + "_eligible"
    assert client.post(f"/setups/{eligible_id}/outcome", json={"outcome": "WIN"}).status_code == 200
    assert client.post(f"/setups/{eligible_id}/outcome", json={"outcome": "LOSS"}).status_code == 200
    client.post(f"/setups/{fresh_setup_payload['setup_id']}_test/outcome", json={"outcome": "WIN"})
    summary = client.get("/evaluation").json()
    assert summary["eligible_candidates"] == 1
    assert summary["manual_outcomes"] == {"LOSS": 1}
    assert summary["excluded"] == {"delivery_test": 1, "legacy_revision": 1, "non_live_provider": 1, "not_approved": 1, "pending_or_failed": 1}
    assert summary["accuracy_status"] == "NOT_ESTABLISHED"
    assert "win_rate" not in summary
    assert "Forward evaluation" in client.get("/dashboard").text


def test_evaluation_empty_and_authentication(client, monkeypatch):
    assert client.get("/evaluation").json()["eligible_candidates"] == 0
    monkeypatch.setenv("DASHBOARD_USERNAME", "operator")
    monkeypatch.setenv("DASHBOARD_PASSWORD", "synthetic-password")
    get_settings.cache_clear()
    assert client.get("/evaluation").status_code == 401
    assert client.get("/health").status_code == 200


def test_blocked_probe_cannot_call_paid_model_or_approve(client, monkeypatch):
    from pathlib import Path
    from scripts.send_sample_webhook import prepare_payload
    path = Path(__file__).resolve().parents[2] / "examples/pine_alert_payload_example.json"
    body = prepare_payload(path, blocked_probe=True)
    payload = json.loads(body)
    assert payload["diagnostics"]["test_mode"] is True
    monkeypatch.setattr("app.workflow.get_llm_provider", lambda _: pytest.fail("Paid model used for blocked probe"))
    assert client.post("/webhook/tradingview?secret=test-secret", content=body,
                       headers={"Content-Type": "application/json"}).status_code == 202
    assert DecisionWorker(get_settings()).run_once()
    result = client.get("/decisions/latest").json()["decision"]
    assert result["model"] == "deterministic-preflight" and result["final_action"] == "NO_TRADE"
    assert "consolidation" in result["validation_rejection_reason"]


def test_probe_ack_timing_and_no_redirects(monkeypatch):
    from scripts.send_sample_webhook import NoRedirect, send_sample
    requests = []
    class Response:
        status = 202
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read(self): return b'{"status":"accepted","setup_id":"synthetic","duplicate":false}'
    class Opener:
        def open(self, request, timeout):
            requests.append(request)
            return Response()
    monkeypatch.setattr("urllib.request.build_opener", lambda *_: Opener())
    result = send_sample("https://example.test/webhooks/tradingview", "synthetic-secret", b'{"setup_id":"synthetic"}', 3)
    assert result["http_status"] == 202 and result["within_3_seconds"] is True
    assert "synthetic-secret" not in str(result) and "example.test" not in str(result)
    assert NoRedirect().redirect_request(None, None, None, None, None, None) is None
    assert requests[0].get_header("X-webhook-secret") == "synthetic-secret"
    with pytest.raises(ValueError):
        send_sample("http://remote.example/webhooks/tradingview", "x", b"{}", 3)


def test_probe_errors_do_not_print_secret_or_host(monkeypatch, capsys):
    import sys
    import urllib.error
    from scripts.send_sample_webhook import main
    monkeypatch.setattr(sys, "argv", ["probe", "--url", "https://example.test/webhooks/tradingview", "--secret", "synthetic-secret", "--blocked-probe"])
    def fail(*_):
        raise urllib.error.URLError("https://secret.example?secret=synthetic-secret")
    monkeypatch.setattr("scripts.send_sample_webhook.send_sample", fail)
    assert main() == 1
    output = capsys.readouterr().err
    assert "URLError" in output
    assert "synthetic-secret" not in output and "secret.example" not in output
