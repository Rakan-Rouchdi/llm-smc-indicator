"""Synthetic feed fixtures; no network, live calendar ingestion or OpenAI calls."""

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.database import SessionLocal
from app.models import CalendarCoverageRecord, CalendarRefreshRecord, CalendarRefreshSchedule
from app.news import calendar_context, utc
from app.news_refresh import CalendarFeedError, CalendarRefreshWorker, fetch_snapshot, parse_rolling_snapshot
from app.worker import DecisionWorker

NOW = datetime(2026, 11, 10, 17, tzinfo=timezone.utc)


def settings(**kwargs):
    return Settings(_env_file=None, news_provider="showmytrades", require_verified_news=True, **kwargs)


def feed(now=NOW):
    published = now - timedelta(minutes=5)
    at = (now + timedelta(hours=1)).replace(microsecond=0)
    return {"generated_at": published.isoformat(), "server_time": int(now.timestamp()),
            "from": (published-timedelta(hours=6)).isoformat(),
            "to": (published+timedelta(days=7)).isoformat(), "count": 1,
            "events": [{"id": "synthetic-speech", "title": "Fed's Test speech", "currency": "USD",
                        "time": at.isoformat(), "ts": int(at.timestamp()), "impact": "low",
                        "status": "scheduled", "confidence": "single_source", "moved_from": ""}]}


def parse(payload=None, now=NOW):
    return parse_rolling_snapshot(json.dumps(payload or feed(now)).encode(), now, settings())


def test_publication_timestamp_conservative_scope_and_clock_independent_digest():
    payload = feed()
    result = parse(payload)
    assert result.modified_at == NOW-timedelta(minutes=5)
    assert result.calendar.events[0].impact == "HIGH"
    assert result.calendar.events[0].symbols == ["ES", "NQ"]
    assert result.calendar.coverage_start == NOW-timedelta(hours=5, minutes=35)
    payload["server_time"] += 60
    assert parse(payload).digest == result.digest


@pytest.mark.parametrize("impact", ["high", "medium", "low", "holiday"])
def test_provider_impact_scale_never_downgrades_medium(impact):
    payload = feed()
    payload["events"][0].update(title="Synthetic release", impact=impact)
    expected = "HIGH" if impact in {"high", "medium"} else "LOW"
    assert parse(payload).calendar.events[0].impact == expected


@pytest.mark.parametrize("field,value", [
    ("generated_at", None), ("generated_at", "2026-11-10T17:00:01Z"),
    ("generated_at", "2026-11-10T15:00:00Z"), ("generated_at", "2026-11-10T17:00:00"),
    ("count", 2), ("count", 0), ("events", []),
    ("from", "2026-11-10T17:00:00Z"), ("to", "2026-11-11T17:00:00Z"),
])
def test_invalid_stale_future_or_incomplete_publication_rejected(field, value):
    payload = feed(); payload[field] = value
    with pytest.raises(ValueError):
        parse(payload)


@pytest.mark.parametrize("field,value", [
    ("time", "2026-11-10T18:00:00"), ("ts", 0), ("currency", "EUR"),
    ("status", "tentative"), ("status", "cancelled"), ("confidence", "sources_disagree"),
    ("confidence", "unknown"), ("moved_from", "2026-11-10T14:00:00Z"),
    ("status", "moved"), ("impact", "unknown"), ("title", ""),
])
def test_uncertain_or_inconsistent_event_rejected(field, value):
    payload = feed(); payload["events"][0][field] = value
    with pytest.raises(ValueError):
        parse(payload)


def test_moved_time_is_used_and_duplicates_rejected():
    payload = feed()
    payload["events"][0].update(status="moved", moved_from="2026-11-11T18:00:00Z")
    assert parse(payload).calendar.events[0].event_time == NOW+timedelta(hours=1)
    payload["events"] *= 2
    payload["count"] = 2
    with pytest.raises(CalendarFeedError, match="duplicate"):
        parse(payload)


def test_blocking_midnight_and_out_of_window_are_not_precise_times():
    for at in (datetime(2026, 11, 11, 5, tzinfo=timezone.utc), NOW+timedelta(days=8)):
        payload = feed()
        payload["events"][0].update(time=at.isoformat(), ts=int(at.timestamp()))
        with pytest.raises(CalendarFeedError):
            parse(payload)


def test_freshness_gate_cannot_be_disabled():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, news_provider="showmytrades", require_verified_news=False)


def test_transport_fixed_public_endpoint_no_credentials(monkeypatch):
    seen = []
    def response(request):
        seen.append(request)
        return httpx.Response(200, headers={"content-type": "application/json"}, json=feed())
    client_type = httpx.Client
    monkeypatch.setattr("app.news_refresh.httpx.Client", lambda **kw: client_type(transport=httpx.MockTransport(response), **kw))
    assert fetch_snapshot(NOW, settings()).modified_at == NOW-timedelta(minutes=5)
    assert seen[0].url.host == "showmytrades.com"
    assert dict(seen[0].url.params) == {"currency": "USD", "impact": "all", "days": "7"}
    assert "authorization" not in seen[0].headers


