# Subscription Tier Payment Provider And DB Implementation Plan

Date: 2026-06-01

## Objective

Plan the remaining work needed to turn the current subscription entitlement scaffold into a real tiered payment system.

The current implementation is intentionally safe but incomplete:

- `GET /api/billing/me` always resolves authenticated users to Free/NONE because subscription storage is not implemented.
- `POST /api/billing/checkout`, `POST /api/billing/cancel`, and `POST /api/billing/webhook` are provider placeholders.
- Plus and Pro access can be tested through service snapshots, but cannot be activated through a real checkout or persisted subscription row.

This plan covers the missing database-backed subscription state, payment provider adapter, webhook processing, cancellation behavior, frontend payment feedback, tests, and release checks.

User-facing report views, chatbot messages, checkout redirects, billing success pages, and webhook processing must not trigger fresh AI report generation. Paid tiers only unlock access to stored scheduled reports. Ordinary users and the chatbot should continue to read stored reports only.

## Required Product Decisions Before Coding

Do not implement provider or schema changes until these decisions are confirmed.

1. Payment provider:
   - Candidate options: Toss Payments Billing, PortOne, Stripe, or another KRW-capable recurring billing provider.
   - Recommendation: choose the provider based on production KRW recurring payment support, webhook reliability, sandbox quality, cancellation support, and developer documentation.
2. Migration strategy:
   - Recommendation: introduce Alembic before adding billing tables.
   - Fallback only if Alembic is explicitly deferred: a documented one-off migration script with rollback notes.
3. Price and tax policy:
   - Confirm whether Plus 1,000 KRW and Pro 3,000 KRW are VAT-inclusive final amounts.
4. Subscription period policy:
   - Confirm whether canceled users keep access until `current_period_end`.
   - Recommended default: `cancel_at_period_end=true` keeps paid entitlement until the paid period ends.
5. Failed renewal policy:
   - Confirm retry and grace period behavior.
   - Recommended default: `PAST_DUE` does not grant paid entitlement unless a grace-period policy is explicitly approved.
6. Refund and downgrade policy:
   - Confirm whether downgrades take effect immediately or at period end.
   - Recommended default: schedule downgrades at period end.
7. Manual/admin override:
   - Decide whether the first production version needs an admin-only subscription override.
   - Recommended default: avoid admin override unless needed for support or QA.
8. Local smoke path:
   - Decide whether local tier states are created through provider sandbox, seed fixtures, or test-only DB rows.

## Target Behavior

| User state | Billing snapshot | Report access | Chatbot access |
| --- | --- | --- | --- |
| Not logged in | none | 401/login required | hidden/401 |
| Free | `FREE` / `NONE` | blocked with paywall | hidden/403 |
| Plus active | `PLUS` / `ACTIVE` | stored reports only | hidden/403 |
| Pro active | `PRO` / `ACTIVE` | stored reports only | available |
| Canceled but paid period active | paid tier / `CANCELED`, `cancel_at_period_end=true` | same as tier until period end | same as tier until period end |
| Expired, unpaid, or past due without grace | `FREE` or inactive status | blocked | hidden/403 |

## Phase 1: Migration Foundation

### Backend Work

- Add a formal migration workflow, preferably Alembic.
- Document migration commands in `backend/DEVELOPMENT_DIRECTION.md` and the subscription feature doc.
- Add a migration that creates subscription billing tables without storing card numbers, provider secrets, or raw provider payloads.

### Proposed Tables

`subscriptions`

- `id`
- `user_id` foreign key to `users.id`
- `tier`: `FREE`, `PLUS`, `PRO`
- `status`: `ACTIVE`, `PAST_DUE`, `CANCELED`, `EXPIRED`
- `provider`
- `provider_customer_id`
- `provider_subscription_id`
- `provider_plan_id`
- `current_period_start`
- `current_period_end`
- `cancel_at_period_end`
- `canceled_at`
- `ended_at`
- `created_at`
- `updated_at`

Recommended constraints:

- index on `user_id`
- unique provider subscription id per provider
- at most one current subscription snapshot per user unless a history-table design is chosen

`billing_events`

- `id`
- `provider`
- `provider_event_id`
- `event_type`
- `processed_status`: `received`, `processed`, `ignored`, `failed`
- `subscription_id`
- `user_id`
- `payload_hash`
- `normalized_summary`
- `error_message`
- `received_at`
- `processed_at`

Recommended constraints:

- unique `(provider, provider_event_id)` for webhook idempotency
- no raw provider payload persistence unless explicitly approved after privacy/security review

### Verification

