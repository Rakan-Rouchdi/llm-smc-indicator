import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture
def valid_setup_payload() -> dict:
    return json.loads((PROJECT_ROOT / "examples" / "tradingview_webhook_example.json").read_text())


@pytest.fixture
def valid_buy_decision_payload() -> dict:
    return json.loads((PROJECT_ROOT / "examples" / "llm_decision_buy_example.json").read_text())
