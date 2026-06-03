import pytest
from pydantic import ValidationError

from app.core.config import Settings


def build_settings(database_url: str) -> Settings:
    return Settings(
        _env_file=None,
        PROJECT_NAME="Project Finance",
        API_V1_STR="/api/v1",
        DATABASE_URL=database_url,
    )


def test_database_url_allows_async_postgres_scheme():
    settings = build_settings("postgresql+asyncpg://finance_user:secret@localhost:5432/finance_db")

    assert settings.database_url_diagnostics() == {
        "source": "DATABASE_URL",
        "scheme": "postgresql+asyncpg",
        "host": "localhost",
        "port": 5432,
    }


def test_database_url_allows_async_sqlite_scheme():
    settings = build_settings("sqlite+aiosqlite:///./test.db")

    assert settings.database_url_diagnostics() == {
        "source": "DATABASE_URL",
        "scheme": "sqlite+aiosqlite",
        "host": None,
        "port": None,
    }


def test_ai_report_generation_enabled_by_default():
    settings = build_settings("sqlite+aiosqlite:///./test.db")

    assert settings.ENABLE_AI_REPORT_GENERATION is True


def test_blank_optional_prepared_statement_cache_size_becomes_none():
    settings = Settings(
        _env_file=None,
        PROJECT_NAME="Project Finance",
        API_V1_STR="/api/v1",
        DATABASE_URL="sqlite+aiosqlite:///./test.db",
        DB_PREPARED_STATEMENT_CACHE_SIZE="",
    )

    assert settings.DB_PREPARED_STATEMENT_CACHE_SIZE is None


def test_database_url_normalizes_sync_postgres_scheme():
    settings = build_settings("postgresql://finance_user:secret@localhost:5432/finance_db")

    assert settings.DATABASE_URL == "postgresql+asyncpg://finance_user:secret@localhost:5432/finance_db"


def test_database_url_falls_back_to_postgres_url_non_pooling_first():
    settings = Settings(
        _env_file=None,
        PROJECT_NAME="Project Finance",
        API_V1_STR="/api/v1",
        DATABASE_URL="",
        POSTGRES_URL_NON_POOLING="postgresql://finance_user:secret@non-pooling.example.com:5432/finance_db",
        POSTGRES_URL="postgresql://finance_user:secret@pooled.example.com:5432/finance_db",
    )

    assert settings.DATABASE_URL == (
        "postgresql+asyncpg://finance_user:secret@non-pooling.example.com:5432/finance_db"
    )
    assert settings.database_url_diagnostics() == {
        "source": "POSTGRES_URL_NON_POOLING",
        "scheme": "postgresql+asyncpg",
        "host": "non-pooling.example.com",
        "port": 5432,
    }


def test_database_url_falls_back_to_postgres_url_when_non_pooling_is_missing():
    settings = Settings(
        _env_file=None,
        PROJECT_NAME="Project Finance",
        API_V1_STR="/api/v1",
        DATABASE_URL="",
        POSTGRES_URL_NON_POOLING="",
        POSTGRES_URL="postgres://finance_user:secret@pooled.example.com:5432/finance_db",
    )

    assert settings.DATABASE_URL == "postgresql+asyncpg://finance_user:secret@pooled.example.com:5432/finance_db"
    assert settings.database_url_diagnostics() == {
        "source": "POSTGRES_URL",
        "scheme": "postgresql+asyncpg",
        "host": "pooled.example.com",
        "port": 5432,
    }


def test_database_url_rejects_unsupported_scheme():
    with pytest.raises(ValidationError, match="DATABASE_URL must use an async SQLAlchemy driver scheme"):
        build_settings("mysql://finance_user:secret@localhost:3306/finance_db")
