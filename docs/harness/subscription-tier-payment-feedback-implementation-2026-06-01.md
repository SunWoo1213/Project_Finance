# Subscription Tier Payment Feedback Implementation

Date: 2026-06-01

## Objective

Implement the safe phase-1 items from `docs/harness/subscription-tier-payment-feedback-improvement-plan-2026-06-01.md` without adding payment-provider integration or database schema changes.

## Files Changed

- `backend/app/api/billing.py`
- `backend/app/schemas.py`
- `backend/tests/test_subscription_api.py`
- `backend/tests/test_report_access_api.py`
- `frontend/src/pages/AssetDetail.jsx`
- `docs/harness/features/subscription-billing.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/feature-index.md`

## Behavior Changes

- `POST /api/billing/checkout` now rejects `FREE` with HTTP 400 before reaching the provider placeholder.
- Plus and Pro checkout requests still return HTTP 501 until a payment provider is selected.
- Billing checkout, cancellation, and webhook placeholder endpoints now have explicit response schemas.
- Report access tests now cover unauthenticated, Free, Plus, and Pro route behavior without LLM calls or report generation.
- `AssetDetail.jsx` now uses the shared `apiClient` and `authHeader` helper for market, report, and community API calls instead of hardcoded backend URLs.

No user-facing request path triggers AI report generation. Report viewing still reads stored scheduled reports only.

## Verification

- Backend: `python -m pytest tests/test_subscription_service.py tests/test_subscription_api.py tests/test_report_access_api.py tests/test_chat_api.py`
  - Result: 19 passed, 2 warnings.
- Frontend: `npm.cmd run lint`
  - Result: passed.
- Frontend: `npm.cmd run build`
  - Result: passed with the existing Vite large chunk warning.

## Follow-Up Risks

- Checkout, cancellation, and webhook processing remain intentionally non-operational until provider, migration, VAT, cancellation, retry, and webhook signature policies are confirmed.
- With no database-backed subscription storage, `/api/billing/me` still returns Free/NONE for authenticated users.
