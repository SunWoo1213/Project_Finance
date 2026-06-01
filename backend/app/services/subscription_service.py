from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User
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
    # The first implementation intentionally avoids a schema change until
    # subscription table migration/provider policy is confirmed.
    _ = (user_id, db)
    return None


def has_active_paid_access(subscription: SubscriptionSnapshot | None) -> bool:
    if subscription is None:
        return False
    return subscription.status == SubscriptionStatus.ACTIVE and subscription.tier in {
        SubscriptionTier.PLUS,
        SubscriptionTier.PRO,
    }


def build_entitlements(subscription: SubscriptionSnapshot | None) -> SubscriptionEntitlements:
    if not has_active_paid_access(subscription):
        return SubscriptionEntitlements(
            tier=SubscriptionTier.FREE,
            status=subscription.status if subscription else SubscriptionStatus.NONE,
            can_view_reports=False,
            can_use_chatbot=False,
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
