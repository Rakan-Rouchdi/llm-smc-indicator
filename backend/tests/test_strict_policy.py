from datetime import datetime, timedelta, timezone

import pytest

from app.config import get_settings
from app.schemas import SetupAlert, LLMTradeDecision
from app.validators import validate_llm_decision, ValidationPolicy
from app.worker import DecisionWorker


@pytest.mark.parametrize("path,value,reason", [
    (("features", "bos", "state"), "NONE", "Aligned BOS"),
    (("features", "htf_bias"), "BEARISH", "Aligned HTF"),
    (("features", "volume", "rvol"), .3, "Thin volume"),
    (("features", "fvg", "state"), "NONE", "Aligned active FVG"),
    (("diagnostics", "fvg_retested"), False, "Confirmed retest"),
    (("diagnostics", "zone_invalidated"), True, "valid zone"),
    (("diagnostics", "companion_aligned"), False, "misaligned"),
    (("diagnostics", "consolidation_clear_bars"), 1, "Consolidation exit"),
    (("diagnostics", "bos_age_bars"), 1, "sequence"),
    (("diagnostics", "bos_age_bars"), 9, "sequence"),
    (("diagnostics", "policy_version"), "legacy", "Unsupported setup policy"),
    (("diagnostics", "bar_close_time"), None, "Exact candle-close"),
    (("diagnostics", "smt_age_bars"), 30, "invalid age"),
    (("rule_score",), 0, "Rule score"),
    (("price",), 6740, "beyond stop or target"),
    (("risk", "risk_points"), 1, "Source risk/reward"),
])
def test_strict_gates(path, value, reason, valid_setup_payload, valid_buy_decision_payload):
    node = valid_setup_payload
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    result = validate_llm_decision(SetupAlert.model_validate(valid_setup_payload), valid_buy_decision_payload)
    assert result.final_action.value == "NO_TRADE"
    assert any(reason in r for r in result.rejections)


def test_no_features_cannot_be_approved(valid_setup_payload, valid_buy_decision_payload):
    features = valid_setup_payload["features"]
    for key in ("fvg", "bos", "smt", "liquidity_sweep"):
        features[key]["state"] = "NONE"
    features.update(htf_bias="BEARISH", displacement="NONE")
    valid_setup_payload["rule_score"] = 0
    result = validate_llm_decision(SetupAlert.model_validate(valid_setup_payload), valid_buy_decision_payload)
    assert result.final_action.value == "NO_TRADE"


def test_unknown_news_blocks_before_llm(client, fresh_setup_payload, monkeypatch):
    monkeypatch.setenv("REQUIRE_VERIFIED_NEWS", "true")
    get_settings.cache_clear()
    monkeypatch.setattr("app.workflow.get_llm_provider", lambda _: pytest.fail("Must not call provider"))
    client.post("/webhook/tradingview?secret=test-secret", json=fresh_setup_payload)
    DecisionWorker(get_settings()).run_once()
    decision = client.get("/decisions/latest").json()["decision"]
    assert decision["model"] == "deterministic-preflight"
    assert decision["final_action"] == "NO_TRADE"
    assert "Verified news" in decision["validation_rejection_reason"]


def test_live_failure_fallback_is_held(client, fresh_setup_payload, monkeypatch):
    from app.llm_client import MockLLMProvider
    class Fallback(MockLLMProvider):
        model_name = "mock-llm-deterministic-openai-fallback"
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    get_settings.cache_clear()
    monkeypatch.setattr("app.workflow.get_llm_provider", lambda _: Fallback())
    client.post("/webhook/tradingview?secret=test-secret", json=fresh_setup_payload)
    DecisionWorker(get_settings()).run_once()
    decision = client.get("/decisions/latest").json()["decision"]
    assert decision["final_action"] == "NO_TRADE"
    assert decision["model"].endswith("fallback")


def test_expired_decision_and_outside_entry_are_rejected(valid_setup_payload, valid_buy_decision_payload):
    valid_buy_decision_payload["expires_at"] = "2026-07-05T13:50:00Z"
    valid_buy_decision_payload["entry"].update(low=6800, high=6800, preferred=6800)
    result = validate_llm_decision(SetupAlert.model_validate(valid_setup_payload), valid_buy_decision_payload,
                                 current_time=datetime(2026, 7, 5, 13, 51, tzinfo=timezone.utc))
    assert any("expired" in r for r in result.rejections)
    assert any("outside" in r for r in result.rejections)


def test_nonfinite_output_rejected(valid_setup_payload, valid_buy_decision_payload):
    valid_buy_decision_payload["stop_loss"] = float("nan")
    result = validate_llm_decision(SetupAlert.model_validate(valid_setup_payload), valid_buy_decision_payload)
    assert result.final_action.value == "NO_TRADE"


def test_news_is_rechecked_after_provider(client, fresh_setup_payload, monkeypatch):
    contexts = iter([{"news": {"status": "CLEAR"}}, {"news": {"status": "BLACKOUT", "blackout_active": True}}])
    monkeypatch.setattr("app.workflow.build_context", lambda *_, **__: next(contexts))
    client.post("/webhook/tradingview?secret=test-secret", json=fresh_setup_payload)
    DecisionWorker(get_settings()).run_once()
    decision = client.get("/decisions/latest").json()["decision"]
    assert decision["llm_decision"]["action"] == "BUY"
    assert decision["final_action"] == "NO_TRADE"
    assert "News blackout active" in decision["validation_rejection_reason"]
