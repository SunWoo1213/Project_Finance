from types import SimpleNamespace
import os

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("PROJECT_NAME", "test")
os.environ.setdefault("API_V1_STR", "/api")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

from app.api import notifications
from app.models import User
from billing_test_utils import create_test_sessionmaker


async def override_current_user():
    return SimpleNamespace(id=1, email="notify@example.com", nickname="notify")


@pytest.mark.asyncio
async def test_notification_preferences_default_and_update():
    engine, Session = await create_test_sessionmaker()
    async with Session() as db:
        db.add(User(email="notify@example.com", nickname="notify"))
        await db.commit()

    async def override_db():
        async with Session() as db:
            yield db

    app = FastAPI()
    app.include_router(notifications.router)
    app.dependency_overrides[notifications.get_db] = override_db
    app.dependency_overrides[notifications.get_current_user] = override_current_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/notifications/preferences")
            assert response.status_code == 200
            assert response.json()["price_change_threshold_percent"] == 3

            response = await client.put(
                "/api/notifications/preferences",
                json={"email_enabled": True, "price_change_threshold_percent": 5.5},
            )
            assert response.status_code == 200
            assert response.json()["email_enabled"] is True
            assert response.json()["price_change_threshold_percent"] == 5.5
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_email_channel_verify_confirm_and_test_history():
    engine, Session = await create_test_sessionmaker()
    async with Session() as db:
        db.add(User(email="notify@example.com", nickname="notify"))
        await db.commit()

    async def override_db():
        async with Session() as db:
            yield db

    app = FastAPI()
    app.include_router(notifications.router)
    app.dependency_overrides[notifications.get_db] = override_db
    app.dependency_overrides[notifications.get_current_user] = override_current_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            verify_response = await client.post(
                "/api/notifications/channels/email/verify",
                json={"email": "notify@example.com"},
            )
            assert verify_response.status_code == 200
            code = verify_response.json()["verification_code"]

            confirm_response = await client.post(
                "/api/notifications/channels/email/confirm",
                json={"email": "notify@example.com", "code": code},
            )
            assert confirm_response.status_code == 200
            assert confirm_response.json()["verified"] is True

            await client.put("/api/notifications/preferences", json={"email_enabled": True})
            test_response = await client.post(
                "/api/notifications/test",
                json={"ticker": "NVDA", "message": "테스트"},
            )
            assert test_response.status_code == 200
            assert test_response.json()["created_events"] == 2
            assert test_response.json()["failed_events"] == 1

            history_response = await client.get("/api/notifications/history")
            assert history_response.status_code == 200
            payload = history_response.json()
            assert {event["channel"] for event in payload} == {"in_app", "email"}
    finally:
        await engine.dispose()
