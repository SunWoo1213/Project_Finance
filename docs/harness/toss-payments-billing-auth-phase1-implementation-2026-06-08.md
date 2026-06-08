# Toss Payments Billing Auth Phase 1 Implementation

Date: 2026-06-08

## Objective

Toss Payments 자동결제 도입 계획의 1차 구현으로, 실제 과금/권한 활성화 전에 필요한 billing-auth 시작 흐름을 추가했다. 이 단계는 스키마 변경 없이 기존 `BillingEvent`를 pending billing intent 저장소로 사용하며, `billingKey` 저장과 첫 결제 승인, 정기 결제 scheduler는 아직 활성화하지 않는다.

## Files Changed

- `backend/app/core/config.py`
- `backend/app/services/payment_service.py`
- `backend/app/api/billing.py`
- `backend/app/schemas.py`
- `backend/tests/test_subscription_api.py`
- `backend/tests/test_toss_payment_service.py`
- `frontend/src/App.jsx`
- `frontend/src/pages/TossBillingAuth.jsx`
- `frontend/src/pages/BillingSuccess.jsx`
- `frontend/src/pages/BillingCancel.jsx`
- `frontend/src/utils/tossPayments.js`
- `.env.example`
- `ENVIRONMENT_VARIABLE_SETUP.md`
- `docs/harness/features/subscription-billing.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/feature-index.md`

## Behavior Changes

- `PAYMENT_PROVIDER=toss`를 인식하는 `TossPaymentsProvider`를 추가했다.
- `POST /api/billing/checkout`은 Toss provider에서 pending billing intent를 `BillingEvent`에 저장하고 `/billing/toss/auth?intent_id=...` URL을 반환한다.
- `GET /api/billing/checkout/{intent_id}`는 로그인 사용자와 intent 소유자를 확인한 뒤 Toss SDK에 필요한 non-secret 값만 반환한다.
- `frontend/src/pages/TossBillingAuth.jsx`는 Toss JS SDK v2를 로드하고 `payment.requestBillingAuth({ method: "CARD" })`를 호출한다.
- Toss success redirect가 `/billing/success`에 도착하면 frontend가 `POST /api/billing/toss/billing-key`를 호출한다.
- `POST /api/billing/toss/billing-key`는 intent 소유자와 `customerKey`를 검증하지만, 현재는 `501`을 반환한다. 이유는 `billingKey`, 결제 idempotency, 갱신 상태를 안전하게 저장할 DB migration이 아직 승인되지 않았기 때문이다.
- Toss webhook은 transmission id 또는 stable hash로 idempotent event id를 만들고 저장하되, 현재 단계에서는 uncorrelated webhook으로 구독 권한을 부여하지 않는다.
- 결제 scheduler 설정값을 추가했지만 `ENABLE_BILLING_SCHEDULER=false`가 기본이며 어떤 scheduler도 새로 시작하지 않는다.

## AI Report Generation Impact

사용자 결제 요청, Toss billing-auth 성공/실패, webhook 처리는 AI report generation을 트리거하지 않는다. 기존 원칙대로 사용자 화면과 챗봇은 저장된 scheduled report만 읽어야 한다.

## Verification Performed

아래 명령을 실행했다.

```powershell
$env:PROJECT_NAME='test'; $env:API_V1_STR='/api'; $env:DATABASE_URL='sqlite+aiosqlite:///./test.db'; python -m pytest tests/test_subscription_api.py tests/test_toss_payment_service.py
cd frontend
npm run lint
npm run build
```

Results:

- `tests/test_subscription_api.py`, `tests/test_toss_payment_service.py`: 13 passed. Python 3.13 `datetime.utcnow()` deprecation warnings만 발생했다.
- `npm run lint`: passed.
- `npm run build`: passed. 기존 Vite chunk size warning과 npm update notice가 출력됐다.

## Follow-Up Risks

- 다음 단계는 DB schema 변경이 필요하다. 최소한 `provider_billing_key`, `provider_payment_key`, `provider_order_id`, `next_billing_at`, `last_billed_at`, `billing_retry_count`, `billing_failure_reason`, `provider_metadata_json` 또는 별도 `BillingIntent`/`BillingAttempt` 테이블이 필요하다.
- `billingKey`는 민감한 결제 credential이므로 schemas, frontend 응답, 로그, 문서에 노출하면 안 된다.
- 첫 결제 승인과 정기 갱신은 Toss POST에 같은 `Idempotency-Key`를 재사용할 수 있도록 DB에 attempt 상태를 남긴 뒤 구현해야 한다.
- `ENABLE_BILLING_SCHEDULER`는 실제 돈을 청구할 수 있으므로 운영에서는 Toss test-mode E2E와 중복 청구 방지 검증 전까지 켜면 안 된다.
