from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..models import User
from ..schemas import (
    BillingCancelResponse,
    BillingCheckoutRequest,
    BillingCheckoutResponse,
    BillingMeResponse,
    BillingPlanResponse,
    BillingWebhookAckResponse,
    SubscriptionEntitlementsResponse,
    SubscriptionTier,
)
from ..services.subscription_service import get_billing_plans, get_user_entitlements
from .deps import get_current_user

router = APIRouter(prefix="/api/billing", tags=["Billing"])


@router.get("/plans", response_model=list[BillingPlanResponse])
async def list_billing_plans():
    return get_billing_plans()


@router.get("/me", response_model=BillingMeResponse)
async def get_my_billing_state(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entitlements = await get_user_entitlements(current_user, db)
    return BillingMeResponse(
        tier=entitlements.tier,
        status=entitlements.status,
        current_period_start=entitlements.current_period_start,
        current_period_end=entitlements.current_period_end,
        cancel_at_period_end=entitlements.cancel_at_period_end,
        entitlements=SubscriptionEntitlementsResponse(
            can_view_reports=entitlements.can_view_reports,
            can_use_chatbot=entitlements.can_use_chatbot,
        ),
    )


@router.post("/checkout", response_model=BillingCheckoutResponse)
async def create_checkout_session(
    payload: BillingCheckoutRequest,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    if payload.tier == SubscriptionTier.FREE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Free plan does not require checkout.",
        )

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Payment provider checkout is not configured yet.",
    )


@router.post("/cancel", response_model=BillingCancelResponse)
async def cancel_subscription(current_user: User = Depends(get_current_user)):
    _ = current_user
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Subscription cancellation is not configured yet.",
    )


@router.post("/webhook", response_model=BillingWebhookAckResponse)
async def receive_billing_webhook():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Payment provider webhook handling is not configured yet.",
    )
