from pathlib import Path


def test_pine_strict_contract_and_clean_default():
    source = (Path(__file__).resolve().parents[2] / "pine/smc_llm_candidate_detector.pine").read_text()
    assert source.count('str.format_time(time_close,') == 2
    assert '"_strict_v1"' in source
    assert 'line.new(' not in source
    assert 'panelMode == "Compact" ? 8 : 20' in source
    assert 'input.bool(false, "Show FVG zones")' in source
    assert 'input.bool(false, "Enable test webhook alert"' in source
    assert 'math.round_to_mintick((entryLow + entryHigh) / 2.0)' in source
    assert 'bullBosRecent and htfBias == "BULLISH"' in source
    assert 'bearBosRecent and htfBias == "BEARISH"' in source
    assert 'barstate.isconfirmed and supportedChart and sessionDataReady and companionAligned and sequenceValid' in source
    for field in ("policy_version", "bar_close_time", "fvg_retested", "zone_invalidated", "companion_aligned", "consolidation_clear_bars"):
        assert field in source


def test_pine_timing_session_and_diagnostic_contract():
    source = (Path(__file__).resolve().parents[2] / "pine/smc_llm_candidate_detector.pine").read_text()
    for level in ("high", "low"):
        assert f'request.security(syminfo.tickerid, "D", {level}[1], lookahead=barmerge.lookahead_on)' in source
    assert 'request.security_lower_tf(syminfo.tickerid, "1", [time, time_close, high, low]' in source
    assert 'trackedSessionComplete := at == starts' in source
    assert 'trackedSessionComplete and at == trackedMinuteClose' in source
    assert 'sessionAsOf == chartClose' in source
    assert source.index('float sweepSessionHigh = completedSessionHigh') < source.index('for i = 0 to minuteCount - 1')
    assert 'sweepSessionEnd <= time' in source
    assert 'currentSessionHigh := namedSession ? high' not in source
    assert '"OPEN / PREVIEW"' in source
    blocker = next(line for line in source.splitlines() if 'string blocker =' in line)
    assert 'barstate.isconfirmed' not in blocker
    assert 'f_event_status(bosState, bosAge' in source
    assert 'f_event_status(sweepState, sweepAge' in source
    assert 'f_event_status(smtState, smtAge' in source
    assert 'f_retire_box(activeFvgBox, fvgState)' in source
    assert 'f_retire_box(activeFvgBox, "SUPERSEDED")' in source


def test_table_is_not_hidden_behind_price_candles():
    source = (Path(__file__).resolve().parents[2] / "pine/smc_llm_candidate_detector.pine").read_text()
    assert "behind_chart=false" in source
