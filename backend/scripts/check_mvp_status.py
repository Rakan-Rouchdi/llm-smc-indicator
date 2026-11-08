import argparse
import base64
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE = PROJECT_ROOT / "smc_llm.db"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_for(url: str):
    parsed = urlsplit(url)
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError("Use an origin URL without credentials or query parameters")
    if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}):
        raise ValueError("Remote monitoring requires HTTPS")
    headers = {}
    username, password = os.getenv("DASHBOARD_USERNAME"), os.getenv("DASHBOARD_PASSWORD")
    if username and password:
        headers["Authorization"] = "Basic " + base64.b64encode(f"{username}:{password}".encode()).decode()
    return urllib.request.Request(url, headers=headers)


def open_request(url, timeout):
    return urllib.request.build_opener(NoRedirect()).open(request_for(url), timeout=timeout)


def fetch_json(url: str, timeout: float) -> tuple[int, dict[str, Any] | None]:
    try:
        with open_request(url, timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
            return response.status, body
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except (urllib.error.URLError, json.JSONDecodeError, ValueError):
        return 0, None


def fetch_status(url: str, timeout: float) -> int:
    try:
        with open_request(url, timeout) as response:
            response.read(1)
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except (urllib.error.URLError, ValueError):
        return 0


def summarize_decision(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not payload or not isinstance(payload.get("decision"), dict):
        return None

    decision = payload["decision"]
    fields = (
        "id",
        "setup_id",
        "created_at",
        "model",
        "final_action",
        "validator_status",
        "confidence",
        "risk_reward",
    )
    return {field: decision.get(field) for field in fields}


def check_database(database_path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(database_path),
        "exists": database_path.is_file(),
        "setup_count": 0,
        "decision_count": 0,
        "latest_decision": None,
        "ok": False,
    }
    if not result["exists"]:
        return result

    try:
        connection = sqlite3.connect(
            f"file:{database_path}?mode=ro",
            uri=True,
            timeout=2,
        )
        connection.row_factory = sqlite3.Row
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        if not {"setup_alerts", "llm_decisions"}.issubset(tables):
            return result

        result["setup_count"] = connection.execute(
            "SELECT COUNT(*) FROM setup_alerts"
        ).fetchone()[0]
        result["decision_count"] = connection.execute(
            "SELECT COUNT(*) FROM llm_decisions"
        ).fetchone()[0]
        latest = connection.execute(
            """
            SELECT setup_id, final_action, validator_status, confidence, created_at
            FROM llm_decisions
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
        result["latest_decision"] = dict(latest) if latest else None
        result["ok"] = result["setup_count"] > 0 and result["decision_count"] > 0
        return result
    except sqlite3.Error as exc:
        result["error"] = str(exc)
        return result
    finally:
        if "connection" in locals():
            connection.close()


def collect_status(
    base_url: str,
    database_path: Path | None,
    timeout: float,
    json_fetcher: Callable[[str, float], tuple[int, dict[str, Any] | None]] = fetch_json,
    status_fetcher: Callable[[str, float], int] = fetch_status,
) -> dict[str, Any]:
    health_status, health_payload = json_fetcher(f"{base_url}/health", timeout)
    decision_status, decision_payload = json_fetcher(
        f"{base_url}/decisions/latest", timeout
    )
    dashboard_status = status_fetcher(f"{base_url}/dashboard", timeout)
    operations_code, operations = json_fetcher(f"{base_url}/status", timeout)
    operations = operations or {}
    database = check_database(database_path) if database_path else {"ok": operations.get("database") == "ok", "source": "hosted /status"}
    decision_summary = summarize_decision(decision_payload)

    checks = {
        "health": {
            "ok": health_status == 200,
            "status_code": health_status,
            "response": health_payload,
        },
        "latest_decision": {
            "ok": decision_status == 200 and decision_summary is not None,
            "status_code": decision_status,
            "response": decision_summary,
        },
        "dashboard": {
            "ok": dashboard_status == 200,
            "status_code": dashboard_status,
        },
        "database": database,
    }
    if database_path is None:
        checks["operations"] = {"ok": operations_code == 200 and operations.get("service_ready") is True,
                                "status_code": operations_code, "response": operations}
    return {
        "base_url": "[redacted]",
        "ok": all(check["ok"] for check in checks.values()),
        "armed": operations.get("armed", False),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check local or hosted MVP; credentials come from environment only.")
    parser.add_argument("--base-url", default=os.getenv("MVP_BASE_URL", "http://127.0.0.1:8003"))
    parser.add_argument("--database", type=Path, help="Optional local SQLite check; omit for hosted Postgres")
    parser.add_argument("--timeout", type=float, default=3.0)
    args = parser.parse_args()

    status = collect_status(
        args.base_url.rstrip("/"),
        args.database.expanduser().resolve() if args.database else None,
        args.timeout,
    )
    print(json.dumps(status, indent=2, default=str))
    return 0 if status["ok"] and status["armed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
