"""Verified manual calendar; missing coverage is UNKNOWN, never implicitly clear."""

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import CalendarCoverageRecord, NewsEventRecord
from app.schemas import CalendarUpdate


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def replace_calendar(db: Session, payload: CalendarUpdate, now: datetime) -> None:
    if not payload.coverage_start <= now <= payload.coverage_end:
        raise ValueError("Coverage must include the verification time")
    # A complete snapshot and its coverage are committed together; no partial clear window.
    db.query(NewsEventRecord).delete()
    for event in payload.events:
        values = event.model_dump(exclude={"symbols"})
        db.add(NewsEventRecord(**values, symbols_json=json.dumps(event.symbols)))
    db.merge(CalendarCoverageRecord(id=1, source=payload.source,
        coverage_start=payload.coverage_start, coverage_end=payload.coverage_end, verified_at=now))
    db.commit()


def calendar_context(db: Session, symbol: str, now: datetime, settings: Settings) -> dict:
    coverage = db.get(CalendarCoverageRecord, 1)
    valid = bool(coverage and utc(coverage.coverage_start) <= now <= utc(coverage.coverage_end)
                 and 0 <= (now - utc(coverage.verified_at)).total_seconds() <= settings.news_max_age_hours * 3600)
    active, relevant = [], []
    if valid:
        for event in db.query(NewsEventRecord).all():
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
    return {"provider": "manual", "status": state, "blackout_active": bool(active),
            "headline_summary": "Verified manual calendar" if valid else "Calendar coverage missing or stale",
            "market_bias": "NEUTRAL", "high_impact_event_name": nearest["title"] if nearest else None,
            "minutes_to_event": nearest["minutes_to_event"] if nearest else None,
            "active_events": active, "recent_headlines": [], "symbol": symbol,
            "current_time": now.isoformat(), "source": coverage.source if coverage else None,
            "verified_at": utc(coverage.verified_at).isoformat() if coverage else None,
            "coverage_end": utc(coverage.coverage_end).isoformat() if coverage else None}
