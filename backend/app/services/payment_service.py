from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models import BillingEvent, Subscription, User
from ..schemas import SubscriptionStatus, SubscriptionTier


class PaymentProviderUnavailable(RuntimeError):
    pass


class PaymentSignatureVerificationError(RuntimeError):
    pass


class PaymentWebhookParseError(RuntimeError):
    pass


@dataclass(frozen=True)
class CheckoutSession:
    checkout_url: str


@dataclass(frozen=True)
class CancellationResult:
    cancel_at_period_end: bool
    status: SubscriptionStatus
    message: str


@dataclass(frozen=True)
class NormalizedWebhookEvent:
    provider: str
    provider_event_id: str
    event_type: str
    payload_hash: str
    user_id: int | None
    provider_customer_id: str | None
    provider_subscription_id: str | None
    provider_plan_id: str | None
    tier: SubscriptionTier | None
    status: SubscriptionStatus | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    summary: dict[str, Any]


@dataclass(frozen=True)
class WebhookProcessResult:
    received: bool
    processed_status: str
    duplicate: bool = False


class PaymentProvider:
    provider_name = "base"

    async def create_checkout_session(
        self,
        user: User,
        tier: SubscriptionTier,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutSession:
        raise NotImplementedError

    async def cancel_subscription(
        self,
        subscription: Subscription,
        cancel_at_period_end: bool = True,
    ) -> CancellationResult:
        raise NotImplementedError

    def verify_webhook_signature(self, headers: dict[str, str], raw_body: bytes) -> None:
        raise NotImplementedError

    def parse_webhook_event(self, headers: dict[str, str], raw_body: bytes) -> dict[str, Any]:
        raise NotImplementedError

    def normalize_event(self, provider_event: dict[str, Any], raw_body: bytes) -> NormalizedWebhookEvent:
        raise NotImplementedError


class MockPaymentProvider(PaymentProvider):
    provider_name = "mock"

    async def create_checkout_session(
        self,
        user: User,
        tier: SubscriptionTier,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutSession:
        plan_id = get_plan_id(tier)
        if not plan_id:
            raise PaymentProviderUnavailable(f"{tier.value} payment plan is not configured.")

        base_url = settings.PAYMENT_MOCK_CHECKOUT_BASE_URL or success_url
        query = urlencode(
            {
                "provider": self.provider_name,
                "tier": tier.value,
                "plan_id": plan_id,
                "user_id": user.id,
                "cancel_url": cancel_url,
            }
        )
        separator = "&" if "?" in base_url else "?"
        return CheckoutSession(checkout_url=f"{base_url}{separator}{query}")

    async def cancel_subscription(
        self,
        subscription: Subscription,
        cancel_at_period_end: bool = True,
    ) -> CancellationResult:
        _ = subscription
        return CancellationResult(
            cancel_at_period_end=cancel_at_period_end,
            status=SubscriptionStatus.CANCELED,
            message="Subscription cancellation is scheduled at the end of the current period.",
        )

    def verify_webhook_signature(self, headers: dict[str, str], raw_body: bytes) -> None:
        secret = settings.PAYMENT_WEBHOOK_SECRET
        if not secret:
            raise PaymentSignatureVerificationError("Payment webhook secret is not configured.")

        signature = headers.get("x-payment-signature") or headers.get("x-mock-signature")
        if not signature:
            raise PaymentSignatureVerificationError("Payment webhook signature is missing.")

        expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        normalized_signature = signature.removeprefix("sha256=")
        if not hmac.compare_digest(expected, normalized_signature):
            raise PaymentSignatureVerificationError("Payment webhook signature is invalid.")

    def parse_webhook_event(self, headers: dict[str, str], raw_body: bytes) -> dict[str, Any]:
        _ = headers
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PaymentWebhookParseError("Payment webhook payload is invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise PaymentWebhookParseError("Payment webhook payload must be a JSON object.")
        return payload

    def normalize_event(self, provider_event: dict[str, Any], raw_body: bytes) -> NormalizedWebhookEvent:
        event_type = str(provider_event.get("type") or provider_event.get("event_type") or "unknown")
        provider_event_id = str(provider_event.get("id") or provider_event.get("event_id") or "")
        if not provider_event_id:
            raise PaymentWebhookParseError("Payment webhook event id is missing.")

        data = provider_event.get("data") or {}
        if not isinstance(data, dict):
            data = {}

        tier = parse_tier(data.get("tier"))
        provider_plan_id = optional_str(data.get("provider_plan_id") or data.get("plan_id"))
        if tier is None and provider_plan_id:
            tier = tier_from_plan_id(provider_plan_id)

        status = status_from_event_type(event_type, data.get("status"))
        user_id = parse_int(data.get("user_id") or provider_event.get("user_id"))
        provider_subscription_id = optional_str(
            data.get("provider_subscription_id")
            or data.get("subscription_id")
            or provider_event.get("subscription_id")
        )
        provider_customer_id = optional_str(data.get("provider_customer_id") or data.get("customer_id"))
        period_start = parse_datetime(data.get("current_period_start"))
        period_end = parse_datetime(data.get("current_period_end"))
        cancel_at_period_end = bool(data.get("cancel_at_period_end", status == SubscriptionStatus.CANCELED))

        summary = {
            "provider_event_id": provider_event_id,
            "event_type": event_type,
            "user_id": user_id,
            "provider_subscription_id": provider_subscription_id,
            "provider_plan_id": provider_plan_id,
            "tier": tier.value if tier else None,
            "status": status.value if status else None,
            "current_period_start": period_start.isoformat() if period_start else None,
            "current_period_end": period_end.isoformat() if period_end else None,
            "cancel_at_period_end": cancel_at_period_end,
        }

        return NormalizedWebhookEvent(
            provider=self.provider_name,
            provider_event_id=provider_event_id,
            event_type=event_type,
            payload_hash=hashlib.sha256(raw_body).hexdigest(),
            user_id=user_id,
            provider_customer_id=provider_customer_id,
            provider_subscription_id=provider_subscription_id,
            provider_plan_id=provider_plan_id,
            tier=tier,
            status=status,
            current_period_start=period_start,
            current_period_end=period_end,
            cancel_at_period_end=cancel_at_period_end,
            summary=summary,
        )


def get_payment_provider() -> PaymentProvider:
    provider = (settings.PAYMENT_PROVIDER or "").strip().lower()
    if provider == "mock":
        return MockPaymentProvider()
    raise PaymentProviderUnavailable("Payment provider is not configured.")


def get_plan_id(tier: SubscriptionTier) -> str | None:
    is_mock = (settings.PAYMENT_PROVIDER or "").strip().lower() == "mock"
    if tier == SubscriptionTier.PLUS:
        return settings.PAYMENT_PLUS_PLAN_ID or ("mock_plus_monthly" if is_mock else None)
    if tier == SubscriptionTier.PRO:
        return settings.PAYMENT_PRO_PLAN_ID or ("mock_pro_monthly" if is_mock else None)
    return None


def tier_from_plan_id(provider_plan_id: str) -> SubscriptionTier | None:
    is_mock = (settings.PAYMENT_PROVIDER or "").strip().lower() == "mock"
    plus_plan = settings.PAYMENT_PLUS_PLAN_ID or ("mock_plus_monthly" if is_mock else None)
    pro_plan = settings.PAYMENT_PRO_PLAN_ID or ("mock_pro_monthly" if is_mock else None)
    if provider_plan_id == plus_plan:
        return SubscriptionTier.PLUS
    if provider_plan_id == pro_plan:
        return SubscriptionTier.PRO
    return None


def parse_tier(value: Any) -> SubscriptionTier | None:
    if value is None:
        return None
    try:
        tier = SubscriptionTier(str(value).upper())
    except ValueError:
        return None
    return tier if tier != SubscriptionTier.FREE else None


def status_from_event_type(event_type: str, explicit_status: Any) -> SubscriptionStatus | None:
    if explicit_status:
        try:
            return SubscriptionStatus(str(explicit_status).upper())
        except ValueError:
            pass

    normalized = event_type.lower().replace("_", ".")
    if normalized in {"subscription.created", "subscription.activated", "payment.succeeded", "invoice.paid"}:
        return SubscriptionStatus.ACTIVE
    if normalized in {"payment.failed", "invoice.payment.failed", "subscription.past.due"}:
        return SubscriptionStatus.PAST_DUE
    if normalized in {"subscription.canceled", "subscription.cancelled"}:
        return SubscriptionStatus.CANCELED
    if normalized in {"subscription.ended", "subscription.expired", "subscription.deleted"}:
        return SubscriptionStatus.EXPIRED
    if normalized in {"subscription.plan.changed", "subscription.updated"}:
        return SubscriptionStatus.ACTIVE
    return None


def optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_datetime(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


async def get_cancelable_subscription(db: AsyncSession, user_id: int) -> Subscription | None:
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .where(Subscription.status == SubscriptionStatus.ACTIVE.value)
        .order_by(Subscription.updated_at.desc(), Subscription.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def apply_cancellation_result(
    db: AsyncSession,
    subscription: Subscription,
    result: CancellationResult,
) -> Subscription:
    now = datetime.utcnow()
    subscription.status = result.status.value
    subscription.cancel_at_period_end = result.cancel_at_period_end
    subscription.canceled_at = now
    subscription.updated_at = now
    if result.status == SubscriptionStatus.EXPIRED:
        subscription.ended_at = now
    await db.commit()
    await db.refresh(subscription)
    return subscription


async def process_webhook_event(
    db: AsyncSession,
    event: NormalizedWebhookEvent,
) -> WebhookProcessResult:
    existing = await find_billing_event(db, event.provider, event.provider_event_id)
    if existing is not None:
        return WebhookProcessResult(received=True, processed_status=existing.processed_status, duplicate=True)

    billing_event = BillingEvent(
        provider=event.provider,
        provider_event_id=event.provider_event_id,
        event_type=event.event_type,
        processed_status="received",
        user_id=event.user_id,
        payload_hash=event.payload_hash,
        normalized_summary=event.summary,
        received_at=datetime.utcnow(),
    )
    db.add(billing_event)

    try:
        subscription = await apply_subscription_transition(db, event, billing_event)
        if subscription is None:
            billing_event.processed_status = "ignored"
        else:
            billing_event.subscription = subscription
            billing_event.user_id = subscription.user_id
            billing_event.processed_status = "processed"
        billing_event.processed_at = datetime.utcnow()
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return WebhookProcessResult(received=True, processed_status="processed", duplicate=True)
    except Exception as exc:
        await db.rollback()
        failed_event = await find_billing_event(db, event.provider, event.provider_event_id)
        if failed_event is None:
            failed_event = BillingEvent(
                provider=event.provider,
                provider_event_id=event.provider_event_id,
                event_type=event.event_type,
                processed_status="failed",
                user_id=event.user_id,
                payload_hash=event.payload_hash,
                normalized_summary=event.summary,
                error_message=str(exc),
                received_at=datetime.utcnow(),
                processed_at=datetime.utcnow(),
            )
            db.add(failed_event)
        else:
            failed_event.processed_status = "failed"
            failed_event.error_message = str(exc)
            failed_event.processed_at = datetime.utcnow()
        await db.commit()
        return WebhookProcessResult(received=True, processed_status="failed")

    return WebhookProcessResult(received=True, processed_status=billing_event.processed_status)


async def find_billing_event(db: AsyncSession, provider: str, provider_event_id: str) -> BillingEvent | None:
    result = await db.execute(
        select(BillingEvent)
        .where(BillingEvent.provider == provider)
        .where(BillingEvent.provider_event_id == provider_event_id)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def apply_subscription_transition(
    db: AsyncSession,
    event: NormalizedWebhookEvent,
    billing_event: BillingEvent,
) -> Subscription | None:
    if event.status is None:
        return None
    if event.tier is None and event.status == SubscriptionStatus.ACTIVE:
        raise ValueError("Active subscription event is missing a paid tier.")
    if not event.provider_subscription_id:
        raise ValueError("Subscription event is missing provider subscription id.")

    subscription = await find_subscription_by_provider(db, event.provider, event.provider_subscription_id)
    if subscription is None:
        if event.user_id is None:
            raise ValueError("New subscription event is missing user id.")
        subscription = Subscription(
            user_id=event.user_id,
            provider=event.provider,
            provider_subscription_id=event.provider_subscription_id,
            tier=(event.tier or SubscriptionTier.FREE).value,
            status=event.status.value,
            created_at=datetime.utcnow(),
        )
        db.add(subscription)

    now = datetime.utcnow()
    if event.tier is not None:
        subscription.tier = event.tier.value
    subscription.status = event.status.value
    subscription.provider_customer_id = event.provider_customer_id or subscription.provider_customer_id
    subscription.provider_plan_id = event.provider_plan_id or subscription.provider_plan_id
    subscription.current_period_start = event.current_period_start or subscription.current_period_start
    subscription.current_period_end = event.current_period_end or subscription.current_period_end
    subscription.cancel_at_period_end = event.cancel_at_period_end
    subscription.updated_at = now

    if event.status == SubscriptionStatus.CANCELED:
        subscription.canceled_at = now
    if event.status == SubscriptionStatus.EXPIRED:
        subscription.ended_at = now
        subscription.cancel_at_period_end = False

    await db.flush()
    if event.status == SubscriptionStatus.ACTIVE:
        prior_result = await db.execute(
            select(Subscription)
            .where(Subscription.user_id == subscription.user_id)
            .where(Subscription.id != subscription.id)
            .where(Subscription.status.in_([SubscriptionStatus.ACTIVE.value, SubscriptionStatus.CANCELED.value]))
        )
        for prior_subscription in prior_result.scalars():
            prior_subscription.status = SubscriptionStatus.EXPIRED.value
            prior_subscription.cancel_at_period_end = False
            prior_subscription.ended_at = now
            prior_subscription.updated_at = now

    billing_event.subscription = subscription
    return subscription


async def find_subscription_by_provider(
    db: AsyncSession,
    provider: str,
    provider_subscription_id: str,
) -> Subscription | None:
    result = await db.execute(
        select(Subscription)
        .where(Subscription.provider == provider)
        .where(Subscription.provider_subscription_id == provider_subscription_id)
        .limit(1)
    )
    return result.scalar_one_or_none()
