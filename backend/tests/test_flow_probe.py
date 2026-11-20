import copy
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest

from app.config import get_settings
from app.database import SessionLocal
from app.flow_probe import FlowProbe, run_flow_probe
from app.llm_client import MockLLMProvider, no_trade_decision
from app.models import FlowProbeRecord, LLMDecisionRecord, NotificationRecord, SetupAlertRecord, AutoOutcomeRecord
from app.worker import DecisionWorker


AUTH = ("operator", "synthetic-password")
CLEAR = {"news": {"status": "CLEAR", "blackout_active": False}, "news_blackout_active": False,
         "telegram": {"summary": "Mock Telegram context"}}


@pytest.fixture
def flow_case(client, fresh_setup_payload, monkeypatch):
    raw = fresh_setup_payload
    raw.update(symbol="CME_MINI_DL:NQ1!", root_symbol="NQ", companion_symbol="CME_MINI_DL:ES1!",
               setup_id="CME_MINI_DL:NQ1!_5_TEST_1795105800000_42")
    raw["diagnostics"]["test_mode"] = True
    raw["features"]["bos"]["state"] = "NONE"
    # First use the unchanged webhook/worker path. Its failed preflight must
    # remain a stored NO_TRADE, with no OpenAI call or production notification.
    monkeypatch.setattr("app.workflow.get_llm_provider", lambda _: pytest.fail("Preflight bypassed"))
    assert client.post("/webhook/tradingview?secret=test-secret", json=raw).status_code == 202
    assert DecisionWorker(get_settings()).run_once()
    for name, value in {"DASHBOARD_USERNAME": AUTH[0], "DASHBOARD_PASSWORD": AUTH[1],
                        "LLM_PROVIDER": "openai", "OPENAI_API_KEY": "synthetic-key",
                        "OPENAI_MODEL": "gpt-4o-mini", "REQUIRE_VERIFIED_NEWS": "true",
                        "NEWS_PROVIDER": "manual", "ENABLE_NOTIFICATIONS": "true",
                        "TELEGRAM_BOT_TOKEN": "synthetic-token", "TELEGRAM_CHAT_ID": "12345"}.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    monkeypatch.setattr("app.flow_probe.build_context", lambda *_, **__: copy.deepcopy(CLEAR))
    calls, sends = [], []

    class Live:
        model_name = "gpt-4o-mini"

        def decide(self, data):
            calls.append(data)
            return no_trade_decision(data["setup_alert"]["setup_id"], ["Synthetic test has no aligned BOS"])

    monkeypatch.setattr("app.flow_probe.get_llm_provider", lambda _: Live())
    monkeypatch.setattr("app.flow_probe.send_private_telegram_text", lambda _, text: sends.append(text) or ("SENT", None))
    return client, raw, {"test_id": str(uuid4()), "setup_id": raw["setup_id"], "tradingview_log_verified": True}, calls, sends


def test_flow_auth_and_input_are_operator_only(flow_case):
    client, _, request, calls, sends = flow_case
    assert client.post("/diagnostics/flow-tests", json=request).status_code == 401
    assert client.get(f"/diagnostics/flow-tests/{request['test_id']}").status_code == 401
    for change in ({"tradingview_log_verified": False}, {"test_id": "invalid"}, {"text": "BUY"}):
        assert client.post("/diagnostics/flow-tests", auth=AUTH, json=request | change).status_code == 422
    assert not calls and not sends


