from types import SimpleNamespace
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api import billing
from app.core.config import settings
from app.models import Subscription, User
from app.schemas import SubscriptionStatus, SubscriptionTier
from billing_test_utils import create_test_sessionmaker


async def override_db():
    yield object()


async def override_current_user():
    return SimpleNamespace(id=1, email="user@example.com", nickname="tester")


@pytest.mark.asyncio
async def test_billing_plans_are_public():
    app = FastAPI()
    app.include_router(billing.router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/billing/plans")

    assert response.status_code == 200
    payload = response.json()
    assert [plan["tier"] for plan in payload] == ["FREE", "PLUS", "PRO"]


@pytest.mark.asyncio
async def test_billing_me_requires_authentication():
    app = FastAPI()
    app.include_router(billing.router)
    app.dependency_overrides[billing.get_db] = override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/billing/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_billing_me_returns_free_entitlements_without_subscription():
    engine, Session = await create_test_sessionmaker()
    app = FastAPI()
    app.include_router(billing.router)
    app.dependency_overrides[billing.get_current_user] = override_current_user

    async def override_real_db():
        async with Session() as db:
            yield db

    app.dependency_overrides[billing.get_db] = override_real_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/billing/me")

        assert response.status_code == 200
        payload = response.json()
        assert payload["tier"] == "FREE"
        assert payload["status"] == "NONE"
        assert payload["entitlements"] == {
            "can_view_reports": False,
            "can_use_chatbot": False,
            "can_use_notifications": False,
        }
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_billing_me_returns_db_backed_pro_entitlements():
    engine, Session = await create_test_sessionmaker()
    now = datetime.utcnow()
    async with Session() as db:
        user = User(email="billing-pro@example.com", nickname="billing-pro")
        db.add(user)
        await db.flush()
        db.add(
            Subscription(
                user_id=user.id,
                tier=SubscriptionTier.PRO.value,
                status=SubscriptionStatus.ACTIVE.value,
                provider="mock",
                provider_subscription_id="sub_api_pro",
                current_period_start=now,
                current_period_end=now + timedelta(days=30),
            )
        )
        await db.commit()
        user_id = user.id

    async def override_pro_user():
        return SimpleNamespace(id=user_id, email="billing-pro@example.com", nickname="billing-pro")

    async def override_real_db():
        async with Session() as db:
            yield db

    app = FastAPI()
    app.include_router(billing.router)
    app.dependency_overrides[billing.get_db] = override_real_db
    app.dependency_overrides[billing.get_current_user] = override_pro_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/billing/me")

        assert response.status_code == 200
        payload = response.json()
        assert payload["tier"] == "PRO"
        assert payload["status"] == "ACTIVE"
        assert payload["entitlements"] == {
            "can_view_reports": True,
            "can_use_chatbot": True,
            "can_use_notifications": True,
        }
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_billing_checkout_rejects_free_tier_before_provider_work():
    app = FastAPI()
    app.include_router(billing.router)
    app.dependency_overrides[billing.get_current_user] = override_current_user
    app.dependency_overrides[billing.get_db] = override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/billing/checkout", json={"tier": "FREE"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Free plan does not require checkout."


@pytest.mark.asyncio
@pytest.mark.parametrize("tier", ["PLUS", "PRO"])
async def test_billing_checkout_provider_unavailable_returns_clear_error(tier, monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", None)
    app = FastAPI()
    app.include_router(billing.router)
    app.dependency_overrides[billing.get_current_user] = override_current_user
    app.dependency_overrides[billing.get_db] = override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/billing/checkout", json={"tier": tier})

    assert response.status_code == 503
    assert response.json()["detail"] == "Payment provider is not configured."


@pytest.mark.asyncio
@pytest.mark.parametrize("tier", ["PLUS", "PRO"])
async def test_billing_checkout_mock_activates_subscription_immediately(tier, monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "mock")
    engine, Session = await create_test_sessionmaker()
    async with Session() as db:
        user = User(email="mock-checkout@example.com", nickname="mock-checkout")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        user_id = user.id

    async def override_mock_user():
        return SimpleNamespace(id=user_id, email="mock-checkout@example.com", nickname="mock-checkout")

    async def override_real_db():
        async with Session() as db:
            yield db

    app = FastAPI()
    app.include_router(billing.router)
    app.dependency_overrides[billing.get_current_user] = override_mock_user
    app.dependency_overrides[billing.get_db] = override_real_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/billing/checkout",
                json={
                    "tier": tier,
                    "success_url": "http://frontend.test/billing/success",
                    "cancel_url": "http://frontend.test/billing/cancel",
                },
            )

            assert response.status_code == 200
            payload = response.json()
            assert payload["activated"] is True
            assert payload["checkout_url"] == "http://frontend.test/billing/success"

            me_response = await client.get("/api/billing/me")

        assert me_response.status_code == 200
        me_payload = me_response.json()
        assert me_payload["tier"] == tier
        assert me_payload["status"] == "ACTIVE"
        assert me_payload["entitlements"]["can_view_reports"] is True
        assert me_payload["entitlements"]["can_use_chatbot"] is (tier == "PRO")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_billing_checkout_mock_reactivation_keeps_single_active_row(monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "mock")
    engine, Session = await create_test_sessionmaker()
    async with Session() as db:
        user = User(email="mock-reactivate@example.com", nickname="mock-reactivate")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        user_id = user.id

    async def override_mock_user():
        return SimpleNamespace(id=user_id, email="mock-reactivate@example.com", nickname="mock-reactivate")

    async def override_real_db():
        async with Session() as db:
            yield db

    app = FastAPI()
    app.include_router(billing.router)
    app.dependency_overrides[billing.get_current_user] = override_mock_user
    app.dependency_overrides[billing.get_db] = override_real_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            first = await client.post("/api/billing/checkout", json={"tier": "PLUS"})
            second = await client.post("/api/billing/checkout", json={"tier": "PRO"})

            assert first.status_code == 200
            assert second.status_code == 200

            me_response = await client.get("/api/billing/me")

        assert me_response.json()["tier"] == "PRO"

        async with Session() as db:
            result = await db.execute(
                select(Subscription).where(Subscription.user_id == user_id)
            )
            subscriptions = list(result.scalars())

        active = [sub for sub in subscriptions if sub.status == SubscriptionStatus.ACTIVE.value]
        assert len(subscriptions) == 1
        assert len(active) == 1
        assert active[0].tier == SubscriptionTier.PRO.value
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_billing_checkout_toss_creates_billing_auth_intent(monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "toss")
    monkeypatch.setattr(settings, "TOSS_CLIENT_KEY", "test_ck_example")
    engine, Session = await create_test_sessionmaker()

    async with Session() as db:
        user = User(email="toss-checkout@example.com", nickname="toss-checkout")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        user_id = user.id

    async def override_toss_user():
        return SimpleNamespace(id=user_id, email="toss-checkout@example.com", nickname="toss-checkout")

    async def override_real_db():
        async with Session() as db:
            yield db

    app = FastAPI()
    app.include_router(billing.router)
    app.dependency_overrides[billing.get_db] = override_real_db
    app.dependency_overrides[billing.get_current_user] = override_toss_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/billing/checkout",
                json={
                    "tier": "PLUS",
                    "success_url": "http://frontend.test/billing/success",
                    "cancel_url": "http://frontend.test/billing/cancel",
                },
            )

            assert response.status_code == 200
            checkout_url = response.json()["checkout_url"]
            parsed = urlparse(checkout_url)
            intent_id = parse_qs(parsed.query)["intent_id"][0]
            assert checkout_url.startswith("http://frontend.test/billing/toss/auth?")

            intent_response = await client.get(f"/api/billing/checkout/{intent_id}")

        assert intent_response.status_code == 200
        payload = intent_response.json()
        assert payload["provider"] == "toss"
        assert payload["mode"] == "billing_auth"
        assert payload["client_key"] == "test_ck_example"
        assert payload["tier"] == "PLUS"
        assert payload["amount_krw"] == 1000
        assert payload["success_url"].startswith("http://frontend.test/billing/success?")
        assert "authKey" not in payload
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_billing_cancel_marks_subscription_canceled_at_period_end(monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "mock")
    engine, Session = await create_test_sessionmaker()
    now = datetime.utcnow()
    async with Session() as db:
        user = User(email="cancel@example.com", nickname="cancel")
        db.add(user)
        await db.flush()
        db.add(
            Subscription(
                user_id=user.id,
                tier=SubscriptionTier.PLUS.value,
                status=SubscriptionStatus.ACTIVE.value,
                provider="mock",
                provider_subscription_id="sub_cancel",
                current_period_start=now,
                current_period_end=now + timedelta(days=30),
            )
        )
        await db.commit()
        user_id = user.id

    async def override_cancel_user():
        return SimpleNamespace(id=user_id, email="cancel@example.com", nickname="cancel")

    async def override_real_db():
        async with Session() as db:
            yield db

    app = FastAPI()
    app.include_router(billing.router)
    app.dependency_overrides[billing.get_db] = override_real_db
    app.dependency_overrides[billing.get_current_user] = override_cancel_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/billing/cancel")

        async with Session() as db:
            subscription = await db.get(Subscription, 1)

        assert response.status_code == 200
        assert response.json()["canceled"] is True
        assert subscription.status == SubscriptionStatus.CANCELED.value
        assert subscription.cancel_at_period_end is True
    finally:
        await engine.dispose()
