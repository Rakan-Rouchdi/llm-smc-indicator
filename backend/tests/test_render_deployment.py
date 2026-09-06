from app.database import normalize_database_url


def test_neon_postgres_url_uses_psycopg_driver() -> None:
    assert (
        normalize_database_url("postgresql://user:secret@example.neon.tech/app?sslmode=require")
        == "postgresql+psycopg://user:secret@example.neon.tech/app?sslmode=require"
    )


def test_legacy_postgres_url_uses_psycopg_driver() -> None:
    assert normalize_database_url("postgres://user:secret@host/app") == (
        "postgresql+psycopg://user:secret@host/app"
    )


def test_sqlite_url_is_unchanged() -> None:
    assert normalize_database_url("sqlite:///./smc_llm.db") == "sqlite:///./smc_llm.db"


def test_health_supports_head_requests(client) -> None:
    response = client.head("/health")

    assert response.status_code == 200
    assert response.content == b""
