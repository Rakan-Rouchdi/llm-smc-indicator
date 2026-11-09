import pytest

from app.config import get_settings
from app.database import SessionLocal
from app.models import LLMDecisionRecord, SetupAlertRecord
from scripts.preview_mvp import SCENARIOS, preview_environment, seed_preview


def test_preview_settings_neutralize_external_credentials(tmp_path):
    env = preview_environment(tmp_path / "preview.db")
    assert env["LLM_PROVIDER"] == "mock" and env["OPENAI_API_KEY"] == ""
    assert env["ENABLE_NOTIFICATIONS"] == "false" and env["TELEGRAM_BOT_TOKEN"] == ""
    assert env["NEWS_PROVIDER"] == "manual" and env["DECISION_WORKER_ENABLED"] == "false"
    assert len(env["WEBHOOK_SECRET"]) >= 32
    assert str(tmp_path) in env["DATABASE_URL"]


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_preview_cases_render_and_never_notify(client, scenario):
    seed_preview(scenario, get_settings().model_copy(update={"require_verified_news": True}))
    with SessionLocal() as db:
        assert db.query(SetupAlertRecord).count() == 4
        rows = db.query(LLMDecisionRecord).all()
        assert len(rows) == 4
        for row in rows:
            assert row.final_action == ("BUY" if "_approved_" in row.setup_id else "NO_TRADE")
    latest = client.get("/decisions/latest").json()["decision"]
    assert f"_{scenario}_" in latest["setup_id"]
    assert client.get("/notifications").json() == {"notifications": []}
    page = client.get("/dashboard")
    assert page.status_code == 200 and "DELIVERY TEST" in page.text
    assert f"local_preview_{scenario}_" in page.text
    detail = client.get(f"/dashboard/setups/{latest['setup_id']}")
    assert detail.status_code == 200 and "DELIVERY TEST" in detail.text


def test_preview_rejects_live_provider(client):
    settings = get_settings().model_copy(update={"llm_provider": "openai"})
    with pytest.raises(ValueError):
        seed_preview("approved", settings)
