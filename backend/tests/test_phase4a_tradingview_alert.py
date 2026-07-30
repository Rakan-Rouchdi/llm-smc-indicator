from datetime import datetime, timezone

from app.schema_validation import validate_setup_alert_schema
from app.schemas import SetupAlert


def _freshen_pine_payload(payload: dict) -> dict:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    payload["bar_time"] = now.isoformat().replace("+00:00", "Z")
    payload["setup_id"] = f"CME_MINI_DL:ES1!_5_{int(now.timestamp() * 1000)}_pytest"
    return payload


def test_pine_style_payload_matches_schema(pine_alert_payload):
    validate_setup_alert_schema(pine_alert_payload)
    alert = SetupAlert.model_validate(pine_alert_payload)

    assert alert.source.value == "tradingview_pine"
    assert alert.setup_id.startswith("CME_MINI_DL:ES1!_5_")
    assert alert.symbol == "CME_MINI_DL:ES1!"
    assert alert.diagnostics["notes"] == "Phase 2 Pine MVP payload"


def test_pine_style_payload_posts_to_webhook_with_query_secret(client, pine_alert_payload):
    payload = _freshen_pine_payload(pine_alert_payload)

    response = client.post("/webhook/tradingview?secret=test-secret", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processed"
    assert body["setup"]["setup_id"] == payload["setup_id"]
    assert body["setup"]["raw_payload"]["symbol"] == "CME_MINI_DL:ES1!"
    assert body["llm_decision"]["action"] == "BUY"
    assert body["validator"]["validator_status"] == "APPROVED"


def test_phase4d_test_mode_payload_matches_schema(pine_alert_payload):
    payload = _freshen_pine_payload(pine_alert_payload)
    payload["setup_id"] = payload["setup_id"].replace("_pytest", "_TEST_pytest")
    payload["rule_score"] = 100
    payload["features"].update(
        {
            "bos": {"state": "NONE", "level": None},
            "fvg": {
                "state": "BULLISH",
                "low": 6720.75,
                "high": 6721.75,
                "age_bars": 0,
            },
            "liquidity_sweep": {
                "state": "NONE",
                "level": None,
                "pool_type": "NONE",
                "age_bars": None,
            },
            "smt": {"state": "NONE", "lookback": 20},
            "volume": {"rvol": 1.0, "state": "NEUTRAL"},
            "consolidation": {
                "active": False,
                "directional_efficiency": 1.0,
                "range_atr_multiple": 3.0,
            },
            "htf_bias": "NEUTRAL",
            "displacement": "NONE",
        }
    )
    payload["diagnostics"] = {
        "test_mode": True,
        "atr": 5.25,
        "mintick": 0.25,
        "notes": "Phase 4D webhook delivery test",
    }

    validate_setup_alert_schema(payload)
    alert = SetupAlert.model_validate(payload)

    assert alert.diagnostics["test_mode"] is True
    assert alert.features.consolidation.active is False
