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
        "scheme": "postgresql+asyncpg",
        "host": "localhost",
        "port": 5432,
    }


def test_database_url_allows_async_sqlite_scheme():
    settings = build_settings("sqlite+aiosqlite:///./test.db")

    assert settings.database_url_diagnostics() == {
        "scheme": "sqlite+aiosqlite",
        "host": None,
        "port": None,
    }


def test_database_url_rejects_sync_postgres_scheme():
    with pytest.raises(ValidationError, match="DATABASE_URL must use an async SQLAlchemy driver scheme"):
        build_settings("postgresql://finance_user:secret@localhost:5432/finance_db")
