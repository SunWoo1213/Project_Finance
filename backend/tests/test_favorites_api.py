from types import SimpleNamespace
import os

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("PROJECT_NAME", "test")
os.environ.setdefault("API_V1_STR", "/api")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

from app.api import favorites
from app.models import User
from billing_test_utils import create_test_sessionmaker


async def override_db_empty():
    yield object()


async def override_current_user():
    return SimpleNamespace(id=1, email="favorite@example.com", nickname="favorite")


@pytest.mark.asyncio
async def test_favorites_requires_authentication():
    app = FastAPI()
    app.include_router(favorites.router)
    app.dependency_overrides[favorites.get_db] = override_db_empty

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/favorites")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_import_local_favorites_merges_by_ticker():
    engine, Session = await create_test_sessionmaker()
    async with Session() as db:
        user = User(email="favorite@example.com", nickname="favorite")
        db.add(user)
        await db.commit()

    async def override_db():
        async with Session() as db:
            yield db

    app = FastAPI()
    app.include_router(favorites.router)
    app.dependency_overrides[favorites.get_db] = override_db
    app.dependency_overrides[favorites.get_current_user] = override_current_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/favorites/import-local",
                json={
                    "favorites": [
                        {"symbol": "NVDA", "name": "NVIDIA", "categoryKey": "us_top10"},
                        {"symbol": "NVDA", "name": "NVIDIA Corp", "categoryKey": "us_top10"},
                        {"symbol": "BTC-USD", "name": "Bitcoin", "categoryKey": "cryptos"},
                    ]
                },
            )

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 2
        assert {item["symbol"] for item in payload} == {"NVDA", "BTC-USD"}
        assert next(item for item in payload if item["symbol"] == "NVDA")["name"] == "NVIDIA Corp"
    finally:
        await engine.dispose()
