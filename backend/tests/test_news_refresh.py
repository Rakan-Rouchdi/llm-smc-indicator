import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import httpx
import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.database import SessionLocal
from app.models import CalendarCoverageRecord, CalendarRefreshRecord, NewsEventRecord
from app.news import calendar_context, utc
from app.news_refresh import CalendarFeedError, CalendarRefreshWorker, FeedSnapshot, fetch_snapshot, parse_snapshot, week_bounds
from app.schemas import CalendarUpdate
from app.worker import DecisionWorker

NOW = datetime(2026, 11, 8, 18, tzinfo=timezone.utc)


def settings():
    return Settings(_env_file=None, news_provider="forexfactory", require_verified_news=True)


def feed():
    return [
        {"country": "USD", "title": "FOMC Member Test Speaks", "date": "2026-11-09T08:40:00-05:00", "impact": "Low"},
        {"country": "USD", "title": "CPI y/y", "date": "2026-11-10T08:30:00-05:00", "impact": "High"},
        {"country": "EUR", "title": "Fixture", "date": "2026-11-09T09:00:00+01:00", "impact": "High"},
    ]


def parse(rows=None, modified=NOW - timedelta(minutes=10), now=NOW):
    return parse_snapshot(json.dumps(feed() if rows is None else rows).encode(),
                          format_datetime(modified) if modified else None, now, settings())


def snapshot(now, age_hours=0, event_time=None):
    events = [] if event_time is None else [{"event_id": "test-event", "title": "Synthetic HIGH event",
        "event_time": event_time, "impact": "HIGH", "symbols": ["ES", "NQ"]}]
    calendar = CalendarUpdate(source="Forex Factory weekly export; synthetic test only",
        coverage_start=now-timedelta(days=2), coverage_end=now+timedelta(days=2), events=events)
    return FeedSnapshot(calendar, now-timedelta(hours=age_hours), "fixture-digest")


def test_parser_utc_scope_conservative_speeches_and_week_edges():
    result = parse()
    assert len(result.calendar.events) == 2
    event = result.calendar.events[0]
    assert event.event_time.isoformat() == "2026-11-09T13:40:00+00:00"
    assert event.impact == "HIGH" and event.symbols == ["ES", "NQ"]
    assert result.modified_at == NOW - timedelta(minutes=10)
    assert result.calendar.coverage_start.isoformat() == "2026-11-08T05:30:00+00:00"
    assert result.calendar.coverage_end.isoformat() == "2026-11-15T04:30:00+00:00"


@pytest.mark.parametrize("modified", [None, NOW+timedelta(seconds=1), NOW-timedelta(hours=24)])
def test_missing_future_or_stale_publisher_date_rejected(modified):
    with pytest.raises(CalendarFeedError):
        parse(modified=modified)


@pytest.mark.parametrize("raw", [b"not-json", b"{}", b"[]", b"x"*(2*1024*1024+1)])
def test_bad_body_rejected(raw):
    with pytest.raises(ValueError):
        parse_snapshot(raw, format_datetime(NOW), NOW, settings())


@pytest.mark.parametrize("field,value", [
    ("date", "2026-11-09T08:40:00"), ("date", "Tentative"),
    ("date", "2026-11-02T08:40:00-05:00"), ("date", "2026-11-09T00:00:00-05:00"),
    ("impact", "Unknown"), ("title", ""),
])
def test_ambiguous_invalid_or_wrong_week_event_blocks_snapshot(field, value):
    rows = feed(); rows[0][field] = value
    with pytest.raises(ValueError):
        parse(rows)


def test_duplicates_and_missing_usd_are_not_clear():
    with pytest.raises(CalendarFeedError, match="duplicate"):
        parse(feed() + [feed()[0]])
    with pytest.raises(CalendarFeedError, match="usd"):
        parse([feed()[-1]])


def test_week_rollover_and_dst_are_bounded():
    start, end = week_bounds(datetime(2026, 11, 1, 12, tzinfo=timezone.utc))
    assert (end-start).total_seconds() == 169*3600
    with pytest.raises(CalendarFeedError, match="boundary"):
        parse(now=datetime(2026, 11, 8, 5, 10, tzinfo=timezone.utc),
              modified=datetime(2026, 11, 8, 5, tzinfo=timezone.utc))


def test_auto_provider_cannot_disable_stale_data_gate():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, news_provider="forexfactory", require_verified_news=False)


