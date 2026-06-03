# Toss Payments Billing Integration Plan

Date: 2026-06-03

## Objective

`Project_Finance`의 기존 구독/권한 구조에 Toss Payments 자동결제(빌링)를 production payment provider로 연결하기 위한 상세 구현 계획이다. 이 문서는 하네스 엔지니어링 인계용 계획서이며, 현재 코드 변경 없이 향후 구현자가 읽고 바로 작업 범위, 위험, 검증 경로를 판단할 수 있도록 작성한다.

현재 결제 기능은 `Free`, `Plus`, `Pro` 요금제, DB-backed subscription snapshot, provider-neutral payment boundary, mock provider, report/chatbot entitlement gate를 이미 가진다. 따라서 Toss Payments 도입은 결제 기능을 처음부터 새로 만드는 작업이 아니라, 기존 `payment_service.py` provider boundary에 Toss adapter와 자동결제 lifecycle을 추가하는 작업이다.

## External References Checked

- Toss Payments 자동결제(빌링) 이해하기: `https://docs.tosspayments.com/guides/v2/billing`
- Toss Payments 자동결제 결제창 연동하기: `https://docs.tosspayments.com/guides/v2/billing/integration`
- Toss Payments 자동결제 API 연동하기: `https://docs.tosspayments.com/guides/v2/billing/integration-api`
- Toss Payments Core API reference: `https://docs.tosspayments.com/reference`
- Toss Payments webhook events: `https://docs.tosspayments.com/reference/using-api/webhook-events`
- Toss Payments webhook guide: `https://docs.tosspayments.com/guides/v2/webhook`

Important Toss constraints from the checked docs:

- Monthly subscription products should use Toss Payments automatic billing, not one-off payment, if recurring billing is required.
- Automatic billing requires additional Toss Payments contract/risk review before live use.
- The browser opens Toss billing auth through SDK `requestBillingAuth()`.
- Billing auth success redirects with `authKey` and `customerKey`.
- The backend exchanges `authKey` and `customerKey` for a `billingKey` through `POST /v1/billing/authorizations/issue`.
- The backend charges with `POST /v1/billing/{billingKey}` using `customerKey`, `amount`, `orderId`, and `orderName`.
- Toss Payments does not provide a subscription scheduler for this use case. The application must schedule future recurring charge attempts.
- A canceled subscription should generally stop future billing attempts. The billing key can also be deleted when the product policy requires immediate payment-method removal.
- Toss webhook events include transmission headers and `PAYMENT_STATUS_CHANGED`, but the current Toss webhook reference states that automatic billing completion does not send a payment status webhook because request and approval happen together. Automatic billing completion must therefore be applied from the backend API response for `POST /v1/billing/{billingKey}`.
- The Toss automatic billing webhook currently relevant to billing-key lifecycle is `BILLING_DELETED`; payment status webhooks should be treated as reconciliation inputs only when they can be strictly correlated to known orders/payments.

## Current Project Fit

### Existing Strengths

- `backend/app/api/billing.py` already exposes:
  - `GET /api/billing/plans`
  - `GET /api/billing/me`
  - `POST /api/billing/checkout`
  - `POST /api/billing/cancel`
  - `POST /api/billing/webhook`
- `backend/app/services/payment_service.py` already defines a provider interface:
  - `create_checkout_session`
  - `cancel_subscription`
  - `verify_webhook_signature`
  - `parse_webhook_event`
  - `normalize_event`
- `backend/app/models.py` already has:
  - `Subscription`
  - `BillingEvent`
- `backend/app/services/subscription_service.py` already converts subscription state into product entitlements.
- `backend/app/api/deps.py` already gates:
  - stored AI report access for Plus/Pro
  - chatbot access for Pro
- `frontend/src/pages/Pricing.jsx` already starts checkout from selected tier.
- `frontend/src/pages/BillingSuccess.jsx` already polls server state instead of trusting a client-side redirect.
- `frontend/src/pages/BillingCancel.jsx` already preserves existing entitlement state after failed/canceled payment.

### Main Gaps

