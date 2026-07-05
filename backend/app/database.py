from collections.abc import Generator

from sqlalchemy import inspect, text
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _connect_args(database_url: str) -> dict[str, bool]:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


settings = get_settings()
engine = create_engine(
    settings.database_url,
    connect_args=_connect_args(settings.database_url),
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def configure_database(database_url: str) -> None:
    global engine

    engine.dispose()
    engine = create_engine(
        database_url,
        connect_args=_connect_args(database_url),
        future=True,
    )
    SessionLocal.configure(bind=engine)


def _sqlite_add_column_if_missing(table_name: str, column_name: str, column_sql: str) -> None:
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name in existing_columns:
        return

    with engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}"))


def _run_lightweight_migrations() -> None:
    _sqlite_add_column_if_missing("setup_alerts", "parsed_setup_json", "parsed_setup_json TEXT")
    _sqlite_add_column_if_missing("setup_alerts", "enriched_context_json", "enriched_context_json TEXT")
    _sqlite_add_column_if_missing("llm_decisions", "validator_result_json", "validator_result_json TEXT")
    _sqlite_add_column_if_missing("llm_decisions", "validation_rejection_reason", "validation_rejection_reason TEXT")
    _sqlite_add_column_if_missing("llm_decisions", "risk_reward", "risk_reward FLOAT")
    _sqlite_add_column_if_missing("llm_decisions", "take_profit_2", "take_profit_2 FLOAT")


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _run_lightweight_migrations()


def reset_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
