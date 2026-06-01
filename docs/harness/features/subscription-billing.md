# Subscription Billing Feature Notes

Date: 2026-06-01

## Current Behavior

Subscription billing is partially implemented. The app has plan metadata, an authenticated current-entitlement endpoint, backend report/chatbot gates, frontend pricing/success/cancel routes, a subscription store, plan badge, and report paywall UI.

There is still no payment provider integration, no monthly renewal state, and no database-backed subscription storage. Until subscription tables and webhook updates are implemented, `GET /api/billing/me` returns Free/NONE for authenticated users.

The target tier model is:

| Tier | Monthly price | AI report access | Chatbot access |
| --- | ---: | --- | --- |
| Free | 0 KRW | No | No |
| Plus | 1,000 KRW / month | Yes | No |
| Pro | 3,000 KRW / month | Yes | Yes |

## Ownership Map

- Frontend route shell: `frontend/src/App.jsx`
- Header billing entry points: `frontend/src/components/Header.jsx`
- Report gate UI: `frontend/src/pages/AssetDetail.jsx`
- Chatbot visibility: `frontend/src/components/ChatbotLauncher.jsx`
- Auth and entitlement state: `frontend/src/store/authStore.js`, `frontend/src/store/subscriptionStore.js`
- Shared API client: `frontend/src/utils/apiClient.js`
- Backend user/subscription models: `backend/app/models.py`
- API schemas: `backend/app/schemas.py`
- Auth and entitlement dependencies: `backend/app/api/deps.py`
- Billing router: `backend/app/api/billing.py`
- Chat API gate: `backend/app/api/chat.py`
- Report endpoint gate: `backend/app/main.py` unless report routes are split later
- Subscription logic: `backend/app/services/subscription_service.py`
- Future payment provider adapter: `backend/app/services/payment_service.py`

## Data Flow

1. User logs in through the existing Google-only auth flow.
2. Frontend fetches `GET /api/billing/me` with the app JWT.
3. Backend returns entitlement state. Current implementation returns Free/NONE until database-backed subscriptions are added.
4. Free users see report upgrade prompts and no chatbot launcher.
5. Plus users can fetch stored reports but do not see the chatbot launcher.
6. Pro users can fetch stored reports and use the chatbot.
7. Plan purchase starts from `POST /api/billing/checkout`; current implementation returns HTTP 501 until a provider is selected.
8. The payment provider completes billing authorization or subscription creation.
9. Provider webhook verifies the event signature and updates local subscription state.
10. Frontend success page refreshes `GET /api/billing/me`, but access is granted only after backend subscription state is active.

## Contracts

- Plan metadata endpoint: `GET /api/billing/plans`
- Current billing endpoint: `GET /api/billing/me`
- Checkout endpoint placeholder: `POST /api/billing/checkout` returns HTTP 501 until provider integration.
- Cancellation endpoint placeholder: `POST /api/billing/cancel` returns HTTP 501 until provider integration.
- Webhook endpoint placeholder: `POST /api/billing/webhook` returns HTTP 501 until provider integration.
- Report access: `GET /api/reports/{ticker}` requires active Plus or Pro entitlement.
- Chatbot access: `POST /api/chat/message` requires active Pro entitlement.
- User-facing report and chatbot requests must not trigger report generation.

## Change Rules

- Ask for confirmation before implementing DB schema changes or payment provider integration.
- Do not store card numbers or payment credentials.
- Do not expose provider secret keys or webhook secrets to the frontend.
- Webhooks must verify signatures and be idempotent.
- Backend entitlements are authoritative; frontend state is only for display.
- Paid tiers grant stored report access only. They do not broaden report scheduler coverage by themselves.

## Verification

- Backend entitlement tests around Free, Plus, Pro, expired, canceled, and duplicate webhook states.
- Backend API tests around report and chat access gates.
- Frontend build after adding pricing, paywall, and chatbot visibility gates.
- Manual smoke tests with Free, Plus, and Pro accounts.

## Change Records

- `docs/harness/subscription-tier-payment-plan-2026-06-01.md`
- `docs/harness/subscription-tier-payment-implementation-2026-06-01.md`
- `docs/harness/subscription-tier-payment-verification-2026-06-01.md`
- `docs/harness/subscription-tier-payment-feedback-improvement-plan-2026-06-01.md`
- `docs/harness/subscription-tier-payment-feedback-implementation-2026-06-01.md`
- `docs/harness/subscription-tier-payment-provider-db-implementation-plan-2026-06-01.md`

## Open Risks

- The repository does not yet have formal migration tooling.
- The payment provider is not selected yet.
- Monthly billing policies for VAT, cancellation, failed renewals, downgrades, and refunds need product confirmation.
- Existing report scheduler coverage is conservative, so paid users may still see pending reports for assets without stored scheduled reports.