- The current provider implementation only supports `mock`; `PAYMENT_PROVIDER=toss` is not implemented.
- Current `Subscription` fields are provider-neutral but do not explicitly track Toss billing lifecycle fields such as `billingKey`, `customerKey`, current/next billing order id, next billing date, and retry state.
- Current `POST /api/billing/checkout` returns a generic `checkout_url`, while Toss automatic billing needs an SDK page that calls `requestBillingAuth()`.
- There is no backend endpoint to exchange Toss `authKey` for `billingKey`.
- There is no backend endpoint/service to approve the first Toss automatic billing charge after billing key issuance.
- There is no recurring billing scheduler.
- Current webhook processing assumes a generic provider signature model; Toss payment webhooks have event-specific header semantics and should be treated differently from the mock HMAC model.

## Recommended Product Decision

Use Toss Payments automatic billing for Plus/Pro monthly subscriptions.

Do not use one-off payment as the default production design unless the product explicitly changes from recurring subscription to manual monthly purchase. The current product model says:

| Tier | Price | Entitlement |
| --- | ---: | --- |
| Free | 0 KRW / month | no paid AI report or chatbot entitlement |
| Plus | 1,000 KRW / month | stored scheduled AI report access |
| Pro | 3,000 KRW / month | stored scheduled AI report access and chatbot access |

User-facing requests and chatbot requests must continue to read stored scheduled reports only. Toss integration must not trigger AI report generation and must not broaden report scheduler coverage by itself.

## Target Architecture

```text
Browser
  -> React/Vite pricing page
  -> backend POST /api/billing/checkout
  -> React Toss billing auth page
  -> Toss SDK requestBillingAuth()
  -> React billing auth success route with authKey/customerKey
  -> backend POST /api/billing/toss/billing-key
  -> Toss API POST /v1/billing/authorizations/issue
  -> backend POST /v1/billing/{billingKey} for first charge
  -> PostgreSQL Subscription + BillingEvent update
  -> frontend GET /api/billing/me refresh

Recurring renewal:
APScheduler / explicit job
  -> due active subscriptions
  -> Toss API POST /v1/billing/{billingKey}
  -> Subscription period update or PAST_DUE transition
```

## Proposed Backend Changes

### 1. Configuration

Files:

- `backend/app/core/config.py`
- `.env_example`
- `ENVIRONMENT_VARIABLE_SETUP.md`
- `docs/harness/features/deployment-runtime.md`

Add Toss-specific variable names. Secret values must remain environment-only and must not be exposed in docs or frontend source.

Suggested backend env names:

- `PAYMENT_PROVIDER=toss`
- `TOSS_API_BASE_URL=https://api.tosspayments.com`
- `TOSS_CLIENT_KEY`
- `TOSS_SECRET_KEY`
- `TOSS_PLUS_AMOUNT_KRW=1000`
- `TOSS_PRO_AMOUNT_KRW=3000`
- `TOSS_BILLING_SUCCESS_URL`
- `TOSS_BILLING_FAIL_URL`
- `ENABLE_BILLING_SCHEDULER=false`
- `BILLING_RENEWAL_INTERVAL_MINUTES=60`
- `BILLING_RETRY_LIMIT=3`
- `BILLING_RETRY_BACKOFF_HOURS=24`

Notes:

- `TOSS_CLIENT_KEY` may be sent to the browser because Toss SDK uses it.
- `TOSS_SECRET_KEY` must never be sent to the browser.
- Existing `PAYMENT_PLUS_PLAN_ID` and `PAYMENT_PRO_PLAN_ID` can remain for provider-neutral compatibility, but Toss automatic billing does not require Stripe-style price IDs. Future implementation can either leave them unused for `toss` or map them to internal Toss plan codes such as `plus_monthly` and `pro_monthly`.

### 2. Database Model

Files:

- `backend/app/models.py`
- `backend/alembic/versions/`
- possibly `backend/app/schemas.py`

This is a DB schema change. Ask for confirmation before implementing.

Current `Subscription` has:

- `provider`
- `provider_customer_id`
- `provider_subscription_id`
- `provider_plan_id`
- `current_period_start`
- `current_period_end`
- `cancel_at_period_end`
- `canceled_at`
- `ended_at`

Recommended additions:

