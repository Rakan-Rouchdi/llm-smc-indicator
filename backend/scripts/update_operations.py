"""Submit an operator-verified calendar or alert observation without URL/secret output."""
import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from scripts.check_mvp_status import NoRedirect, request_for


def submit(base_url, kind, path, timeout=10):
    routes = {"news-calendar": "/context/news-calendar", "alert-observation": "/monitoring/alert"}
    payload = json.loads(Path(path).read_text())
    request = request_for(base_url.rstrip("/") + routes[kind])
    request.method = "PUT"
    request.data = json.dumps(payload).encode()
    request.add_header("Content-Type", "application/json")
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout) as response:
        return response.status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["news-calendar", "alert-observation"])
    parser.add_argument("file", type=Path)
    args = parser.parse_args()
    try:
        status = submit(os.environ["MVP_BASE_URL"], args.kind, args.file)
    except urllib.error.HTTPError as exc:
        print(f"Update rejected: HTTP {exc.code}. Check authentication and payload schema.")
        return 1
    except (OSError, ValueError, KeyError):
        print("Update failed. Check MVP_BASE_URL, credentials, file, and connectivity.")
        return 1
    print(f"Recorded operator snapshot: HTTP {status}. No TradingView alert was changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
