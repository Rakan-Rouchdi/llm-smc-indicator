import json
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.config import get_settings
from app.database import SessionLocal
from app.llm_client import MockLLMProvider
from app.models import AutoOutcomeRecord, LLMDecisionRecord, NotificationRecord, PriceBarRecord, SetupAlertRecord
from app.outcome_engine import PriceBar, evaluate_paper_path
from app.outcome_tracking import evaluate_outcomes_once, latest_automatic
from app.workflow import process_tradingview_alert

T = datetime(2026, 11, 14, 10, tzinfo=timezone.utc)


def bar(minute, o=101, h=103, l=100.5, c=102, contract="CME_MINI_DL:NQZ2026", start=T):
    return PriceBar(open_time=start+timedelta(minutes=minute), close_time=start+timedelta(minutes=minute+1),
        open=o, high=h, low=l, close=c, contract=contract)


def evaluate(path_bars, **overrides):
    args = dict(action="BUY", entry=100, stop=98, target=104, decided_at=T,
        expires_at=T+timedelta(minutes=3), anchor_time=T, anchor_price=100,
        bars=[bar(-1, 100, 101, 99, 100), *path_bars], now=T+timedelta(minutes=10))
    args.update(overrides)
    return evaluate_paper_path(**args)


@pytest.mark.parametrize("side,outcome", [("BUY", "WIN"), ("BUY", "LOSS"), ("SELL", "WIN"), ("SELL", "LOSS")])
def test_ordered_paper_exits(side, outcome):
    first = bar(0, 100, 101, 99, 100)
    high_exit = (side == "BUY") == (outcome == "WIN")
    second = bar(1, 100, 105 if high_exit else 101, 99 if high_exit else 95, 100)
    kwargs = {} if side == "BUY" else dict(action="SELL", stop=102, target=96)
    assert evaluate([first, second], **kwargs)["outcome"] == outcome


@pytest.mark.parametrize("bars,reason", [
    ([bar(1)], "MISSING_BARS"),
    ([bar(0, 101, 105, 99, 103)], "ENTRY_EXIT_SAME_BAR"),
    ([bar(0, 100, 105, 97, 100)], "BOTH_EXITS_SAME_BAR"),
    ([bar(0, 100, 101, 99, 100), bar(1, 100, 105, 97, 100)], "BOTH_EXITS_SAME_BAR"),
    ([bar(0, contract="CME_MINI_DL:NQH2027")], "CONTRACT_ROLL"),
    ([bar(0), bar(0)], "DUPLICATE_BARS"),
])
def test_uncertain_sequences_are_unknown(bars, reason):
    result = evaluate(bars)
    assert result["outcome"] == "UNKNOWN" and result["reason"] == reason


def test_partial_boundary_and_pre_entry_extremes():
    assert evaluate([bar(0, 100, 101, 99, 100)], decided_at=T+timedelta(seconds=30))["reason"] == "PARTIAL_BOUNDARY_BAR"
    assert evaluate([bar(0), bar(1), bar(2, 100, 101, 99, 100)], expires_at=T+timedelta(minutes=2, seconds=30))["reason"] == "PARTIAL_BOUNDARY_BAR"
    assert evaluate([bar(0, 102, 105, 101, 103), bar(1, 100, 101, 99, 100)])["outcome"] == "UNKNOWN"
    assert evaluate([bar(0), bar(1), bar(2)])["outcome"] == "EXPIRED"


def test_missing_anchor_and_price_basis_mismatch():
    assert evaluate([], bars=[])["reason"] == "MISSING_ANCHOR"
    assert evaluate([bar(0)], anchor_price=100.25)["reason"] == "PRICE_BASIS_MISMATCH"
    assert evaluate([bar(0)], expires_at=None)["reason"] == "INVALID_EXPIRY_OR_ANCHOR"
    assert evaluate([bar(0)], stop=105)["reason"] == "INVALID_LEVELS"
    assert evaluate([bar(0)], entry=float("nan"))["reason"] == "INVALID_LEVELS"


def test_complete_horizon_does_not_invent_a_result():
    bars = [bar(i, 100, 101, 99, 100) for i in range(1440)]
    result = evaluate(bars, now=T+timedelta(hours=25))
    assert result["outcome"] == "UNKNOWN" and result["reason"] == "UNRESOLVED_AT_HORIZON"