| Column | Purpose |
| --- | --- |
| `provider_billing_key` | Toss `billingKey`; backend-only sensitive billing credential |
| `provider_payment_key` | latest Toss `paymentKey` returned by charge approval, when available |
| `provider_order_id` | latest app-generated Toss `orderId` |
| `next_billing_at` | scheduler due date for next monthly charge |
| `last_billed_at` | last successful automatic billing timestamp |
| `billing_retry_count` | current renewal retry count |
| `billing_failure_reason` | sanitized latest failure code/message |
| `metadata` or `provider_metadata` | masked card info and provider response summary, no raw card number |

Mapping guidance:

- Store Toss `customerKey` in `provider_customer_id`.
- Store Toss `billingKey` in `provider_billing_key`, not in user-facing schemas.
- Use `provider_subscription_id` as an internal stable subscription identifier if Toss does not provide a subscription id. For example: `toss-sub-{subscription.id}` after initial flush, or a generated UUID before persistence.
- Use `provider_plan_id` as internal plan code: `plus_monthly` or `pro_monthly`.
- Never store card number, CVC, card password, identity number, or raw payment credentials.
- Masked card metadata from Toss response can be stored only if it is useful for user-facing payment-method display.
- Avoid naming a SQLAlchemy declarative attribute `metadata`; it collides conceptually with SQLAlchemy's model metadata. Prefer `provider_metadata_json` or `billing_metadata_json`.
- Treat `provider_billing_key` as a sensitive payment credential. Prefer field-level encryption or a secret-management/KMS-backed encryption helper before production; at minimum keep it out of logs, schemas, frontend responses, analytics, and error traces.
- Add a unique constraint or idempotency guard for provider/order identifiers used for Toss charges, for example `(provider, provider_order_id)` when stored on an attempt table.

Optional separate table:

- A separate `BillingAttempt` table would be cleaner for recurring charge history, retries, and reconciliation.
- If implementation time is limited, use `BillingEvent` first and add `BillingAttempt` later.
- If adding `BillingAttempt`, include `subscription_id`, `provider`, `order_id`, `payment_key`, `amount_krw`, `status`, `attempted_at`, `processed_at`, `failure_code`, `failure_message`, and `raw_payload_hash`.

### 3. Payment Provider Adapter

Files:

- `backend/app/services/payment_service.py`
- optional new file: `backend/app/services/toss_payment_service.py`

Recommended approach:

- Keep `PaymentProvider` as the interface.
- Add `TossPaymentsProvider`.
- Avoid stuffing large Toss-specific logic into the same file if `payment_service.py` becomes hard to read. A new `toss_payment_service.py` can implement the adapter and be imported by `get_payment_provider()`.

Required provider capabilities:

- Create a billing auth session/intention for Toss SDK.
- Exchange `authKey` and `customerKey` for `billingKey`.
- Approve first automatic billing charge.
- Approve recurring automatic billing charge.
- Cancel future renewal in local DB.
- Optionally delete Toss billing key for immediate payment-method removal.
- Parse Toss webhook payloads and map them to local events.

HTTP client:

- Use an async HTTP client such as `httpx.AsyncClient` if already available in dependencies.
- Toss Core API uses Basic authorization with `base64("{TOSS_SECRET_KEY}:")`.
- Set timeouts of at least 60 seconds for automatic billing approval because Toss docs state automatic billing approval can take up to 60 seconds.
- Send an `Idempotency-Key` header for every Toss POST that can create or approve a payment, especially first charge and recurring charge approval. Store the idempotency key with the billing intent/attempt so retrying the same operation cannot create a duplicate charge.
- On timeout or ambiguous network failure after `POST /v1/billing/{billingKey}`, do not immediately create a new order and charge again. First reconcile by idempotency response, `orderId` lookup, or `paymentKey` lookup when available.
- Sanitize Toss error responses before storing them in `billing_failure_reason` or returning them to the frontend. Keep provider error code and a user-safe message; avoid raw request headers, auth values, or full provider payload dumps.

### 4. API Contracts

Existing:

- `POST /api/billing/checkout`

Recommended Toss-compatible options:

Option A, preserve existing contract:

- `POST /api/billing/checkout` returns an internal frontend URL such as `/billing/toss/auth?intent_id=...`.
- The auth page fetches the billing intent and starts Toss SDK.
- This preserves `Pricing.jsx` mental model and keeps provider-specific details mostly behind the backend.

