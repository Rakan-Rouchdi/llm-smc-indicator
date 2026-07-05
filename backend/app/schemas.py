from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(str, Enum):
    tradingview_pine = "tradingview_pine"


class RootSymbol(str, Enum):
    ES = "ES"
    NQ = "NQ"
    UNKNOWN = "UNKNOWN"


class Direction(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class ThreeState(str, Enum):
    NONE = "NONE"
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class FVGState(str, Enum):
    NONE = "NONE"
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    MITIGATED = "MITIGATED"


class VolumeState(str, Enum):
    THIN = "THIN"
    NEUTRAL = "NEUTRAL"
    STRONG = "STRONG"


class HTFBias(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class Displacement(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    WEAK = "WEAK"
    NONE = "NONE"


class SessionName(str, Enum):
    ASIA = "ASIA"
    LONDON = "LONDON"
    NY_AM = "NY_AM"
    NY_PM = "NY_PM"
    OFF_HOURS = "OFF_HOURS"


class TradeAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    NO_TRADE = "NO_TRADE"


class OutcomeStatus(str, Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"


class Bias(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class EntryZoneType(str, Enum):
    FVG = "FVG"
    OB = "OB"
    IFVG = "IFVG"
    UNKNOWN = "UNKNOWN"


class DecisionEntryType(str, Enum):
    FVG = "FVG"
    OB = "OB"
    IFVG = "IFVG"
    NONE = "NONE"


class SetupEntry(StrictModel):
    zone_type: EntryZoneType
    low: float
    high: float
    preferred: float

    @model_validator(mode="after")
    def validate_zone_order(self) -> "SetupEntry":
        if self.low > self.high:
            raise ValueError("entry.low must be less than or equal to entry.high")
        if not self.low <= self.preferred <= self.high:
            raise ValueError("entry.preferred must be inside entry low/high")
        return self


class Risk(StrictModel):
    stop_loss: float
    take_profit_1: float
    risk_reward: float
    risk_points: float
    reward_points: float


class BOSFeature(StrictModel):
    state: ThreeState
    level: float | None


class FVGFeature(StrictModel):
    state: FVGState
    low: float | None
    high: float | None
    age_bars: int | None


class OrderBlockFeature(StrictModel):
    state: ThreeState
    low: float | None
    high: float | None
    age_bars: int | None


class LiquiditySweepFeature(StrictModel):
    state: ThreeState
    level: float | None
    pool_type: str
    age_bars: int | None


class SMTFeature(StrictModel):
    state: ThreeState
    lookback: int


class VolumeFeature(StrictModel):
    rvol: float
    state: VolumeState


class ConsolidationFeature(StrictModel):
    active: bool
    directional_efficiency: float
    range_atr_multiple: float


class SetupFeatures(StrictModel):
    bos: BOSFeature
    fvg: FVGFeature
    order_block: OrderBlockFeature
    liquidity_sweep: LiquiditySweepFeature
    smt: SMTFeature
    volume: VolumeFeature
    consolidation: ConsolidationFeature
    htf_bias: HTFBias
    displacement: Displacement


class SessionContext(StrictModel):
    name: SessionName
    current_high: float | None
    current_low: float | None
    completed_high: float | None
    completed_low: float | None


class SetupAlert(StrictModel):
    schema_version: Literal["1.0"]
    setup_id: str = Field(min_length=8)
    source: Source
    symbol: str
    root_symbol: RootSymbol
    companion_symbol: str
    timeframe: str
    bar_time: datetime
    bar_index: int
    direction: Direction
    rule_score: int = Field(ge=0, le=100)
    price: float
    entry: SetupEntry
    risk: Risk
    features: SetupFeatures
    session: SessionContext
    diagnostics: dict[str, Any]


class DecisionEntry(StrictModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    entry_type: DecisionEntryType = Field(alias="type")
    low: float | None
    high: float | None
    preferred: float | None

    @model_validator(mode="after")
    def validate_decision_zone(self) -> "DecisionEntry":
        values = [self.low, self.high, self.preferred]
        if self.entry_type == DecisionEntryType.NONE:
            return self
        if any(value is None for value in values):
            raise ValueError("trade entries require low, high, and preferred")
        if self.low is not None and self.high is not None and self.low > self.high:
            raise ValueError("entry.low must be less than or equal to entry.high")
        if (
            self.low is not None
            and self.high is not None
            and self.preferred is not None
            and not self.low <= self.preferred <= self.high
        ):
            raise ValueError("entry.preferred must be inside entry low/high")
        return self


class TakeProfit(StrictModel):
    tp1: float | None
    tp2: float | None


class LLMTradeDecision(StrictModel):
    schema_version: Literal["1.0"]
    setup_id: str
    action: TradeAction
    bias: Bias
    confidence: int = Field(ge=0, le=100)
    entry: DecisionEntry
    stop_loss: float | None
    take_profit: TakeProfit
    risk_reward: float | None
    expires_at: datetime | None
    headline_driver: str
    reason_summary: str = Field(min_length=1, max_length=500)
    confluence_notes: list[str] = Field(min_length=0, max_length=10)
    blocking_conditions: list[str] = Field(min_length=0, max_length=10)
    validation_notes: list[str] = Field(min_length=0, max_length=10)
    requires_human_review: bool


def validate_setup_alert(payload: dict[str, Any]) -> SetupAlert:
    return SetupAlert.model_validate(payload)


def validate_llm_trade_decision(payload: dict[str, Any]) -> LLMTradeDecision:
    return LLMTradeDecision.model_validate(payload)


class OutcomeUpdate(StrictModel):
    outcome: OutcomeStatus
    hit_target: str | None = None
    mfe_points: float | None = None
    mae_points: float | None = None
    notes: str | None = None