@pytest.mark.parametrize("change", [{"high": 99}, {"low": 105}, {"open": float("inf")},
    {"close_time": "2026-11-14T10:02:00Z"}, {"open_time": "2026-11-14T10:00:00"}])
def test_invalid_price_bar_rejected(change):
    raw = bar(0).model_dump()
    raw.update(change)
    with pytest.raises(ValidationError): PriceBar.model_validate(raw)


@pytest.fixture
def live_candidate(client, fresh_setup_payload, monkeypatch):
    class Recorded(MockLLMProvider):
        model_name = "fixture-openai-response"
    monkeypatch.setattr("app.workflow.get_llm_provider", lambda _: Recorded())
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    start = now-timedelta(minutes=5)
    with SessionLocal() as db:
        process_tradingview_alert(fresh_setup_payload, db,
            get_settings().model_copy(update={"llm_provider": "openai"}),
            context_override={"news": {"status": "CLEAR"}})
        s, d = db.query(SetupAlertRecord).one(), db.query(LLMDecisionRecord).one()
        # Synthetic stored evidence, not live market data or a bypass of production approval.
        raw = json.loads(s.payload_json)
        raw["diagnostics"].update(detector_revision="timing_sessions_v2", bar_close_time=start.isoformat())
        raw["price"] = 100
        s.symbol, s.payload_json = "CME_MINI_DL:NQ1!", json.dumps(raw)
        d.created_at, d.entry_preferred, d.stop_loss, d.take_profit_1 = start, 100, 98, 104
        output = json.loads(d.raw_output_json)
        output["expires_at"] = (start+timedelta(minutes=3)).isoformat()
        d.raw_output_json = json.dumps(output)
        db.commit()
        decision_id = d.id
    monkeypatch.setenv("OUTCOME_TRACKING_ENABLED", "true")
    monkeypatch.setenv("REQUIRE_VERIFIED_NEWS", "true")
    monkeypatch.setenv("OUTCOME_FEED_ID", "nq-paper-v1")
    monkeypatch.setenv("OUTCOME_FEED_SYMBOL", "CME_MINI_DL:NQ1!")
    get_settings.cache_clear()
    payload = {"schema_version": "1.0", "source": "tradingview_price_feed", "feed_revision": "paper_ohlcv_v1",
        "feed_id": "nq-paper-v1", "symbol": "CME_MINI_DL:NQ1!", "price_basis": "standard_unadjusted",
        "emitted_at": now.isoformat(), "bars": [b.model_dump(mode="json") for b in
            [bar(-1, 100, 101, 99, 100, start=start), bar(0, 100, 101, 99, 100, start=start),
             bar(1, 101, 105, 100, 104, start=start)]]}
    return payload, decision_id


def post_prices(client, payload):
    return client.post("/webhooks/tradingview/prices?secret=test-secret", json=payload)


def test_feed_to_automatic_outcome_is_deduplicated_and_does_not_trade(client, live_candidate):
    payload, decision_id = live_candidate
    assert post_prices(client, payload).json()["added"] == 3
    assert post_prices(client, payload).json()["added"] == 0
    assert evaluate_outcomes_once(get_settings()) == 1
    assert evaluate_outcomes_once(get_settings()) == 0
    result = client.get("/forward-testing").json()["rows"][0]
    assert result["automatic"]["outcome"] == "WIN" and result["review"] is None
    assert client.get("/evaluation").json()["automatic_paper_outcomes"] == {"WIN": 1}
    assert client.get("/evaluation").json()["manual_outcomes"] == {"UNRECORDED": 1}
    assert len(client.get(f"/forward-testing/decisions/{decision_id}/automatic").json()["evaluations"]) == 1
    with SessionLocal() as db:
        assert db.query(SetupAlertRecord).count() == db.query(LLMDecisionRecord).count() == 1
        assert db.query(NotificationRecord).count() == 0
        assert db.query(PriceBarRecord).count() == 3
    assert "Automatic paper outcome" in client.get("/dashboard/forward-testing").text