Option B, extend response shape:

- `POST /api/billing/checkout` returns:
  - `provider`
  - `mode`
  - `client_key`
  - `customer_key`
  - `order_id`
  - `amount`
  - `order_name`
  - `success_url`
  - `fail_url`
- `Pricing.jsx` or a dedicated page starts Toss SDK directly.

Recommended: Option A for smallest frontend disruption and cleaner provider boundary.

New or adjusted endpoints:

- `POST /api/billing/checkout`
  - Creates a server-side billing intent.
  - Validates tier and amount.
  - Returns an auth URL or structured Toss auth data.
- `GET /api/billing/checkout/{intent_id}`
  - Returns non-secret SDK parameters for a pending billing auth intent.
  - Requires authenticated user and ownership check.
- `POST /api/billing/toss/billing-key`
  - Receives `intent_id`, `authKey`, `customerKey`.
  - Validates intent owner, tier, amount, and customer key.
  - Calls Toss billing key issue API.
  - Stores billing key securely.
  - Calls first automatic billing approval.
  - Activates subscription only after successful backend approval.
- `POST /api/billing/cancel`
  - Marks local subscription `cancel_at_period_end=true`.
  - Prevents future recurring charge attempts.
  - Optionally deletes billing key only for immediate cancellation policy.
- `POST /api/billing/webhook`
  - Stores Toss event idempotently.
  - Updates local state only when event can be correlated to an existing order/payment/subscription.
  - Does not grant entitlement from uncorrelated webhook data.

### 5. Billing Intent Persistence

The implementation needs a place to persist pending checkout/auth state. Do not trust tier or amount only from frontend query parameters.

Options:

- Add `BillingIntent` table.
- Use `BillingEvent` with `event_type="billing_intent.created"` for early MVP.
- Use a short-lived signed token if the system wants to avoid a table, but DB storage is preferable for auditability.

Recommended table fields:

- `id`
- `user_id`
- `provider`
- `tier`
- `amount_krw`
- `order_id`
- `order_name`
- `customer_key`
- `status`: `PENDING`, `AUTHORIZED`, `PAID`, `FAILED`, `EXPIRED`, `CANCELED`
- `success_url`
- `fail_url`
- `created_at`
- `expires_at`
- `processed_at`
- `failure_code`
- `failure_message`
- `idempotency_key`
- `provider_payment_key`
- `attempt_type`: `FIRST_CHARGE`, `RENEWAL`, `RETRY`, `MANUAL_RECONCILIATION`

Why it matters:

- Toss docs emphasize verifying amount/order data before approval.
- The backend must reject mismatched `customerKey`, tier, or amount.
- A pending intent gives future agents a reliable audit trail for failed/canceled auth.
- A persisted idempotency key lets the backend safely retry ambiguous first-charge/finalize calls without double charging.

### 6. Subscription Renewal Service

Files:

- `backend/app/main.py`
- `backend/app/services/subscription_service.py`
- new `backend/app/services/billing_scheduler.py` or `backend/app/services/billing_renewal_service.py`

Add a billing scheduler only behind explicit env flags.

Suggested behavior:

1. Scheduler wakes every `BILLING_RENEWAL_INTERVAL_MINUTES`.
2. Query subscriptions where:
   - `provider = "toss"`
   - `status = "ACTIVE"` or retryable `PAST_DUE`
   - `cancel_at_period_end = false`
   - `next_billing_at <= now`
   - `provider_billing_key is not null`
3. Generate a unique `orderId` for the renewal attempt.
4. Acquire a DB transaction/row lock or equivalent concurrency guard before charging so two scheduler instances cannot process the same subscription at the same time.
5. Call Toss `POST /v1/billing/{billingKey}` with:
   - `customerKey`
   - `amount`
   - `orderId`
   - `orderName`
   - user email/name when available
   - `taxFreeAmount=0` unless tax policy says otherwise
6. On success:
   - update `current_period_start`
   - update `current_period_end`
   - update `next_billing_at`
   - reset retry count
   - set `status=ACTIVE`
   - record `BillingEvent`
