from datetime import datetime, timedelta

from app.schemas import SubscriptionStatus, SubscriptionTier
from app.services.subscription_service import (
    SubscriptionSnapshot,
    build_entitlements,
    get_billing_plans,
)


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
