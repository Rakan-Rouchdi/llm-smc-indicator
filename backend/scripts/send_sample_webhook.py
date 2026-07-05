import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PAYLOAD = PROJECT_ROOT / "examples" / "tradingview_webhook_example.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Send the sample TradingView webhook payload.")
    parser.add_argument("--url", default="http://localhost:8000/webhook/tradingview")
    parser.add_argument("--secret", default="change-me")
    parser.add_argument("--payload", default=str(DEFAULT_PAYLOAD))
    args = parser.parse_args()

    payload = Path(args.payload).read_text()
    request = urllib.request.Request(
        args.url,
        data=payload.encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Secret": args.secret,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
            print(json.dumps(json.loads(body), indent=2))
            return 0
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        print(body, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
