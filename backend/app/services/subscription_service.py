from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Subscription, User
from ..schemas import (
    BillingPlanResponse,
    SubscriptionStatus,
    SubscriptionTier,
)


@dataclass(frozen=True)
class SubscriptionSnapshot:
    tier: SubscriptionTier
    status: SubscriptionStatus
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False


@dataclass(frozen=True)
class SubscriptionEntitlements:
    tier: SubscriptionTier
    status: SubscriptionStatus
    can_view_reports: bool
    can_use_chatbot: bool
    can_use_notifications: bool
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False


PLAN_CATALOG = [
    BillingPlanResponse(
        tier=SubscriptionTier.FREE,
        name="Free",
        monthly_price_krw=0,
        billing_cycle="month",
        can_view_reports=False,
        can_use_chatbot=False,
        description="시장 데이터와 커뮤니티 읽기 중심의 기본 플랜입니다.",
    ),
    BillingPlanResponse(
        tier=SubscriptionTier.PLUS,
        name="Plus",
        monthly_price_krw=1000,
        billing_cycle="month",
        can_view_reports=True,
        can_use_chatbot=False,
        description="저장된 스케줄 AI 리포트를 볼 수 있는 월 구독 플랜입니다.",
    ),
    BillingPlanResponse(
        tier=SubscriptionTier.PRO,
        name="Pro",
        monthly_price_krw=3000,
        billing_cycle="month",
        can_view_reports=True,
        can_use_chatbot=True,
        description="AI 리포트와 챗봇을 모두 사용할 수 있는 월 구독 플랜입니다.",
    ),
]


def get_billing_plans() -> list[BillingPlanResponse]:
    return PLAN_CATALOG


async def get_user_subscription(
    user_id: int,
    db: AsyncSession,
) -> SubscriptionSnapshot | None:
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .order_by(desc(Subscription.updated_at), desc(Subscription.created_at), desc(Subscription.id))
        .limit(1)
    )
    subscription = result.scalar_one_or_none()
    if subscription is None:
        return None

    return normalize_subscription_snapshot(
        SubscriptionSnapshot(
            tier=_coerce_tier(subscription.tier),
            status=_coerce_status(subscription.status),
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end,
            cancel_at_period_end=subscription.cancel_at_period_end,
        )
    )


def _coerce_tier(value: str | None) -> SubscriptionTier:
    try:
        return SubscriptionTier(value or SubscriptionTier.FREE.value)
    except ValueError:
        return SubscriptionTier.FREE


def _coerce_status(value: str | None) -> SubscriptionStatus:
    try:
        return SubscriptionStatus(value or SubscriptionStatus.NONE.value)
    except ValueError:
        return SubscriptionStatus.NONE


def _now() -> datetime:
    return datetime.utcnow()


def normalize_subscription_snapshot(subscription: SubscriptionSnapshot) -> SubscriptionSnapshot:
    if subscription.current_period_end and subscription.current_period_end <= _now():
        return SubscriptionSnapshot(
            tier=subscription.tier,
            status=SubscriptionStatus.EXPIRED,
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end,
            cancel_at_period_end=subscription.cancel_at_period_end,
        )
    return subscription


def has_active_paid_access(subscription: SubscriptionSnapshot | None) -> bool:
    if subscription is None:
        return False
    if subscription.tier not in {SubscriptionTier.PLUS, SubscriptionTier.PRO}:
        return False
    if subscription.current_period_end and subscription.current_period_end <= _now():
        return False
    if subscription.status == SubscriptionStatus.ACTIVE:
        return True
    return (
        subscription.status == SubscriptionStatus.CANCELED
        and subscription.cancel_at_period_end
        and subscription.current_period_end is not None
        and subscription.current_period_end > _now()
    )


def build_entitlements(subscription: SubscriptionSnapshot | None) -> SubscriptionEntitlements:
    if subscription is not None:
        subscription = normalize_subscription_snapshot(subscription)

    if not has_active_paid_access(subscription):
        return SubscriptionEntitlements(
            tier=SubscriptionTier.FREE,
            status=subscription.status if subscription else SubscriptionStatus.NONE,
            can_view_reports=False,
            can_use_chatbot=False,
            can_use_notifications=False,
            current_period_start=subscription.current_period_start if subscription else None,
            current_period_end=subscription.current_period_end if subscription else None,
            cancel_at_period_end=subscription.cancel_at_period_end if subscription else False,
        )

    tier = subscription.tier
    return SubscriptionEntitlements(
        tier=tier,
        status=subscription.status,
        can_view_reports=tier in {SubscriptionTier.PLUS, SubscriptionTier.PRO},
        can_use_chatbot=tier == SubscriptionTier.PRO,
        can_use_notifications=tier in {SubscriptionTier.PLUS, SubscriptionTier.PRO},
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        cancel_at_period_end=subscription.cancel_at_period_end,
    )


async def get_user_entitlements(
    user: User,
    db: AsyncSession,
) -> SubscriptionEntitlements:
    subscription = await get_user_subscription(user.id, db)
    return build_entitlements(subscription)