def test_linked_flow_is_idempotent_and_never_a_production_approval(flow_case):
    client, raw, request, calls, sends = flow_case
    result = client.post("/diagnostics/flow-tests", auth=AUTH, json=request)
    assert result.status_code == 200
    body = result.json()
    assert body["status"] == "SENT" and body["final_action"] == "NO_TRADE"
    assert body["result"]["model"] == "gpt-4o-mini" and body["result"]["schema_valid"]
    assert body["result"]["validator"]["validator_status"] == "REJECTED"
    assert body["eligible_for_outcomes"] is False
    assert client.post("/diagnostics/flow-tests", auth=AUTH, json=request).json() == body
    assert client.get(f"/diagnostics/flow-tests/{request['test_id']}", auth=AUTH).json() == body
    assert len(calls) == len(sends) == 1
    assert calls[0]["setup_alert"] == raw
    assert "END-TO-END DELIVERY TEST" in sends[0] and "not a BUY/SELL signal" in sends[0]
    assert "Entry" not in sends[0] and "NO_TRADE" in sends[0]
    with SessionLocal() as db:
        assert db.query(FlowProbeRecord).count() == 1
        assert db.query(LLMDecisionRecord).count() == 1
        assert db.query(LLMDecisionRecord).one().model == "deterministic-preflight"
        assert db.query(NotificationRecord).count() == db.query(AutoOutcomeRecord).count() == 0
    assert get_settings().require_verified_news is True


@pytest.mark.parametrize("state", ["UNKNOWN", "BLACKOUT", "STALE", "UNVERIFIED"])
def test_news_blocks_model_and_telegram(flow_case, monkeypatch, state):
    client, _, request, calls, sends = flow_case
    monkeypatch.setattr("app.flow_probe.build_context", lambda *_, **__: {"news": {"status": state}})
    result = client.post("/diagnostics/flow-tests", auth=AUTH, json=request).json()
    assert result["status"] == "BLOCKED" and result["final_action"] == "NO_TRADE"
    assert not calls and not sends


def test_news_rechecked_after_model_before_message(flow_case, monkeypatch):
    client, _, request, calls, sends = flow_case
    contexts = iter([CLEAR, {"news": {"status": "BLACKOUT", "blackout_active": True}}])
    monkeypatch.setattr("app.flow_probe.build_context", lambda *_, **__: next(contexts))
    result = client.post("/diagnostics/flow-tests", auth=AUTH, json=request).json()
    assert result["status"] == "BLOCKED" and result["result"]["schema_valid"]
    assert len(calls) == 1 and not sends
    assert "News blackout active" in result["result"]["validator"]["rejections"]


@pytest.mark.parametrize("field,value", [("LLM_PROVIDER", "mock"), ("OPENAI_API_KEY", ""),
    ("REQUIRE_VERIFIED_NEWS", "false"), ("NEWS_PROVIDER", "mock"), ("ENABLE_NOTIFICATIONS", "false"),
    ("TELEGRAM_BOT_TOKEN", ""), ("TELEGRAM_CHAT_ID", ""), ("NOTIFICATION_WEBHOOK_URL", "https://example.test/hook")])
def test_unsafe_configuration_refused(flow_case, monkeypatch, field, value):
    client, _, request, calls, sends = flow_case
    monkeypatch.setenv(field, value)
    get_settings.cache_clear()
    assert client.post("/diagnostics/flow-tests", auth=AUTH, json=request).status_code == 409
    assert not calls and not sends


@pytest.mark.parametrize("case", ["natural", "old", "future", "wrong_symbol", "wrong_tf", "approved", "pending", "bad_id"])
def test_non_test_or_unready_receipt_refused(flow_case, case):
    client, _, request, calls, sends = flow_case
    with SessionLocal() as db:
        record = db.query(SetupAlertRecord).one()
        raw = json.loads(record.payload_json)
        if case == "natural": raw["diagnostics"]["test_mode"] = False
        if case == "old": record.received_at = datetime.now(timezone.utc) - timedelta(minutes=16)
        if case == "future": raw["diagnostics"]["bar_close_time"] = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        if case == "wrong_symbol": raw["symbol"] = "CME_MINI_DL:ES1!"
        if case == "wrong_tf": raw["timeframe"] = "240"
        if case == "approved": db.query(LLMDecisionRecord).one().final_action = "BUY"
        if case == "pending": record.status = "PROCESSING"
        if case == "bad_id": raw["setup_id"] += "\nInvented signal"
        record.payload_json = json.dumps(raw)
        db.commit()
    assert client.post("/diagnostics/flow-tests", auth=AUTH, json=request).status_code == 409
    assert not calls and not sends


