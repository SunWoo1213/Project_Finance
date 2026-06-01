# 티어별 결제 피드백 개선 계획서

작성일: 2026-06-01

## 목적

`docs/harness/subscription-tier-payment-verification-2026-06-01.md`의 검증 결과를 바탕으로, 현재 구독 권한 스캐폴드를 실제로 검증 가능한 티어 기반 결제 흐름으로 발전시킨다.

구현 중 반드시 유지해야 할 규칙은 다음과 같다.

- 백엔드 권한 검사가 최종 권한 기준이다.
- 프론트엔드 paywall과 버튼 숨김은 UX 보조 수단일 뿐이다.
- 사용자와 챗봇은 저장된 scheduled report만 읽을 수 있다.
- 리포트 화면 진입, 챗봇 메시지, checkout redirect, 결제 성공 페이지, webhook 처리는 새로운 AI 리포트 생성을 트리거하면 안 된다.
- 카드 번호, provider secret, webhook secret, raw payment payload는 저장소에 저장하거나 프론트엔드에 노출하지 않는다.

## 피드백 요약

검증 문서는 다음 다섯 가지 실질적인 개선 지점을 기록했다.

1. 구독 저장소, 결제 provider 연동, webhook 처리가 없어 실제 유료 구독 상태가 활성화될 수 없다.
2. Free, Plus, Pro 계정을 대상으로 한 end-to-end smoke 경로가 없다.
3. 리포트 조회 endpoint 권한 gate를 직접 검증하는 API 테스트가 부족하다.
4. `POST /api/billing/checkout` 요청 스키마가 `FREE` 티어를 허용한다. checkout은 Plus와 Pro만 지원해야 한다.
5. `frontend/src/pages/AssetDetail.jsx`의 리포트 호출이 shared API client 대신 하드코딩된 backend URL을 사용한다.

## 구현 전략

작업을 안전한 provider 이전 단계와, 명시적으로 승인된 결제 provider 단계로 나눈다. 이렇게 하면 DB schema 변경과 실제 결제 연동 없이도 테스트와 계약을 먼저 단단하게 만들 수 있고, 위험도가 높은 schema/provider 작업은 정책 결정 이후에 진행할 수 있다.

## 1단계: 안전한 계약과 테스트 개선

이 단계는 실제 결제 provider나 DB schema 변경이 필요하지 않다.

### 백엔드 작업

- `backend/app/api/billing.py`에서 `FREE` checkout 요청을 거부한다.
- `backend/app/schemas.py`에서 다음 응답 스키마를 추가하거나 정리한다.
  - `BillingCheckoutResponse`
  - `BillingCancelResponse`
  - router가 명시적 response model을 유지한다면 최소 webhook acknowledgement shape
- checkout, cancel, webhook endpoint는 provider 작업 승인 전까지 계속 `501`을 반환하되, 잘못된 티어 검증은 provider 위임 전에 수행한다.
- 리포트 route 권한 테스트를 직접 추가한다.
  - token 없음: `401`
  - Free 권한: `403`
  - Plus 권한: 저장된 리포트 조회까지 도달하고 `200` 또는 `404`
  - Pro 권한: 저장된 리포트 조회까지 도달하고 `200` 또는 `404`
- 테스트는 LLM 호출과 리포트 생성을 사용하지 않도록 격리한다.

### 프론트엔드 작업

- `frontend/src/pages/AssetDetail.jsx`의 리포트 fetch를 `frontend/src/utils/apiClient.js` 또는 동일한 base URL 정책을 따르는 얇은 shared API helper로 이동한다.
- 현재 Free/Plus/Pro UI 동작을 유지한다.
  - 비로그인 사용자는 로그인/업그레이드 안내를 본다.
  - Free 사용자는 리포트 paywall을 보고 리포트 fetch를 시도하지 않는다.
  - Plus와 Pro 사용자는 저장된 리포트를 조회할 수 있다.
  - Pro 사용자만 챗봇 UI를 보고 사용할 수 있다.

### 검증