@pytest.mark.parametrize("published_after_start,accepted", [(2, True), (10, False), (-7200, False)])
def test_transport_uses_receipt_time_without_future_or_stale_tolerance(monkeypatch, published_after_start, accepted):
    payload = feed(NOW+timedelta(seconds=published_after_start, minutes=5))
    ticks = iter([0.0, 3.0, 3.0])
    monkeypatch.setattr("app.news_refresh.clock.monotonic", lambda: next(ticks))
    client_type = httpx.Client
    transport = httpx.MockTransport(lambda _: httpx.Response(200, headers={"content-type": "application/json"}, json=payload))
    monkeypatch.setattr("app.news_refresh.httpx.Client", lambda **kw: client_type(transport=transport, **kw))
    if accepted:
        assert fetch_snapshot(NOW, settings()).modified_at == NOW+timedelta(seconds=2)
    else:
        with pytest.raises(CalendarFeedError, match="stale_or_future"):
            fetch_snapshot(NOW, settings())


def test_provider_switch_isolated_state_and_stale_block_survives_restart(client, monkeypatch):
    with SessionLocal() as db:
        db.add(CalendarRefreshSchedule(id=1, next_attempt_at=NOW+timedelta(hours=8), consecutive_failures=4))
        db.add(CalendarRefreshRecord(id=1, last_attempt_at=NOW, last_error="publisher_http_429"))
        db.commit()
    monkeypatch.setattr("app.news_refresh.fetch_snapshot", lambda *_: parse())
    assert CalendarRefreshWorker(settings()).run_once(NOW)
    assert not CalendarRefreshWorker(settings()).run_once(NOW+timedelta(minutes=1))
    with SessionLocal() as db:
        assert db.get(CalendarRefreshRecord, 1).last_error == "publisher_http_429"
        assert db.get(CalendarRefreshRecord, 2).last_error is None
        assert utc(db.get(CalendarCoverageRecord, 1).verified_at) == NOW-timedelta(minutes=5)
        assert calendar_context(db, "ES", NOW, settings())["status"] == "CLEAR"
        assert calendar_context(db, "NQ", NOW+timedelta(hours=1), settings())["status"] == "BLACKOUT"
        assert calendar_context(db, "ES", NOW+timedelta(hours=2), settings())["status"] == "UNKNOWN"
        # A rollback cannot silently relabel another provider's snapshot as verified.
        ff = Settings(_env_file=None, news_provider="forexfactory", require_verified_news=True)
        assert calendar_context(db, "ES", NOW, ff)["status"] == "UNKNOWN"


def test_failed_refresh_never_relabels_old_data_fresh(client, monkeypatch):
    monkeypatch.setattr("app.news_refresh.fetch_snapshot", lambda *_: parse())
    worker = CalendarRefreshWorker(settings())
    assert worker.run_once(NOW)
    def failed(*_):
        raise CalendarFeedError("publisher_http_503")
    monkeypatch.setattr("app.news_refresh.fetch_snapshot", failed)
    assert worker.run_once(NOW+timedelta(hours=1))
    with SessionLocal() as db:
        assert utc(db.get(CalendarCoverageRecord, 1).verified_at) == NOW-timedelta(minutes=5)
        assert calendar_context(db, "ES", NOW+timedelta(hours=2), settings())["status"] == "UNKNOWN"
        assert db.get(CalendarRefreshSchedule, 2).consecutive_failures == 1


@pytest.mark.parametrize("case,expected", [("clear", "BUY"), ("stale", "NO_TRADE"), ("blackout", "NO_TRADE")])
def test_new_feed_webhook_validator_dashboard_and_manual_lock(client, monkeypatch, fresh_setup_payload, case, expected):
    monkeypatch.setenv("NEWS_PROVIDER", "showmytrades")
    monkeypatch.setenv("REQUIRE_VERIFIED_NEWS", "true")
    get_settings.cache_clear()
    now = datetime.now(timezone.utc)
    payload = feed(now)
    if case == "blackout":
        at = now.replace(microsecond=0)
        payload["events"][0].update(time=at.isoformat(), ts=int(at.timestamp()))
    result = parse(payload, now)
    monkeypatch.setattr("app.news_refresh.fetch_snapshot", lambda *_: result)
    CalendarRefreshWorker(get_settings()).run_once(now)
    if case == "stale":
        with SessionLocal() as db:
            db.get(CalendarCoverageRecord, 1).verified_at = now-timedelta(hours=2)
            db.commit()
    if case != "clear":
        monkeypatch.setattr("app.workflow.get_llm_provider", lambda *_: pytest.fail("Blocked setup must skip LLM"))
    fresh_setup_payload["diagnostics"]["test_mode"] = True
    assert client.post("/webhook/tradingview?secret=test-secret", json=fresh_setup_payload).status_code == 202
    assert DecisionWorker(get_settings()).run_once()
    decision = client.get("/decisions/latest").json()["decision"]
    assert decision["final_action"] == expected
    assert "Calendar refresh: showmytrades" in client.get("/dashboard").text
    assert client.get("/status").json()["news_refresh"]["provider"] == "showmytrades"
    assert client.put("/context/news-calendar", json=result.calendar.model_dump(mode="json")).status_code == 409
