import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture
def valid_setup_payload() -> dict:
    return json.loads((PROJECT_ROOT / "examples" / "tradingview_webhook_example.json").read_text())


@pytest.fixture
def valid_buy_decision_payload() -> dict:
    return json.loads((PROJECT_ROOT / "examples" / "llm_decision_buy_example.json").read_text())


@pytest.fixture
def pine_alert_payload() -> dict:
    return json.loads((PROJECT_ROOT / "examples" / "pine_alert_payload_example.json").read_text())


@pytest.fixture
def fresh_setup_payload(valid_setup_payload) -> dict:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    valid_setup_payload["bar_time"] = now.isoformat().replace("+00:00", "Z")
    valid_setup_payload["setup_id"] = f"CME_MINI_ES1_5_{now.strftime('%Y%m%dT%H%M%SZ')}_pytest"
    return valid_setup_payload


@pytest.fixture
def client(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("MAX_SETUP_AGE_MINUTES", "60")

    from app.config import get_settings
    from app.database import configure_database, reset_db

    get_settings.cache_clear()
    configure_database(database_url)
    reset_db()

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client

    get_settings.cache_clear()
