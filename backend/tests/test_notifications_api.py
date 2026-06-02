from types import SimpleNamespace
import os

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

os.environ.setdefault("PROJECT_NAME", "test")
os.environ.setdefault("API_V1_STR", "/api")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

from app.api import notifications
from app.models import NotificationChannelConnection, User
from app.services import notification_service
from app.services.notification_service import DeliveryResult
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
async def test_email_channel_verify_confirm_and_test_history(monkeypatch):
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

    async def fake_send_verification_code(db, connection):
        return DeliveryResult(success=True)

    async def fake_send_email(destination, event):
        return DeliveryResult(success=True)

    monkeypatch.setattr(notifications, "send_email_verification_code", fake_send_verification_code)
    monkeypatch.setattr(notification_service, "_send_email", fake_send_email)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            verify_response = await client.post(
                "/api/notifications/channels/email/verify",
                json={"email": "notify@example.com"},
            )
            assert verify_response.status_code == 200
            assert verify_response.json()["verification_code"] is None
            assert verify_response.json()["message"] == "Gmail로 확인 코드를 보냈습니다."

            async with Session() as db:
                result = await db.execute(
                    select(NotificationChannelConnection).where(
                        NotificationChannelConnection.user_id == 1,
                        NotificationChannelConnection.channel == "email",
                    )
                )
                connection = result.scalar_one()
                code = connection.verification_code
                assert code

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
            assert test_response.json()["sent_events"] == 1
            assert test_response.json()["failed_events"] == 0

            history_response = await client.get("/api/notifications/history")
            assert history_response.status_code == 200
            payload = history_response.json()
            assert {event["channel"] for event in payload} == {"in_app", "email"}
            assert {event["status"] for event in payload} == {"sent"}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_email_verify_does_not_expose_code_when_gmail_delivery_fails(monkeypatch):
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

    async def fake_send_verification_code(db, connection):
        return DeliveryResult(success=False, error_message="Gmail email settings are incomplete.")

    monkeypatch.setattr(notifications, "send_email_verification_code", fake_send_verification_code)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/notifications/channels/email/verify",
                json={"email": "notify@example.com"},
            )
            assert response.status_code == 503
            assert "verification_code" not in response.text
    finally:
        await engine.dispose()
