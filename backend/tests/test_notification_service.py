import os

import pytest

os.environ.setdefault("PROJECT_NAME", "test")
os.environ.setdefault("API_V1_STR", "/api")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

from app.core.cache import market_cache
from app.models import NotificationChannelConnection, NotificationEvent, User
from app.services.favorite_service import upsert_user_favorite
from app.services import notification_service
from app.services.notification_service import (
    DeliveryResult,
    create_notification_events,
    evaluate_notifications,
    list_history,
    send_pending_notifications,
)
from billing_test_utils import create_test_sessionmaker


@pytest.mark.asyncio
async def test_evaluate_notifications_uses_market_cache_and_dedupes_price_events():
    engine, Session = await create_test_sessionmaker()
    original_prices = market_cache.get("prices")
    market_cache["prices"] = {
        "us_top10": {
            "NVIDIA": {
                "symbol": "NVDA",
                "currentPrice": 1000,
                "changePercent": 4.2,
                "history_prices": [960, 1000],
                "marketCap": 100,
            }
        }
    }

    try:
        async with Session() as db:
            user = User(email="service@example.com", nickname="service")
            db.add(user)
            await db.flush()
            await upsert_user_favorite(
                db,
                user_id=user.id,
                ticker="NVDA",
                display_name="NVIDIA",
                category_key="us_top10",
            )

        async with Session() as db:
            created = await evaluate_notifications(db)
            assert created == 1
            created_again = await evaluate_notifications(db)
            assert created_again == 0
            history = await list_history(db, user_id=1)

        assert len(history) == 1
        assert history[0].event_type == "price_change"
        assert history[0].channel == "in_app"
        assert history[0].status == "sent"
    finally:
        market_cache["prices"] = original_prices
        await engine.dispose()


@pytest.mark.asyncio
async def test_send_pending_email_event_marks_sent_when_gmail_adapter_succeeds(monkeypatch):
    engine, Session = await create_test_sessionmaker()

    async def fake_send_email(destination, event):
        assert destination == "service@example.com"
        assert event.title == "테스트 알림"
        return DeliveryResult(success=True)

    monkeypatch.setattr(notification_service, "_send_email", fake_send_email)

    try:
        async with Session() as db:
            user = User(email="service@example.com", nickname="service")
            db.add(user)
            await db.flush()
            db.add(
                NotificationChannelConnection(
                    user_id=user.id,
                    channel="email",
                    destination="service@example.com",
                    verified=True,
                    verification_status="verified",
                )
            )
            await create_notification_events(
                db,
                user_id=user.id,
                ticker="NVDA",
                event_type="test",
                title="테스트 알림",
                body="본문",
                payload=None,
                dedupe_key="email-success",
                channels=["email"],
            )

        async with Session() as db:
            sent, failed = await send_pending_notifications(db)
            assert sent == 1
            assert failed == 0
            event = await db.get(NotificationEvent, 1)
            assert event.status == "sent"
            assert event.sent_at is not None
            assert event.error_message is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_send_pending_email_event_keeps_retry_state_when_gmail_adapter_fails(monkeypatch):
    engine, Session = await create_test_sessionmaker()

    async def fake_send_email(destination, event):
        return DeliveryResult(success=False, error_message="Gmail returned HTTP 500.")

    monkeypatch.setattr(notification_service, "_send_email", fake_send_email)

    try:
        async with Session() as db:
            user = User(email="service@example.com", nickname="service")
            db.add(user)
            await db.flush()
            db.add(
                NotificationChannelConnection(
                    user_id=user.id,
                    channel="email",
                    destination="service@example.com",
                    verified=True,
                    verification_status="verified",
                )
            )
            await create_notification_events(
                db,
                user_id=user.id,
                ticker="NVDA",
                event_type="test",
                title="테스트 알림",
                body="본문",
                payload=None,
                dedupe_key="email-failure",
                channels=["email"],
            )

        async with Session() as db:
            sent, failed = await send_pending_notifications(db)
            assert sent == 0
            assert failed == 1
            event = await db.get(NotificationEvent, 1)
            assert event.status == "pending"
            assert event.attempts == 1
            assert event.next_attempt_at is not None
            assert event.error_message == "Gmail returned HTTP 500."
    finally:
        await engine.dispose()
