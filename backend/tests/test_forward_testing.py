import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest

from app.config import get_settings
from app.database import SessionLocal
from app.forward_testing import COHORT_START
from app.llm_client import MockLLMProvider
from app.models import ForwardReviewRecord, LLMDecisionRecord, SetupAlertRecord
from app.workflow import process_tradingview_alert


@pytest.fixture
def reviewable(client, fresh_setup_payload, monkeypatch):
    class RecordedResponse(MockLLMProvider):
        model_name = "fixture-live-response"
    monkeypatch.setattr("app.workflow.get_llm_provider", lambda _: RecordedResponse())
    with SessionLocal() as db:
        process_tradingview_alert(fresh_setup_payload, db,
            get_settings().model_copy(update={"llm_provider": "openai"}),
            context_override={"news": {"status": "CLEAR"}})
        row = db.query(SetupAlertRecord).one()
        payload = json.loads(row.payload_json)
        payload["diagnostics"]["detector_revision"] = "timing_sessions_v2"
        row.payload_json = json.dumps(payload)
        db.commit()
        decision_id = db.query(LLMDecisionRecord).one().id
    return decision_id


def review_body(**overrides):
    return {"outcome": "UNKNOWN", "entry_status": "UNKNOWN", "source_verified": False,
            "observed_until": datetime.now(timezone.utc).isoformat(),
            "notes": "Synthetic observation; no verified event ordering available.", **overrides}


def test_ledger_and_append_only_paper_review(client, reviewable):
    endpoint = f"/forward-testing/decisions/{reviewable}/reviews"
    assert client.post(endpoint, json=review_body()).status_code == 200
    assert client.post(endpoint, json=review_body(outcome="WIN", entry_status="TOUCHED", source_verified=True)).status_code == 200
    assert len(client.get(endpoint).json()["reviews"]) == 2
    ledger = client.get("/forward-testing").json()
    assert ledger["total_receipts"] == 1
    assert ledger["rows"][0]["review"]["outcome"] == "WIN"
    assert ledger["rows"][0]["cohort_status"] == "ELIGIBLE_PAPER_REVIEW"
    assert ledger["accuracy_status"] == "NOT_ESTABLISHED"
    assert client.get("/evaluation").json()["manual_outcomes"] == {"WIN": 1}
    html = client.get("/dashboard/forward-testing").text
    assert 'name="entry_status"' in html and "Append a correction" in html
    with SessionLocal() as db:
        assert db.query(ForwardReviewRecord).count() == 2
        assert db.query(LLMDecisionRecord).one().validator_status == "APPROVED"


@pytest.mark.parametrize("changes", [
    {"outcome": "WIN"}, {"outcome": "LOSS", "entry_status": "TOUCHED"},
    {"outcome": "EXPIRED"}, {"notes": "short"},
    {"observed_until": "2026-01-01T00:00:00Z"},
    {"observed_until": "2099-01-01T00:00:00Z"}, {"observed_until": "2026-11-13T00:00:00"},
    {"outcome": "EXPIRED", "entry_status": "NOT_TOUCHED"},
])
def test_invalid_reviews_rejected(client, reviewable, changes):
    assert client.post(f"/forward-testing/decisions/{reviewable}/reviews", json=review_body(**changes)).status_code == 422
    with SessionLocal() as db:
        assert db.query(ForwardReviewRecord).count() == 0


@pytest.mark.parametrize("case,expected", [("test", "DELIVERY_TEST"), ("legacy", "LEGACY_REVISION"),
    ("blocked", "NOT_APPROVED"), ("fallback", "NON_LIVE_PROVIDER"), ("pending", "PENDING_OR_FAILED")])
def test_exclusions_stay_visible_but_cannot_be_reviewed(client, reviewable, case, expected):
    with SessionLocal() as db:
        setup, decision = db.query(SetupAlertRecord).one(), db.query(LLMDecisionRecord).one()
        payload = json.loads(setup.payload_json)
        if case == "test": payload["diagnostics"]["test_mode"] = True
        if case == "legacy": payload["diagnostics"]["detector_revision"] = "old"
        if case == "blocked": decision.validator_status = "REJECTED"
        if case == "fallback": decision.model = "mock-openai-fallback"
        if case == "pending": db.delete(decision)
        setup.payload_json = json.dumps(payload)
        db.commit()
    assert client.get("/forward-testing").json()["rows"][0]["cohort_status"] == expected
    assert client.post(f"/forward-testing/decisions/{reviewable}/reviews", json=review_body()).status_code == (404 if case == "pending" else 409)


def test_cohort_cutoff_pagination_and_auth(client, reviewable, monkeypatch):
    assert client.get("/forward-testing?limit=1&offset=1").json()["rows"] == []
    assert client.get("/forward-testing?limit=101").status_code == 422
    with SessionLocal() as db:
        db.query(SetupAlertRecord).one().received_at = COHORT_START - timedelta(seconds=1)
        db.commit()
    assert client.get("/forward-testing").json()["total_receipts"] == 0
    assert "Waiting for the first receipt" in client.get("/dashboard/forward-testing").text
    assert client.post(f"/forward-testing/decisions/{reviewable}/reviews", json=review_body()).status_code == 409
    monkeypatch.setenv("DASHBOARD_USERNAME", "operator")
    monkeypatch.setenv("DASHBOARD_PASSWORD", "synthetic-password")
    get_settings.cache_clear()
    for path in ("/forward-testing", "/dashboard/forward-testing", f"/forward-testing/decisions/{reviewable}/reviews"):
        assert client.get(path).status_code == 401
    assert client.post(f"/forward-testing/decisions/{reviewable}/reviews", json=review_body()).status_code == 401
    assert client.get("/health").status_code == 200


def test_review_notes_are_escaped(client, reviewable):
    client.post(f"/forward-testing/decisions/{reviewable}/reviews", json=review_body(notes="<script>alert('synthetic')</script>"))
    assert "<script>alert" not in client.get("/dashboard/forward-testing").text
    assert "&lt;script&gt;" in client.get("/dashboard/forward-testing").text


def test_review_window_cannot_be_extended_after_the_fact(client, reviewable):
    with SessionLocal() as db:
        db.get(LLMDecisionRecord, reviewable).created_at = datetime.now(timezone.utc) - timedelta(hours=25)
        db.commit()
    result = client.post(f"/forward-testing/decisions/{reviewable}/reviews", json=review_body())
    assert result.status_code == 422 and "24-hour" in result.json()["detail"]


def test_elapsed_expiry_without_touch_can_be_recorded(client, reviewable):
    with SessionLocal() as db:
        row = db.get(LLMDecisionRecord, reviewable)
        raw = json.loads(row.raw_output_json)
        raw["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        row.raw_output_json = json.dumps(raw)
        db.commit()
    assert client.post(f"/forward-testing/decisions/{reviewable}/reviews",
        json=review_body(outcome="EXPIRED", entry_status="NOT_TOUCHED")).status_code == 200


def test_dashboard_assets_use_content_versions(client, reviewable):
    static = Path(__file__).resolve().parents[1] / "static"
    css_hash = hashlib.sha256((static / "app.css").read_bytes()).hexdigest()[:12]
    js_hash = hashlib.sha256((static / "forward_testing.js").read_bytes()).hexdigest()[:12]
    for route in ("/dashboard", "/dashboard/setups/1", "/dashboard/forward-testing"):
        assert f"/static/app.css?v={css_hash}" in client.get(route).text
    assert f"/static/forward_testing.js?v={js_hash}" in client.get("/dashboard/forward-testing").text
