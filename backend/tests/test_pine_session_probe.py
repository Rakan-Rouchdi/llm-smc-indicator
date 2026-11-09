import importlib.util
from pathlib import Path


def test_probe_uses_actual_production_helpers_and_has_no_alerts():
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("probe", root / "backend/scripts/pine_session_probe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    probe = module.build_probe()
    source = (root / "pine/smc_llm_candidate_detector.pine").read_text()
    helper = source[source.index("f_session_window(int at) =>"):source.index("\n[minuteTimes, minuteCloses, minuteHighs, minuteLows] = request.")]
    assert helper in probe
    assert 'alert(' not in probe and 'strategy(' not in probe
    assert 'runtime.error("Session regression failed:' in probe
    for case in range(12):
        assert f"f_check({case}," in probe