7. On failure:
   - increment retry count
   - set `status=PAST_DUE` when appropriate
   - store sanitized failure reason
   - schedule retry or expire after configured retry limit.

Important:

- This scheduler charges real money in production. Keep it disabled by default.
- Do not co-mingle this with AI report scheduler flags. Billing and AI report generation must stay separate.
- Billing renewal must not trigger report generation.
- If the backend can run more than one process or instance, process-local APScheduler alone is not sufficient for safe production charging unless the DB locking/idempotency design prevents duplicate renewal attempts.
- Store and compute billing period timestamps consistently. Prefer UTC in DB and convert only for display, while keeping Toss response timestamps parseable with their original offsets.

## Proposed Frontend Changes

Files:

- `frontend/src/App.jsx`
- `frontend/src/pages/Pricing.jsx`
- `frontend/src/pages/BillingSuccess.jsx`
- `frontend/src/pages/BillingCancel.jsx`
- new `frontend/src/pages/TossBillingAuth.jsx`
- optional new `frontend/src/utils/tossPayments.js`

Recommended flow:

1. User clicks Plus/Pro in `Pricing.jsx`.
2. `Pricing.jsx` calls `POST /api/billing/checkout`.
3. Backend returns `/billing/toss/auth?intent_id=...`.
4. React Router renders `TossBillingAuth`.
5. `TossBillingAuth` fetches intent data from backend.
6. `TossBillingAuth` initializes Toss SDK with `clientKey`.
7. It initializes a payment instance with the server-provided `customerKey`, then calls `requestBillingAuth()` with `method`, `successUrl`, `failUrl`, and optional safe customer display fields.
8. Toss redirects to success route with `authKey` and `customerKey`.
9. Success page calls backend finalize endpoint.
10. Success page refreshes `GET /api/billing/me`.

Frontend rules:

- Never include `TOSS_SECRET_KEY` in Vite env.
- Treat `TOSS_CLIENT_KEY` as public.
- Do not activate entitlement from frontend redirect state.
- Show pending state while backend finalizes.
- Show Toss fail code/message in a user-safe way, but do not leak raw backend secrets or internal stack traces.
- Keep `BillingSuccess.jsx` polling behavior because webhook/API response timing can still lag.

Important SDK correction:

- In Toss Payments JS SDK v2, `tossPayments.payment({ customerKey })` owns the `customerKey`.
- `payment.requestBillingAuth()` is for registering the billing method and currently requires `method`, `successUrl`, and `failUrl`; do not rely on it to carry billing charge `orderId` or `amount`.
- Keep `orderId`, `orderName`, `amount`, tier, and intended first-charge metadata in the backend billing intent, then use those values only when the backend calls `POST /v1/billing/{billingKey}`.
- If the product only wants card subscriptions, pass `method: "CARD"` and document that account-based automatic billing is intentionally out of scope.
- The SDK `payment({ customerKey })` reference has a stricter maximum than the Core API billing endpoint in current docs. Generate an unpredictable `customerKey` that is safe for both surfaces, preferably 50 characters or fewer and including one allowed special character such as `_`.

## Webhook Strategy

Current generic webhook design is useful but should be adapted carefully for Toss.

Recommended handling:

- Use Toss `tosspayments-webhook-transmission-id` as provider event id when present.
- Fall back to a stable hash of `eventType`, `createdAt`, and relevant `data` identifiers only if no transmission id is available.
- Use `eventType` as event type.
- Correlate payment events by `data.orderId`, `data.paymentKey`, or known subscription metadata.
- For `PAYMENT_STATUS_CHANGED`, map Toss payment status to local event summaries, but do not grant new entitlement unless it matches a known billing intent or subscription charge attempt.
- Store `payload_hash` and normalized summary in `BillingEvent`.
- Do not expect automatic billing completion to arrive through `PAYMENT_STATUS_CHANGED` under the current Toss webhook reference; backend API approval response remains authoritative for charges initiated by this app.
- Handle `BILLING_DELETED` as a billing-key lifecycle signal. It should mark the stored billing key unusable or schedule user/payment-method remediation, but it must not by itself create or extend paid entitlement.

Signature caution:

- Toss webhook signature docs are event-specific. As of the checked docs, `tosspayments-webhook-signature` is documented for some webhook categories, while payment status webhooks mainly provide transmission metadata.
- Future implementation must re-check Toss production dashboard webhook verification guidance before enforcing a signature rule for `PAYMENT_STATUS_CHANGED`.
- If Toss does not provide a payment webhook signature for this event, rely on HTTPS endpoint secrecy, event idempotency, provider API reconciliation by `paymentKey`/`orderId`, and strict correlation to existing billing attempts.
- The existing `PaymentProvider.verify_webhook_signature()` interface may need to become provider/event aware for Toss. A Toss provider should not reject payment or billing lifecycle webhooks solely because `tosspayments-webhook-signature` is absent on events where Toss does not send that header.

## Cancellation and Plan Change Policy

### Cancellation

Recommended default:

- `POST /api/billing/cancel` sets `cancel_at_period_end=true`.
- User keeps entitlement through `current_period_end`.
- Renewal scheduler skips canceled-at-period-end subscriptions.
- At period end, subscription becomes `EXPIRED`.

Optional immediate cancellation:

- Delete Toss billing key with `DELETE /v1/billing/{billingKey}`.
- Mark subscription `CANCELED` or `EXPIRED` depending on product policy.
- This should be separate from the default period-end cancellation behavior.

### Upgrade and Downgrade

Open product decision:

- Plus -> Pro can be immediate full Pro charge, prorated manual policy, or next-period change.
- Pro -> Plus can be next-period downgrade to avoid refund complexity.

Recommended MVP:

- Do not support plan switching in the first Toss integration.
- Allow cancel then resubscribe, or implement new subscription creation that expires the old one only after successful new first charge.

## Environment and Deployment Notes

Local/test:

- Use Toss test client/secret keys only.
- Keep `ENABLE_BILLING_SCHEDULER=false`.
- Test billing key issuance and first charge in Toss test mode.

Production:

- Confirm Toss automatic billing contract is active.
- Set live `TOSS_CLIENT_KEY` and `TOSS_SECRET_KEY` through hosted runtime secret management.
- Set `PAYMENT_PROVIDER=toss`.
- Enable billing scheduler only after successful dry-run verification.
- Register webhook endpoint:
  - `https://<backend-host>/api/billing/webhook`
- Verify CORS allows frontend origin.
- Verify frontend success/fail URLs are registered and reachable.

Vercel/Supabase note:

- If backend remains FastAPI outside Vercel, the billing scheduler should run in the backend host.
- If backend is split into serverless functions later, recurring billing needs a durable cron/job strategy rather than relying on process-local APScheduler.

## Test Plan

Backend unit tests:

- `TossPaymentsProvider` builds correct Basic auth header without exposing secret.
- `TossPaymentsProvider` sends `Idempotency-Key` for charge-creating POST requests and reuses the stored key on retry of the same attempt.
- Plan tier maps to expected amount.
- Invalid tier or Free tier cannot create Toss billing auth.
- Billing intent ownership check rejects another user.
- `authKey` finalize rejects mismatched `customerKey`.
- Generated Toss `customerKey` is unpredictable, contains an allowed special character, and satisfies the stricter JS SDK length boundary.
- Billing auth finalize ignores frontend-provided tier/amount/order values and uses the persisted billing intent.
- First charge activates Plus/Pro only after Toss approval response.
- Failed first charge does not grant entitlement.
- Timeout or ambiguous response from first charge enters reconciliation/pending state and does not create a second charge with a new order id.
- Renewal success extends `current_period_end`.
- Renewal failure sets `PAST_DUE` or retry state.
- `cancel_at_period_end` subscriptions are skipped by renewal job.
- Concurrent renewal worker simulation cannot create two provider charge attempts for the same subscription period.
- Duplicate webhook transmission id is idempotent.
- Uncorrelated webhook does not grant entitlement.
- `BILLING_DELETED` marks/remediates the billing key lifecycle without extending entitlement.
- Toss payment/status webhooks without a signature header are handled according to the event type and strict correlation rules, not rejected by a mock-provider HMAC assumption.

Backend integration/API tests:

