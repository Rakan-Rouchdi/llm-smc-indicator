"""Pine bar_time is the bar OPEN; candidates are emitted on confirmed closes."""

from datetime import datetime, timedelta, timezone

from app.schemas import SetupAlert


def setup_timing(setup: SetupAlert, now: datetime) -> dict[str, object]:
    opened = setup.bar_time
    if opened.tzinfo is None:
        raise ValueError("Bar timestamp must include a timezone")
    # The deployed v13 indicator emits minute resolutions and an opening time.
    # Limit the compatibility calculation to the validated intraday timeframes.
    durations = {"5": 5, "15": 15, "60": 60, "240": 240}
    minutes = durations.get(setup.timeframe)
    if minutes is None:
        raise ValueError("Unsupported timeframe for candle-close calculation")
    closed = opened + timedelta(minutes=minutes)
    basis = "bar_open_plus_timeframe"
    explicit_close = setup.diagnostics.get("bar_close_time")
    if explicit_close is not None:
        closed = datetime.fromisoformat(str(explicit_close).replace("Z", "+00:00"))
        if closed.tzinfo is None or not opened < closed <= opened + timedelta(minutes=minutes):
            raise ValueError("Invalid candle-close timestamp")
        basis = "explicit_bar_close_time"
    return {
        "bar_open_time": opened.astimezone(timezone.utc).isoformat(),
        "bar_close_time": closed.astimezone(timezone.utc).isoformat(),
        "evaluated_at": now.astimezone(timezone.utc).isoformat(),
        "age_minutes": round((now - closed).total_seconds() / 60, 4),
        "basis": basis,
    }
