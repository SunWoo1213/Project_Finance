import os

import pytest
from sqlalchemy import select

os.environ.setdefault("PROJECT_NAME", "test")
os.environ.setdefault("API_V1_STR", "/api")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

from app.core.cache import market_cache
from app.models import AIReport, Asset, AssetCategory, NotificationChannelConnection, NotificationEvent, User
from app.services.favorite_service import upsert_user_favorite
from app.services import notification_service
from app.services.notification_service import (
    DeliveryResult,
    create_notification_events,
    create_scheduled_digest_notifications,
    evaluate_notifications,
    get_delivery_configuration_status,
    list_history,
    send_email_verification_code,
    send_welcome_notification_for_channel,
    send_pending_notifications,
)
from billing_test_utils import create_test_sessionmaker


@pytest.mark.asyncio
async def test_scheduled_digest_creates_one_message_per_active_delivery_channel(monkeypatch):
    engine, Session = await create_test_sessionmaker()
    original_prices = market_cache.get("prices")
    monkeypatch.setattr(notification_service.settings, "FRONTEND_BASE_URL", "https://finance.example.com")
    market_cache["prices"] = {
        "us_top10": {
            "NVIDIA": {
                "symbol": "NVDA",
                "currentPrice": 1024.5,
                "source": "test-cache",
            }
        },
        "crypto": {
            "Bitcoin": {
                "symbol": "BTC-USD",
                "currentPrice": 65000.25,
                "source": "test-cache",
            }
        },
    }

    try:
        async with Session() as db:
            user = User(email="service@example.com", nickname="service")
            db.add(user)
            await db.flush()
            await notification_service.update_preferences(
                db,
                user.id,
                {"email_enabled": True, "telegram_enabled": True},
            )
            db.add_all([
                NotificationChannelConnection(
                    user_id=user.id,
                    channel="email",
                    destination="service@example.com",
                    verified=True,
                    verification_status="verified",
                ),
                NotificationChannelConnection(
                    user_id=user.id,
                    channel="telegram",
                    destination="123456789",
                    verified=True,
                    verification_status="verified",
                ),
            ])
            await upsert_user_favorite(
                db,
                user_id=user.id,
                ticker="NVDA",
                display_name="NVIDIA",
                category_key="stock_us",
            )
            await upsert_user_favorite(
                db,
                user_id=user.id,
                ticker="BTC-USD",
                display_name="Bitcoin",
                category_key="crypto",
            )
            await db.commit()

        async with Session() as db:
            created = await create_scheduled_digest_notifications(db, schedule_label="09:00")
            created_again = await create_scheduled_digest_notifications(db, schedule_label="09:00")
            result = await db.execute(select(NotificationEvent).order_by(NotificationEvent.channel.asc()))
            events = list(result.scalars().all())

        assert created == 2
        assert created_again == 0
        assert {event.channel for event in events} == {"email", "telegram"}
        assert {event.status for event in events} == {"pending"}
        assert {event.event_type for event in events} == {"scheduled_digest"}
        assert {event.ticker for event in events} == {"DIGEST"}
        assert all(event.dedupe_key.startswith("digest:1:") for event in events)
        assert {event.dedupe_key.rsplit(":", 1)[-1] for event in events} == {"0900"}
        assert "오늘 09:00 기준 즐겨찾기 자산 요약입니다." in events[0].body
        assert "NVIDIA(NVDA): $1,024.50" in events[0].body
        assert "Bitcoin(BTC-USD): $65,000.25" in events[0].body
        assert "https://finance.example.com/detail/NVDA" in events[0].body
        assert "English" in events[0].body
        assert events[0].payload_json["asset_count"] == 2
        assert events[0].payload_json["shown_asset_count"] == 2
    finally:
        market_cache["prices"] = original_prices
        await engine.dispose()


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
        assert "English" in history[0].body
    finally:
        market_cache["prices"] = original_prices
        await engine.dispose()


