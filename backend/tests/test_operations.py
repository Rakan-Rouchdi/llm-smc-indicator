from datetime import datetime, timedelta, timezone

import pytest

from app.config import get_settings
from app.database import SessionLocal
from app.models import CalendarCoverageRecord, AlertObservationRecord
from app.news import calendar_context
from app.monitoring import alert_status
from scripts.check_mvp_status import request_for, collect_status


def calendar(now, events=None):
    return {"source": "Test fixture, not real events", "coverage_start": (now - timedelta(hours=1)).isoformat(),
            "coverage_end": (now + timedelta(days=2)).isoformat(), "events": events or []}


def test_calendar_unknown_clear_blackout_and_expiry(client):
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        assert calendar_context(db, "ES", now, get_settings())["status"] == "UNKNOWN"
    event = {"event_id": "test", "title": "Synthetic event", "event_time": now.isoformat(),
             "impact": "HIGH", "symbols": ["ES"], "blackout_minutes_before": 30, "blackout_minutes_after": 30}
    assert client.put("/context/news-calendar", json=calendar(now, [event])).status_code == 200
    with SessionLocal() as db:
        assert calendar_context(db, "ES", now, get_settings())["status"] == "UNKNOWN"  # verified after now
        verified = db.get(CalendarCoverageRecord, 1).verified_at.replace(tzinfo=timezone.utc)
        assert calendar_context(db, "ES", verified, get_settings())["status"] == "BLACKOUT"
        assert calendar_context(db, "NQ", verified, get_settings())["status"] == "CLEAR"
        assert calendar_context(db, "ES", now + timedelta(minutes=30), get_settings())["status"] == "BLACKOUT"
        assert calendar_context(db, "ES", now + timedelta(minutes=31), get_settings())["status"] == "CLEAR"
        assert calendar_context(db, "ES", now + timedelta(hours=25), get_settings())["status"] == "UNKNOWN"


def test_calendar_invalid_snapshot_does_not_replace(client):
    now = datetime.now(timezone.utc)
    assert client.put("/context/news-calendar", json=calendar(now)).status_code == 200
    bad = calendar(now + timedelta(days=5))
    assert client.put("/context/news-calendar", json=bad).status_code == 422
    assert client.get("/context/news-calendar").json()["ES"]["status"] == "CLEAR"


@pytest.mark.parametrize("days,active,age,status", [(-1, True, 0, "EXPIRED"), (10, False, 0, "STOPPED"),
    (10, True, 25, "UNKNOWN"), (3, True, 0, "EXPIRING"), (10, True, 0, "ACTIVE")])
def test_alert_observation_states(client, days, active, age, status):
    now = datetime.now(timezone.utc)
    payload = {"alert_id": "123", "symbol": "CME_MINI:NQ1!", "timeframe": "240", "active": active,
               "expires_at": (now + timedelta(days=days)).isoformat()}
    assert client.put("/monitoring/alert", json=payload).status_code == 200
    with SessionLocal() as db:
        row = db.get(AlertObservationRecord, 1)
        row.observed_at = now - timedelta(hours=age)
        db.commit()
        assert alert_status(db, get_settings(), now)["status"] == status


def test_monitoring_distinguishes_health_from_readiness(client):
    assert client.get("/health").status_code == 200
    status = client.get("/status").json()
    assert status["armed"] is False
    assert status["service_ready"] is False
    assert status["alert"]["status"] == "UNKNOWN"
    assert "Not confirmed ready" in client.get("/dashboard").text


def test_new_endpoints_require_auth(client, monkeypatch):
    monkeypatch.setenv("DASHBOARD_USERNAME", "operator")
    monkeypatch.setenv("DASHBOARD_PASSWORD", "test-password")
    get_settings.cache_clear()
    for path in ("/context/news-calendar", "/notifications", "/status"):
        assert client.get(path).status_code == 401
    assert client.put("/context/news-calendar", json={}).status_code == 401
    assert client.put("/monitoring/alert", json={}).status_code == 401


def test_receipt_timings_are_safe_and_include_commit(client, fresh_setup_payload, caplog):
    import logging
    with caplog.at_level(logging.INFO):
        response = client.post("/webhook/tradingview?secret=test-secret", json=fresh_setup_payload)
    assert response.status_code == 202
    assert response.headers["x-request-id"]
    metrics = client.get("/status").json()["receipts"]["latest"]
    assert all(key in metrics for key in ("db_connect_ms", "lookup_ms", "commit_ms", "validation_ms", "application_ms"))
    messages = [r.message for r in caplog.records if r.name == "app.monitoring"]
    assert messages and all("test-secret" not in m for m in messages)


def test_receipt_metric_includes_storage_delay(client, fresh_setup_payload, monkeypatch):
    import time
    import app.main
    accept = app.main.accept_tradingview_alert
    def slow_storage(*args):
        time.sleep(.06)
        return accept(*args)
    monkeypatch.setattr(app.main, "accept_tradingview_alert", slow_storage)
    assert client.post("/webhook/tradingview?secret=test-secret", json=fresh_setup_payload).status_code == 202
    assert client.get("/status").json()["receipts"]["latest"]["application_ms"] >= 60


def test_hosted_cli_uses_auth_and_no_local_sqlite(monkeypatch):
    monkeypatch.setenv("DASHBOARD_USERNAME", "operator")
    monkeypatch.setenv("DASHBOARD_PASSWORD", "test-password")
    assert request_for("https://example.test/status").get_header("Authorization").startswith("Basic ")
    with pytest.raises(ValueError):
        request_for("http://remote.example/status")
    with pytest.raises(ValueError):
        request_for("https://example.test/status?secret=x")
    def fetch(url, timeout):
        if url.endswith("/status"):
            return 200, {"database": "ok", "service_ready": True, "armed": False}
        if url.endswith("/decisions/latest"):
            return 200, {"decision": {"final_action": "NO_TRADE"}}
        return 200, {"status": "ok"}
    result = collect_status("https://example.test", None, 1, fetch, lambda *_: 200)
    assert result["ok"] is True and result["armed"] is False
    assert "example.test" not in str(result)


def test_operator_helper_updates_only_named_endpoint(tmp_path, monkeypatch):
    from scripts.update_operations import submit
    path = tmp_path / "snapshot.json"
    path.write_text('{"source":"test"}')
    requests = []
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *_): pass
    class Opener:
        def open(self, request, timeout):
            requests.append(request)
            return Response()
    monkeypatch.setattr("urllib.request.build_opener", lambda *_: Opener())
    assert submit("https://example.test", "news-calendar", path) == 200
    assert requests[0].method == "PUT"
    assert requests[0].full_url == "https://example.test/context/news-calendar"