@pytest.mark.parametrize("case", ["fallback", "malformed", "schema", "mismatch", "exception"])
def test_provider_failure_never_sends_or_leaks_errors(flow_case, monkeypatch, case):
    client, _, request, _, sends = flow_case
    class Broken:
        model_name = "mock-openai-fallback" if case == "fallback" else "gpt-4o-mini"
        def decide(self, data):
            if case == "exception": raise RuntimeError("https://secret.invalid/?key=do-not-print")
            if case == "malformed": return {"action": "BUY"}
            output = no_trade_decision("wrong" if case == "mismatch" else request["setup_id"], ["Test"])
            return output.model_copy(update={"confidence": 1000}) if case == "schema" else output
    monkeypatch.setattr("app.flow_probe.get_llm_provider", lambda _: Broken())
    result = client.post("/diagnostics/flow-tests", auth=AUTH, json=request)
    assert result.json()["status"] == "FAILED" and not sends
    assert "do-not-print" not in result.text
    client.post("/diagnostics/flow-tests", auth=AUTH, json=request)
    assert not sends


def test_raw_buy_cannot_become_a_real_approval(flow_case, monkeypatch):
    client, _, request, _, sends = flow_case
    class RawBuy(MockLLMProvider):
        model_name = "gpt-4o-mini"
    monkeypatch.setattr("app.flow_probe.get_llm_provider", lambda _: RawBuy())
    result = client.post("/diagnostics/flow-tests", auth=AUTH, json=request).json()
    assert result["result"]["llm_output"]["action"] == "BUY"
    assert result["final_action"] == result["result"]["validator"]["final_action"] == "NO_TRADE"
    assert "Entry" not in sends[0]
    with SessionLocal() as db:
        assert db.query(NotificationRecord).count() == 0


def test_ambiguous_telegram_attempt_is_never_repeated(flow_case, monkeypatch):
    client, _, request, calls, _ = flow_case
    attempts = []
    def timeout(*_):
        attempts.append(True)
        raise httpx.ReadTimeout("https://api.telegram.org/botprivate-token/sendMessage")
    monkeypatch.setattr("app.flow_probe.send_private_telegram_text", timeout)
    response = client.post("/diagnostics/flow-tests", auth=AUTH, json=request)
    assert response.json()["status"] == "UNKNOWN" and "private-token" not in response.text
    client.post("/diagnostics/flow-tests", auth=AUTH, json=request)
    assert len(calls) == len(attempts) == 1
    assert client.post("/diagnostics/flow-tests", auth=AUTH, json=request | {"test_id": str(uuid4())}).status_code == 409


def test_receipt_expiring_during_model_is_blocked(flow_case):
    _, _, request, calls, sends = flow_case
    now = datetime.now(timezone.utc)
    ticks = iter([now, now, now, now + timedelta(minutes=16), now + timedelta(minutes=16),
                  now + timedelta(minutes=16), now + timedelta(minutes=16)])
    with SessionLocal() as db:
        result = run_flow_probe(db, get_settings(), FlowProbe(**request), clock=lambda: next(ticks))
    assert result["status"] == "BLOCKED" and calls and not sends


def test_flow_disabled_without_operator_credentials(client):
    assert client.post("/diagnostics/flow-tests", json={"test_id": str(uuid4()), "setup_id": "x",
                                                       "tradingview_log_verified": True}).status_code == 503


def test_one_minute_limit_and_reference_cannot_be_rebound(flow_case):
    from fastapi import HTTPException
    client, raw, request, calls, sends = flow_case
    second = copy.deepcopy(raw)
    second["setup_id"] = second["setup_id"].replace("_42", "_43")
    assert client.post("/webhook/tradingview?secret=test-secret", json=second).status_code == 202
    assert DecisionWorker(get_settings()).run_once()
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        assert run_flow_probe(db, get_settings(), FlowProbe(**request), clock=lambda: now)["status"] == "SENT"
        for candidate in (request | {"setup_id": second["setup_id"]},
                          request | {"test_id": str(uuid4()), "setup_id": second["setup_id"]}):
            with pytest.raises(HTTPException) as exc:
                run_flow_probe(db, get_settings(), FlowProbe(**candidate), clock=lambda: now)
            assert exc.value.status_code == 409
    assert len(calls) == len(sends) == 1