@pytest.mark.asyncio
async def test_report_notification_uses_detail_link_price_and_omits_report_body(monkeypatch):
    engine, Session = await create_test_sessionmaker()
    original_prices = market_cache.get("prices")
    monkeypatch.setattr(notification_service.settings, "FRONTEND_BASE_URL", "https://finance.example.com")
    market_cache["prices"] = {
        "us_top10": {
            "NVIDIA": {
                "symbol": "NVDA",
                "currentPrice": 1024.5,
                "source": "test-cache",
            }
        }
    }

    try:
        async with Session() as db:
            user = User(email="service@example.com", nickname="service")
            asset = Asset(ticker="NVDA", name="NVIDIA", category=AssetCategory.STOCK_US)
            db.add_all([user, asset])
            await db.flush()
            await upsert_user_favorite(
                db,
                user_id=user.id,
                ticker="NVDA",
                display_name="NVIDIA",
                category_key="stock_us",
            )
            db.add(AIReport(asset_id=asset.id, final_content="old stored report"))
            await db.commit()

        async with Session() as db:
            assert await evaluate_notifications(db) == 0

        async with Session() as db:
            asset = (await db.execute(select(Asset).where(Asset.ticker == "NVDA"))).scalar_one()
            db.add(AIReport(asset_id=asset.id, final_content="new report body should stay private"))
            await db.commit()

        async with Session() as db:
            created = await evaluate_notifications(db)
            history = await list_history(db, user_id=1)

        assert created == 1
        event = history[0]
        assert event.event_type == "report"
        assert event.title == "즐겨찾기한 자산에 대한 보고서 발신입니다."
        assert "https://finance.example.com/detail/NVDA" in event.body
        assert "현재 가격: $1,024.50" in event.body
        assert "English" in event.body
        assert "Asset detail page: https://finance.example.com/detail/NVDA" in event.body
        assert "new report body should stay private" not in event.body
        assert event.payload_json["detail_url"] == "https://finance.example.com/detail/NVDA"
        assert event.payload_json["current_price"] == 1024.5
        assert event.payload_json["current_price_text"] == "$1,024.50"
        assert event.payload_json["price_source"] == "test-cache"
    finally:
        market_cache["prices"] = original_prices
        await engine.dispose()


@pytest.mark.asyncio
async def test_report_notification_uses_price_fallback_when_cache_is_missing(monkeypatch):
    engine, Session = await create_test_sessionmaker()
    original_prices = market_cache.get("prices")
    monkeypatch.setattr(notification_service.settings, "FRONTEND_BASE_URL", "http://localhost:5173")
    market_cache["prices"] = {}

    try:
        async with Session() as db:
            user = User(email="service@example.com", nickname="service")
            asset = Asset(ticker="BTC-USD", name="Bitcoin", category=AssetCategory.CRYPTO)
            db.add_all([user, asset])
            await db.flush()
            await upsert_user_favorite(
                db,
                user_id=user.id,
                ticker="BTC-USD",
                display_name="Bitcoin",
                category_key="crypto",
            )
            db.add(AIReport(asset_id=asset.id, final_content="old stored report"))
            await db.commit()

        async with Session() as db:
            assert await evaluate_notifications(db) == 0

        async with Session() as db:
            asset = (await db.execute(select(Asset).where(Asset.ticker == "BTC-USD"))).scalar_one()
            db.add(AIReport(asset_id=asset.id, final_content="new stored report"))
            await db.commit()

        async with Session() as db:
            created = await evaluate_notifications(db)
            history = await list_history(db, user_id=1)

        assert created == 1
        assert "현재 가격: 확인 중" in history[0].body
        assert "http://localhost:5173/detail/BTC-USD" in history[0].body
        assert "Current price: 확인 중" in history[0].body
        assert history[0].payload_json["current_price"] is None
        assert history[0].payload_json["current_price_text"] == "확인 중"
    finally:
        market_cache["prices"] = original_prices
        await engine.dispose()


