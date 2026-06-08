# Subscription Billing Feature Notes

Date: 2026-06-01

## Current Behavior

Subscription billing is partially implemented. The app has plan metadata, an authenticated current-entitlement endpoint, backend report/chatbot gates, frontend pricing/success/cancel routes, a subscription store, plan badge, report paywall UI, database-backed subscription snapshots, a provider-neutral payment boundary with a local mock provider, and a first Toss Payments billing-auth intent flow.

Production Toss Payments billing is not complete yet. With `PAYMENT_PROVIDER=toss` and `TOSS_CLIENT_KEY`, `POST /api/billing/checkout` creates a pending server-side billing intent in `BillingEvent` and returns `/billing/toss/auth?intent_id=...`; the frontend page starts Toss SDK v2 `requestBillingAuth()`. Billing key storage, first charge approval, recurring renewal, and entitlement activation still require an approved DB schema migration. Until `PAYMENT_PROVIDER` and provider settings are configured, checkout and webhook routes return a clear provider-unavailable error. When the mock provider is configured, `GET /api/billing/me` reads the latest stored subscription row and webhook processing can activate Plus/Pro entitlements without generating reports.

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
- Payment provider adapter: `backend/app/services/payment_service.py`
- Manual grant operator script: `backend/scripts/grant_subscription.py`
- Billing migration workflow: `backend/alembic/`

## Data Flow

1. User logs in through the existing Google-only auth flow.
2. Frontend fetches `GET /api/billing/me` with the app JWT.
3. Backend returns entitlement state from the latest stored subscription snapshot, falling back to Free/NONE when no active paid state exists.
4. Free users see report upgrade prompts and no chatbot launcher.
5. Plus users can fetch stored reports but do not see the chatbot launcher.
6. Pro users can fetch stored reports and use the chatbot.
7. Plan purchase starts from `POST /api/billing/checkout`; it rejects Free, requires provider configuration, and returns a provider checkout URL without granting entitlement.
8. The payment provider completes billing authorization or subscription creation.
9. Provider webhook verifies the event signature and updates local subscription state.
10. Frontend success page refreshes `GET /api/billing/me`, but access is granted only after backend subscription state is active.

## Contracts

- Plan metadata endpoint: `GET /api/billing/plans`
- Current billing endpoint: `GET /api/billing/me`
- Checkout endpoint: `POST /api/billing/checkout` returns a `checkout_url` for Plus/Pro when a provider is configured; it does not create paid entitlement.
- Toss billing-auth intent endpoint: `GET /api/billing/checkout/{intent_id}` returns non-secret SDK parameters for the authenticated owner of a pending Toss billing intent.
- Toss billing-key finalize endpoint: `POST /api/billing/toss/billing-key` validates the owner and `customerKey`, then currently returns `501` until the billing schema migration for secure billingKey and renewal state storage is approved.
- Cancellation endpoint: `POST /api/billing/cancel` schedules cancellation at period end for the current active provider-backed subscription.
- Manual grant: `python -m scripts.grant_subscription --email <email> --tier PLUS|PRO [--days N]` creates/updates a `provider="manual"` subscription row to grant paid entitlement without payment; `--revoke` expires it. Operator-only, no auth gate.
- Webhook endpoint: `POST /api/billing/webhook` verifies signatures, stores an idempotent billing event summary, and applies normalized subscription transitions.
- Hosted database bootstrap: `python -m alembic upgrade head` now creates the current core schema plus subscription and billing tables for a fresh Supabase database.
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

- `docs/harness/toss-payments-billing-integration-plan-2026-06-03.md`
- `docs/harness/toss-payments-billing-auth-phase1-implementation-2026-06-08.md`
- `docs/harness/subscription-tier-payment-plan-2026-06-01.md`
- `docs/harness/subscription-tier-payment-implementation-2026-06-01.md`
- `docs/harness/subscription-tier-payment-verification-2026-06-01.md`
- `docs/harness/subscription-tier-payment-feedback-improvement-plan-2026-06-01.md`
- `docs/harness/subscription-tier-payment-feedback-implementation-2026-06-01.md`
- `docs/harness/subscription-tier-payment-provider-db-implementation-plan-2026-06-01.md`
- `docs/harness/subscription-tier-payment-provider-db-implementation-2026-06-01.md`
- `docs/harness/vercel-supabase-deployment-implementation-2026-06-01.md`
- `docs/harness/project-gap-remediation-plan-2026-06-02.md`
- `docs/harness/manual-subscription-grant-script-2026-06-03.md`

## Open Risks

- Production payment provider selection is now planned around Toss Payments, but automatic billing contract approval, test/live key setup, and dashboard/webhook setup remain open.
- Toss automatic billing requires app-owned recurring charge scheduling; there is no billing renewal scheduler in the current implementation.
- Monthly billing policies for VAT, cancellation, failed renewals, downgrades, and refunds need product confirmation.
- Existing report scheduler coverage is conservative, so paid users may still see pending reports for assets without stored scheduled reports.
