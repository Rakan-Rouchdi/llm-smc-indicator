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
    reason_summary: Mapped[str] = mapped_column(Text)
    blocking_conditions_json: Mapped[str] = mapped_column(Text)


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
