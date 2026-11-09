"""Versioned consistency checks for Pine facts, not independent market-data verification."""

import re
from datetime import datetime

from app.schemas import SetupAlert

POLICY_VERSION = "strict_v1"


def confirmation_score(setup: SetupAlert) -> int:
    f, direction = setup.features, setup.direction.value
    return sum((
        25 if f.fvg.state.value == direction else 0,
        20 if f.bos.state.value == direction else 0,
        10 if f.liquidity_sweep.state.value == direction else 0,
        10 if f.smt.state.value == direction else 0,
        15 if f.htf_bias.value == direction else 0,
        10 if f.volume.state.value == "STRONG" else 0,
        10 if f.displacement.value == direction else 0,
    ))


def setup_rejections(setup: SetupAlert, minimum: int = 75, max_bars: int = 6) -> list[str]:
    f, d, direction = setup.features, setup.diagnostics, setup.direction.value
    errors = []
    contract = re.fullmatch(r"(ES|NQ)(?:[1-9]!|[FGHJKMNQUVXZ][0-9]{1,4})", setup.symbol.rsplit(":", 1)[-1])
    if contract is None or contract.group(1) != setup.root_symbol.value:
        errors.append("Unsupported instrument; strict_v1 supports ES/NQ only")
    if d.get("policy_version") != POLICY_VERSION:
        errors.append("Unsupported setup policy; update the Pine alert snapshot")
    if not d.get("bar_close_time"):
        errors.append("Exact candle-close timestamp is required")
    if f.fvg.state.value != direction or setup.entry.zone_type.value != "FVG":
        errors.append("Aligned active FVG is required")
    elif (f.fvg.low, f.fvg.high) != (setup.entry.low, setup.entry.high):
        errors.append("Entry zone differs from the source FVG")
    if f.bos.state.value != direction:
        errors.append("Aligned BOS is required")
    if f.bos.level is None:
        errors.append("BOS price level is required")
    if f.htf_bias.value != direction:
        errors.append("Aligned HTF bias is required")
    if f.volume.state.value == "THIN" or f.volume.rvol < 0.7:
        errors.append("Thin volume blocks the setup")
    if f.volume.state.value == "STRONG" and f.volume.rvol < 1.5:
        errors.append("Strong volume requires RVOL of at least 1.5")
    if d.get("fvg_retested") is not True or d.get("zone_invalidated") is not False:
        errors.append("Confirmed retest of a valid zone is required")
    if d.get("companion_aligned") is not True:
        errors.append("Companion bars are missing or misaligned")
    # Older saved alert snapshots remain compatible until the approved cutover.
    # New detector revisions must attest to complete minute coverage at close.
    if d.get("detector_revision") == "timing_sessions_v2":
        if d.get("session_data_ready") is not True or d.get("session_resolution") != "1":
            errors.append("Complete one-minute session data is required")
        try:
            closed = datetime.fromisoformat(d["bar_close_time"].replace("Z", "+00:00"))
            as_of = d.get("session_as_of_ms")
            if closed.tzinfo is None or type(as_of) is not int or as_of != int(closed.timestamp() * 1000):
                raise ValueError
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
            errors.append("Session data must end at the confirmed candle close")
        pool_end = d.get("sweep_session_end_ms")
        if pool_end is not None and (type(pool_end) is not int or pool_end > int(setup.bar_time.timestamp() * 1000)):
            errors.append("Sweep session pool must predate the chart bar")
    clear_bars = d.get("consolidation_clear_bars")
    if type(clear_bars) is not int or clear_bars < 2:
        errors.append("Consolidation exit is not confirmed")
    fvg_age, bos_age = f.fvg.age_bars, d.get("bos_age_bars")
    if (type(fvg_age) is not int or type(bos_age) is not int
            or not 1 <= fvg_age <= bos_age <= min(fvg_age + 2, max_bars)):
        errors.append("BOS/FVG sequence or age is invalid")
    liquidity = False
    for state, age in [(f.liquidity_sweep.state.value, f.liquidity_sweep.age_bars),
                       (f.smt.state.value, d.get("smt_age_bars"))]:
        if state == direction and type(age) is int and type(bos_age) is int and bos_age <= age <= max_bars:
            liquidity = True
        elif state == direction:
            errors.append("Scored liquidity evidence has an invalid age")
    if not liquidity:
        errors.append("Recent aligned liquidity evidence must precede BOS")
    score = confirmation_score(setup)
    if setup.rule_score != score:
        errors.append("Rule score does not match source confirmations")
    if min(score, setup.rule_score) < minimum:
        errors.append("Rule score below strict policy threshold")
    low, high = sorted((setup.risk.stop_loss, setup.risk.take_profit_1))
    if not low < setup.price < high:
        errors.append("Signal price is already beyond stop or target")
    sign = 1 if direction == "BULLISH" else -1
    risk = sign * (setup.entry.preferred - setup.risk.stop_loss)
    reward = sign * (setup.risk.take_profit_1 - setup.entry.preferred)
    if risk <= 0 or reward <= 0:
        errors.append("Source risk geometry is invalid")
    elif (abs(risk - setup.risk.risk_points) > .001 or abs(reward - setup.risk.reward_points) > .001
          or abs(reward / risk - setup.risk.risk_reward) > .05 or reward / risk < 1.5):
        errors.append("Source risk/reward is inconsistent or below minimum")
    return errors
