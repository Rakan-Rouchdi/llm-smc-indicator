import json
import logging
from uuid import uuid4

import httpx
import pytest

from app.config import Settings, get_settings
from app.database import SessionLocal
from app.models import LLMDecisionRecord, NotificationProbeRecord, NotificationRecord, SetupAlertRecord
from app.notification_probe import send_telegram_probe


@pytest.fixture
def probe_client(client, monkeypatch):
    for name, value in {"DASHBOARD_USERNAME": "operator", "DASHBOARD_PASSWORD": "test-password",
                        "REQUIRE_VERIFIED_NEWS": "true", "TELEGRAM_BOT_TOKEN": "synthetic-token",
                        "TELEGRAM_CHAT_ID": "12345"}.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    return client


AUTH = ("operator", "test-password")


def test_probe_authentication_and_input(probe_client, monkeypatch):
    monkeypatch.setattr("app.notification_probe.send_telegram_probe", lambda *_: pytest.fail("Unexpected send"))
    assert probe_client.post("/notifications/test", json={"test_id": str(uuid4())}).status_code == 401
    assert probe_client.post("/notifications/test", auth=AUTH, json={"test_id": "invalid"}).status_code == 422
    assert probe_client.post("/notifications/test", auth=AUTH, json={"test_id": str(uuid4()), "text": "BUY"}).status_code == 422
    assert probe_client.get(f"/notifications/tests/{uuid4()}").status_code == 401


def test_probe_sends_once_without_creating_decisions(probe_client, monkeypatch):
    sent = []
    monkeypatch.setattr("app.notification_probe.send_telegram_probe", lambda _, key: sent.append(key) or ("SENT", None))
    test_id = str(uuid4())
    response = probe_client.post("/notifications/test", auth=AUTH, json={"test_id": test_id})
    assert response.status_code == 200 and response.json()["status"] == "SENT"
    assert response.json()["kind"] == "TRANSPORT_TEST_ONLY"
    assert probe_client.post("/notifications/test", auth=AUTH, json={"test_id": test_id}).json()["status"] == "SENT"
    assert probe_client.post("/notifications/test", auth=AUTH, json={"test_id": str(uuid4())}).status_code == 429
    assert sent == [test_id]
    assert probe_client.get(f"/notifications/tests/{test_id}", auth=AUTH).json()["status"] == "SENT"
    with SessionLocal() as db:
        assert db.query(NotificationProbeRecord).count() == 1
        for model in (SetupAlertRecord, LLMDecisionRecord, NotificationRecord):
            assert db.query(model).count() == 0
    assert get_settings().require_verified_news is True
    assert get_settings().enable_notifications is False


def test_probe_timeout_is_unknown_and_never_retried(probe_client, monkeypatch):
    def timeout(*_):
        raise httpx.ReadTimeout("https://api.telegram.org/botprivate-token/sendMessage")
    monkeypatch.setattr("app.notification_probe.send_telegram_probe", timeout)
    test_id = str(uuid4())
    response = probe_client.post("/notifications/test", auth=AUTH, json={"test_id": test_id})
    assert response.json()["status"] == "UNKNOWN"
    assert response.json()["last_error"] == "ReadTimeout"
    assert "private-token" not in response.text
    monkeypatch.setattr("app.notification_probe.send_telegram_probe", lambda *_: pytest.fail("Ambiguous send retried"))
    assert probe_client.post("/notifications/test", auth=AUTH, json={"test_id": test_id}).json()["status"] == "UNKNOWN"


@pytest.mark.parametrize("name,value", [("REQUIRE_VERIFIED_NEWS", "false"), ("TELEGRAM_BOT_TOKEN", ""),
    ("TELEGRAM_CHAT_ID", ""), ("NOTIFICATION_WEBHOOK_URL", "https://example.test/other")])
def test_probe_configuration_fails_closed(probe_client, monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    monkeypatch.setattr("app.notification_probe.send_telegram_probe", lambda *_: pytest.fail("Unsafe send"))
    assert probe_client.post("/notifications/test", auth=AUTH, json={"test_id": str(uuid4())}).status_code == 409


def test_probe_disabled_without_dashboard_credentials(client):
    assert client.post("/notifications/test", json={"test_id": str(uuid4())}).status_code == 503


@pytest.mark.parametrize("kind,chat_id,expected", [("private", 12345, "SENT"), ("group", 12345, "FAILED"),
                                                 ("private", 99999, "FAILED")])
def test_transport_only_targets_configured_private_chat(monkeypatch, kind, chat_id, expected):
    requests = []
    def respond(request):
        requests.append(request)
        if request.url.path.endswith("/getChat"):
            return httpx.Response(200, json={"ok": True, "result": {"type": kind, "id": chat_id}})
        body = json.loads(request.content)
        assert body["chat_id"] == "12345"
        assert "DELIVERY TEST" in body["text"] and "not a BUY/SELL signal" in body["text"]
        assert body["protect_content"] is True
        return httpx.Response(200, json={"ok": True, "result": {"chat": {"type": "private", "id": 12345}}})
    real_client = httpx.Client
    monkeypatch.setattr("app.notification_probe.httpx.Client", lambda **kwargs: real_client(
        transport=httpx.MockTransport(respond), **kwargs))
    settings = Settings(_env_file=None, telegram_bot_token="synthetic-token", telegram_chat_id="12345")
    assert send_telegram_probe(settings, str(uuid4()))[0] == expected
    assert len(requests) == (2 if expected == "SENT" else 1)


@pytest.mark.parametrize("status,body", [(302, {}), (429, {}), (200, []), (200, {"ok": False})])
def test_transport_rejects_redirects_failures_and_malformed_chat(monkeypatch, status, body):
    real_client = httpx.Client
    monkeypatch.setattr("app.notification_probe.httpx.Client", lambda **kwargs: real_client(
        transport=httpx.MockTransport(lambda _: httpx.Response(status, json=body)), **kwargs))
    settings = Settings(_env_file=None, telegram_bot_token="synthetic-token", telegram_chat_id="12345")
    assert send_telegram_probe(settings, str(uuid4()))[0] == "FAILED"


@pytest.mark.parametrize("logger,message,secret", [
    ("httpx", "https://api.telegram.org/botsynthetic-token/sendMessage", "synthetic-token"),
    ("httpcore.http11", "/bot123456:abcdefghijklmnopqrstuvwx/sendMessage", "123456:abcdefghijklmnopqrstuvwx"),
    ("httpcore.http2", "token=123456:abcdefghijklmnopqrstuvwx", "123456:abcdefghijklmnopqrstuvwx"),
])
def test_telegram_tokens_are_redacted_from_http_logs(caplog, logger, message, secret):
    from app.logging_config import protect_access_logs
    protect_access_logs()
    with caplog.at_level(logging.INFO, logger=logger):
        logging.getLogger(logger).info("Request %s", message)
    assert secret not in caplog.text and "[REDACTED]" in caplog.text
