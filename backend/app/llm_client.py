from __future__ import annotations

from datetime import timedelta
from typing import Any, Protocol

from app.config import Settings
from app.schemas import (
    Bias,
    DecisionEntry,
    DecisionEntryType,
    LLMTradeDecision,
    SetupAlert,
    TakeProfit,
    TradeAction,
)


class LLMProvider(Protocol):
    model_name: str

    def decide(self, llm_input: dict[str, Any]) -> LLMTradeDecision:
        ...


class MockLLMProvider:
    model_name = "mock-llm-deterministic"

    def decide(self, llm_input: dict[str, Any]) -> LLMTradeDecision:
        setup = SetupAlert.model_validate(llm_input["setup_alert"])
        context = llm_input.get("context", {})
        news = context.get("news") if isinstance(context.get("news"), dict) else {}
        blackout_active = bool(context.get("news_blackout_active")) or bool(news.get("blackout_active"))
        blocked = blackout_active or setup.features.consolidation.active

        if blocked:
            return LLMTradeDecision(
                schema_version="1.0",
                setup_id=setup.setup_id,
                action=TradeAction.NO_TRADE,
                bias=Bias.NEUTRAL,
                confidence=0,
                entry=DecisionEntry(type=DecisionEntryType.NONE, low=None, high=None, preferred=None),
                stop_loss=None,
                take_profit=TakeProfit(tp1=None, tp2=None),
                risk_reward=None,
                expires_at=None,
                headline_driver=news.get("headline_summary") or "Mock blocked context",
                reason_summary="Mock provider returned no trade because a blocking condition is active.",
                confluence_notes=[],
                blocking_conditions=["Mock blocking condition active"],
                validation_notes=["Mock LLM provider used because live credentials are not configured."],
                requires_human_review=False,
            )

        action = TradeAction.BUY if setup.direction.value == "BULLISH" else TradeAction.SELL
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
            reason_summary="Mock provider mirrored the structured setup into a deterministic test decision.",
            confluence_notes=[
                f"{setup.direction.value.title()} source setup",
                f"Rule score {setup.rule_score}",
            ],
            blocking_conditions=[],
            validation_notes=["Mock LLM provider used because live credentials are not configured."],
            requires_human_review=False,
        )


class OpenAICompatibleLLMProvider:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.model_name = settings.llm_model

    def decide(self, llm_input: dict[str, Any]) -> LLMTradeDecision:
        raise RuntimeError("Live OpenAI-compatible provider is deferred beyond Phase 1.")


def get_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "openai" and settings.openai_api_key:
        return OpenAICompatibleLLMProvider(settings)
    return MockLLMProvider()
