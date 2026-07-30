import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@lru_cache
def _setup_alert_validator() -> Draft202012Validator:
    schema_path = PROJECT_ROOT / "schemas" / "setup_alert.schema.json"
    schema = json.loads(schema_path.read_text())
    return Draft202012Validator(schema)


def validate_setup_alert_schema(payload: dict[str, Any]) -> None:
    _setup_alert_validator().validate(payload)


@lru_cache
def _llm_trade_decision_validator() -> Draft202012Validator:
    schema_path = PROJECT_ROOT / "schemas" / "llm_trade_decision.schema.json"
    schema = json.loads(schema_path.read_text())
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_llm_trade_decision_schema(payload: dict[str, Any]) -> None:
    _llm_trade_decision_validator().validate(payload)


def format_schema_error(exc: JsonSchemaValidationError) -> str:
    location = ".".join(str(part) for part in exc.absolute_path)
    prefix = f"{location}: " if location else ""
    return f"{prefix}{exc.message}"
