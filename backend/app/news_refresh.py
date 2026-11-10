"""Bounded public-calendar ingestion, separate from webhook acknowledgement/LLM work."""

import hashlib
import json
import logging
import threading
import time as clock
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, TypeAdapter
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app.config import AUTO_NEWS_PROVIDERS, Settings
from app.database import SessionLocal
from app.models import CalendarRefreshRecord, CalendarRefreshSchedule
from app.news import SOURCE_PREFIXES, max_calendar_age_hours, replace_calendar, utc
from app.schemas import CalendarEvent, CalendarUpdate

logger = logging.getLogger(__name__)
FEED_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
SHOWMYTRADES_URL = "https://showmytrades.com/api/public/calendar/v1?currency=USD&impact=all&days=7"
# Reuse the additive tables, but do not inherit another provider's cooldown,
# publication version or success. Existing Forex Factory installations keep id=1.
PROVIDER_IDS = {"forexfactory": 1, "showmytrades": 2}
MAX_BYTES = 2 * 1024 * 1024
NEW_YORK = ZoneInfo("America/New_York")


class CalendarFeedError(ValueError):
    """Only fixed diagnostic codes, never response bodies or request URLs."""

    def __init__(self, code: str, retry_at: datetime | None = None):
        super().__init__(code)
        self.retry_at = retry_at


def retry_after(value: str | None, now: datetime) -> datetime | None:
    """Honor both standard Retry-After forms without retaining untrusted headers."""
    if not value or len(value) > 128:
        return None
    value = value.strip()
    try:
        if value.isascii() and value.isdecimal():
            at = now + timedelta(seconds=int(value))
        else:
            at = parsedate_to_datetime(value)
            if at.tzinfo is None:
                return None
            at = at.astimezone(timezone.utc)
        return at if at > now else None
    except (TypeError, ValueError, OverflowError):
        return None


class FeedEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = Field(min_length=1, max_length=255)
    country: str = Field(pattern=r"^[A-Z]{3}$")
    date: AwareDatetime
    impact: Literal["High", "Medium", "Low", "Holiday", "Non-Economic"]


class RollingEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    currency: Literal["USD"]
    time: AwareDatetime
    ts: int = Field(strict=True)
    impact: Literal["high", "medium", "low", "holiday"]
    status: Literal["scheduled", "moved", "tentative"]
    confidence: Literal["official", "sources_agree", "single_source", "sources_disagree"]
    moved_from: str


class RollingCalendar(BaseModel):
    model_config = ConfigDict(extra="ignore")
    generated_at: AwareDatetime
    start: AwareDatetime = Field(alias="from")
    end: AwareDatetime = Field(alias="to")
    count: int = Field(strict=True, ge=1, le=500)
    events: list[RollingEvent] = Field(min_length=1, max_length=500)


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