- Migration creates tables on a clean database.
- Migration applies to an existing development database.
- ORM import and FastAPI startup still work.
- Tests prove duplicate provider event ids do not create duplicate state transitions.

## Phase 2: Database-Backed Entitlement Service

### Backend Work

- Add `Subscription` and `BillingEvent` ORM models in `backend/app/models.py`.
- Update `backend/app/services/subscription_service.py` so `get_user_subscription` reads the latest relevant DB subscription snapshot.
- Keep entitlement mapping in the service layer, not in API route handlers.
- Preserve the current backend authority rule:
  - Plus/Pro active can view stored reports.
  - Pro active can use chatbot.
  - Missing, expired, unpaid, or disallowed status falls back to Free behavior.
- Add a small service helper to normalize period-ended subscriptions to inactive access.

### Tests

- `get_user_subscription` returns `None` for no subscription.
- Active Plus can view reports but cannot use chatbot.
- Active Pro can view reports and use chatbot.
- Expired, canceled-after-period, and past-due states do not grant access unless policy says otherwise.
- Canceled-at-period-end keeps access only before `current_period_end`.
- `/api/billing/me` returns the correct snapshot for Free, Plus, Pro, canceled, expired, and past-due fixtures.

## Phase 3: Payment Provider Boundary

### Backend Work

- Create a provider adapter boundary under one of:
  - `backend/app/services/payment_service.py`
  - `backend/app/services/payments/`
- Keep provider-specific code outside route handlers.
- Define a provider-neutral interface:
  - `create_checkout_session(user, tier, success_url, cancel_url)`
  - `cancel_subscription(subscription, cancel_at_period_end=True)`
  - `verify_webhook_signature(headers, raw_body)`
  - `parse_webhook_event(headers, raw_body)`
  - `normalize_event(provider_event)`
- Document provider environment variable names only. Do not document secret values.

Suggested variable names:

- `PAYMENT_PROVIDER`
- `PAYMENT_WEBHOOK_SECRET`
- `PAYMENT_PLUS_PLAN_ID`
- `PAYMENT_PRO_PLAN_ID`
- provider-specific public client key name if the frontend needs it
- provider-specific secret key name for the backend only

### Checkout Route

- `POST /api/billing/checkout`
  - requires authentication
  - rejects `FREE` before calling provider code
  - accepts only `PLUS` or `PRO`
  - creates a provider checkout/billing session
  - returns `BillingCheckoutResponse` with `checkout_url`
  - does not create paid entitlement before webhook confirmation

### Tests

- No token returns 401.
- `FREE` returns 400.
- Provider unavailable returns a clear non-secret error.
- Plus/Pro call the provider adapter with the expected plan id.
- Provider response maps to `checkout_url`.

## Phase 4: Webhook Processing

### Backend Work

- Read the raw request body before parsing.
- Verify webhook signature before trusting any event fields.
- Store a `BillingEvent` record with idempotency protection.
- Normalize provider events to internal subscription transitions.
- Apply subscription changes transactionally with the event record.
- Return a minimal acknowledgement. Do not echo raw provider payloads.

### Event Mapping

Map provider events into internal state transitions:

- subscription created/activated -> `ACTIVE`
- payment succeeded/renewed -> `ACTIVE`, update period dates
- payment failed -> `PAST_DUE` or grace state according to policy
- subscription canceled at period end -> `CANCELED`, `cancel_at_period_end=true`
- subscription ended -> `EXPIRED`
- plan changed -> update tier according to provider plan id
- duplicate event -> acknowledge without repeating side effects
- unknown event -> record as ignored with no entitlement change

### Tests

- Invalid signature returns 400 or 401 according to provider convention.
- Valid activation event creates/updates subscription.
- Duplicate delivery is idempotent.
- Unknown event is acknowledged or ignored according to provider requirement.
- Raw provider payload is not returned in the response.
- Webhook processing does not call report generation or LLM services.

## Phase 5: Cancellation And Lifecycle

### Backend Work

- Implement `POST /api/billing/cancel`.
- Fetch the current active provider-backed subscription.
- Call provider cancellation through the adapter.
- Apply the confirmed local policy:
  - recommended: cancel at period end and preserve access through `current_period_end`
  - if immediate cancellation is approved, revoke paid access immediately
- Return a clear `BillingCancelResponse`.

### Tests

- No token returns 401.
- Free/no active subscription returns a clear 400 or 404.
- Active subscription calls provider cancellation.
- Cancellation updates local state only according to provider confirmation or webhook policy.
- Canceled subscription access matches the approved period-end policy.

