from datetime import datetime, timezone

from app.schemas import LLMTradeDecision, SetupAlert
from app.validators import (
    ValidationPolicy,
    calculate_risk_reward,
    validate_llm_decision,
)


def _fresh_time() -> datetime:
    return datetime(2026, 7, 5, 13, 46, tzinfo=timezone.utc)


def test_validator_approves_valid_buy(valid_setup_payload, valid_buy_decision_payload):
    setup = SetupAlert.model_validate(valid_setup_payload)
    decision = LLMTradeDecision.model_validate(valid_buy_decision_payload)

    result = validate_llm_decision(setup, decision, current_time=_fresh_time())

    assert result.validator_status == "APPROVED"
    assert result.final_action.value == "BUY"
    assert result.final_confidence == 76


def test_risk_reward_calculation_for_buy():
    rr = calculate_risk_reward("BUY", entry=100.0, stop_loss=95.0, take_profit_1=110.0)

    assert rr == 2.0


def test_validator_rejects_consolidation(valid_setup_payload, valid_buy_decision_payload):
    valid_setup_payload["features"]["consolidation"]["active"] = True
    setup = SetupAlert.model_validate(valid_setup_payload)
    decision = LLMTradeDecision.model_validate(valid_buy_decision_payload)

    result = validate_llm_decision(setup, decision, current_time=_fresh_time())

    assert result.validator_status == "REJECTED"
    assert result.final_action.value == "NO_TRADE"
    assert "Setup is blocked during consolidation" in result.rejections


def test_validator_rejects_news_blackout(valid_setup_payload, valid_buy_decision_payload):
    setup = SetupAlert.model_validate(valid_setup_payload)
    decision = LLMTradeDecision.model_validate(valid_buy_decision_payload)

    result = validate_llm_decision(
        setup,
        decision,
        context={"news_blackout_active": True},
        current_time=_fresh_time(),
    )

    assert result.validator_status == "REJECTED"
    assert "News blackout active" in result.rejections


def test_validator_rejects_buy_with_bad_stop(valid_setup_payload, valid_buy_decision_payload):
    valid_buy_decision_payload["stop_loss"] = 6722.25
    setup = SetupAlert.model_validate(valid_setup_payload)
    decision = LLMTradeDecision.model_validate(valid_buy_decision_payload)

    result = validate_llm_decision(setup, decision, current_time=_fresh_time())

    assert result.validator_status == "REJECTED"
    assert "BUY stop loss must be below entry" in result.rejections


def test_validator_rejects_low_rr(valid_setup_payload, valid_buy_decision_payload):
    valid_buy_decision_payload["risk_reward"] = 1.0
    setup = SetupAlert.model_validate(valid_setup_payload)
    decision = LLMTradeDecision.model_validate(valid_buy_decision_payload)

    result = validate_llm_decision(
        setup,
        decision,
        policy=ValidationPolicy(min_risk_reward=1.5),
        current_time=_fresh_time(),
    )

    assert result.validator_status == "REJECTED"
    assert "Risk/reward below minimum" in result.rejections


def test_validator_approves_valid_sell(valid_setup_payload, valid_buy_decision_payload):
    valid_setup_payload["direction"] = "BEARISH"
    valid_setup_payload["features"]["bos"]["state"] = "BEARISH"
    valid_setup_payload["features"]["fvg"]["state"] = "BEARISH"
    valid_setup_payload["features"]["liquidity_sweep"]["state"] = "BEARISH"
    valid_setup_payload["features"]["smt"]["state"] = "BEARISH"
    valid_setup_payload["features"]["htf_bias"] = "BEARISH"
    valid_setup_payload["features"]["displacement"] = "BEARISH"
    valid_setup_payload["risk"]["stop_loss"] = 6727.75
    valid_setup_payload["risk"]["take_profit_1"] = 6708.25
    valid_setup_payload["risk"]["risk_reward"] = 2.0

    valid_buy_decision_payload["action"] = "SELL"
    valid_buy_decision_payload["bias"] = "BEARISH"
    valid_buy_decision_payload["stop_loss"] = 6727.75
    valid_buy_decision_payload["take_profit"]["tp1"] = 6708.25
    valid_buy_decision_payload["risk_reward"] = 2.0

    setup = SetupAlert.model_validate(valid_setup_payload)
    decision = LLMTradeDecision.model_validate(valid_buy_decision_payload)

    result = validate_llm_decision(setup, decision, current_time=_fresh_time())

    assert result.validator_status == "APPROVED"
    assert result.final_action.value == "SELL"


def test_validator_rejects_sell_with_bad_stop(valid_setup_payload, valid_buy_decision_payload):
    valid_setup_payload["direction"] = "BEARISH"
    valid_buy_decision_payload["action"] = "SELL"
    valid_buy_decision_payload["bias"] = "BEARISH"
    valid_buy_decision_payload["stop_loss"] = 6718.0
    valid_buy_decision_payload["take_profit"]["tp1"] = 6708.25
    valid_buy_decision_payload["risk_reward"] = 2.0

    setup = SetupAlert.model_validate(valid_setup_payload)
    decision = LLMTradeDecision.model_validate(valid_buy_decision_payload)

    result = validate_llm_decision(setup, decision, current_time=_fresh_time())

    assert result.validator_status == "REJECTED"
    assert "SELL stop loss must be above entry" in result.rejections


def test_validator_rejects_malformed_llm_output(valid_setup_payload):
    setup = SetupAlert.model_validate(valid_setup_payload)

    result = validate_llm_decision(setup, {"schema_version": "1.0"}, current_time=_fresh_time())

    assert result.validator_status == "REJECTED"
    assert result.final_action.value == "NO_TRADE"
    assert result.rejections[0].startswith("Malformed LLM output")
