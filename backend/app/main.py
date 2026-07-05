import json
from datetime import datetime, timezone
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.context import build_context
from app.dashboard import router as dashboard_router
from app.database import SessionLocal, get_db, init_db
from app.llm_client import get_llm_provider
from app.llm_prompt import PROMPT_VERSION
from app.models import LLMDecisionRecord, SetupAlertRecord
from app.schemas import SetupAlert
from app.validators import ValidationPolicy, validate_llm_decision

app = FastAPI(title="SMC LLM Trade Setup Validator", version="0.1.0")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(dashboard_router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _authenticate(
    header_secret: str | None,
    query_secret: str | None,
    settings: Settings,
) -> None:
    provided_secret = header_secret or query_secret
    if not provided_secret or provided_secret != settings.webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")


def process_setup_decision(setup_payload: dict) -> None:
    settings = get_settings()
    setup_alert = SetupAlert.model_validate(setup_payload)
    context = build_context(setup_alert.root_symbol.value)
    llm_input = {
        "schema_version": "1.0",
        "prompt_version": PROMPT_VERSION,
        "setup_alert": setup_alert.model_dump(mode="json"),
        "context": context,
        "risk_policy": {
            "min_confidence_for_trade": settings.llm_confidence_approve_threshold,
            "min_risk_reward": 1.5,
            "max_setup_age_minutes": settings.max_setup_age_minutes,
            "no_trade_during_blackout": True,
            "no_trade_when_consolidation": True,
        },
    }

    provider = get_llm_provider(settings)
    llm_decision = provider.decide(llm_input)
    validator_result = validate_llm_decision(
        setup_alert=setup_alert,
        decision=llm_decision,
        context=context,
        policy=ValidationPolicy(
            min_confidence_for_trade=settings.llm_confidence_approve_threshold,
            min_risk_reward=1.5,
            max_setup_age_minutes=settings.max_setup_age_minutes,
        ),
        current_time=datetime.now(timezone.utc),
    )

    with SessionLocal() as db:
        db.add(
            LLMDecisionRecord(
                setup_id=setup_alert.setup_id,
                model=provider.model_name,
                prompt_version=PROMPT_VERSION,
                raw_input_json=json.dumps(llm_input, default=str),
                raw_output_json=llm_decision.model_dump_json(by_alias=True),
                validator_status=validator_result.validator_status,
                final_action=validator_result.final_action.value,
                confidence=validator_result.final_confidence,
                entry_preferred=llm_decision.entry.preferred,
                stop_loss=llm_decision.stop_loss,
                take_profit_1=llm_decision.take_profit.tp1,
                reason_summary=llm_decision.reason_summary,
                blocking_conditions_json=json.dumps(validator_result.rejections),
            )
        )
        setup_record = (
            db.query(SetupAlertRecord)
            .filter(SetupAlertRecord.setup_id == setup_alert.setup_id)
            .one_or_none()
        )
        if setup_record is not None:
            setup_record.status = "PROCESSED"
        db.commit()


@app.post("/webhook/tradingview")
@app.post("/webhooks/tradingview")
def tradingview_webhook(
    alert: SetupAlert,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    x_webhook_secret: Annotated[str | None, Header(alias="X-Webhook-Secret")] = None,
    secret: Annotated[str | None, Query()] = None,
) -> dict[str, object]:
    _authenticate(x_webhook_secret, secret, settings)

    existing = (
        db.query(SetupAlertRecord)
        .filter(SetupAlertRecord.setup_id == alert.setup_id)
        .one_or_none()
    )
    if existing is not None:
        return {"status": "duplicate", "setup_id": alert.setup_id, "duplicate": True}

    db.add(
        SetupAlertRecord(
            setup_id=alert.setup_id,
            symbol=alert.symbol,
            timeframe=alert.timeframe,
            bar_time=alert.bar_time,
            direction=alert.direction.value,
            rule_score=alert.rule_score,
            payload_json=alert.model_dump_json(),
            status="ACCEPTED",
        )
    )
    db.commit()

    background_tasks.add_task(process_setup_decision, alert.model_dump(mode="json"))
    return {"status": "accepted", "setup_id": alert.setup_id, "duplicate": False}
