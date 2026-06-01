# Subscription Tier Payment Implementation

Date: 2026-06-01

## Objective

Start the tiered subscription implementation from `docs/harness/subscription-tier-payment-plan-2026-06-01.md` without making the risky payment-provider or database schema changes that still need product confirmation.

## Files Changed

- Backend:
  - `backend/app/schemas.py`
  - `backend/app/api/deps.py`
  - `backend/app/api/billing.py`
  - `backend/app/api/chat.py`
  - `backend/app/main.py`
  - `backend/app/services/subscription_service.py`
  - `backend/tests/test_subscription_service.py`
  - `backend/tests/test_subscription_api.py`
  - `backend/tests/test_chat_api.py`
- Frontend:
  - `frontend/src/App.jsx`
  - `frontend/src/components/Header.jsx`
  - `frontend/src/components/PlanBadge.jsx`
  - `frontend/src/components/Paywall.jsx`
  - `frontend/src/pages/AssetDetail.jsx`
  - `frontend/src/pages/Pricing.jsx`
  - `frontend/src/pages/BillingSuccess.jsx`
  - `frontend/src/pages/BillingCancel.jsx`
  - `frontend/src/store/subscriptionStore.js`
- Documentation:
  - `docs/harness/features/subscription-billing.md`
  - `docs/harness/features/asset-detail-ai-community.md`
  - `docs/harness/features/chatbot-assistant.md`
  - `docs/harness/features/frontend-routing-shell.md`
  - `docs/harness/feature-index.md`

## Behavior Changes

- Added public `GET /api/billing/plans` returning Free, Plus, and Pro plan metadata.
- Added authenticated `GET /api/billing/me` returning current tier, status, and entitlements.
- Added placeholder `POST /api/billing/checkout`, `POST /api/billing/cancel`, and `POST /api/billing/webhook` endpoints that return HTTP 501 until a provider is selected.
- Added reusable entitlement dependencies:
  - `require_report_access`: active Plus or Pro required.
  - `require_chatbot_access`: active Pro required.
- `GET /api/reports/{ticker}` now requires report entitlement.
- `POST /api/chat/message` now requires chatbot entitlement.
- Added frontend subscription state loaded from `GET /api/billing/me` when a token is present.
- Added `/pricing`, `/billing/success`, and `/billing/cancel` routes.
- Added plan badge and report paywall UI.
- `AssetDetail.jsx` now avoids report fetches unless `can_view_reports` is true and shows an upgrade prompt for Free/no entitlement.
- `ChatbotLauncher` now renders only when `can_use_chatbot` is true.

No user-facing request path triggers AI report generation. Report viewing still reads stored scheduled reports only.

## Deliberately Deferred

- No `Subscription` or `BillingEvent` database tables were added because schema changes require confirmation.
- No payment provider adapter was implemented because the provider, VAT, cancellation, retry, refund, and admin policies remain open.
- Because subscription storage is not implemented yet, `GET /api/billing/me` currently returns Free/NONE for all authenticated users.

## Verification

- Backend: `python -m pytest tests/test_subscription_service.py tests/test_subscription_api.py tests/test_chat_api.py`
  - Result: 12 passed, 1 warning about `datetime.utcnow()` in the new service test.
- Frontend: `npm.cmd run lint`
  - Result: passed.
- Frontend: `npm.cmd run build`
  - Result: passed after rerunning outside the sandbox because Vite needed to write a temporary config file under `frontend/node_modules/.vite-temp`.

## Follow-Up Risks

- The repository has no formal migration flow, so adding subscription tables still needs an explicit migration decision.
- The checkout, cancel, and webhook endpoints are intentionally non-operational until a payment provider and webhook signature policy are selected.
- With no subscription storage, all users remain Free; temporary test data or schema work is needed before manual Plus/Pro smoke testing.
- Backend gates are authoritative, so future provider/webhook work must update database-backed entitlement lookup before enabling checkout.
