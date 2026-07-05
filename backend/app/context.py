from datetime import datetime, timezone
from typing import Any


class MockNewsAdapter:
    def build_context(self, symbol: str, current_time: datetime | None = None) -> dict[str, Any]:
        return {
            "news_blackout_active": False,
            "active_news_events": [],
            "recent_headlines": [],
            "current_time": (current_time or datetime.now(timezone.utc)).isoformat(),
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
    news["telegram_summary"] = MockTelegramAdapter().latest_summary()
    return news