def parse_rolling_snapshot(body: bytes, now: datetime, settings: Settings) -> FeedSnapshot:
    if len(body) > MAX_BYTES:
        raise CalendarFeedError("response_too_large")
    feed = RollingCalendar.model_validate_json(body)
    published = feed.generated_at.astimezone(timezone.utc)
    # server_time and HTTP Date are request clocks, NOT calendar freshness.
    # generated_at is publisher assembly time, not proof every upstream is live.
    if not 0 <= (now - published).total_seconds() < max_calendar_age_hours(settings) * 3600:
        raise CalendarFeedError("stale_or_future_publisher_timestamp")
    if feed.count != len(feed.events):
        raise CalendarFeedError("incomplete_event_list")
    if feed.start != published - timedelta(hours=6) or feed.end != published + timedelta(days=7):
        raise CalendarFeedError("unexpected_coverage_window")
    start = feed.start + timedelta(minutes=settings.default_blackout_minutes_after)
    end = feed.end - timedelta(minutes=settings.default_blackout_minutes_before)
    if not start <= now < end:
        raise CalendarFeedError("coverage_gap")
    events, identities = [], set()
    for row in feed.events:
        at = row.time.astimezone(timezone.utc)
        if at.timestamp() != row.ts or not feed.start <= at <= feed.end:
            raise CalendarFeedError("inconsistent_event_time")
        if row.id in identities:
            raise CalendarFeedError("duplicate_event")
        identities.add(row.id)
        if row.status == "tentative" or row.confidence == "sources_disagree":
            raise CalendarFeedError("ambiguous_event_schedule")
        if row.status == "moved":
            previous = TypeAdapter(AwareDatetime).validate_python(row.moved_from)
            if previous == at:
                raise CalendarFeedError("invalid_rescheduled_event")
        elif row.moved_from:
            raise CalendarFeedError("invalid_rescheduled_event")
        fed = row.title.casefold().startswith(("fed ", "fed's ", "fomc", "federal reserve"))
        # Provider impact scales differ. Block MEDIUM as well as HIGH rather than
        # downgrade e.g. claims that the previous provider rated HIGH.
        impact = "HIGH" if row.impact in {"high", "medium"} or fed else "LOW"
        if impact == "HIGH" and at.astimezone(NEW_YORK).time() == time():
            raise CalendarFeedError("ambiguous_blocking_event_time")
        events.append(CalendarEvent(
            event_id="smt-" + hashlib.sha256(row.id.encode()).hexdigest()[:32],
            title=row.title, event_time=at, impact=impact, symbols=["ES", "NQ"],
            blackout_minutes_before=settings.default_blackout_minutes_before,
            blackout_minutes_after=settings.default_blackout_minutes_after,
        ))
    calendar = CalendarUpdate(
        source=SOURCE_PREFIXES["showmytrades"] + " high/medium and Fed appearances blocked; publisher assembly timestamp",
        coverage_start=start, coverage_end=end, events=events,
    )
    # Exclude volatile response clocks so an unchanged publication is not a
    # version conflict merely because it was downloaded at a different time.
    digest = hashlib.sha256(calendar.model_dump_json().encode()).hexdigest()
    return FeedSnapshot(calendar, published, digest)


def fetch_snapshot(now: datetime, settings: Settings) -> FeedSnapshot:
    # A fixed official export URL avoids arbitrary-URL/credential forwarding.
    # Redirects, HTML challenges and errors fail closed; no browser scraping.
    with httpx.Client(timeout=settings.news_fetch_timeout_seconds, follow_redirects=False) as client:
        started = clock.monotonic()
        deadline = started + settings.news_fetch_timeout_seconds * 2
        url = SHOWMYTRADES_URL if settings.news_provider == "showmytrades" else FEED_URL
        with client.stream("GET", url, headers={"Accept": "application/json"}) as response:
            if response.status_code != 200:
                # Preserve the actionable status, never the response body or URL.
                received_at = now + timedelta(seconds=clock.monotonic() - started)
                raise CalendarFeedError(f"publisher_http_{response.status_code}",
                                        retry_after(response.headers.get("retry-after"), received_at))
            if "application/json" not in response.headers.get("content-type", ""):
                raise CalendarFeedError("unexpected_feed_response")
            body = bytearray()
            for chunk in response.iter_bytes():
                if clock.monotonic() > deadline:
                    raise CalendarFeedError("feed_download_deadline")
                body.extend(chunk)
                if len(body) > MAX_BYTES:
                    raise CalendarFeedError("response_too_large")
            if settings.news_provider == "showmytrades":
                return parse_rolling_snapshot(bytes(body), now, settings)
            return parse_snapshot(bytes(body), response.headers.get("last-modified"), now, settings)


