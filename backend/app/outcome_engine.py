"""Conservative OHLC paper observations, never fills or trade instructions."""
from datetime import datetime, timedelta
from math import isfinite
import re
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class PriceBar(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    open_time: AwareDatetime
    close_time: AwareDatetime
    contract: str = Field(min_length=1, max_length=100, pattern=r"^[A-Z0-9_:!.-]+$")
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)

    @model_validator(mode="after")
    def valid_bar(self):
        if (self.close_time-self.open_time).total_seconds() != 60 or self.open_time.timestamp() % 60:
            raise ValueError("Only complete minute-aligned 60-second bars are supported")
        if not self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high:
            raise ValueError("Invalid OHLC envelope")
        return self


class PriceBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"]
    source: Literal["tradingview_price_feed"]
    feed_revision: Literal["paper_ohlcv_v1"]
    feed_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    symbol: Literal["CME_MINI_DL:NQ1!", "CME_MINI:NQ1!", "CME_MINI_DL:ES1!", "CME_MINI:ES1!"]
    price_basis: Literal["standard_unadjusted"]
    emitted_at: AwareDatetime
    bars: list[PriceBar] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def ordered(self):
        times = [b.open_time for b in self.bars]
        if times != sorted(set(times)):
            raise ValueError("Bars must be unique and ordered oldest first")
        root = self.symbol.split(":")[1][:-2]
        if any(not re.fullmatch(r"(?:CME_MINI(?:_DL)?:)?" + root + r"[HMUZ][0-9]{4}", b.contract) for b in self.bars):
            raise ValueError("Underlying contract must match the ES/NQ feed root")
        return self


def evaluate_paper_path(*, action, entry, stop, target, decided_at, expires_at,
                        anchor_time, anchor_price, bars: list[PriceBar], now):
    """No favorable OHLC ordering assumptions; ambiguity is always UNKNOWN.

    The anchor verifies the setup's exact closing price and contract against the
    independent feed. Post-decision coverage must be continuous, including
    partial first/last minutes. Session gaps are not silently filled.
    """
    def result(outcome="UNKNOWN", reason="WAITING_DATA", entered=None, resolved=None):
        return {"outcome": outcome, "reason": reason,
                "entry_bar_close": entered.isoformat() if entered else None,
                "resolution_bar_close": resolved.isoformat() if resolved else None,
                "method": "conservative_1m_ohlc_v1", "paper_only": True}
    values = [entry, stop, target, anchor_price]
    if any(not isinstance(v, (int, float)) or isinstance(v, bool) or not isfinite(v) for v in values):
        return result(reason="INVALID_LEVELS")
    if not ((action == "BUY" and stop < entry < target) or (action == "SELL" and target < entry < stop)):
        return result(reason="INVALID_LEVELS")
    horizon = decided_at + timedelta(hours=24)
    if expires_at is None or not decided_at < expires_at <= horizon or anchor_time > decided_at:
        return result(reason="INVALID_EXPIRY_OR_ANCHOR")
    bars = sorted(bars, key=lambda b: b.open_time)
    anchors = [b for b in bars if b.close_time == anchor_time]
    if len(anchors) != 1:
        return result(reason="MISSING_ANCHOR")
    anchor = anchors[0]
    if abs(anchor.close - anchor_price) > 0.000001:
        return result(reason="PRICE_BASIS_MISMATCH")
    if len({b.open_time for b in bars}) != len(bars):
        return result(reason="DUPLICATE_BARS")
    entered = None
    expected = anchor.close_time
    for b in bars:
        if b.open_time < expected:
            continue
        if b.close_time > now:
            return result(reason="UNCONFIRMED_BAR", entered=entered)
        if b.open_time != expected:
            return result(reason="MISSING_BARS", entered=entered)
        if b.contract != anchor.contract:
            return result(reason="CONTRACT_ROLL", entered=entered)
        expected = b.close_time
        if b.close_time <= decided_at:
            continue
        boundary = horizon if entered else expires_at
        if b.open_time >= boundary:
            return result("UNKNOWN" if entered else "EXPIRED",
                          "UNRESOLVED_AT_HORIZON" if entered else "NO_ENTRY_BEFORE_EXPIRY", entered)
        entry_touch = b.low <= entry <= b.high
        stop_touch = b.low <= stop if action == "BUY" else b.high >= stop
        target_touch = b.high >= target if action == "BUY" else b.low <= target
        partial = b.open_time < decided_at or b.close_time > boundary
        if partial and (entry_touch if entered is None else stop_touch or target_touch):
            return result(reason="PARTIAL_BOUNDARY_BAR", entered=entered)
        if entered is None and entry_touch:
            entered = b.close_time
            # Only an entry at the exact bar open proves entry preceded that bar's extrema.
            if (stop_touch or target_touch) and b.open != entry:
                return result(reason="ENTRY_EXIT_SAME_BAR", entered=entered)
        if entered:
            if stop_touch and target_touch:
                return result(reason="BOTH_EXITS_SAME_BAR", entered=entered)
            if stop_touch or target_touch:
                return result("LOSS" if stop_touch else "WIN", "ORDERED_BAR_RANGE_TOUCH", entered, b.close_time)
        if b.close_time >= (horizon if entered else expires_at):
            return result("UNKNOWN" if entered else "EXPIRED",
                          "UNRESOLVED_AT_HORIZON" if entered else "NO_ENTRY_BEFORE_EXPIRY", entered)
    return result(reason="WAITING_DATA" if now <= horizon + timedelta(minutes=30) else "INCOMPLETE_COVERAGE", entered=entered)
