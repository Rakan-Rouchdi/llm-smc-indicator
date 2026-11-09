"""Hourly public-calendar ingestion, separate from webhook acknowledgement/LLM work."""

import hashlib
import json
import logging
import threading
import time as clock
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Literal
from zoneinfo import ZoneInfo

import httpx
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, TypeAdapter

from app.config import Settings
from app.database import SessionLocal
from app.models import CalendarRefreshRecord
from app.news import replace_calendar, utc
from app.schemas import CalendarEvent, CalendarUpdate

logger = logging.getLogger(__name__)
FEED_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
MAX_BYTES = 2 * 1024 * 1024
NEW_YORK = ZoneInfo("America/New_York")


class CalendarFeedError(ValueError):
    """Only fixed diagnostic codes, never response bodies or request URLs."""


class FeedEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = Field(min_length=1, max_length=255)
    country: str = Field(pattern=r"^[A-Z]{3}$")
    date: AwareDatetime
    impact: Literal["High", "Medium", "Low", "Holiday", "Non-Economic"]


@dataclass(frozen=True)
class FeedSnapshot:
    calendar: CalendarUpdate
    modified_at: datetime
    digest: str


def week_bounds(now: datetime) -> tuple[datetime, datetime]:
    # The publisher's weekly export is Sunday-Saturday in New York time.
    local = now.astimezone(NEW_YORK)
    sunday = local.date() - timedelta(days=(local.weekday() + 1) % 7)
    start = datetime.combine(sunday, time(), NEW_YORK)
    return start.astimezone(timezone.utc), (start + timedelta(days=7)).astimezone(timezone.utc)


def parse_snapshot(body: bytes, modified: str | None, now: datetime, settings: Settings) -> FeedSnapshot:
    if len(body) > MAX_BYTES:
        raise CalendarFeedError("response_too_large")
    if not modified:
        raise CalendarFeedError("missing_publisher_timestamp")
    try:
        modified_at = parsedate_to_datetime(modified)
        if modified_at.tzinfo is None:
            raise ValueError
        modified_at = modified_at.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        raise CalendarFeedError("invalid_publisher_timestamp") from None
    age = (now - modified_at).total_seconds()
    if not 0 <= age < settings.news_max_age_hours * 3600:
        raise CalendarFeedError("stale_or_future_publisher_timestamp")
    raw = json.loads(body)
    if not isinstance(raw, list) or not 1 <= len(raw) <= 2000:
        raise CalendarFeedError("empty_or_invalid_event_list")
    rows = TypeAdapter(list[FeedEvent]).validate_python(raw)
    start, end = week_bounds(now)
    if any(not start <= row.date < end for row in rows):
        raise CalendarFeedError("wrong_week_or_mixed_coverage")
    events, identities = [], set()
    for row in rows:
        if row.country != "USD":
            continue
        at = row.date.astimezone(timezone.utc)
        identity = f"{row.country}|{row.title}|{at.isoformat()}"
        if identity in identities:
            raise CalendarFeedError("duplicate_event")
        identities.add(identity)
        # Preserve the existing conservative policy for scheduled Fed appearances,
        # even when the publisher rates a speech Low/Medium.
        fed = row.title.startswith(("FOMC", "Fed "))
        impact = "HIGH" if fed else {"High": "HIGH", "Medium": "MEDIUM"}.get(row.impact, "LOW")
        if impact == "HIGH" and row.date.astimezone(NEW_YORK).time() == time():
            raise CalendarFeedError("ambiguous_blocking_event_time")
        events.append(CalendarEvent(
            event_id="ff-" + hashlib.sha256(identity.encode()).hexdigest()[:32],
            title=row.title, event_time=at, impact=impact, symbols=["ES", "NQ"],
            blackout_minutes_before=settings.default_blackout_minutes_before,
            blackout_minutes_after=settings.default_blackout_minutes_after,
        ))
    if not events:
        raise CalendarFeedError("missing_usd_coverage")
    # Without adjacent-week snapshots, do not certify the edges where a blackout
    # from the previous/next week's event could overlap this week.
    start += timedelta(minutes=settings.default_blackout_minutes_after)
    end -= timedelta(minutes=settings.default_blackout_minutes_before)
    if not start <= now < end:
        raise CalendarFeedError("week_boundary_coverage_gap")
    calendar = CalendarUpdate(
        source="Forex Factory weekly export; scheduled USD events; Fed appearances elevated to HIGH",
        coverage_start=start, coverage_end=end, events=events,
    )
    return FeedSnapshot(calendar, modified_at, hashlib.sha256(body).hexdigest())