def test_refresh_cooldown_restart_and_publisher_timestamp(client, monkeypatch):
    calls = []
    def fetch(*_):
        calls.append(1)
        return parse()
    monkeypatch.setattr("app.news_refresh.fetch_snapshot", fetch)
    assert CalendarRefreshWorker(settings()).run_once(NOW)
    assert not CalendarRefreshWorker(settings()).run_once(NOW+timedelta(minutes=30))
    assert CalendarRefreshWorker(settings()).run_once(NOW+timedelta(hours=1))
    with SessionLocal() as db:
        coverage = db.get(CalendarCoverageRecord, 1)
        assert utc(coverage.verified_at) == NOW-timedelta(minutes=10)
        assert utc(db.get(CalendarRefreshRecord, 1).last_success_at) == NOW+timedelta(hours=1)
        assert db.query(NewsEventRecord).count() == 2
    assert len(calls) == 2


@pytest.mark.parametrize("failure", [httpx.ReadTimeout("private-response"), httpx.ConnectError("private-response"),
    ValueError("private-response"), CalendarFeedError("missing_publisher_timestamp")])
def test_failure_preserves_last_good_without_renewing_freshness(client, monkeypatch, failure, caplog):
    monkeypatch.setattr("app.news_refresh.fetch_snapshot", lambda *_: parse())
    worker = CalendarRefreshWorker(settings()); worker.run_once(NOW)
    def fail(*_):
        raise failure
    monkeypatch.setattr("app.news_refresh.fetch_snapshot", fail)
    worker.run_once(NOW+timedelta(hours=1))
    with SessionLocal() as db:
        assert utc(db.get(CalendarCoverageRecord, 1).verified_at) == NOW-timedelta(minutes=10)
        assert db.query(NewsEventRecord).count() == 2
        assert calendar_context(db, "ES", NOW+timedelta(hours=1), settings())["status"] == "CLEAR"
        assert calendar_context(db, "ES", NOW+timedelta(hours=24), settings())["status"] == "UNKNOWN"
        assert db.get(CalendarRefreshRecord, 1).last_error
    assert "private-response" not in caplog.text


def test_stale_or_conflicting_snapshot_cannot_replace_newer(client, monkeypatch):
    monkeypatch.setattr("app.news_refresh.fetch_snapshot", lambda *_: parse())
    worker = CalendarRefreshWorker(settings()); worker.run_once(NOW)
    newer = parse()
    for i, bad in enumerate((FeedSnapshot(newer.calendar, newer.modified_at-timedelta(seconds=1), newer.digest),
                            FeedSnapshot(newer.calendar, newer.modified_at, "different")), start=1):
        monkeypatch.setattr("app.news_refresh.fetch_snapshot", lambda *_, value=bad: value)
        worker.run_once(NOW+timedelta(hours=i))
        with SessionLocal() as db:
            assert utc(db.get(CalendarCoverageRecord, 1).verified_at) == newer.modified_at
            assert db.get(CalendarRefreshRecord, 1).content_sha256 == newer.digest


def test_atomic_refresh_rolls_back_partial_event_changes(client, monkeypatch):
    monkeypatch.setattr("app.news_refresh.fetch_snapshot", lambda *_: parse())
    worker = CalendarRefreshWorker(settings()); worker.run_once(NOW)
    def broken(db, *_args, **_kwargs):
        db.query(NewsEventRecord).delete()
        raise RuntimeError("simulated database failure")
    monkeypatch.setattr("app.news_refresh.replace_calendar", broken)
    worker.run_once(NOW+timedelta(hours=1))
    with SessionLocal() as db:
        assert db.query(NewsEventRecord).count() == 2
        assert utc(db.get(CalendarRefreshRecord, 1).last_success_at) == NOW


