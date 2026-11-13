import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PAYLOAD = PROJECT_ROOT / "examples" / "tradingview_webhook_example.json"


def prepare_payload(
    payload_path: Path,
    preserve_payload: bool = False,
    now: datetime | None = None,
    blocked_probe: bool = False,
) -> bytes:
    payload = json.loads(payload_path.read_text())
    if not preserve_payload:
        current_time = now or datetime.now(timezone.utc)
        minutes = {"5": 5, "15": 15, "60": 60, "240": 240}.get(payload["timeframe"])
        if minutes is None:
            raise ValueError("Sample timeframe is not supported")
        timestamp = (current_time - timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
        unique_suffix = int(current_time.timestamp() * 1000)
        payload["bar_time"] = timestamp
        payload["setup_id"] = f"{payload['setup_id']}_manual_{unique_suffix}"
        payload["diagnostics"]["test_mode"] = True
        payload["diagnostics"]["bar_close_time"] = current_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    if blocked_probe:
        payload["diagnostics"].update(test_mode=True,
            notes="Controlled HTTP delivery probe, not a TradingView-originated signal. Consolidation deliberately blocks approval and paid model use.")
        payload["features"]["consolidation"]["active"] = True
    return json.dumps(payload).encode("utf-8")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def send_sample(url: str, secret: str, payload: bytes, timeout: float) -> dict:
    target = urlsplit(url)
    if (not target.hostname or target.username or target.password or target.fragment
            or target.path not in {"/webhook/tradingview", "/webhooks/tradingview"}
            or not (target.scheme == "https" or target.scheme == "http" and target.hostname in {"localhost", "127.0.0.1", "::1"})):
        raise ValueError("Use an HTTPS webhook endpoint, or HTTP on loopback only")
    if not secret or timeout <= 0:
        raise ValueError("A secret and positive timeout are required")
    request = urllib.request.Request(url, data=payload, method="POST",
        headers={"Content-Type": "application/json", "X-Webhook-Secret": secret})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    started = time.perf_counter()
    with opener.open(request, timeout=timeout) as response:
        body = json.loads(response.read())
        expected_id = json.loads(payload)["setup_id"]
        if (not isinstance(body, dict) or body.get("setup_id") != expected_id
                or body.get("status") not in {"accepted", "duplicate"}):
            raise ValueError("Unexpected webhook acknowledgement")
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        # Only expose known acknowledgement fields, never URLs, exception text or arbitrary response bodies.
        return {"http_status": response.status, "status": body.get("status"),
                "setup_id": body.get("setup_id"), "duplicate": body.get("duplicate"),
                "acknowledgement_ms": elapsed_ms, "within_3_seconds": elapsed_ms < 3000}


def main() -> int:
    parser = argparse.ArgumentParser(description="Send the sample TradingView webhook payload.")
    parser.add_argument(
        "--url",
        default=os.getenv(
            "MVP_WEBHOOK_URL",
            "http://127.0.0.1:8003/webhooks/tradingview",
        ),
    )
    parser.add_argument("--secret", default=os.getenv("WEBHOOK_SECRET"))
    parser.add_argument("--payload", default=str(DEFAULT_PAYLOAD))
    parser.add_argument("--blocked-probe", action="store_true",
                        help="Mark a delivery test and force NO_TRADE without a paid model call.")
    parser.add_argument(
        "--preserve-payload",
        action="store_true",
        help="Send the file unchanged instead of refreshing bar_time and setup_id.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("MVP_WEBHOOK_TIMEOUT_SECONDS", "3")),
        help="Seconds to wait for the durable receipt acknowledgement (LLM runs later).",
    )
    args = parser.parse_args()

    if not args.secret:
        parser.error("set WEBHOOK_SECRET or pass --secret")

    try:
        payload = prepare_payload(Path(args.payload), args.preserve_payload, blocked_probe=args.blocked_probe)
        result = send_sample(args.url, args.secret, payload, args.timeout)
        print(json.dumps(result, indent=2))
        return 0 if result["http_status"] in {200, 202} and result["status"] in {"accepted", "duplicate"} else 1
    except urllib.error.HTTPError as exc:
        print(f"Webhook returned HTTP {exc.code}; response details omitted", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"Webhook probe failed: {type(exc).__name__}; details omitted", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
