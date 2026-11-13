from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SetupAlertRecord(Base):
    __tablename__ = "setup_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    setup_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    symbol: Mapped[str] = mapped_column(String(100), index=True)
    timeframe: Mapped[str] = mapped_column(String(30))
    bar_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    direction: Mapped[str] = mapped_column(String(20))
    rule_score: Mapped[int] = mapped_column(Integer)
    payload_json: Mapped[str] = mapped_column(Text)
    parsed_setup_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    enriched_context_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="ACCEPTED")


class LLMDecisionRecord(Base):
    __tablename__ = "llm_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    setup_id: Mapped[str] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(100))
    raw_input_json: Mapped[str] = mapped_column(Text)
    raw_output_json: Mapped[str] = mapped_column(Text)
    validator_status: Mapped[str] = mapped_column(String(30))
    final_action: Mapped[str] = mapped_column(String(30))
    confidence: Mapped[int] = mapped_column(Integer)
    entry_preferred: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit_1: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit_2: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_reward: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason_summary: Mapped[str] = mapped_column(Text)
    blocking_conditions_json: Mapped[str] = mapped_column(Text)
    validator_result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class DecisionJobRecord(Base):
    __tablename__ = "decision_jobs"

    setup_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    status: Mapped[str] = mapped_column(String(30), default="QUEUED", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(100), nullable=True)


class NewsEventRecord(Base):
    __tablename__ = "news_events"

    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    impact: Mapped[str] = mapped_column(String(30))
    symbols_json: Mapped[str] = mapped_column(Text)
    blackout_minutes_before: Mapped[int] = mapped_column(Integer, default=30)
    blackout_minutes_after: Mapped[int] = mapped_column(Integer, default=30)


class HeadlineRecord(Base):
    __tablename__ = "headlines"

    headline_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    headline: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(100))
    impact: Mapped[str] = mapped_column(String(30))
    bias: Mapped[str] = mapped_column(String(30))
    symbols_json: Mapped[str] = mapped_column(Text)


class TelegramSummaryRecord(Base):
    __tablename__ = "telegram_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    window_minutes: Mapped[int] = mapped_column(Integer)
    source_count: Mapped[int] = mapped_column(Integer)
    buy_count: Mapped[int] = mapped_column(Integer)
    sell_count: Mapped[int] = mapped_column(Integer)
    neutral_count: Mapped[int] = mapped_column(Integer)
    dominant_bias: Mapped[str] = mapped_column(String(30))
    confidence: Mapped[int] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(Text)


class OutcomeRecord(Base):
    __tablename__ = "outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    setup_id: Mapped[str] = mapped_column(String(255), index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    outcome: Mapped[str] = mapped_column(String(30))
    hit_target: Mapped[str | None] = mapped_column(String(30), nullable=True)
    mfe_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    mae_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class CalendarCoverageRecord(Base):
    __tablename__ = "calendar_coverage"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(255))
    coverage_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    coverage_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AlertObservationRecord(Base):
    __tablename__ = "alert_observations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(100))
    symbol: Mapped[str] = mapped_column(String(100))
    timeframe: Mapped[str] = mapped_column(String(30))
    active: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CalendarRefreshRecord(Base):
    __tablename__ = "calendar_refresh"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(100), nullable=True)


class CalendarRefreshSchedule(Base):
    __tablename__ = "calendar_refresh_schedule"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempt_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)


class NotificationRecord(Base):
    __tablename__ = "notification_outbox"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    decision_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    channel: Mapped[str] = mapped_column(String(30))
    destination_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30), default="QUEUED", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(100), nullable=True)


class NotificationProbeRecord(Base):
    __tablename__ = "notification_probes"
    test_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    minute_bucket: Mapped[int] = mapped_column(Integer, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    status: Mapped[str] = mapped_column(String(30), default="UNKNOWN")
    last_error: Mapped[str | None] = mapped_column(String(100), nullable=True)