def fetch_snapshot(now: datetime, settings: Settings) -> FeedSnapshot:
    # A fixed official export URL avoids arbitrary-URL/credential forwarding.
    # Redirects, HTML challenges and errors fail closed; no browser scraping.
    with httpx.Client(timeout=settings.news_fetch_timeout_seconds, follow_redirects=False) as client:
        deadline = clock.monotonic() + settings.news_fetch_timeout_seconds * 2
        with client.stream("GET", FEED_URL, headers={"Accept": "application/json"}) as response:
            if response.status_code != 200:
                # Preserve the actionable status, never the response body or URL.
                raise CalendarFeedError(f"publisher_http_{response.status_code}")
            if response.status_code != 200 or "application/json" not in response.headers.get("content-type", ""):
                raise CalendarFeedError("unexpected_feed_response")
            body = bytearray()
            for chunk in response.iter_bytes():
                if clock.monotonic() > deadline:
                    raise CalendarFeedError("feed_download_deadline")
                body.extend(chunk)
                if len(body) > MAX_BYTES:
                    raise CalendarFeedError("response_too_large")
            return parse_snapshot(bytes(body), response.headers.get("last-modified"), now, settings)


class CalendarRefreshWorker:
    """One refresher per service instance; durable cooldown survives restarts."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._run, name="calendar-refresh", daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self._stop.set()
        self.thread.join(timeout=self.settings.news_fetch_timeout_seconds + 2)

    def run_once(self, now: datetime | None = None) -> bool:
        if self.settings.news_provider != "forexfactory":
            return False
        now = now or datetime.now(timezone.utc)
        with SessionLocal() as db:
            state = db.get(CalendarRefreshRecord, 1)
            if state and 0 <= (now - utc(state.last_attempt_at)).total_seconds() < self.settings.news_refresh_interval_minutes * 60:
                return False
            state = state or CalendarRefreshRecord(id=1)
            state.last_attempt_at = now
            db.add(state)
            db.commit()
        try:
            snapshot = fetch_snapshot(now, self.settings)
            with SessionLocal() as db:
                state = db.get(CalendarRefreshRecord, 1, with_for_update=True)
                if state.source_modified_at:
                    previous = utc(state.source_modified_at)
                    if snapshot.modified_at < previous:
                        raise CalendarFeedError("publisher_timestamp_regressed")
                    if snapshot.modified_at == previous and snapshot.digest != state.content_sha256:
                        raise CalendarFeedError("publisher_version_conflict")
                # The publisher timestamp, NOT fetch time, controls freshness.
                # Events, coverage and successful refresh metadata commit atomically.
                replace_calendar(db, snapshot.calendar, now, verified_at=snapshot.modified_at, commit=False)
                state.last_success_at = now
                state.source_modified_at = snapshot.modified_at
                state.content_sha256 = snapshot.digest
                state.last_error = None
                db.commit()
            logger.info("calendar_refresh_succeeded events=%s", len(snapshot.calendar.events))
        except Exception as exc:
            code = str(exc) if isinstance(exc, CalendarFeedError) else type(exc).__name__
            logger.warning("calendar_refresh_failed error_type=%s", code)
            with SessionLocal() as db:
                state = db.get(CalendarRefreshRecord, 1)
                state.last_error = code
                db.commit()
            # Retain the last good snapshot without extending its freshness.
        return True

    def _run(self):
        while not self._stop.is_set():
            try:
                self.run_once()
            except Exception as exc:
                logger.error("calendar_refresh_unavailable error_type=%s", type(exc).__name__)
            self._stop.wait(self.settings.news_refresh_interval_minutes * 60)


def refresh_status(db, settings: Settings) -> dict:
    state = db.get(CalendarRefreshRecord, 1)
    return {
        "enabled": settings.news_provider == "forexfactory",
        "provider": settings.news_provider,
        "interval_minutes": settings.news_refresh_interval_minutes,
        "last_attempt_at": utc(state.last_attempt_at).isoformat() if state else None,
        "last_success_at": utc(state.last_success_at).isoformat() if state and state.last_success_at else None,
        "source_modified_at": utc(state.source_modified_at).isoformat() if state and state.source_modified_at else None,
        "last_error": state.last_error if state else None,
    }
