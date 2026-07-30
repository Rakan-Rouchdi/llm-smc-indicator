import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PAYLOAD = PROJECT_ROOT / "examples" / "tradingview_webhook_example.json"


def prepare_payload(
    payload_path: Path,
    preserve_payload: bool = False,
    now: datetime | None = None,
) -> bytes:
    payload = json.loads(payload_path.read_text())
    if not preserve_payload:
        current_time = now or datetime.now(timezone.utc)
        timestamp = current_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        unique_suffix = int(current_time.timestamp() * 1000)
        payload["bar_time"] = timestamp
        payload["setup_id"] = f"{payload['setup_id']}_manual_{unique_suffix}"
    return json.dumps(payload).encode("utf-8")


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
    parser.add_argument(
        "--preserve-payload",
        action="store_true",
        help="Send the file unchanged instead of refreshing bar_time and setup_id.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("MVP_WEBHOOK_TIMEOUT_SECONDS", "60")),
        help="Seconds to wait for the complete webhook-to-LLM workflow.",
    )
    args = parser.parse_args()

    if not args.secret:
        parser.error("set WEBHOOK_SECRET or pass --secret")

    payload = prepare_payload(Path(args.payload), args.preserve_payload)
    request = urllib.request.Request(
        args.url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Secret": args.secret,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            body = response.read().decode("utf-8")
            print(json.dumps(json.loads(body), indent=2))
            return 0
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        print(body, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
