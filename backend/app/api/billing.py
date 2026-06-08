from fastapi import APIRouter, Depends, HTTPException, Request, status
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
    TossBillingIntentResponse,
    TossBillingKeyRequest,
    TossBillingKeyResponse,
)
from ..services.payment_service import (
    PaymentProviderUnavailable,
    PaymentSignatureVerificationError,
    PaymentWebhookParseError,
    apply_cancellation_result,
    create_toss_billing_auth_session,
    get_cancelable_subscription,
    get_payment_provider,
    get_toss_billing_auth_intent,
    process_webhook_event,
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
    db: AsyncSession = Depends(get_db),
):
    if payload.tier == SubscriptionTier.FREE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Free plan does not require checkout.",
        )

    success_url = payload.success_url or "http://localhost:5173/billing/success"
    cancel_url = payload.cancel_url or "http://localhost:5173/billing/cancel"
    try:
        provider = get_payment_provider()
        if provider.provider_name == "toss":
            session = await create_toss_billing_auth_session(
                db=db,
                user=current_user,
                tier=payload.tier,
                success_url=success_url,
                fail_url=cancel_url,
            )
        else:
            session = await provider.create_checkout_session(
                user=current_user,
                tier=payload.tier,
                success_url=success_url,
                cancel_url=cancel_url,
            )
    except PaymentProviderUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return BillingCheckoutResponse(checkout_url=session.checkout_url)


@router.get("/checkout/{intent_id}", response_model=TossBillingIntentResponse)
async def get_checkout_intent(
    intent_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        provider = get_payment_provider()
        if provider.provider_name != "toss":
            raise PaymentProviderUnavailable("Toss billing is not configured.")
        intent = await get_toss_billing_auth_intent(db, current_user.id, intent_id)
    except PaymentProviderUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    if intent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Billing intent was not found.")

    return TossBillingIntentResponse(
        intent_id=intent.intent_id,
        client_key=intent.client_key,
        customer_key=intent.customer_key,
        tier=intent.tier,
        amount_krw=intent.amount_krw,
        order_name=intent.order_name,
        success_url=intent.success_url,
        fail_url=intent.fail_url,
    )


@router.post("/toss/billing-key", response_model=TossBillingKeyResponse)
async def finalize_toss_billing_key(
    payload: TossBillingKeyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        provider = get_payment_provider()
        if provider.provider_name != "toss":
            raise PaymentProviderUnavailable("Toss billing is not configured.")
        intent = await get_toss_billing_auth_intent(db, current_user.id, payload.intent_id)
    except PaymentProviderUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    if intent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Billing intent was not found.")
    if payload.customer_key != intent.customer_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Toss customerKey does not match the billing intent.")

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Toss billing key finalization requires the approved billing schema migration "
            "so billingKey and renewal state can be stored securely."
        ),
    )


@router.post("/cancel", response_model=BillingCancelResponse)
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    subscription = await get_cancelable_subscription(db, current_user.id)
    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active provider-backed subscription is available to cancel.",
        )

    try:
        provider = get_payment_provider()
        result = await provider.cancel_subscription(subscription, cancel_at_period_end=True)
        await apply_cancellation_result(db, subscription, result)
    except PaymentProviderUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return BillingCancelResponse(canceled=True, message=result.message)


@router.post("/webhook", response_model=BillingWebhookAckResponse)
async def receive_billing_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    raw_body = await request.body()
    headers = {key.lower(): value for key, value in request.headers.items()}

    try:
        provider = get_payment_provider()
        provider.verify_webhook_signature(headers, raw_body)
        provider_event = provider.parse_webhook_event(headers, raw_body)
        normalized_event = provider.normalize_event(provider_event, raw_body)
        await process_webhook_event(db, normalized_event)
    except PaymentProviderUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except PaymentSignatureVerificationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PaymentWebhookParseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return BillingWebhookAckResponse(received=True)
