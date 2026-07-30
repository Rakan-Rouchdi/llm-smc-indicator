from copy import deepcopy


WEBHOOK_HEADERS = {"X-Webhook-Secret": "test-secret"}


def _post_webhook(client, payload):
    return client.post("/webhook/tradingview", json=payload, headers=WEBHOOK_HEADERS)


def test_full_valid_webhook_to_decision_flow(client, fresh_setup_payload):
    response = _post_webhook(client, fresh_setup_payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processed"
    assert body["setup"]["setup_id"] == fresh_setup_payload["setup_id"]
    assert body["llm_decision"]["action"] == "BUY"
    assert body["validator"]["validator_status"] == "APPROVED"
    assert body["final_decision"]["action"] == "BUY"


def test_invalid_webhook_rejection(client, fresh_setup_payload):
    fresh_setup_payload.pop("setup_id")

    response = _post_webhook(client, fresh_setup_payload)

    assert response.status_code == 422
    assert "setup_id" in response.json()["detail"]


def test_mock_llm_decision_saved(client, fresh_setup_payload):
    _post_webhook(client, fresh_setup_payload)

    response = client.get("/decisions/latest")

    assert response.status_code == 200
    decision = response.json()["decision"]
    assert decision["model"] == "mock-llm-deterministic"
    assert decision["llm_decision"]["action"] == "BUY"


def test_validator_result_saved(client, fresh_setup_payload):
    _post_webhook(client, fresh_setup_payload)

    response = client.get(f"/setups/{fresh_setup_payload['setup_id']}")

    assert response.status_code == 200
    decision = response.json()["decisions"][0]
    assert decision["validator_status"] == "APPROVED"
    assert decision["validator_result"]["final_action"] == "BUY"


def test_dashboard_route_loads(client, fresh_setup_payload):
    _post_webhook(client, fresh_setup_payload)

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "SMC LLM Dashboard" in response.text
    assert fresh_setup_payload["symbol"] in response.text
    assert "mock-llm-deterministic" in response.text

    detail = client.get(f"/dashboard/setups/{fresh_setup_payload['setup_id']}")
    assert detail.status_code == 200
    assert fresh_setup_payload["setup_id"] in detail.text


def test_latest_decision_endpoint_works(client, fresh_setup_payload):
    _post_webhook(client, fresh_setup_payload)

    response = client.get("/decisions/latest")

    assert response.status_code == 200
    assert response.json()["decision"]["setup_id"] == fresh_setup_payload["setup_id"]


def test_news_blackout_converts_trade_to_no_trade(client, fresh_setup_payload, monkeypatch):
    def blackout_context(symbol, current_time=None):
        return {
            "symbol": symbol,
            "current_time": current_time.isoformat() if current_time else None,
            "news_blackout_active": True,
            "news": {
                "blackout_active": True,
                "headline_summary": "Mock high-impact event blackout.",
                "market_bias": "NEUTRAL",
                "high_impact_event_name": "Mock CPI",
                "minutes_to_event": 8,
            },
            "telegram": {
                "bullish_count": 1,
                "bearish_count": 1,
                "neutral_count": 2,
                "source_count": 4,
                "summary": "Mock mixed Telegram flow.",
            },
        }

    monkeypatch.setattr("app.workflow.build_context", blackout_context)

    response = _post_webhook(client, fresh_setup_payload)

    assert response.status_code == 200
    body = response.json()
    assert body["final_decision"]["action"] == "NO_TRADE"
    assert body["validator"]["validator_status"] == "REJECTED"
    assert "News blackout active" in body["validator"]["rejections"]


def test_consolidation_converts_trade_to_no_trade(client, fresh_setup_payload):
    payload = deepcopy(fresh_setup_payload)
    payload["features"]["consolidation"]["active"] = True

    response = _post_webhook(client, payload)

    assert response.status_code == 200
    body = response.json()
    assert body["final_decision"]["action"] == "NO_TRADE"
    assert body["validator"]["validator_status"] == "REJECTED"
    assert "Setup is blocked during consolidation" in body["validator"]["rejections"]


def test_webhook_alias_and_outcome_endpoint(client, fresh_setup_payload):
    response = client.post("/webhooks/tradingview", json=fresh_setup_payload, headers=WEBHOOK_HEADERS)
    assert response.status_code == 200

    outcome = client.post(
        f"/setups/{fresh_setup_payload['setup_id']}/outcome",
        json={"outcome": "UNKNOWN", "notes": "Phase 3 placeholder outcome."},
    )

    assert outcome.status_code == 200
    assert outcome.json()["outcome"]["outcome"] == "UNKNOWN"