@pytest.mark.asyncio
async def test_welcome_notification_sends_once_per_channel(monkeypatch):
    engine, Session = await create_test_sessionmaker()
    sent_messages = []

    async def fake_send_gmail(destination, subject, body):
        sent_messages.append((destination, subject, body))
        return DeliveryResult(success=True)

    monkeypatch.setattr(notification_service, "_send_gmail_message", fake_send_gmail)

    try:
        async with Session() as db:
            user = User(email="service@example.com", nickname="service")
            db.add(user)
            await db.commit()
            await db.refresh(user)

            first = await send_welcome_notification_for_channel(
                db,
                user_id=user.id,
                channel="email",
                destination=user.email,
            )
            second = await send_welcome_notification_for_channel(
                db,
                user_id=user.id,
                channel="email",
                destination=user.email,
            )

        async with Session() as db:
            result = await db.execute(select(NotificationEvent))
            events = list(result.scalars().all())

        assert first is not None
        assert second is not None
        assert first.id == second.id
        assert len(events) == 1
        assert events[0].event_type == "welcome"
        assert events[0].status == "sent"
        assert events[0].dedupe_key == "welcome:1:email"
        assert not events[0].body.startswith(events[0].title)
        assert "English" in events[0].body
        assert sent_messages == [
            (
                "service@example.com",
                "Project Finance를 이용해주셔서 감사합니다.",
                notification_service.WELCOME_NOTIFICATION_BODY,
            )
        ]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_news_notification_uses_detail_link_instead_of_external_news_link(monkeypatch):
    engine, Session = await create_test_sessionmaker()
    original_latest_context = market_cache.get("latest_context")
    original_prices = market_cache.get("prices")
    monkeypatch.setattr(notification_service.settings, "FRONTEND_BASE_URL", "https://finance.example.com")

    try:
        market_cache["prices"] = {}
        market_cache["latest_context"] = {
            "NVDA": {
                "news": [
                    {
                        "title": "Old headline",
                        "source": "Example News",
                        "link": "https://external.example/old",
                    }
                ]
            }
        }

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
            await db.commit()

        async with Session() as db:
            assert await evaluate_notifications(db) == 0

        market_cache["latest_context"] = {
            "NVDA": {
                "news": [
                    {
                        "title": "Fresh headline",
                        "source": "Example News",
                        "link": "https://external.example/fresh",
                    }
                ]
            }
        }

        async with Session() as db:
            created = await evaluate_notifications(db)
            history = await list_history(db, user_id=1)

        assert created == 1
        event = history[0]
        assert event.event_type == "news"
        assert "Fresh headline" in event.body
        assert "https://finance.example.com/detail/NVDA" in event.body
        assert "https://external.example/fresh" not in event.body
        assert "English" in event.body
        assert event.payload_json["detail_url"] == "https://finance.example.com/detail/NVDA"
    finally:
        market_cache["latest_context"] = original_latest_context
        market_cache["prices"] = original_prices
        await engine.dispose()


@pytest.mark.asyncio
async def test_welcome_notification_skips_missing_destination():
    engine, Session = await create_test_sessionmaker()

    try:
        async with Session() as db:
            user = User(email="service@example.com", nickname="service")
            db.add(user)
            await db.commit()
            await db.refresh(user)

            event = await send_welcome_notification_for_channel(
                db,
                user_id=user.id,
                channel="telegram",
                destination=None,
            )

        async with Session() as db:
            result = await db.execute(select(NotificationEvent))
            events = list(result.scalars().all())

        assert event is None
        assert events == []
    finally:
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


def test_delivery_configuration_status_reports_missing_settings_without_values(monkeypatch):
    monkeypatch.setattr(notification_service.settings, "EMAIL_PROVIDER", "gmail")
    monkeypatch.setattr(notification_service.settings, "EMAIL_FROM_ADDRESS", None)
    monkeypatch.setattr(notification_service.settings, "GMAIL_CLIENT_ID", "client-id")
    monkeypatch.setattr(notification_service.settings, "GMAIL_CLIENT_SECRET", None)
    monkeypatch.setattr(notification_service.settings, "GMAIL_REFRESH_TOKEN", None)
    monkeypatch.setattr(notification_service.settings, "TELEGRAM_BOT_TOKEN", None)
    monkeypatch.setattr(notification_service.settings, "ENABLE_SCHEDULER", True)
    monkeypatch.setattr(notification_service.settings, "ENABLE_NOTIFICATION_SCHEDULER", False)

    status = get_delivery_configuration_status()

    assert status["scheduler"]["enabled"] is False
    assert status["email"]["configured"] is False
    assert status["email"]["missing_keys"] == [
        "EMAIL_FROM_ADDRESS",
        "GMAIL_CLIENT_SECRET",
        "GMAIL_REFRESH_TOKEN",
    ]
    assert "client-id" not in str(status)
    assert status["telegram"]["missing_keys"] == ["TELEGRAM_BOT_TOKEN"]