def test_conflicting_correction_preserves_old_evidence_and_marks_unknown(client, live_candidate):
    payload, decision_id = live_candidate
    post_prices(client, payload)
    evaluate_outcomes_once(get_settings())
    payload["bars"][1]["low"] = 97
    assert post_prices(client, payload).json()["conflicts"] == 1
    assert evaluate_outcomes_once(get_settings()) == 1
    with SessionLocal() as db:
        assert latest_automatic(db, [decision_id])[decision_id]["reason"] == "CONFLICTING_PRICE_EVIDENCE"
        assert db.query(AutoOutcomeRecord).count() == 2


@pytest.mark.parametrize("condition", ["test", "rejected", "fallback", "legacy"])
def test_ineligible_decisions_never_auto_scored(client, live_candidate, condition):
    payload, _ = live_candidate
    with SessionLocal() as db:
        d, s = db.query(LLMDecisionRecord).one(), db.query(SetupAlertRecord).one()
        raw = json.loads(s.payload_json)
        if condition == "test": raw["diagnostics"]["test_mode"] = True
        if condition == "legacy": raw["diagnostics"]["detector_revision"] = "old"
        if condition == "rejected": d.validator_status = "REJECTED"
        if condition == "fallback": d.model = "mock-fallback"
        s.payload_json = json.dumps(raw)
        db.commit()
    post_prices(client, payload)
    assert evaluate_outcomes_once(get_settings()) == 0


def test_feed_auth_schema_disabled_and_no_safety_mutation(client, live_candidate, monkeypatch):
    payload, _ = live_candidate
    assert client.post("/webhooks/tradingview/prices", json=payload).status_code == 401
    for changed in ({"symbol": "CME_MINI:NQ1!"}, {"feed_id": "wrong"},
                    {"emitted_at": "2099-01-01T00:00:00Z"}, {"price_basis": "adjusted"}):
        assert post_prices(client, {**payload, **changed}).status_code == 422
    assert client.post("/webhooks/tradingview/prices?secret=test-secret", content=b"x"*32769).status_code == 413
    assert post_prices(client, {**payload, "bars": payload["bars"]*2}).status_code == 422
    monkeypatch.setenv("OUTCOME_TRACKING_ENABLED", "false")
    get_settings.cache_clear()
    assert post_prices(client, payload).status_code == 422
    assert evaluate_outcomes_once(get_settings()) == 0
    monkeypatch.setenv("DASHBOARD_USERNAME", "operator")
    monkeypatch.setenv("DASHBOARD_PASSWORD", "synthetic-password")
    get_settings.cache_clear()
    assert client.get("/forward-testing/decisions/1/automatic").status_code == 401


def test_wrong_underlying_and_future_bars_rejected(client, live_candidate):
    payload, _ = live_candidate
    payload["bars"][0]["contract"] = "CME_MINI_DL:ESZ2026"
    assert post_prices(client, payload).status_code == 422
    payload["bars"][0]["contract"] = "CME_MINI_DL:NQZ2026"
    future = datetime.now(timezone.utc).replace(second=0, microsecond=0)+timedelta(hours=1)
    payload["bars"] = [bar(0, start=future).model_dump(mode="json")]
    assert post_prices(client, payload).status_code == 422


def test_price_receipt_wakes_worker_without_running_llm(client, live_candidate, monkeypatch):
    from app.main import app
    calls = []
    class WakeOnly:
        def notify(self): calls.append("wake")
    monkeypatch.setattr(app.state, "decision_worker", WakeOnly())
    monkeypatch.setattr("app.workflow.get_llm_provider", lambda _: pytest.fail("Prices must not call an LLM"))
    assert post_prices(client, live_candidate[0]).status_code == 202
    assert calls == ["wake"]


def test_background_loop_runs_outcomes(client, monkeypatch):
    from app.worker import DecisionWorker
    worker = DecisionWorker(get_settings().model_copy(update={"outcome_tracking_enabled": True}))
    calls = []
    monkeypatch.setattr(worker, "run_once", lambda: False)
    monkeypatch.setattr("app.worker.deliver_one", lambda _: False)
    def check(_):
        calls.append("evaluated")
        worker._stop.set()
        worker._wake.set()
    monkeypatch.setattr("app.worker.evaluate_outcomes_once", check)
    worker._run()
    assert calls == ["evaluated"]
    assert worker._next_delay() == 300


def test_auto_tracking_cannot_disable_news_gate(client, monkeypatch):
    monkeypatch.setenv("OUTCOME_TRACKING_ENABLED", "true")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="REQUIRE_VERIFIED_NEWS"):
        get_settings()