- `POST /api/billing/checkout` returns Toss auth route/data when `PAYMENT_PROVIDER=toss`.
- `GET /api/billing/me` reflects Active Plus/Pro after finalized charge.
- `POST /api/billing/cancel` blocks renewal and preserves entitlement until period end.
- Report endpoint remains gated by stored subscription entitlement.
- Chat endpoint remains Pro-only.

Frontend tests/smoke checks:

- `/pricing` starts checkout for authenticated users.
- Unauthenticated users receive login-required feedback.
- Toss auth page handles loading, SDK failure, auth redirect, and fail redirect.
- Success page finalizes auth and refreshes subscription state.
- Cancel/fail page shows safe error state and does not alter entitlement.

Manual Toss test mode checks:

- Billing auth success with test card.
- Billing auth cancellation.
- First automatic billing approval.
- Duplicate retry of the same first-charge/finalize operation with the same idempotency key.
- Retry/failure scenario if Toss sandbox supports failure cards.
- `BILLING_DELETED` delivery if the dashboard/test flow supports it.
- Webhook delivery and duplicate delivery handling.

Commands after implementation:

- Backend: `pytest` or targeted billing tests under `backend/tests/`.
- Frontend: `npm run lint` and `npm run build` from `frontend/`.
- Optional local smoke: run backend with billing scheduler disabled, run frontend, complete Toss test billing auth.

## Implementation Phases

### Phase 0: Product and Contract Confirmation

- Confirm Toss automatic billing contract path.
- Confirm Plus/Pro prices and VAT/tax policy.
- Confirm cancellation policy.
- Confirm failed-payment grace period.
- Confirm whether plan switching is in scope.

Exit criteria:

- Product decisions are documented.
- Toss test keys are available in local/hosted secret storage.

### Phase 1: Provider and Intent Foundation

- Add Toss env settings.
- Add billing intent persistence.
- Add Toss provider adapter.
- Keep scheduler disabled.
- Add backend tests with mocked Toss API responses.

Exit criteria:

- Backend can create a Toss billing auth intent without granting entitlement.
- No real external API call is required in tests.

### Phase 2: Frontend Toss Billing Auth

- Add Toss auth route/page.
- Update pricing checkout flow.
- Add finalize call on success.
- Preserve existing success polling behavior.

Exit criteria:

- Toss test billing auth can be started from `/pricing`.
- Failed/canceled auth does not modify entitlement.

### Phase 3: First Charge and Entitlement Activation

- Exchange `authKey` for `billingKey`.
- Approve first automatic billing charge.
- Store subscription and billing event.
- Activate Plus/Pro only on successful backend charge approval.

Exit criteria:

- `GET /api/billing/me` returns active Plus/Pro after successful first charge.
- Report/chat gates behave according to tier.

### Phase 4: Recurring Billing Scheduler

- Add renewal service and scheduler flag.
- Add retry and past-due behavior.
- Add cancellation skip behavior.
- Add tests around due subscriptions.

Exit criteria:

- Scheduler can be tested with mocked Toss API.
- Scheduler remains disabled unless `ENABLE_BILLING_SCHEDULER=true`.

### Phase 5: Webhook and Reconciliation

- Add Toss webhook normalization.
- Store idempotent event records.
- Correlate payment events to known intents/attempts.
- Add reconciliation helper to fetch payment by `paymentKey` or `orderId` when needed.

Exit criteria:

- Duplicate webhook is harmless.
- Unknown webhook is recorded but does not grant access.

### Phase 6: Production Readiness

- Update deployment docs and env guide.
- Verify hosted callback URLs.
- Run full test suite/build.
- Perform Toss test-mode end-to-end checkout.
- Enable live settings only after contract and test-mode success.

Exit criteria:

