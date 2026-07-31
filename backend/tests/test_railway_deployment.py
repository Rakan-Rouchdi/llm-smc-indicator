from pathlib import Path

from app.config import Settings, get_settings


WEBHOOK_HEADERS = {"X-Webhook-Secret": "test-secret"}


def _set_dashboard_auth(monkeypatch) -> None:
    monkeypatch.setenv("DASHBOARD_USERNAME", "dashboard-test-user")
    monkeypatch.setenv("DASHBOARD_PASSWORD", "dashboard-test-password")
    get_settings.cache_clear()


def test_dashboard_requires_authentication_when_configured(
    client,
    fresh_setup_payload,
    monkeypatch,
):
    response = client.post(
        "/webhook/tradingview",
        json=fresh_setup_payload,
        headers=WEBHOOK_HEADERS,
    )
    assert response.status_code == 200

    _set_dashboard_auth(monkeypatch)

    unauthenticated = client.get("/dashboard")
    assert unauthenticated.status_code == 401
    assert unauthenticated.headers["www-authenticate"].startswith("Basic")

    invalid = client.get(
        "/dashboard",
        auth=("dashboard-test-user", "wrong-password"),
    )
    assert invalid.status_code == 401

    authenticated = client.get(
        "/dashboard",
        auth=("dashboard-test-user", "dashboard-test-password"),
    )
    assert authenticated.status_code == 200
    assert "SMC LLM Dashboard" in authenticated.text

    detail = client.get(
        f"/dashboard/setups/{fresh_setup_payload['setup_id']}",
        auth=("dashboard-test-user", "dashboard-test-password"),
    )
    assert detail.status_code == 200
    assert fresh_setup_payload["setup_id"] in detail.text


def test_dashboard_remains_available_without_auth_in_development(client):
    response = client.get("/dashboard")

    assert response.status_code == 200


def test_production_dashboard_is_unavailable_without_credentials(
    client,
    monkeypatch,
):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("DASHBOARD_USERNAME", raising=False)
    monkeypatch.delenv("DASHBOARD_PASSWORD", raising=False)
    get_settings.cache_clear()

    response = client.get("/dashboard")

    assert response.status_code == 503


def test_health_remains_public_when_dashboard_auth_is_enabled(client, monkeypatch):
    _set_dashboard_auth(monkeypatch)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_webhook_still_requires_its_own_secret(client, fresh_setup_payload):
    unauthorized = client.post("/webhook/tradingview", json=fresh_setup_payload)
    assert unauthorized.status_code == 401

    authorized = client.post(
        "/webhook/tradingview",
        json=fresh_setup_payload,
        headers=WEBHOOK_HEADERS,
    )
    assert authorized.status_code == 200


def test_railway_port_and_persistent_database_configuration(monkeypatch, tmp_path):
    monkeypatch.setenv("PORT", "9123")
    monkeypatch.setenv("APP_PORT", "8000")
    monkeypatch.setenv("DATABASE_URL", "sqlite:////data/smc_llm.db")

    settings = Settings(_env_file=None)

    assert settings.app_port == 9123
    assert settings.database_url == "sqlite:////data/smc_llm.db"

    data_directory = tmp_path / "data"
    data_directory.mkdir()
    database_path = data_directory / "smc_llm.db"
    database_url = f"sqlite:///{database_path}"

    from app.database import configure_database, reset_db

    configure_database(database_url)
    reset_db()

    assert Path(database_path).is_file()
