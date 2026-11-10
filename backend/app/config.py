from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AUTO_NEWS_PROVIDERS = {"forexfactory", "showmytrades"}


class Settings(BaseSettings):
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = Field(
        default=8000,
        validation_alias=AliasChoices("PORT", "APP_PORT"),
        ge=1,
        le=65535,
    )
    database_url: str = "sqlite:///./smc_llm.db"
    webhook_secret: str = "change-me"
    decision_worker_enabled: bool = True
    dashboard_username: str | None = None
    dashboard_password: SecretStr | None = None
    llm_provider: Literal["mock", "openai"] = "mock"
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = Field(default=20, gt=0)
    llm_max_retries: int = Field(default=2, ge=0, le=10)
    llm_confidence_approve_threshold: int = 70
    llm_confidence_watchlist_threshold: int = 55
    max_setup_age_minutes: int = 15
    min_rule_score: int = Field(default=75, ge=75, le=100)
    confirmation_max_bars: int = Field(default=6, ge=3, le=6)
    news_provider: Literal["mock", "manual", "forexfactory", "showmytrades"] = "mock"
    require_verified_news: bool = True
    news_max_age_hours: int = Field(default=24, ge=1, le=168)
    news_refresh_interval_minutes: int = Field(default=60, ge=15, le=720)
    news_fetch_timeout_seconds: float = Field(default=10, gt=0, le=15)
    alert_observation_max_hours: int = Field(default=24, ge=1, le=168)
    notification_timeout_seconds: float = Field(default=5, gt=0, le=15)
    default_blackout_minutes_before: int = 30
    default_blackout_minutes_after: int = 30
    notification_webhook_url: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    enable_notifications: bool = False
    timezone: str = "America/New_York"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator(
        "openai_api_key",
        "dashboard_username",
        "dashboard_password",
        "notification_webhook_url",
        "telegram_bot_token",
        "telegram_chat_id",
        mode="before",
    )
    @classmethod
    def empty_string_to_none(cls, value: str | None) -> str | None:
        if value == "":
            return None
        return value

    @model_validator(mode="after")
    def automated_news_requires_freshness_gate(self):
        if self.news_provider in AUTO_NEWS_PROVIDERS and not self.require_verified_news:
            raise ValueError("Automatic news requires REQUIRE_VERIFIED_NEWS=true")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
