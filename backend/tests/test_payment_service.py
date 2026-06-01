import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models import BillingEvent, Subscription, User
from app.schemas import SubscriptionStatus, SubscriptionTier
from app.services.payment_service import (
    MockPaymentProvider,
    PaymentProviderUnavailable,
    PaymentSignatureVerificationError,
    get_payment_provider,
    process_webhook_event,
)
from billing_test_utils import create_test_sessionmaker, signed_json_headers


def test_get_payment_provider_requires_configuration(monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", None)

    with pytest.raises(PaymentProviderUnavailable):
        get_payment_provider()


def test_mock_webhook_signature_validation(monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_WEBHOOK_SECRET", "secret")
    provider = MockPaymentProvider()
    payload = {"id": "evt_1", "type": "subscription.activated"}
    raw_body = json.dumps(payload).encode("utf-8")

    provider.verify_webhook_signature(signed_json_headers(payload, "secret"), raw_body)

    with pytest.raises(PaymentSignatureVerificationError):
        provider.verify_webhook_signature({"x-payment-signature": "bad"}, raw_body)


@pytest.mark.asyncio
async def test_valid_activation_webhook_creates_subscription(monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "mock")
    engine, Session = await create_test_sessionmaker()
    now = datetime.utcnow()
    provider = MockPaymentProvider()
    payload = {
        "id": "evt_activate",
        "type": "subscription.activated",
        "data": {
            "user_id": 1,
            "tier": "PLUS",
            "subscription_id": "sub_plus",
            "customer_id": "cus_1",
            "current_period_start": now.isoformat(),
            "current_period_end": (now + timedelta(days=30)).isoformat(),
        },
    }
    raw_body = json.dumps(payload).encode("utf-8")

    try:
        async with Session() as db:
            db.add(User(id=1, email="webhook@example.com", nickname="webhook"))
            await db.commit()

            event = provider.normalize_event(payload, raw_body)
            result = await process_webhook_event(db, event)

            assert result.processed_status == "processed"
            subscription = (await db.execute(select(Subscription))).scalar_one_or_none()
            billing_event = (await db.execute(select(BillingEvent))).scalar_one_or_none()

            assert subscription is not None
            assert subscription.tier == SubscriptionTier.PLUS.value
            assert subscription.status == SubscriptionStatus.ACTIVE.value
            assert billing_event is not None
            assert billing_event.processed_status == "processed"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_duplicate_webhook_is_idempotent(monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "mock")
    engine, Session = await create_test_sessionmaker()
    now = datetime.utcnow()
    provider = MockPaymentProvider()
    payload = {
        "id": "evt_duplicate",
        "type": "subscription.activated",
        "data": {
            "user_id": 1,
            "tier": "PRO",
            "subscription_id": "sub_duplicate",
            "current_period_start": now.isoformat(),
            "current_period_end": (now + timedelta(days=30)).isoformat(),
        },
    }
    raw_body = json.dumps(payload).encode("utf-8")

    try:
        async with Session() as db:
            db.add(User(id=1, email="duplicate@example.com", nickname="duplicate"))
            await db.commit()

            event = provider.normalize_event(payload, raw_body)
            first = await process_webhook_event(db, event)
            second = await process_webhook_event(db, event)

            event_count = len((await db.execute(select(BillingEvent))).scalars().all())
            subscription_count = len((await db.execute(select(Subscription))).scalars().all())

            assert first.processed_status == "processed"
            assert second.duplicate is True
            assert event_count == 1
            assert subscription_count == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_unknown_webhook_event_is_recorded_as_ignored(monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "mock")
    engine, Session = await create_test_sessionmaker()
    provider = MockPaymentProvider()
    payload = {"id": "evt_unknown", "type": "something.unmapped", "data": {"user_id": 1}}
    raw_body = b'{"id":"evt_unknown","type":"something.unmapped","data":{"user_id":1}}'

    try:
        async with Session() as db:
            db.add(User(id=1, email="unknown@example.com", nickname="unknown"))
            await db.commit()

            event = provider.normalize_event(payload, raw_body)
            result = await process_webhook_event(db, event)
            billing_event = (await db.execute(select(BillingEvent))).scalar_one_or_none()

            assert result.processed_status == "ignored"
            assert billing_event.processed_status == "ignored"
    finally:
        await engine.dispose()
