import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from scripts.check_mvp_status import check_database, collect_status
from scripts.send_sample_webhook import prepare_payload


def _create_status_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE setup_alerts (
            id INTEGER PRIMARY KEY,
            setup_id TEXT NOT NULL
        );
        CREATE TABLE llm_decisions (
            id INTEGER PRIMARY KEY,
            setup_id TEXT NOT NULL,
            final_action TEXT NOT NULL,
            validator_status TEXT NOT NULL,
            confidence INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );
        INSERT INTO setup_alerts (setup_id) VALUES ('setup-test');
        INSERT INTO llm_decisions (
            setup_id, final_action, validator_status, confidence, created_at
        ) VALUES ('setup-test', 'BUY', 'APPROVED', 80, '2026-07-30T16:48:00Z');
        """
    )
    connection.commit()
    connection.close()


def test_check_database_reports_latest_records(tmp_path):
    database_path = tmp_path / "status.db"
    _create_status_database(database_path)

    status = check_database(database_path)

    assert status["ok"] is True
    assert status["setup_count"] == 1
    assert status["decision_count"] == 1
    assert status["latest_decision"]["final_action"] == "BUY"


def test_collect_status_requires_all_checks(tmp_path):
    database_path = tmp_path / "status.db"
    _create_status_database(database_path)

    def fake_json_fetcher(url: str, timeout: float):
        del timeout
        if url.endswith("/health"):
            return 200, {"status": "ok"}
        return 200, {"decision": {"final_action": "BUY"}}

    status = collect_status(
        "http://127.0.0.1:8003",
        database_path,
        1.0,
        json_fetcher=fake_json_fetcher,
        status_fetcher=lambda _url, _timeout: 200,
    )

    assert status["ok"] is True
    assert status["checks"]["dashboard"]["status_code"] == 200
    assert status["checks"]["latest_decision"]["response"]["final_action"] == "BUY"


def test_prepare_payload_refreshes_time_and_setup_id(tmp_path):
    payload_path = tmp_path / "payload.json"
    payload_path.write_text('{"setup_id": "setup-test", "bar_time": "old"}')
    now = datetime(2026, 7, 30, 17, 0, tzinfo=timezone.utc)

    payload = prepare_payload(payload_path, now=now)

    assert b'"bar_time": "2026-07-30T17:00:00Z"' in payload
    assert b'"setup_id": "setup-test_manual_1785430800000"' in payload
