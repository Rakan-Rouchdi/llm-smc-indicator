"""Bounded calendar coverage; missing, unsupported or stale data is never clear."""

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, true
from sqlalchemy.orm import Session

from app.config import AUTO_NEWS_PROVIDERS, Settings
from app.models import CalendarCoverageRecord, NewsEventRecord
from app.schemas import CalendarUpdate

SOURCE_PREFIXES = {"forexfactory": "Forex Factory weekly export;",
                   "showmytrades": "ShowMyTrades USD calendar;"}


def max_calendar_age_hours(settings: Settings) -> int:
    # A rolling aggregator publication has a shorter safety lifetime than a
    # manually checked calendar. Configuration may tighten, never extend it.
    return min(settings.news_max_age_hours, 2) if settings.news_provider == "showmytrades" else settings.news_max_age_hours


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def replace_calendar(db: Session, payload: CalendarUpdate, now: datetime, *,
                     verified_at: datetime | None = None, commit: bool = True) -> None:
    if not payload.coverage_start <= now <= payload.coverage_end:
        raise ValueError("Coverage must include the verification time")
    verified_at = verified_at or now
    if verified_at > now:
        raise ValueError("Calendar verification cannot be in the future")
    # A complete snapshot and its coverage are committed together; no partial clear window.
    db.query(NewsEventRecord).delete()
    for event in payload.events:
        values = event.model_dump(exclude={"symbols"})
        db.add(NewsEventRecord(**values, symbols_json=json.dumps(event.symbols)))
    db.merge(CalendarCoverageRecord(id=1, source=payload.source,
        coverage_start=payload.coverage_start, coverage_end=payload.coverage_end, verified_at=verified_at))
    if commit:
        db.commit()


def calendar_context(db: Session, symbol: str, now: datetime, settings: Settings) -> dict:
    # Read coverage and events in one statement so refresh cannot mix two versions
    # under PostgreSQL's READ COMMITTED isolation.
    rows = db.execute(select(CalendarCoverageRecord, NewsEventRecord).outerjoin(
        NewsEventRecord, true()).where(CalendarCoverageRecord.id == 1)).all()
    coverage = rows[0][0] if rows else None
    provider = next((key for key, prefix in SOURCE_PREFIXES.items()
                     if coverage and coverage.source.startswith(prefix)), "manual")
    automated = provider in AUTO_NEWS_PROVIDERS
    max_age = max_calendar_age_hours(settings)
    # Switching providers (including rollback to manual) requires a matching
    # snapshot; a setting change is not verification of the old provider's data.
    matches_provider = (provider == settings.news_provider or
                        (not automated and settings.news_provider not in AUTO_NEWS_PROVIDERS))
    valid = bool(symbol in {"ES", "NQ"} and coverage
                 and matches_provider
                 and utc(coverage.coverage_start) <= now < utc(coverage.coverage_end)
                 and 0 <= (now - utc(coverage.verified_at)).total_seconds() < max_age * 3600)
    active, relevant = [], []
    if valid:
        for _, event in rows:
            if event is None:
                continue
            if symbol not in json.loads(event.symbols_json) or event.impact != "HIGH":
                continue
            at = utc(event.event_time)
            item = {"event_id": event.event_id, "title": event.title, "event_time": at.isoformat(),
                    "minutes_to_event": round((at - now).total_seconds() / 60, 2)}
            if at >= now:
                relevant.append(item)
            if at - timedelta(minutes=event.blackout_minutes_before) <= now <= at + timedelta(minutes=event.blackout_minutes_after):
                active.append(item)
    nearest = min(active or relevant, key=lambda item: abs(item["minutes_to_event"]), default=None)
    state = "UNKNOWN" if not valid else "BLACKOUT" if active else "CLEAR"
    return {"provider": provider, "status": state, "blackout_active": bool(active),
            "headline_summary": ("Published scheduled USD calendar; not a guarantee of completeness" if automated else "Verified manual calendar")
                if valid else "Calendar coverage missing, stale or unsupported",
            "market_bias": "NEUTRAL", "high_impact_event_name": nearest["title"] if nearest else None,
            "minutes_to_event": nearest["minutes_to_event"] if nearest else None,
            "active_events": active, "recent_headlines": [], "symbol": symbol,
            "current_time": now.isoformat(), "source": coverage.source if coverage else None,
            "verified_at": utc(coverage.verified_at).isoformat() if coverage else None,
            "fresh_until": min(utc(coverage.coverage_end), utc(coverage.verified_at)
                + timedelta(hours=max_age)).isoformat() if coverage else None,
            "coverage_end": utc(coverage.coverage_end).isoformat() if coverage else None}
