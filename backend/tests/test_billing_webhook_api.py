import json
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api import billing
from app.core.config import settings
from app.models import Subscription, User
from app.schemas import SubscriptionStatus, SubscriptionTier
from billing_test_utils import create_test_sessionmaker, signed_json_headers


@pytest.mark.asyncio
async def test_billing_webhook_invalid_signature_returns_400(monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "mock")
    monkeypatch.setattr(settings, "PAYMENT_WEBHOOK_SECRET", "secret")

    app = FastAPI()
    app.include_router(billing.router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/billing/webhook",
            content=b'{"id":"evt_bad","type":"subscription.activated"}',
            headers={"x-payment-signature": "bad"},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Payment webhook signature is invalid."


@pytest.mark.asyncio
async def test_billing_webhook_valid_activation_updates_subscription(monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "mock")
    monkeypatch.setattr(settings, "PAYMENT_WEBHOOK_SECRET", "secret")
    engine, Session = await create_test_sessionmaker()
    now = datetime.utcnow()
    payload = {
        "id": "evt_route_activate",
        "type": "subscription.activated",
        "data": {
            "user_id": 1,
            "tier": "PRO",
            "subscription_id": "sub_route_pro",
            "current_period_start": now.isoformat(),
            "current_period_end": (now + timedelta(days=30)).isoformat(),
        },
    }

    async def override_real_db():
        async with Session() as db:
            yield db

    app = FastAPI()
    app.include_router(billing.router)
    app.dependency_overrides[billing.get_db] = override_real_db

    try:
        async with Session() as db:
            db.add(User(id=1, email="route-webhook@example.com", nickname="route-webhook"))
            await db.commit()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/billing/webhook",
                content=json.dumps(payload).encode("utf-8"),
                headers=signed_json_headers(payload, "secret"),
            )

        async with Session() as db:
            subscription = (await db.execute(select(Subscription))).scalar_one_or_none()

        assert response.status_code == 200
        assert response.json() == {"received": True}
        assert subscription is not None
        assert subscription.tier == SubscriptionTier.PRO.value
        assert subscription.status == SubscriptionStatus.ACTIVE.value
    finally:
        await engine.dispose()
