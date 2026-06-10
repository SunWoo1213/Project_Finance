import os
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

os.environ.setdefault("PROJECT_NAME", "test")
os.environ.setdefault("API_V1_STR", "/api")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

from app.api import notifications
from app.models import NotificationChannelConnection, Subscription, User
from app.schemas import SubscriptionStatus, SubscriptionTier
from app.services import notification_service
from app.services.notification_service import DeliveryResult
from billing_test_utils import create_test_sessionmaker


async def override_current_user():
    return SimpleNamespace(id=1, email="notify@example.com", nickname="notify")


async def seed_paid_subscription(Session, *, user_id=1, tier=SubscriptionTier.PLUS):
    """외부 발송 알림 게이트를 통과할 수 있는 활성 유료 구독을 시드한다."""
    now = datetime.utcnow()
    async with Session() as db:
        db.add(
            Subscription(
                user_id=user_id,
                tier=tier.value,
                status=SubscriptionStatus.ACTIVE.value,
                provider="mock",
                provider_subscription_id=f"sub_{tier.value.lower()}",
                current_period_start=now,
                current_period_end=now + timedelta(days=30),
            )
        )
        await db.commit()


def build_notifications_app(Session):
    async def override_db():
        async with Session() as db:
            yield db

    app = FastAPI()
    app.include_router(notifications.router)
    app.dependency_overrides[notifications.get_db] = override_db
    app.dependency_overrides[notifications.get_current_user] = override_current_user
    return app


@pytest.mark.asyncio
async def test_notification_preferences_default_and_update():
    engine, Session = await create_test_sessionmaker()
    async with Session() as db:
        db.add(User(email="notify@example.com", nickname="notify"))
        await db.commit()

    await seed_paid_subscription(Session)

    app = build_notifications_app(Session)

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

    await seed_paid_subscription(Session)

    app = build_notifications_app(Session)

    async def fake_send_verification_code(db, connection):
        return DeliveryResult(success=True)

    async def fake_send_email(destination, event):
        return DeliveryResult(success=True)

    welcome_calls = []

    async def fake_send_welcome(db, *, user_id, channel, destination):
        welcome_calls.append((user_id, channel, destination))
        return None

    monkeypatch.setattr(notifications, "send_email_verification_code", fake_send_verification_code)
    monkeypatch.setattr(notification_service, "_send_email", fake_send_email)
    monkeypatch.setattr(notifications, "send_welcome_notification_for_channel", fake_send_welcome)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            verify_response = await client.post(
                "/api/notifications/channels/email/verify",
                json={"email": "notify@example.com"},
            )
            assert verify_response.status_code == 200
            assert verify_response.json()["verification_code"] is None

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
            assert welcome_calls == [(1, "email", "notify@example.com")]

            await client.put("/api/notifications/preferences", json={"email_enabled": True})
            test_response = await client.post(
                "/api/notifications/test",
                json={"ticker": "NVDA", "message": "test message"},
            )
            assert test_response.status_code == 200
            payload = test_response.json()
            assert payload["created_events"] == 2
            assert payload["sent_events"] == 1
            assert payload["failed_events"] == 0
            assert payload["delivery_status"]["email"]["provider"] == "gmail"

            history_response = await client.get("/api/notifications/history")
            assert history_response.status_code == 200
            history = history_response.json()
            assert {event["channel"] for event in history} == {"in_app", "email"}
            assert {event["status"] for event in history} == {"sent"}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_email_verify_does_not_expose_code_when_gmail_delivery_fails(monkeypatch):
    engine, Session = await create_test_sessionmaker()
    async with Session() as db:
        db.add(User(email="notify@example.com", nickname="notify"))
        await db.commit()

    await seed_paid_subscription(Session)

    app = build_notifications_app(Session)

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


@pytest.mark.asyncio
async def test_telegram_connect_contract_uses_manual_chat_id_flow():
    engine, Session = await create_test_sessionmaker()
    async with Session() as db:
        db.add(User(email="notify@example.com", nickname="notify"))
        await db.commit()

    await seed_paid_subscription(Session)

    app = build_notifications_app(Session)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/notifications/channels/telegram/connect", json={})
            assert response.status_code == 200
            payload = response.json()
            assert payload["verification_code"]
            assert "manual chat_id" in payload["message"]
            assert "/start" not in payload["message"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_telegram_verify_rejects_non_numeric_chat_id():
    engine, Session = await create_test_sessionmaker()
    async with Session() as db:
        db.add(User(email="notify@example.com", nickname="notify"))
        await db.commit()

    await seed_paid_subscription(Session)

    app = build_notifications_app(Session)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            connect_response = await client.post("/api/notifications/channels/telegram/connect", json={})
            code = connect_response.json()["verification_code"]

            response = await client.post(
                "/api/notifications/channels/telegram/verify",
                json={"code": code, "chat_id": "not-a-chat-id"},
            )
            assert response.status_code == 422
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_free_user_blocked_from_external_notification_endpoints():
    """구독이 없는 Free 사용자는 외부 발송 엔드포인트에서 403을 받는다."""
    engine, Session = await create_test_sessionmaker()
    async with Session() as db:
        db.add(User(email="notify@example.com", nickname="notify"))
        await db.commit()

    # 구독 시드 없음 → Free → can_use_notifications False

    app = build_notifications_app(Session)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            connect = await client.post("/api/notifications/channels/telegram/connect", json={})
            assert connect.status_code == 403

            tg_verify = await client.post(
                "/api/notifications/channels/telegram/verify",
                json={"code": "ABC123", "chat_id": "12345"},
            )
            assert tg_verify.status_code == 403

            email_verify = await client.post(
                "/api/notifications/channels/email/verify",
                json={"email": "notify@example.com"},
            )
            assert email_verify.status_code == 403

            email_confirm = await client.post(
                "/api/notifications/channels/email/confirm",
                json={"email": "notify@example.com", "code": "123456"},
            )
            assert email_confirm.status_code == 403

            test_send = await client.post(
                "/api/notifications/test",
                json={"ticker": "NVDA", "message": "test"},
            )
            assert test_send.status_code == 403
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_free_user_preferences_gate_blocks_only_external_enable():
    """Free 사용자는 telegram/email ON은 403이지만, in_app 토글과 끄기는 허용된다."""
    engine, Session = await create_test_sessionmaker()
    async with Session() as db:
        db.add(User(email="notify@example.com", nickname="notify"))
        await db.commit()

    app = build_notifications_app(Session)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # in_app 알림 타입 토글은 모든 등급에서 허용
            in_app = await client.put(
                "/api/notifications/preferences",
                json={"price_change_enabled": False, "daily_digest_enabled": True},
            )
            assert in_app.status_code == 200
            assert in_app.json()["price_change_enabled"] is False
            assert in_app.json()["daily_digest_enabled"] is True

            # 외부 발송 채널 끄기(False)는 허용
            disable_email = await client.put(
                "/api/notifications/preferences",
                json={"email_enabled": False},
            )
            assert disable_email.status_code == 200

            # telegram/email 켜기(True)는 PLUS 이상 필요 → 403
            enable_email = await client.put(
                "/api/notifications/preferences",
                json={"email_enabled": True},
            )
            assert enable_email.status_code == 403

            enable_telegram = await client.put(
                "/api/notifications/preferences",
                json={"telegram_enabled": True},
            )
            assert enable_telegram.status_code == 403
    finally:
        await engine.dispose()
