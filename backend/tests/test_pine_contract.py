from pathlib import Path


def test_pine_strict_contract_and_clean_default():
    source = (Path(__file__).resolve().parents[2] / "pine/smc_llm_candidate_detector.pine").read_text()
    assert source.count('str.format_time(time_close,') == 2
    assert '"_strict_v1"' in source
    assert 'line.new(' not in source
    assert 'panelMode == "Compact" ? 7 : 20' in source
    assert 'input.bool(false, "Show FVG zones")' in source
    assert 'input.bool(false, "Enable test webhook alert"' in source
    assert 'math.round_to_mintick((entryLow + entryHigh) / 2.0)' in source
    assert 'bullBosRecent and htfBias == "BULLISH"' in source
    assert 'bearBosRecent and htfBias == "BEARISH"' in source
    assert 'barstate.isconfirmed and supportedChart and companionAligned and sequenceValid' in source
    for field in ("policy_version", "bar_close_time", "fvg_retested", "zone_invalidated", "companion_aligned", "consolidation_clear_bars"):
        assert field in source
