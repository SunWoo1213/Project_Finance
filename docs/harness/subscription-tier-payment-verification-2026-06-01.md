# Subscription Tier Payment Verification

Date: 2026-06-01

## Objective

Verify the tiered subscription payment implementation and record the remaining gaps for future harness engineering work.

This audit treats the current code as the source of truth. It does not inspect `.env` values and does not exercise live payment providers.

## Scope Reviewed

- `docs/harness/subscription-tier-payment-plan-2026-06-01.md`
- `docs/harness/subscription-tier-payment-implementation-2026-06-01.md`
- `docs/harness/features/subscription-billing.md`
- `backend/app/services/subscription_service.py`
- `backend/app/api/billing.py`
- `backend/app/api/deps.py`
- `backend/app/api/chat.py`
- `backend/app/main.py`
- `backend/app/schemas.py`
- `backend/tests/test_subscription_service.py`
- `backend/tests/test_subscription_api.py`
- `backend/tests/test_chat_api.py`
- `frontend/src/App.jsx`
- `frontend/src/pages/Pricing.jsx`
- `frontend/src/pages/AssetDetail.jsx`
- `frontend/src/pages/BillingSuccess.jsx`
- `frontend/src/pages/BillingCancel.jsx`
- `frontend/src/store/subscriptionStore.js`
- `frontend/src/components/Header.jsx`
- `frontend/src/components/ChatbotLauncher.jsx`
- `frontend/src/components/Paywall.jsx`

## Verified Behavior

- The public plan catalog exposes Free, Plus, and Pro with the intended 0 / 1,000 / 3,000 KRW monthly prices.
- `GET /api/billing/me` requires authentication and currently returns Free/NONE because there is no subscription storage yet.
- Backend entitlement helpers enforce:
  - Plus and Pro can view stored AI reports.
  - Only Pro can use the chatbot.
  - Missing, expired, or inactive subscriptions fall back to no paid entitlements.
- `GET /api/reports/{ticker}` depends on `require_report_access`, so report reads are backend-gated by Plus/Pro entitlement.
- `POST /api/chat/message` depends on `require_chatbot_access`, so direct API calls require Pro entitlement.
- `POST /api/ai/generate/{ticker}` remains disabled and returns 403 after authentication; user-facing subscription flows do not trigger fresh AI report generation.
- Frontend subscription state loads from `GET /api/billing/me`, hides the chatbot launcher unless `can_use_chatbot` is true, and avoids report fetches unless `can_view_reports` is true.
- Pricing, billing success, and billing cancel routes are present.

## Verification Commands

- Backend focused tests:
  - Initial `python -m pytest tests/test_subscription_service.py tests/test_subscription_api.py tests/test_chat_api.py` failed because the base Python interpreter could not find `pytest`.
  - Rerun with the existing user-site package path and test-safe env values passed:
    `python -m pytest tests/test_subscription_service.py tests/test_subscription_api.py tests/test_chat_api.py`
  - Result: 12 passed, 1 warning about `datetime.utcnow()` in `test_subscription_service.py`.
- Frontend lint:
  - `npm.cmd run lint`
  - Result: passed.
- Frontend production build:
  - `npm.cmd run build`
  - Result: passed. Vite still reports the existing large bundle warning.

## Findings

### High: real paid subscriptions cannot become active yet

`backend/app/services/subscription_service.py` intentionally returns `None` from `get_user_subscription`, and `backend/app/api/billing.py` returns 501 for checkout, cancel, and webhook endpoints. There are also no `Subscription` or `BillingEvent` models in `backend/app/models.py`.

Impact: every authenticated user remains Free/NONE. The current implementation is a safe entitlement scaffold, not a working payment system.

Future work:

- Add a migration-backed `Subscription` table and a webhook idempotency table.
- Implement `get_user_subscription` against the database.
- Add provider-specific checkout, cancellation, webhook signature verification, and status mapping.
- Confirm provider, VAT, refund, renewal failure, downgrade, and cancellation policies before enabling real checkout.

### High: no end-to-end Plus/Pro smoke path exists

The tests can unit-check entitlement snapshots, but the app cannot currently create a real Plus or Pro user through storage. Manual smoke testing with paid tiers is blocked until a test-safe subscription row, admin override, fixture, or provider sandbox flow exists.

Impact: report and chatbot gates pass focused tests, but real account behavior cannot be verified end to end.

Future work:

- Add test fixtures or a local-only seed path for Free, Plus, and Pro users after subscription storage exists.
- Smoke-test `GET /api/billing/me`, `GET /api/reports/{ticker}`, and `POST /api/chat/message` with all three tiers.

### Medium: report endpoint gate lacks direct API tests

`GET /api/reports/{ticker}` is wired to `require_report_access`, but the focused tests only cover subscription service behavior, billing endpoints, and chat API gating. There is no direct test proving report reads return 401 without a token, 403 for Free, and 200/404 for Plus or Pro depending on stored report availability.

Impact: future changes to `main.py` or report routing could weaken paid report access without a failing test.

Future work:

- Add report access tests with dependency overrides for unauthenticated, Free, Plus, and Pro cases.
- Keep the test isolated from real LLM generation; the route should read stored report rows only.

### Medium: checkout schema allows `FREE`

`BillingCheckoutRequest.tier` accepts the full `SubscriptionTier` enum, including `FREE`. The frontend avoids checkout for Free, but the backend should reject Free checkout requests before any future provider adapter is called.

Impact: once a provider is wired, a direct API call could ask the backend to create an invalid checkout unless the service layer adds a guard.

Future work:

- Reject `FREE` with 400 or 422 in `POST /api/billing/checkout`.
- Consider a narrower request enum for paid checkout tiers only.
- Add tests for Free checkout rejection and unauthenticated checkout rejection.

### Medium: report fetch still bypasses the shared API client

`frontend/src/pages/AssetDetail.jsx` fetches reports from hardcoded `http://localhost:8000/api/reports/...` while billing calls use `apiClient` and `VITE_API_BASE_URL`.

Impact: paid report access can break in deployed or non-local environments even when billing state loads correctly.

Future work:

- Move report, market, and community calls to `apiClient` or a shared API helper.
- Verify `VITE_API_BASE_URL` drives all backend calls consistently.

### Low: payment endpoint contracts are placeholders

The checkout, cancel, and webhook routes have no response models and currently return 501. This is acceptable for the scaffold, but future implementation should make contracts explicit.

Future work:

- Define `BillingCheckoutResponse` with a provider checkout URL or session ID.
- Define cancellation response shape and webhook processing result conventions.
- Keep webhook responses minimal and avoid leaking provider payloads.

## Follow-Up Checklist

1. Decide payment provider and product policies.
2. Choose migration strategy before adding subscription tables.
3. Add database-backed subscription and billing event models.
4. Implement provider adapter and webhook signature verification.
5. Reject invalid checkout tiers server-side.
6. Add report route entitlement tests.
7. Convert hardcoded frontend backend URLs to the shared API client.
8. Run Free, Plus, and Pro manual smoke tests after a real subscription state path exists.

## Notes For Future Harness Work

- Backend entitlements are the authority. Frontend visibility is only UX.
- Paid tiers should grant access to stored scheduled reports only. User requests, chatbot messages, and payment redirects must not generate fresh AI reports.
- Do not store card numbers or provider secrets in the repository.
- Existing working tree had unrelated `.pytest_deps` deletions and subscription documentation edits before this audit; those were not reverted.