- 백엔드:
  - `python -m pytest tests/test_subscription_service.py tests/test_subscription_api.py tests/test_chat_api.py`
  - 새 리포트 권한 테스트 모듈 또는 관련 focused test path를 추가 실행한다.
- 프론트엔드:
  - `npm.cmd run lint`
  - `npm.cmd run build`

## 2단계: 제품 및 운영 정책 결정

다음 결정이 문서화되기 전에는 schema 변경이나 provider 연동을 시작하지 않는다.

- 결제 provider: Toss Payments Billing, PortOne, Stripe, 또는 KRW 정기 결제를 지원하는 다른 provider 중 선택한다.
- migration 전략: Alembic 도입, 문서화된 one-off migration, 또는 다른 명시적 migration workflow 중 선택한다.
- 가격 정책: 1,000 KRW와 3,000 KRW가 VAT 포함 최종 결제 금액인지 확정한다.
- 해지 정책: 권장 목표는 `current_period_end`까지 접근 권한을 유지하고 이후 Free로 downgrade하는 것이다.
- 갱신 실패 정책: retry/grace period와 최종 상태 mapping을 정의한다.
- 환불/관리자 정책: 첫 버전에 수동 관리자 override가 필요한지 결정한다.
- sandbox smoke 경로: provider sandbox 계정, local-only seed script, admin override, test fixture 중 어떤 방식으로 Free/Plus/Pro 상태를 만들지 결정한다.

## 3단계: DB 기반 구독 상태

이 단계는 DB schema를 변경하므로 명시적 승인이 필요하다.

### 백엔드 작업

- `backend/app/models.py`에 `Subscription`과 `BillingEvent` 모델을 추가한다.
- migration 파일 또는 승인된 migration 방식을 추가한다.
- 결제 credential은 저장하지 않고 provider 식별자와 구독 상태만 저장한다.
- provider webhook idempotency를 위한 unique constraint를 추가한다.
  - `provider`
  - `provider_event_id`
- `backend/app/services/subscription_service.py`의 `get_user_subscription`이 DB에서 구독 상태를 읽도록 수정한다.
- 구독 상태를 권한으로 mapping한다.
  - active Plus: 저장된 리포트만 조회 가능
  - active Pro: 저장된 리포트 조회 및 챗봇 사용 가능
  - none, expired, canceled, grace 없는 unpaid: Free 동작
- active, canceled, expired, past due, period-ended, duplicate event case에 대한 service test를 추가한다.

### 검증

- 선택한 test database setup에서 backend subscription/billing 테스트를 실행한다.
- fixture Free, Plus, Pro 사용자에 대해 `GET /api/billing/me`가 올바른 snapshot을 반환하는지 확인한다.

## 4단계: Provider Adapter와 Webhook

이 단계는 provider 선택과 webhook signature 정책이 명시적으로 확정된 뒤 진행한다.

### 백엔드 작업

- `backend/app/services/payment_service.py` 또는 `backend/app/services/payments/` 아래에 provider 경계를 만든다.
- 환경 변수 이름만 문서화하고 실제 값은 절대 기록하지 않는다.
  - `PAYMENT_PROVIDER`
  - `PAYMENT_WEBHOOK_SECRET`
  - `PAYMENT_PLUS_PLAN_ID`
  - `PAYMENT_PRO_PLAN_ID`
  - provider별 client key 또는 secret key 이름
- Plus와 Pro checkout 생성을 구현한다.
- API boundary와 service boundary 양쪽에서 `FREE` checkout을 거부한다.
- provider event 내용을 읽기 전에 webhook signature를 검증한다.
- provider event를 local subscription update로 정규화한다.
- 처리된 webhook event를 `BillingEvent`에 기록하고, 가능하면 구독 상태 변경과 같은 transaction 안에서 처리한다.
- webhook 응답은 최소화하고 raw provider payload를 반환하지 않는다.
- 확정된 해지 정책에 맞춰 cancellation을 구현한다.

### 프론트엔드 작업

