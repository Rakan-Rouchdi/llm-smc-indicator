from __future__ import annotations

import copy
import json
from datetime import timedelta
from pathlib import Path
from typing import Any, Protocol

from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from openai import OpenAI, OpenAIError
from pydantic import ValidationError as PydanticValidationError

from app.config import Settings
from app.schema_validation import validate_llm_trade_decision_schema
from app.schemas import (
    Bias,
    DecisionEntry,
    DecisionEntryType,
    LLMTradeDecision,
    SetupAlert,
    TakeProfit,
    TradeAction,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class LLMProviderError(RuntimeError):
    """Base error for provider failures that can safely use the mock fallback."""


class LLMProviderOutputError(LLMProviderError):
    """Raised when a provider response is missing, malformed, or schema-invalid."""


class LLMProvider(Protocol):
    model_name: str

    def decide(self, llm_input: dict[str, Any]) -> LLMTradeDecision:
        ...


class OpenAIResponsesClient(Protocol):
    class Responses(Protocol):
        def create(self, **kwargs: Any) -> Any:
            ...

    responses: Responses


class MockLLMProvider:
    model_name = "mock-llm-deterministic"

    def decide(self, llm_input: dict[str, Any]) -> LLMTradeDecision:
        setup = SetupAlert.model_validate(llm_input["setup_alert"])
        context = llm_input.get("context", {})
        news = context.get("news") if isinstance(context.get("news"), dict) else {}
        blackout_active = bool(context.get("news_blackout_active")) or bool(
            news.get("blackout_active")
        )
        blocked = blackout_active or setup.features.consolidation.active

        if blocked:
            return LLMTradeDecision(
                schema_version="1.0",
                setup_id=setup.setup_id,
                action=TradeAction.NO_TRADE,
                bias=Bias.NEUTRAL,
                confidence=0,
                entry=DecisionEntry(
                    type=DecisionEntryType.NONE,
                    low=None,
                    high=None,
                    preferred=None,
                ),
                stop_loss=None,
                take_profit=TakeProfit(tp1=None, tp2=None),
                risk_reward=None,
                expires_at=None,
                headline_driver=news.get("headline_summary")
                or "Mock blocked context",
                reason_summary=(
                    "Mock provider returned no trade because a blocking "
                    "condition is active."
                ),
                confluence_notes=[],
                blocking_conditions=["Mock blocking condition active"],
                validation_notes=[
                    "Mock LLM provider used because live credentials are not configured."
                ],
                requires_human_review=False,
            )

        action = (
            TradeAction.BUY
            if setup.direction.value == "BULLISH"
            else TradeAction.SELL
        )
        bias = Bias.BULLISH if action == TradeAction.BUY else Bias.BEARISH
        confidence = max(70, min(85, setup.rule_score))

        return LLMTradeDecision(
            schema_version="1.0",
            setup_id=setup.setup_id,
            action=action,
            bias=bias,
            confidence=confidence,
            entry=DecisionEntry(
                type=DecisionEntryType(setup.entry.zone_type.value)
                if setup.entry.zone_type.value != "UNKNOWN"
                else DecisionEntryType.NONE,
                low=setup.entry.low,
                high=setup.entry.high,
                preferred=setup.entry.preferred,
            ),
            stop_loss=setup.risk.stop_loss,
            take_profit=TakeProfit(tp1=setup.risk.take_profit_1, tp2=None),
            risk_reward=setup.risk.risk_reward,
            expires_at=setup.bar_time + timedelta(minutes=15),
            headline_driver=news.get("headline_summary") or "None",
            reason_summary=(
                "Mock provider mirrored the structured setup into a "
                "deterministic test decision."
            ),
            confluence_notes=[
                f"{setup.direction.value.title()} source setup",
                f"Rule score {setup.rule_score}",
            ],
            blocking_conditions=[],
            validation_notes=[
                "Mock LLM provider used because live credentials are not configured."
            ],
            requires_human_review=False,
        )


def _remove_unsupported_schema_keywords(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _remove_unsupported_schema_keywords(child)
            for key, child in value.items()
            if key not in {"$schema", "format"}
        }
    if isinstance(value, list):
        return [_remove_unsupported_schema_keywords(child) for child in value]
    return value


def _openai_response_schema() -> dict[str, Any]:
    schema_path = PROJECT_ROOT / "schemas" / "llm_trade_decision.schema.json"
    schema = json.loads(schema_path.read_text())
    return _remove_unsupported_schema_keywords(copy.deepcopy(schema))


class OpenAILLMProvider:
    def __init__(
        self,
        settings: Settings,
        client: OpenAIResponsesClient | None = None,
    ):
        if settings.openai_api_key is None:
            raise LLMProviderError("OpenAI provider requires OPENAI_API_KEY.")

        self.settings = settings
        self.model_name = settings.openai_model
        self.client = client or OpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    def decide(self, llm_input: dict[str, Any]) -> LLMTradeDecision:
        from app.llm_prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

        user_prompt = USER_PROMPT_TEMPLATE.format(
            llm_input_json=json.dumps(
                llm_input,
                default=str,
                separators=(",", ":"),
            )
        )

        try:
            response = self.client.responses.create(
                model=self.settings.openai_model,
                instructions=SYSTEM_PROMPT,
                input=user_prompt,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "llm_trade_decision",
                        "strict": True,
                        "schema": _openai_response_schema(),
                    }
                },
                max_output_tokens=1500,
                store=False,
            )
        except (OpenAIError, TimeoutError) as exc:
            raise LLMProviderError("OpenAI request failed.") from exc
        except Exception as exc:
            raise LLMProviderError("OpenAI client failed.") from exc

        if getattr(response, "status", "completed") != "completed":
            raise LLMProviderOutputError("OpenAI response was incomplete.")

        output_text = getattr(response, "output_text", None)
        if not isinstance(output_text, str) or not output_text.strip():
            raise LLMProviderOutputError("OpenAI response did not contain JSON.")

        try:
            payload = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise LLMProviderOutputError("OpenAI response was malformed JSON.") from exc

        if not isinstance(payload, dict):
            raise LLMProviderOutputError("OpenAI response must be a JSON object.")

        try:
            validate_llm_trade_decision_schema(payload)
            decision = LLMTradeDecision.model_validate(payload)
        except (PydanticValidationError, JsonSchemaValidationError) as exc:
            raise LLMProviderOutputError(
                "OpenAI response failed decision schema validation."
            ) from exc

        setup_id = llm_input.get("setup_alert", {}).get("setup_id")
        if decision.setup_id != setup_id:
            raise LLMProviderOutputError(
                "OpenAI response setup_id did not match the input."
            )
        return decision


class FallbackLLMProvider:
    def __init__(self, primary: LLMProvider, fallback: LLMProvider):
        self.primary = primary
        self.fallback = fallback
        self.model_name = primary.model_name
        self.used_fallback = False

    def decide(self, llm_input: dict[str, Any]) -> LLMTradeDecision:
        try:
            decision = self.primary.decide(llm_input)
            self.model_name = self.primary.model_name
            self.used_fallback = False
            return decision
        except LLMProviderError:
            decision = self.fallback.decide(llm_input)
            decision.validation_notes.append(
                "OpenAI provider unavailable; deterministic mock fallback used."
            )
            self.model_name = f"{self.fallback.model_name}-openai-fallback"
            self.used_fallback = True
            return decision


def get_llm_provider(
    settings: Settings,
    *,
    openai_client: OpenAIResponsesClient | None = None,
) -> LLMProvider:
    if settings.llm_provider != "openai" or settings.openai_api_key is None:
        return MockLLMProvider()

    primary = OpenAILLMProvider(settings, client=openai_client)
    return FallbackLLMProvider(primary, MockLLMProvider())
