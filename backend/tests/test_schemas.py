import pytest
from pydantic import ValidationError

from app.schemas import LLMTradeDecision, SetupAlert


def test_setup_alert_accepts_valid_example(valid_setup_payload):
    alert = SetupAlert.model_validate(valid_setup_payload)

    assert alert.setup_id == "CME_MINI_ES1_5_20260705T134500Z_12345"
    assert alert.root_symbol.value == "ES"
    assert alert.features.smt.state.value == "BULLISH"


def test_setup_alert_rejects_missing_required_field(valid_setup_payload):
    valid_setup_payload.pop("setup_id")

    with pytest.raises(ValidationError):
        SetupAlert.model_validate(valid_setup_payload)


def test_setup_alert_rejects_extra_top_level_field(valid_setup_payload):
    valid_setup_payload["unexpected"] = True

    with pytest.raises(ValidationError):
        SetupAlert.model_validate(valid_setup_payload)


def test_llm_decision_accepts_valid_buy_example(valid_buy_decision_payload):
    decision = LLMTradeDecision.model_validate(valid_buy_decision_payload)

    assert decision.action.value == "BUY"
    assert decision.entry.preferred == 6721.25


def test_llm_decision_rejects_malformed_payload(valid_buy_decision_payload):
    valid_buy_decision_payload.pop("action")

    with pytest.raises(ValidationError):
        LLMTradeDecision.model_validate(valid_buy_decision_payload)