- `Pricing.jsx`의 CTA 버튼을 `POST /api/billing/checkout`에 연결한다.
- 백엔드가 반환한 provider checkout URL 또는 billing session URL로 사용자를 redirect한다.
- `/billing/success`에서는 `GET /api/billing/me`를 refresh 또는 polling하고, webhook 반영 전에는 confirmation pending 상태를 명확히 보여준다.
- `/billing/cancel`에서는 복구 가능한 상태를 보여주고 사용자의 현재 티어를 유지한다.
- provider unavailable, checkout rejected, unauthenticated 사용자에 대한 명확한 error state를 추가한다.

### 검증

- provider sandbox에서 Plus와 Pro checkout이 성공한다.
- webhook duplicate delivery가 중복 상태 변경을 만들지 않는다.
- 잘못된 webhook signature가 거부된다.
- cancellation이 확정된 정책대로 동작한다.
- renewal failure가 확정된 상태와 권한 동작으로 mapping된다.

## 5단계: End-to-End Smoke와 Release 준비

### Smoke matrix

| 계정 상태 | 리포트 | 챗봇 | 예상 billing snapshot |
| --- | --- | --- | --- |
| 비로그인 | 로그인 필요 | 숨김 | `/billing/me` snapshot 없음 |
| Free | paywall로 차단 | 숨김 | `FREE` / `NONE` |
| Plus active | 저장된 리포트 조회 가능 | 숨김 | `PLUS` / `ACTIVE` |
| Pro active | 저장된 리포트 조회 가능 | 사용 가능 | `PRO` / `ACTIVE` |
| expired/canceled/unpaid | grace 정책이 없으면 차단 | Pro grace가 승인되지 않았으면 숨김 | 정책별 status |

### Release checklist

- provider dashboard에 확정된 KRW 가격으로 Plus와 Pro 상품이 생성되어 있다.
- provider dashboard에 production webhook URL이 등록되어 있다.
- 배포 환경에 provider env var가 설정되어 있다.
- provider webhook이 상태를 갱신하기 전에 DB migration이 적용되어 있다.
- 새 checkout 계약을 위해 backend 배포가 frontend 배포보다 먼저 진행된다.
- 대상 환경에서 Free, Plus, Pro smoke test가 통과한다.
- 저장된 리포트 접근이 AI 리포트 생성을 트리거하지 않는지 확인한다.

## 단계별 예상 변경 파일

1단계:

- `backend/app/api/billing.py`
- `backend/app/schemas.py`
- `backend/tests/test_subscription_api.py`
- 신규 또는 기존 backend report access test
- `frontend/src/pages/AssetDetail.jsx`
- `frontend/src/utils/apiClient.js`
- `docs/harness/features/subscription-billing.md`
- `docs/harness/feature-index.md`

3단계:

- `backend/app/models.py`
- migration 파일 또는 문서화된 migration script
- `backend/app/services/subscription_service.py`
- `backend/tests/test_subscription_service.py`
- `backend/tests/test_subscription_api.py`

4단계:

- `backend/app/api/billing.py`
- `backend/app/services/payment_service.py` 또는 `backend/app/services/payments/`
- mocked 또는 sandbox provider call을 사용하는 provider-specific test
- `frontend/src/pages/Pricing.jsx`
- `frontend/src/pages/BillingSuccess.jsx`
- `frontend/src/pages/BillingCancel.jsx`
- `frontend/src/store/subscriptionStore.js`

## 후속 위험

- schema 변경과 provider 연동은 의도적으로 confirmation 뒤에 진행한다.
- 실제 유료 구독을 안정적으로 운영하려면 지속 가능한 migration 전략이 필요하다.
- 수동 Plus/Pro 검증을 의미 있게 하려면 sandbox 또는 local fixture 경로가 필요하다.
- provider webhook 처리는 첫 구현부터 보안 민감 영역으로 다루고 idempotent하게 만들어야 한다.
- 유료 접근 권한은 on-demand AI 리포트 생성을 의미하면 안 된다.

## 연결된 기능 문서

- `docs/harness/features/subscription-billing.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/chatbot-assistant.md`
- `docs/harness/features/frontend-routing-shell.md`
