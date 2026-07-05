from datetime import datetime, timezone
from typing import Any, Protocol


class NewsAdapter(Protocol):
    def build_context(self, symbol: str, current_time: datetime | None = None) -> dict[str, Any]:
        ...


class TelegramAdapter(Protocol):
    def latest_summary(self) -> dict[str, Any] | None:
        ...


class MockNewsAdapter:
    def build_context(self, symbol: str, current_time: datetime | None = None) -> dict[str, Any]:
        now = current_time or datetime.now(timezone.utc)
        return {
            "blackout_active": False,
            "headline_summary": "Mock news context; no live news integration configured.",
            "market_bias": "NEUTRAL",
            "high_impact_event_name": None,
            "minutes_to_event": None,
            "active_events": [],
            "recent_headlines": [],
            "current_time": now.isoformat(),
            "symbol": symbol,
        }


class MockTelegramAdapter:
    def latest_summary(self) -> dict[str, Any] | None:
        return {
            "bullish_count": 0,
            "bearish_count": 0,
            "neutral_count": 0,
            "source_count": 0,
            "summary": "Mock Telegram context; no live Telegram integration configured.",
        }


def build_context(symbol: str, current_time: datetime | None = None) -> dict[str, Any]:
    news = MockNewsAdapter().build_context(symbol, current_time=current_time)
    telegram = MockTelegramAdapter().latest_summary()
    return {
        "symbol": symbol,
        "current_time": news["current_time"],
        "news": news,
        "telegram": telegram,
        # Backward-compatible aliases used by the validator and older tests.
        "news_blackout_active": news["blackout_active"],
        "telegram_summary": telegram,
    }