class CalendarRefreshWorker:
    """A database claim serializes fetches across restarts and overlapping deploys."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.provider_id = PROVIDER_IDS.get(settings.news_provider)
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._run, name="calendar-refresh", daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self._stop.set()
        self.thread.join(timeout=self.settings.news_fetch_timeout_seconds + 2)

    def run_once(self, now: datetime | None = None) -> bool:
        if self.settings.news_provider not in AUTO_NEWS_PROVIDERS:
            return False
        now = now or datetime.now(timezone.utc)
        interval = timedelta(minutes=self.settings.news_refresh_interval_minutes)
        attempt_id = uuid4().hex
        with SessionLocal() as db:
            # A separate additive table also upgrades existing PostgreSQL installs.
            # Seed from the previous worker's cooldown rather than fetching on deploy.
            if db.get(CalendarRefreshSchedule, self.provider_id) is None:
                previous = db.get(CalendarRefreshRecord, self.provider_id)
                failed = bool(previous and previous.last_error)
                due = utc(previous.last_attempt_at) + interval * (2 if failed else 1) if previous else now
                db.add(CalendarRefreshSchedule(id=self.provider_id, next_attempt_at=due,
                                              consecutive_failures=int(failed)))
                try:
                    db.commit()
                except IntegrityError:
                    db.rollback()  # Another instance initialized the singleton.
            claimed = db.execute(update(CalendarRefreshSchedule).where(
                CalendarRefreshSchedule.id == self.provider_id,
                CalendarRefreshSchedule.next_attempt_at <= now,
            ).values(next_attempt_at=now + interval, attempt_id=attempt_id))
            if claimed.rowcount != 1:
                db.rollback()
                return False
            state = db.get(CalendarRefreshRecord, self.provider_id)
            state = state or CalendarRefreshRecord(id=self.provider_id)
            state.last_attempt_at = now
            db.add(state)
            db.commit()
        try:
            snapshot = fetch_snapshot(now, self.settings)
            with SessionLocal() as db:
                # Conditional UPDATE locks the claim on both SQLite and PostgreSQL.
                owned = db.execute(update(CalendarRefreshSchedule).where(
                    CalendarRefreshSchedule.id == self.provider_id,
                    CalendarRefreshSchedule.attempt_id == attempt_id,
                ).values(attempt_id=None, consecutive_failures=0, next_attempt_at=now + interval))
                if owned.rowcount != 1:
                    return True  # A later lease owns the result; discard this one.
                state = db.get(CalendarRefreshRecord, self.provider_id, with_for_update=True)
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
                owned = db.execute(update(CalendarRefreshSchedule).where(
                    CalendarRefreshSchedule.id == self.provider_id,
                    CalendarRefreshSchedule.attempt_id == attempt_id,
                ).values(attempt_id=None))
                if owned.rowcount != 1:
                    return True
                schedule = db.get(CalendarRefreshSchedule, self.provider_id)
                schedule.consecutive_failures += 1
                delay = interval * 2 ** min(schedule.consecutive_failures, 3)
                due = now + delay
                if isinstance(exc, CalendarFeedError) and exc.retry_at:
                    due = max(due, exc.retry_at)
                schedule.next_attempt_at = due
                state = db.get(CalendarRefreshRecord, self.provider_id)
                state.last_error = code
                db.commit()
            # Retain the last good snapshot without extending its freshness.
        return True

    def seconds_until_due(self, now: datetime | None = None) -> float:
        now = now or datetime.now(timezone.utc)
        with SessionLocal() as db:
            schedule = db.get(CalendarRefreshSchedule, self.provider_id) if self.provider_id else None
            return max(1, (utc(schedule.next_attempt_at) - now).total_seconds()) if schedule else 60

    def _run(self):
        while not self._stop.is_set():
            try:
                self.run_once()
                delay = self.seconds_until_due()
            except Exception as exc:
                logger.error("calendar_refresh_unavailable error_type=%s", type(exc).__name__)
                delay = 60
            # Recheck durable state at least hourly; very distant HTTP dates must
            # not overflow the platform's threading timeout or hide another worker.
            self._stop.wait(min(delay, 3600))


def refresh_status(db, settings: Settings) -> dict:
    provider_id = PROVIDER_IDS.get(settings.news_provider)
    state = db.get(CalendarRefreshRecord, provider_id) if provider_id else None
    schedule = db.get(CalendarRefreshSchedule, provider_id) if provider_id else None
    return {
        "enabled": settings.news_provider in AUTO_NEWS_PROVIDERS,
        "provider": settings.news_provider,
        "interval_minutes": settings.news_refresh_interval_minutes,
        "last_attempt_at": utc(state.last_attempt_at).isoformat() if state else None,
        "last_success_at": utc(state.last_success_at).isoformat() if state and state.last_success_at else None,
        "source_modified_at": utc(state.source_modified_at).isoformat() if state and state.source_modified_at else None,
        "last_error": state.last_error if state else None,
        "next_attempt_at": utc(schedule.next_attempt_at).isoformat() if schedule else None,
        "consecutive_failures": schedule.consecutive_failures if schedule else 0,
    }
