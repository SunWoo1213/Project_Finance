from datetime import datetime, timedelta

import pytest

from app.models import Subscription, User
from app.schemas import SubscriptionStatus, SubscriptionTier
from app.services.subscription_service import (
    SubscriptionSnapshot,
    build_entitlements,
    get_billing_plans,
    get_user_subscription,
)
from billing_test_utils import create_test_sessionmaker


def test_billing_plans_match_target_tiers():
    plans = {plan.tier: plan for plan in get_billing_plans()}

    assert plans[SubscriptionTier.FREE].monthly_price_krw == 0
    assert plans[SubscriptionTier.FREE].can_view_reports is False
    assert plans[SubscriptionTier.FREE].can_use_chatbot is False
    assert plans[SubscriptionTier.PLUS].monthly_price_krw == 1000
    assert plans[SubscriptionTier.PLUS].can_view_reports is True
    assert plans[SubscriptionTier.PLUS].can_use_chatbot is False
    assert plans[SubscriptionTier.PRO].monthly_price_krw == 3000
    assert plans[SubscriptionTier.PRO].can_view_reports is True
    assert plans[SubscriptionTier.PRO].can_use_chatbot is True


def test_missing_subscription_is_free_without_paid_entitlements():
    entitlements = build_entitlements(None)

    assert entitlements.tier == SubscriptionTier.FREE
    assert entitlements.status == SubscriptionStatus.NONE
    assert entitlements.can_view_reports is False
    assert entitlements.can_use_chatbot is False
    assert entitlements.can_use_notifications is False


def test_active_plus_can_view_reports_but_not_chatbot():
    now = datetime.utcnow()
    entitlements = build_entitlements(
        SubscriptionSnapshot(
            tier=SubscriptionTier.PLUS,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )
    )

    assert entitlements.tier == SubscriptionTier.PLUS
    assert entitlements.can_view_reports is True
    assert entitlements.can_use_chatbot is False
    assert entitlements.can_use_notifications is True


def test_active_pro_can_view_reports_and_chatbot():
    entitlements = build_entitlements(
        SubscriptionSnapshot(
            tier=SubscriptionTier.PRO,
            status=SubscriptionStatus.ACTIVE,
        )
    )

    assert entitlements.tier == SubscriptionTier.PRO
    assert entitlements.can_view_reports is True
    assert entitlements.can_use_chatbot is True
    assert entitlements.can_use_notifications is True


def test_canceled_at_period_end_keeps_paid_access_before_period_end():
    now = datetime.utcnow()
    entitlements = build_entitlements(
        SubscriptionSnapshot(
            tier=SubscriptionTier.PRO,
            status=SubscriptionStatus.CANCELED,
            current_period_start=now - timedelta(days=10),
            current_period_end=now + timedelta(days=20),
            cancel_at_period_end=True,
        )
    )

    assert entitlements.tier == SubscriptionTier.PRO
    assert entitlements.status == SubscriptionStatus.CANCELED
    assert entitlements.can_view_reports is True
    assert entitlements.can_use_chatbot is True
    assert entitlements.can_use_notifications is True


def test_inactive_paid_subscription_falls_back_to_free_entitlements():
    entitlements = build_entitlements(
        SubscriptionSnapshot(
            tier=SubscriptionTier.PRO,
            status=SubscriptionStatus.EXPIRED,
        )
    )

    assert entitlements.tier == SubscriptionTier.FREE
    assert entitlements.status == SubscriptionStatus.EXPIRED
    assert entitlements.can_view_reports is False
    assert entitlements.can_use_chatbot is False
    assert entitlements.can_use_notifications is False


def test_period_ended_subscription_is_normalized_to_expired():
    now = datetime.utcnow()
    entitlements = build_entitlements(
        SubscriptionSnapshot(
            tier=SubscriptionTier.PRO,
            status=SubscriptionStatus.CANCELED,
            current_period_start=now - timedelta(days=40),
            current_period_end=now - timedelta(days=1),
            cancel_at_period_end=True,
        )
    )

    assert entitlements.tier == SubscriptionTier.FREE
    assert entitlements.status == SubscriptionStatus.EXPIRED
    assert entitlements.can_view_reports is False
    assert entitlements.can_use_chatbot is False
    assert entitlements.can_use_notifications is False


@pytest.mark.asyncio
async def test_get_user_subscription_returns_none_for_no_subscription():
    engine, Session = await create_test_sessionmaker()
    try:
        async with Session() as db:
            user = User(email="none@example.com", nickname="none")
            db.add(user)
            await db.commit()
            await db.refresh(user)

            assert await get_user_subscription(user.id, db) is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_get_user_subscription_reads_latest_db_snapshot():
    engine, Session = await create_test_sessionmaker()
    now = datetime.utcnow()
    try:
        async with Session() as db:
            user = User(email="pro@example.com", nickname="pro")
            db.add(user)
            await db.flush()
            db.add(
                Subscription(
                    user_id=user.id,
                    tier=SubscriptionTier.PRO.value,
                    status=SubscriptionStatus.ACTIVE.value,
                    provider="mock",
                    provider_subscription_id="sub_pro",
                    current_period_start=now,
                    current_period_end=now + timedelta(days=30),
                )
            )
            await db.commit()

            snapshot = await get_user_subscription(user.id, db)

            assert snapshot is not None
            assert snapshot.tier == SubscriptionTier.PRO
            assert snapshot.status == SubscriptionStatus.ACTIVE
    finally:
        await engine.dispose()
