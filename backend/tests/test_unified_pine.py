"""Source-contract guards; runtime Pine checks are recorded in the audit doc.

These are not a Python simulation of the trading strategy or a profitability
test. Fingerprints pin the approved logic while the alert plumbing changes.
"""
import hashlib
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "pine/smc_llm_candidate_detector.pine").read_text()


@pytest.mark.parametrize("start,end,digest", [
    ("f_session_window(int at) =>", "// Offset + lookahead_on",
     "ff1e4313c8e54bc65d42f3e0a483fddbe3a7eb4019294fc50c52c98ac365f996"),
    ("float pivotHigh =", "bool shouldAlert =",
     "34dfbc62f06f13fc231507f5fe924bff3c3c6a7863a1629ad92c26abcae4e084"),
    ("if shouldAlert\n", "// Deduplicate chart candidates",
     "754a6be4889d9036f7eedbd19dbb89085f5ac56e3a6199b6a5f05f4ad2155f04"),
])
def test_approved_signal_logic_and_payload_are_preserved(start, end, digest):
    block = SOURCE[SOURCE.index(start):SOURCE.index(end)]
    # Price mode hides drawings only; normalize those explicitly allowed guards.
    block = block.replace(" and signalMode", "").replace("bgcolor(signalMode and ", "bgcolor(")
    assert hashlib.sha256(block.encode()).hexdigest() == digest


def test_one_script_has_mutually_exclusive_alert_streams():
    assert not (ROOT / "pine/smc_paper_price_feed.pine").exists()
    assert SOURCE.count('indicator("SMC LLM Candidate Detector"') == 1
    assert 'input.string("SMC setups", "Alert stream", options=["SMC setups", "Outcome prices"]' in SOURCE
    assert 'bool signalMode = alertStream == "SMC setups"' in SOURCE
    assert 'bool outcomePriceMode = alertStream == "Outcome prices"' in SOURCE
    assert 'bool shouldAlert = signalMode and enableAlerts and not enableTestWebhookAlert and newCandidate' in SOURCE
    assert 'bool shouldSendTestWebhook = signalMode and enableAlerts and enableTestWebhookAlert' in SOURCE
    assert 'if outcomePriceMode and priceChartSupported' in SOURCE
    assert SOURCE.index('string alertStream = input.') > SOURCE.index('bool enableTestWebhookAlert = input.')
    assert SOURCE.count('alert.freq_once_per_bar_close)') == 3
    assert 'alert.freq_all' not in SOURCE


def test_price_mode_preserves_bounded_confirmed_unadjusted_protocol():
    block = SOURCE[SOURCE.index('bool priceChartSupported ='):]
    assert 'chart.is_standard and timeframe.period == "5"' in block
    assert '(syminfo.root == "ES" or syminfo.root == "NQ")' in block
    assert '"^[A-Za-z0-9_-]{1,64}$"' in block
    assert 'backadjustment=backadjustment.off' in block
    assert 'settlement_as_close=settlement_as_close.off' in block
    assert 'session=session.extended' in block
    assert 'syminfo.current_contract' in block
    assert 'if barstate.isconfirmed' in block
    assert 'closesAt <= time_close and (not barstate.isrealtime or closesAt <= timenow)' in block
    assert 'if array.size(priceHistory) > 20' in block
    assert 'array.shift(priceHistory)' in block
    assert 'if enableAlerts and priceFeedIdValid and barstate.isrealtime' in block
    for field in ('tradingview_price_feed', 'paper_ohlcv_v1', 'standard_unadjusted', 'emitted_at', 'contract'):
        assert field in block


def test_funnel_is_cumulative_and_uses_pre_mitigation_closed_state():
    stages = ('Data', 'Retest', 'Sequence', 'Structure', 'Liquidity', 'Consolidation', 'Volume', 'Score')
    for previous, stage in zip(stages, stages[1:]):
        assert f'bool audit{stage} = audit{previous} and ' in SOURCE
    assert 'bool auditData = barstate.isconfirmed and supportedChart and sessionDataReady and companionAligned' in SOURCE
    assert SOURCE.index('lastClosedGate :=') < SOURCE.index('// Mark FVG mitigation after candidate checks')
    assert 'var string lastClosedGate = "NO CLOSED BAR"\nvar int lastClosedAt = na\nif barstate.isconfirmed' in SOURCE
    assert 'CUMULATIVE / NOT WIN RATE' in SOURCE
    assert 'HTF " + effectiveHtfTimeframe + " neutral bars' in SOURCE
    assert 'panelMode == "Funnel" ? position.middle_right : position.top_right' in SOURCE


def test_price_mode_does_not_draw_trade_candidates_or_proof_markers():
    assert 'if newCandidate and showProvisionalTrades and signalMode' in SOURCE
    assert SOURCE.count('if showProofMarkers and signalMode') == 6
    assert SOURCE.count('if showZones and signalMode') == 2
    assert 'bgcolor(signalMode and consolidationActive' in SOURCE
    assert '"Setup / test alerts", "DISABLED"' in SOURCE