@pytest.mark.asyncio
async def test_email_verification_code_body_is_bilingual_and_subject_is_korean(monkeypatch):
    engine, Session = await create_test_sessionmaker()
    sent_messages = []

    async def fake_send_gmail(destination, subject, body):
        sent_messages.append((destination, subject, body))
        return DeliveryResult(success=True)

    monkeypatch.setattr(notification_service, "_send_gmail_message", fake_send_gmail)

    try:
        async with Session() as db:
            user = User(email="service@example.com", nickname="service")
            db.add(user)
            await db.flush()
            connection = NotificationChannelConnection(
                user_id=user.id,
                channel="email",
                destination="service@example.com",
                verified=False,
                verification_status="pending",
                verification_code="ABC123",
            )
            db.add(connection)
            await db.commit()

            delivery = await send_email_verification_code(db, connection)

        assert delivery.success is True
        assert len(sent_messages) == 1
        assert sent_messages[0][0] == "service@example.com"
        assert sent_messages[0][1] == "Project Finance 이메일 확인 코드"
        assert "확인 코드: ABC123" in sent_messages[0][2]
        assert "English" in sent_messages[0][2]
        assert "Verification code: ABC123" in sent_messages[0][2]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_send_pending_telegram_event_marks_failed_after_retry_limit(monkeypatch):
    engine, Session = await create_test_sessionmaker()
    monkeypatch.setattr(notification_service.settings, "TELEGRAM_BOT_TOKEN", None)

    try:
        async with Session() as db:
            user = User(email="service@example.com", nickname="service")
            db.add(user)
            await db.flush()
            db.add(
                NotificationChannelConnection(
                    user_id=user.id,
                    channel="telegram",
                    destination="123456789",
                    verified=True,
                    verification_status="verified",
                )
            )
            await create_notification_events(
                db,
                user_id=user.id,
                ticker="NVDA",
                event_type="test",
                title="Telegram test",
                body="body",
                payload=None,
                dedupe_key="telegram-token-missing",
                channels=["telegram"],
            )
            event = await db.get(NotificationEvent, 1)
            event.attempts = 2
            event.next_attempt_at = None
            await db.commit()

        async with Session() as db:
            sent, failed = await send_pending_notifications(db)
            assert sent == 0
            assert failed == 1
            event = await db.get(NotificationEvent, 1)
            assert event.status == "failed"
            assert event.attempts == 3
            assert event.error_message == "Telegram bot token is not configured."
    finally:
        await engine.dispose()


def test_normalize_app_links_rewrites_localhost_app_links(monkeypatch):
    monkeypatch.setattr(notification_service.settings, "FRONTEND_BASE_URL", "https://finance.example.com")
    body = (
        "NVIDIA(NVDA)\n"
        "  상세 페이지: http://localhost:5173/detail/NVDA\n"
        "  Detail page: http://127.0.0.1:5173/detail/NVDA"
    )
    normalized = notification_service._normalize_app_links(body)
    assert "https://finance.example.com/detail/NVDA" in normalized
    assert "localhost:5173" not in normalized
    assert "127.0.0.1:5173" not in normalized


def test_normalize_app_links_keeps_external_news_links(monkeypatch):
    monkeypatch.setattr(notification_service.settings, "FRONTEND_BASE_URL", "https://finance.example.com")
    body = "관련 뉴스: https://news.example.org/article/123"
    assert notification_service._normalize_app_links(body) == body


def test_normalize_app_links_noop_in_localhost_environment(monkeypatch):
    monkeypatch.setattr(notification_service.settings, "FRONTEND_BASE_URL", "http://localhost:5173")
    body = "  상세 페이지: http://localhost:5173/detail/NVDA"
    # 개발 환경에서는 localhost를 그대로 유지한다.
    assert notification_service._normalize_app_links(body) == body


def test_build_asset_detail_url_warns_on_localhost_in_production(monkeypatch, caplog):
    monkeypatch.setattr(notification_service.settings, "FRONTEND_BASE_URL", "http://localhost:5173")
    monkeypatch.setattr(notification_service.settings, "ENVIRONMENT", "production")
    with caplog.at_level("WARNING"):
        url = notification_service._build_asset_detail_url("NVDA")
    assert url == "http://localhost:5173/detail/NVDA"
    assert any("FRONTEND_BASE_URL" in record.message for record in caplog.records)
