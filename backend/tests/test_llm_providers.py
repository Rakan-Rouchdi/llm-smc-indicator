import copy
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.llm_client import (
    FallbackLLMProvider,
    LLMProviderOutputError,
    MockLLMProvider,
    OpenAILLMProvider,
    get_llm_provider,
)
from app.schemas import TradeAction


class FakeResponses:
    def __init__(self, response=None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.last_request = None

    def create(self, **kwargs):
        self.last_request = kwargs
        if self.error:
            raise self.error
        return self.response


class FakeOpenAIClient:
    def __init__(self, response=None, error: Exception | None = None):
        self.responses = FakeResponses(response=response, error=error)


def _llm_input(setup_payload: dict) -> dict:
    return {
        "schema_version": "1.0",
        "prompt_version": "test",
        "setup_alert": setup_payload,
        "context": {
            "news": {
                "blackout_active": False,
                "headline_summary": "No high-impact event in mock context.",
            },
            "telegram": {
                "bullish_count": 1,
                "bearish_count": 0,
                "neutral_count": 0,
                "source_count": 1,
                "summary": "Mock bullish context.",
            },
            "news_blackout_active": False,
        },
        "risk_policy": {
            "min_confidence_for_trade": 70,
            "min_risk_reward": 1.5,
            "max_setup_age_minutes": 15,
            "no_trade_during_blackout": True,
            "no_trade_when_consolidation": True,
        },
    }


def _openai_settings(**overrides) -> Settings:
    values = {
        "llm_provider": "openai",
        "openai_api_key": "test-only-key",
        "openai_model": "gpt-4o-mini",
        "llm_timeout_seconds": 2,
        "llm_max_retries": 0,
    }
    values.update(overrides)
    return Settings(**values)


def test_mock_provider_is_default(fresh_setup_payload):
    provider = get_llm_provider(Settings())

    decision = provider.decide(_llm_input(fresh_setup_payload))

    assert isinstance(provider, MockLLMProvider)
    assert decision.action == TradeAction.BUY


def test_openai_provider_selected_only_when_configured():
    provider = get_llm_provider(
        _openai_settings(),
        openai_client=FakeOpenAIClient(),
    )

    assert isinstance(provider, FallbackLLMProvider)
    assert isinstance(provider.primary, OpenAILLMProvider)


def test_missing_openai_api_key_uses_mock():
    provider = get_llm_provider(
        Settings(llm_provider="openai", openai_api_key=None)
    )

    assert isinstance(provider, MockLLMProvider)


def test_malformed_openai_output_is_rejected(fresh_setup_payload):
    response = SimpleNamespace(status="completed", output_text="{not-json")
    provider = OpenAILLMProvider(
        _openai_settings(),
        client=FakeOpenAIClient(response=response),
    )

    with pytest.raises(LLMProviderOutputError):
        provider.decide(_llm_input(fresh_setup_payload))


def test_schema_invalid_openai_output_is_rejected(fresh_setup_payload):
    response = SimpleNamespace(
        status="completed",
        output_text='{"schema_version":"1.0","setup_id":"incomplete"}',
    )
    provider = OpenAILLMProvider(
        _openai_settings(),
        client=FakeOpenAIClient(response=response),
    )

    with pytest.raises(LLMProviderOutputError):
        provider.decide(_llm_input(fresh_setup_payload))


def test_schema_valid_openai_output_passes(
    fresh_setup_payload,
    valid_buy_decision_payload,
):
    payload = copy.deepcopy(valid_buy_decision_payload)
    payload["setup_id"] = fresh_setup_payload["setup_id"]
    response = SimpleNamespace(
        status="completed",
        output_text=__import__("json").dumps(payload),
    )
    client = FakeOpenAIClient(response=response)
    provider = OpenAILLMProvider(_openai_settings(), client=client)

    decision = provider.decide(_llm_input(fresh_setup_payload))

    assert decision.action == TradeAction.BUY
    request = client.responses.last_request
    assert request["text"]["format"]["strict"] is True
    assert "setup_alert" in request["input"]
    assert "telegram" in request["input"]
    assert request["store"] is False


def test_openai_failure_falls_back_to_mock(fresh_setup_payload):
    provider = get_llm_provider(
        _openai_settings(),
        openai_client=FakeOpenAIClient(error=TimeoutError("test timeout")),
    )

    decision = provider.decide(_llm_input(fresh_setup_payload))

    assert isinstance(provider, FallbackLLMProvider)
    assert provider.used_fallback is True
    assert provider.model_name.endswith("openai-fallback")
    assert decision.action == TradeAction.BUY
    assert any("fallback" in note for note in decision.validation_notes)