## Phase 6: Frontend Payment Feedback

### Frontend Work

- Keep `Pricing.jsx` connected to `POST /api/billing/checkout`.
- Show precise button and toast states:
  - unauthenticated: route to login or prompt login
  - Free/current plan: no checkout
  - provider unavailable: explain payment setup is unavailable
  - checkout created: redirect to provider checkout URL
- Update `/billing/success`:
  - fetch or poll `GET /api/billing/me`
  - show "confirmation pending" until webhook state becomes active
  - do not assume access before backend confirms active entitlement
- Update `/billing/cancel`:
  - show that checkout was canceled/interrupted
  - keep current tier visible
  - offer retry/pricing navigation
- Ensure `subscriptionStore.js` refreshes after success/cancel and login.

### Tests And Manual Checks

- `npm.cmd run lint`
- `npm.cmd run build`
- Manual smoke:
  - unauthenticated pricing CTA
  - Free user checkout attempt
  - Plus checkout success pending -> active
  - Pro checkout success pending -> active
  - checkout cancellation
  - provider error message

## Phase 7: End-To-End Smoke Matrix

After provider sandbox and DB-backed subscriptions exist, verify:

| Flow | Expected result |
| --- | --- |
| Free user opens detail report area | paywall, no report fetch |
| Plus user opens detail report area | `GET /api/reports/{ticker}` allowed, stored report or pending state |
| Plus user calls chat endpoint directly | 403 |
| Pro user opens detail report area | stored report or pending state |
| Pro user opens chatbot | launcher visible, chat endpoint allowed |
| Missing stored report | scheduled pending state, no generation call |
| Billing success before webhook | pending confirmation |
| Billing success after webhook | active entitlement shown |
| Duplicate webhook | no duplicate state change |
| Invalid webhook signature | rejected |
| Canceled at period end | entitlement preserved until period end if approved |
| Expired period | entitlement revoked |

## Verification Commands

Backend focused tests after implementation:

```powershell
cd backend
python -m pytest tests/test_subscription_service.py tests/test_subscription_api.py tests/test_report_access_api.py tests/test_chat_api.py
```

Add new provider/migration tests as files are introduced, for example:

```powershell
cd backend
python -m pytest tests/test_payment_service.py tests/test_billing_webhook_api.py
```

Frontend checks:

```powershell
cd frontend
npm.cmd run lint
npm.cmd run build
```

Database check:

```powershell
docker compose up -d db
```

Then run the migration command selected in Phase 1.

## Release Checklist

- Provider production products/plans exist for Plus and Pro.
- Production webhook URL is registered in the provider dashboard.
- Production backend has provider env vars set.
- Migration has run before webhook traffic is enabled.
- Backend with checkout contract is deployed before frontend checkout UI.
- Sandbox smoke has passed for Free, Plus, Pro, cancel, duplicate webhook, invalid signature, and failed payment.
- Logs do not include card numbers, provider secrets, webhook secrets, raw payment payloads, or JWTs.
- User-facing paths still do not trigger report generation.

## Files Expected To Change

Backend:

- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/app/api/billing.py`
- `backend/app/api/deps.py` if dependency shape changes
- `backend/app/services/subscription_service.py`
- `backend/app/services/payment_service.py` or `backend/app/services/payments/`
- migration files after migration strategy is chosen
- backend tests under `backend/tests/`

Frontend:

- `frontend/src/pages/Pricing.jsx`
- `frontend/src/pages/BillingSuccess.jsx`
- `frontend/src/pages/BillingCancel.jsx`
- `frontend/src/store/subscriptionStore.js`
- possibly `frontend/src/utils/apiClient.js`

Documentation:

- `docs/harness/features/subscription-billing.md`
- `docs/harness/features/asset-detail-ai-community.md` if report entitlement behavior changes
- `docs/harness/features/chatbot-assistant.md` if chatbot entitlement behavior changes
- `docs/harness/features/frontend-routing-shell.md` if routes or shell behavior change
- `docs/harness/feature-index.md`
- a focused implementation record under `docs/harness/`

## Follow-Up Risks

- Payment provider APIs differ substantially; adapter tests should mock provider responses and avoid live network calls by default.
- Billing state is high impact. Avoid broad refactors while implementing migration, provider, and webhook behavior.
- Without an approved migration workflow, production billing state will be hard to operate safely.
- Without a provider sandbox account, end-to-end Plus/Pro smoke remains blocked.
- If the report scheduler does not cover a paid user's requested ticker, the user can have paid access but still see a scheduled-pending report state.