@pytest.mark.parametrize("case,action,reason", [
    ("clear", "BUY", None), ("blackout", "NO_TRADE", "News blackout"),
    ("stale", "NO_TRADE", "Verified news"), ("gold", "NO_TRADE", "Unsupported instrument"),
    ("gold_mislabeled", "NO_TRADE", "Unsupported instrument"),
])
def test_automated_context_webhook_and_dashboard(client, fresh_setup_payload, monkeypatch, case, action, reason):
    now = datetime.now(timezone.utc)
    monkeypatch.setenv("NEWS_PROVIDER", "forexfactory")
    monkeypatch.setenv("REQUIRE_VERIFIED_NEWS", "true")
    get_settings.cache_clear()
    value = snapshot(now, age_hours=25 if case == "stale" else 0,
                     event_time=now if case == "blackout" else None)
    monkeypatch.setattr("app.news_refresh.fetch_snapshot", lambda *_: value)
    assert CalendarRefreshWorker(get_settings()).run_once(now)
    fresh_setup_payload["diagnostics"]["test_mode"] = True
    if case == "gold":
        fresh_setup_payload.update(symbol="OANDA:XAUUSD", root_symbol="UNKNOWN")
    elif case == "gold_mislabeled":
        fresh_setup_payload.update(symbol="OANDA:XAUUSD", root_symbol="ES")
    if reason:
        monkeypatch.setattr("app.workflow.get_llm_provider", lambda *_: pytest.fail("Blocked setup must skip LLM"))
    assert client.post("/webhook/tradingview?secret=test-secret", json=fresh_setup_payload).status_code == 202
    assert DecisionWorker(get_settings()).run_once()
    decision = client.get("/decisions/latest").json()["decision"]
    assert decision["final_action"] == action
    if reason:
        assert reason in decision["validation_rejection_reason"]
    page = client.get("/dashboard")
    assert page.status_code == 200 and "DELIVERY TEST" in page.text and action in page.text
    assert "Calendar refresh: forexfactory" in page.text
    assert client.get(f"/dashboard/setups/{fresh_setup_payload['setup_id']}").status_code == 200
    assert client.get("/status").json()["news_refresh"]["enabled"] is True
    assert client.put("/context/news-calendar", json=value.calendar.model_dump(mode="json")).status_code == 409


def test_unsupported_symbol_and_expired_coverage_never_clear(client, monkeypatch):
    monkeypatch.setattr("app.news_refresh.fetch_snapshot", lambda *_: parse())
    CalendarRefreshWorker(settings()).run_once(NOW)
    with SessionLocal() as db:
        assert calendar_context(db, "UNKNOWN", NOW, settings())["status"] == "UNKNOWN"
        end = utc(db.get(CalendarCoverageRecord, 1).coverage_end)
        assert calendar_context(db, "NQ", end, settings())["status"] == "UNKNOWN"


def test_refresh_is_opt_in(client, monkeypatch):
    monkeypatch.setattr("app.news_refresh.fetch_snapshot", lambda *_: pytest.fail("Unexpected network"))
    assert not CalendarRefreshWorker(get_settings()).run_once()
    assert client.app.state.calendar_worker is None


@pytest.mark.parametrize("status,content_type", [(302, "application/json"), (429, "application/json"),
    (503, "application/json"), (200, "text/html")])
def test_transport_rejects_redirect_error_and_html(monkeypatch, status, content_type):
    client_type = httpx.Client
    transport = httpx.MockTransport(lambda _: httpx.Response(status, headers={"content-type": content_type}, content=b"[]"))
    monkeypatch.setattr("app.news_refresh.httpx.Client", lambda **kwargs: client_type(transport=transport, **kwargs))
    with pytest.raises((CalendarFeedError, httpx.HTTPStatusError)):
        fetch_snapshot(NOW, settings())


def test_transport_reads_publisher_timestamp_and_fixed_host(monkeypatch):
    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(200, headers={"content-type": "application/json", "last-modified": format_datetime(NOW)},
                              json=feed())
    client_type = httpx.Client
    monkeypatch.setattr("app.news_refresh.httpx.Client", lambda **kwargs: client_type(transport=httpx.MockTransport(respond), **kwargs))
    assert fetch_snapshot(NOW, settings()).modified_at == NOW
    assert requests[0].url.host == "nfs.faireconomy.media"
    assert "authorization" not in requests[0].headers


def test_auto_worker_starts_and_stops_with_app(client, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    calls = []
    class Worker:
        def __init__(self, settings): assert settings.news_provider == "forexfactory"
        def start(self): calls.append("start")
        def stop(self): calls.append("stop")
    monkeypatch.setenv("NEWS_PROVIDER", "forexfactory")
    monkeypatch.setenv("REQUIRE_VERIFIED_NEWS", "true")
    get_settings.cache_clear()
    monkeypatch.setattr("app.main.CalendarRefreshWorker", Worker)
    with TestClient(app) as nested:
        assert nested.get("/health").status_code == 200
        assert calls == ["start"]
    assert calls == ["start", "stop"]
