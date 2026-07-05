from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import ValidationError

from app.schemas import Direction, LLMTradeDecision, SetupAlert, TradeAction


ValidatorStatus = Literal["APPROVED", "REJECTED"]


@dataclass(frozen=True)
class ValidationPolicy:
    min_confidence_for_trade: int = 70
    min_risk_reward: float = 1.5
    max_setup_age_minutes: int = 15
    no_trade_during_blackout: bool = True
    no_trade_when_consolidation: bool = True


@dataclass(frozen=True)
class ValidatorResult:
    validator_status: ValidatorStatus
    final_action: TradeAction
    final_confidence: int
    rejections: list[str]
    warnings: list[str]

    def model_dump(self) -> dict[str, Any]:
        return {
            "validator_status": self.validator_status,
            "final_action": self.final_action.value,
            "final_confidence": self.final_confidence,
            "rejections": self.rejections,
            "warnings": self.warnings,
        }


def calculate_risk_reward(
    action: TradeAction | str,
    entry: float,
    stop_loss: float,
    take_profit_1: float,
) -> float | None:
    trade_action = TradeAction(action)
    if trade_action == TradeAction.BUY:
        risk = entry - stop_loss
        reward = take_profit_1 - entry
    elif trade_action == TradeAction.SELL:
        risk = stop_loss - entry
        reward = entry - take_profit_1
    else:
        return None

    if risk <= 0 or reward <= 0:
        return None
    return round(reward / risk, 4)


def _reject(rejections: list[str], warnings: list[str] | None = None) -> ValidatorResult:
    return ValidatorResult(
        validator_status="REJECTED",
        final_action=TradeAction.NO_TRADE,
        final_confidence=0,
        rejections=rejections,
        warnings=warnings or [],
    )


def _coerce_decision(decision: LLMTradeDecision | dict[str, Any]) -> LLMTradeDecision | ValidatorResult:
    if isinstance(decision, LLMTradeDecision):
        return decision
    try:
        return LLMTradeDecision.model_validate(decision)
    except ValidationError as exc:
        return _reject([f"Malformed LLM output: {exc.errors()[0]['msg']}"])


def validate_llm_decision(
    setup_alert: SetupAlert,
    decision: LLMTradeDecision | dict[str, Any],
    context: dict[str, Any] | None = None,
    policy: ValidationPolicy | None = None,
    current_time: datetime | None = None,
) -> ValidatorResult:
    context = context or {}
    policy = policy or ValidationPolicy()
    warnings = ["Confidence is a setup-quality score, not a win probability."]
    rejections: list[str] = []

    coerced_decision = _coerce_decision(decision)
    if isinstance(coerced_decision, ValidatorResult):
        return coerced_decision

    llm_decision = coerced_decision

    if llm_decision.setup_id != setup_alert.setup_id:
        rejections.append("LLM setup_id does not match setup alert")

    if policy.no_trade_during_blackout and context.get("news_blackout_active") is True:
        rejections.append("News blackout active")

    if policy.no_trade_when_consolidation and setup_alert.features.consolidation.active:
        rejections.append("Setup is blocked during consolidation")

    if current_time is not None:
        setup_age_minutes = (current_time - setup_alert.bar_time).total_seconds() / 60
        if setup_age_minutes > policy.max_setup_age_minutes:
            rejections.append("Setup is stale")

    if llm_decision.action == TradeAction.NO_TRADE:
        rejections.append("LLM chose NO_TRADE")

    if llm_decision.action in {TradeAction.BUY, TradeAction.SELL}:
        entry = llm_decision.entry.preferred
        stop_loss = llm_decision.stop_loss
        take_profit_1 = llm_decision.take_profit.tp1

        if entry is None or stop_loss is None or take_profit_1 is None:
            rejections.append("Trade decision requires numeric entry, stop loss, and TP1")
        else:
            if llm_decision.action == TradeAction.BUY:
                if setup_alert.direction != Direction.BULLISH:
                    rejections.append("BUY conflicts with bearish source setup")
                if stop_loss >= entry:
                    rejections.append("BUY stop loss must be below entry")
                if take_profit_1 <= entry:
                    rejections.append("BUY take profit must be above entry")

            if llm_decision.action == TradeAction.SELL:
                if setup_alert.direction != Direction.BEARISH:
                    rejections.append("SELL conflicts with bullish source setup")
                if stop_loss <= entry:
                    rejections.append("SELL stop loss must be above entry")
                if take_profit_1 >= entry:
                    rejections.append("SELL take profit must be below entry")

            computed_rr = calculate_risk_reward(
                llm_decision.action,
                entry,
                stop_loss,
                take_profit_1,
            )
            if computed_rr is None:
                rejections.append("Risk/reward cannot be calculated")
            elif llm_decision.risk_reward is not None and abs(computed_rr - llm_decision.risk_reward) > 0.05:
                rejections.append("Risk/reward does not match entry, stop, and target")

        if llm_decision.risk_reward is None:
            rejections.append("Trade decision requires risk/reward")
        elif llm_decision.risk_reward < policy.min_risk_reward:
            rejections.append("Risk/reward below minimum")

        if llm_decision.confidence < policy.min_confidence_for_trade:
            rejections.append("Confidence below approval threshold")

    if rejections:
        return _reject(rejections, warnings)

    return ValidatorResult(
        validator_status="APPROVED",
        final_action=llm_decision.action,
        final_confidence=llm_decision.confidence,
        rejections=[],
        warnings=warnings,
    )
