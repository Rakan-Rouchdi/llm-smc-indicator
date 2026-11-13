"""Isolated, disposable UI fixtures. No .env loading, external calls or live alerts."""

import argparse
import json
import os
import secrets
import sys
import tempfile
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
SCENARIOS = ("approved", "blackout", "stale", "gold")


def preview_environment(database_path: Path) -> dict[str, str]:
    return {
        "APP_ENV": "development", "DATABASE_URL": f"sqlite:///{database_path}",
        "WEBHOOK_SECRET": secrets.token_urlsafe(32), "DASHBOARD_USERNAME": "", "DASHBOARD_PASSWORD": "",
        "LLM_PROVIDER": "mock", "OPENAI_API_KEY": "", "NEWS_PROVIDER": "manual",
        "REQUIRE_VERIFIED_NEWS": "true", "NEWS_MAX_AGE_HOURS": "24",
        "ENABLE_NOTIFICATIONS": "false", "NOTIFICATION_WEBHOOK_URL": "", "TELEGRAM_BOT_TOKEN": "",
        "OUTCOME_TRACKING_ENABLED": "false", "OUTCOME_FEED_ID": "",
        "TELEGRAM_CHAT_ID": "", "DECISION_WORKER_ENABLED": "false",
        "MIN_RULE_SCORE": "75", "CONFIRMATION_MAX_BARS": "6", "MAX_SETUP_AGE_MINUTES": "15",
    }


def seed_preview(latest: str, settings, now: datetime | None = None):
    from app.database import SessionLocal
    from app.news import replace_calendar
    from app.schemas import CalendarUpdate
    from app.workflow import process_tradingview_alert

    if (latest not in SCENARIOS or settings.llm_provider != "mock" or settings.enable_notifications
            or not settings.require_verified_news):
        raise ValueError("Preview requires mock mode, verified-news gating, notifications disabled and a known scenario")
    now = now or datetime.now(timezone.utc)
    template = json.loads((BACKEND.parent / "examples/pine_alert_payload_example.json").read_text())
    for case in [name for name in SCENARIOS if name != latest] + [latest]:
        payload = deepcopy(template)
        payload.update(setup_id=f"local_preview_{case}_{now.strftime('%Y%m%dT%H%M%S%f')}",
                       bar_time=(now-timedelta(minutes=5)).isoformat())
        payload["diagnostics"].update(test_mode=True, bar_close_time=now.isoformat(),
            notes="LOCAL UI FIXTURE. Synthetic prices; not a market signal or TradingView delivery.")
        if case == "gold":
            payload.update(symbol="OANDA:XAUUSD", root_symbol="UNKNOWN")
        status = "BLACKOUT" if case == "blackout" else "UNKNOWN" if case in {"stale", "gold"} else "CLEAR"
        context = {"symbol": payload["root_symbol"], "current_time": now.isoformat(), "news": {
            "provider": "preview-fixture", "status": status, "blackout_active": case == "blackout",
            "headline_summary": "Synthetic closed-market UI fixture", "market_bias": "NEUTRAL",
        }, "telegram": {"summary": "Synthetic UI fixture; no external context"}}
        with SessionLocal() as db:
            process_tradingview_alert(payload, db, settings, current_time=now, context_override=context)
    events = [] if latest != "blackout" else [{"event_id": "preview-news", "title": "Synthetic blackout",
        "event_time": now, "impact": "HIGH", "symbols": ["ES", "NQ"]}]
    calendar = CalendarUpdate(source="LOCAL PREVIEW synthetic calendar, not verified market news",
        coverage_start=now-timedelta(days=2), coverage_end=now+timedelta(days=2), events=events)
    with SessionLocal() as db:
        replace_calendar(db, calendar, now, verified_at=now-timedelta(hours=25) if latest == "stale" else now)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8012)
    parser.add_argument("--scenario", choices=SCENARIOS, default="approved")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Choose a port between 1024 and 65535")
    with tempfile.TemporaryDirectory(prefix="smc-ui-preview-") as directory:
        os.environ.update(preview_environment(Path(directory) / "preview.db"))
        from app.config import Settings, get_settings
        # Explicitly bypass both local .env files; inherited credentials are blanked above.
        Settings.model_config["env_file"] = None
        get_settings.cache_clear()
        from app.database import init_db
        init_db()
        seed_preview(args.scenario, get_settings())
        import uvicorn
        print(f"LOCAL SYNTHETIC PREVIEW: http://127.0.0.1:{args.port}/dashboard", flush=True)
        uvicorn.run("app.main:app", host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
