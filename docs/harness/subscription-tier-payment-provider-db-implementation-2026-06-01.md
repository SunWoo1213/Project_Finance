# Subscription Tier Payment Provider And DB Implementation

Date: 2026-06-01

## Objective

Implement the database-backed subscription state and provider-neutral payment boundary planned in `docs/harness/subscription-tier-payment-provider-db-implementation-plan-2026-06-01.md` without selecting or calling a live production payment provider.

## Files Changed

- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/app/api/billing.py`
- `backend/app/core/config.py`
- `backend/app/services/subscription_service.py`
- `backend/app/services/payment_service.py`
- `backend/alembic.ini`
- `backend/alembic/env.py`
- `backend/alembic/script.py.mako`
- `backend/alembic/versions/20260601_0001_add_subscription_billing_tables.py`
- `backend/requirements.txt`
- `backend/tests/billing_test_utils.py`
- `backend/tests/test_subscription_service.py`
- `backend/tests/test_subscription_api.py`
- `backend/tests/test_payment_service.py`
- `backend/tests/test_billing_webhook_api.py`
- `frontend/src/pages/Pricing.jsx`
- `frontend/src/pages/BillingSuccess.jsx`
- `frontend/src/pages/BillingCancel.jsx`
- `backend/DEVELOPMENT_DIRECTION.md`
- `docs/harness/features/subscription-billing.md`
- `docs/harness/feature-index.md`

## Behavior Changes

- Added `subscriptions` and `billing_events` ORM models with provider subscription and provider event idempotency constraints.
- Added an Alembic migration workflow and first billing-table revision.
- `GET /api/billing/me` now reads the latest subscription snapshot from the database.
- Active Plus grants stored report access only; active Pro grants stored report and chatbot access.
- `CANCELED` subscriptions with `cancel_at_period_end=true` keep entitlement only until `current_period_end`.
- Expired, past-due, missing, or period-ended subscriptions fall back to Free behavior.
- Added `backend/app/services/payment_service.py` as the provider-neutral boundary.
- Added a local `mock` payment provider for tests and local smoke. It is enabled only when `PAYMENT_PROVIDER=mock`.
- Checkout rejects Free and returns 503 until a provider is configured. With mock provider configured, checkout returns a URL and does not create entitlement.
- Webhooks verify HMAC signatures when the mock provider is used, persist only a payload hash and normalized summary, and process duplicate event ids idempotently.
- Cancellation schedules cancellation at period end for the current active subscription and preserves access until period end.
- Frontend checkout sends success/cancel URLs, shows provider setup errors clearly, polls billing state on success, and refreshes billing state after canceled checkout.

## Verification Performed

- Pending in this working copy until Python and frontend dependencies are installed in the local test environment:
  - `python -m pytest tests/test_subscription_service.py tests/test_subscription_api.py tests/test_report_access_api.py tests/test_chat_api.py tests/test_payment_service.py tests/test_billing_webhook_api.py`
  - `npm.cmd run build`

## Follow-Up Risks

- A production payment provider is still not selected. Replace or extend the mock provider with the chosen provider adapter before real billing.
- Production webhook secrets and plan ids must be configured through environment variables only.
- Run `alembic upgrade head` on production-like databases before enabling provider webhook traffic.
- User-facing report and chatbot flows still read stored scheduled reports only; webhook, checkout, success, and cancel flows do not trigger fresh AI report generation.