- Production secrets are configured outside source control.
- Billing scheduler activation is an explicit deployment step.

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Toss automatic billing contract not approved | Cannot launch recurring subscription | Keep mock provider and document contract dependency |
| Billing scheduler charges real money | Financial/customer risk | Default `ENABLE_BILLING_SCHEDULER=false`, add dry-run/mocked tests, enable only after production review |
| Frontend tampers with amount/tier | Undercharge or incorrect entitlement | Store billing intent server-side and validate before billing key issue/charge |
| Webhook mismatch or missing webhook | Stale entitlement | Use backend Toss API response as primary source for app-initiated charges; use webhook for reconciliation |
| Billing key exposure | Unauthorized charges | Store only backend-side; never expose in schemas, logs, docs, or frontend |
| Duplicate renewals | Double charge | Unique `orderId`, due-row locking or transaction guard, `BillingEvent`/`BillingAttempt` idempotency |
| Retry after timeout creates a second charge | Double charge and customer support incident | Persist `Idempotency-Key`, reuse it on retry, and reconcile by `orderId`/`paymentKey` before issuing a new charge |
| `requestBillingAuth()` treated like payment request | Broken billing auth flow or mismatched amount assumptions | Keep amount/order data server-side and use SDK billing auth only for method registration |
| Toss webhook signature semantics copied from mock provider | Valid Toss payment/billing lifecycle events rejected or invalid events trusted | Make verification provider/event aware and reconcile unsigned payment events through Toss query APIs plus strict local correlation |
| Multiple backend instances run scheduler | Duplicate renewal processing | Use DB row locking, unique attempt/order constraints, and idempotency keys; avoid relying only on process-local scheduler state |
| SQLAlchemy `metadata` attribute collision | Migration/runtime model errors | Use `provider_metadata_json` or similar explicit column name |
| Failed renewal policy unclear | User support issue | Define grace period and cancellation/expiration behavior before live scheduler |
| Serverless runtime lacks persistent scheduler | Renewals do not run | Use hosted backend scheduler or external cron/durable workflow |

## Files Expected To Change During Implementation

Backend:

- `backend/app/core/config.py`
- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/app/api/billing.py`
- `backend/app/services/payment_service.py`
- `backend/app/services/toss_payment_service.py` if split out
- `backend/app/services/subscription_service.py`
- `backend/app/services/billing_renewal_service.py`
- `backend/app/main.py`
- `backend/alembic/versions/*.py`
- `backend/tests/test_billing*.py` or related targeted test files

Frontend:

- `frontend/src/App.jsx`
- `frontend/src/pages/Pricing.jsx`
- `frontend/src/pages/BillingSuccess.jsx`
- `frontend/src/pages/BillingCancel.jsx`
- `frontend/src/pages/TossBillingAuth.jsx`
- `frontend/src/store/subscriptionStore.js` if additional state is needed
- `frontend/src/utils/apiClient.js` if endpoint helpers are added
- `frontend/package.json` only if an npm Toss SDK package is used instead of script loading

Docs:

- `.env_example`
- `ENVIRONMENT_VARIABLE_SETUP.md`
- `docs/harness/features/subscription-billing.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/feature-index.md`
- future implementation record under `docs/harness/`

## Verification Performed For This Plan

- Read current repository guidance and feature documentation workflow.
- Inspected current subscription billing feature document.
- Inspected current billing feature index entry.
- Inspected current billing router, payment provider boundary, subscription service, ORM models, and billing schemas to compare the plan with actual implementation.
- Checked existing working tree with `git status --short`.
- Re-checked official Toss Payments documentation pages listed above on 2026-06-03.
- Added review corrections for Toss JS SDK billing-auth parameters, automatic billing webhook expectations, `BILLING_DELETED`, idempotency keys, billing-key sensitivity, SQLAlchemy metadata naming, retry/reconciliation, and multi-instance scheduler concurrency.

No code, tests, build, or runtime verification was performed because this task is documentation-only.

## Commands Not Run

- `pytest`: not run because no backend code was changed.
- `npm run lint`: not run because no frontend code was changed.
- `npm run build`: not run because no frontend code was changed.
- Local backend/frontend servers: not started because this is a planning document.

## Follow-Up For Future Harness Agents

1. Before implementation, ask the user to confirm DB schema changes and Toss automatic billing scope.
2. Re-check Toss Payments docs before coding because payment APIs and webhook verification rules can change.
3. Implement with tests using mocked Toss API responses first.
4. Do not inspect or print `.env`; document env variable names only.
5. Keep AI report generation isolated. Billing entitlement changes must never trigger fresh user-facing AI report generation.
6. After implementation, add a separate implementation record under `docs/harness/` and link it from `docs/harness/features/subscription-billing.md` and `docs/harness/feature-index.md`.
