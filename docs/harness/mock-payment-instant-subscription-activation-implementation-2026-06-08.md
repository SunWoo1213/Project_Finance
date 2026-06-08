# Mock 결제 즉시 구독 활성화 구현

Date: 2026-06-08
Feature area: Subscription billing and tier entitlements
Plan: `docs/harness/mock-payment-instant-subscription-activation-plan-2026-06-08.md`
Feature doc: `docs/harness/features/subscription-billing.md`

## 목적

`PAYMENT_PROVIDER=mock`인 개발/데모 환경에서 요금제 페이지의 "구독 시작"을 누르면 결제 제공자 연동 없이 **즉시 해당 등급(Plus/Pro) 구독이 활성화**되도록 한다. 기존 mock 동작은 리다이렉트 URL만 반환하고 실제 권한은 webhook으로만 부여돼, mock 환경에서는 구독이 끝내 활성화되지 않던 문제를 해결한다.

이 경로는 **mock provider 한정**이다. Toss 및 미설정 provider 동작은 변경하지 않았다.

## 변경 파일

### Backend
- `backend/app/schemas.py`
  - `BillingCheckoutResponse`에 선택 필드 `activated: bool = False` 추가. 기존 toss/미설정 응답은 기본값으로 호환 유지.
- `backend/app/services/payment_service.py`
  - `mock_provider_subscription_id(user_id)` 추가: `mock_{user_id}` 형태로 사용자당 단일 mock 구독 행을 유지.
  - `activate_mock_subscription(db, user, tier, period_days=30)` 추가:
    - 유료 등급(PLUS/PRO)만 허용, plan 미설정 시 `PaymentProviderUnavailable`.
    - `provider="mock"` 단일 행을 조회/생성하고 `status=ACTIVE`, 기간 30일, `provider_plan_id=get_plan_id(tier)`로 설정.
    - 같은 사용자의 다른 ACTIVE/CANCELED 구독은 EXPIRED 처리(`apply_subscription_transition`의 단일-활성-행 패턴 재사용).
- `backend/app/api/billing.py`
  - `POST /api/billing/checkout`에 `provider.provider_name == "mock"` 분기 추가. mock이면 `activate_mock_subscription` 호출 후 `BillingCheckoutResponse(checkout_url=success_url, activated=True)` 반환. toss/기타 분기는 기존 흐름 유지.

### Frontend
- `frontend/src/pages/Pricing.jsx`
  - `useNavigate`, 구독 스토어의 `fetchMe` 사용 추가.
  - checkout 응답에 `activated === true`이면 `fetchMe(token)`로 권한 갱신 → 성공 토스트 → `/billing/success`로 이동. 그 외에는 기존 `checkout_url` 리다이렉트 동작 유지.

### Tests
- `backend/tests/test_subscription_api.py`
  - 기존 `test_billing_checkout_paid_tiers_return_provider_checkout_url`(옛 mock 리다이렉트 기대)를 새 동작에 맞춰 교체:
    - `test_billing_checkout_mock_activates_subscription_immediately`: mock checkout이 `activated=True`와 success_url을 반환하고, 이후 `GET /api/billing/me`가 PLUS/PRO·ACTIVE·올바른 entitlement를 반환하는지 검증.
    - `test_billing_checkout_mock_reactivation_keeps_single_active_row`: PLUS→PRO 재구독 시 행이 1개로 유지되고 ACTIVE가 PRO 1건인지 검증.
  - `from sqlalchemy import select` import 추가.

## 동작 변화

- mock: "구독 시작" → 즉시 ACTIVE 구독 생성 → 권한 즉시 반영(리포트 게이트 해제, PRO면 챗봇 노출). 응답 `activated=True`.
- toss: 변경 없음(billing-auth intent 생성 → `/billing/toss/auth`).
- 미설정: 변경 없음(503 provider-unavailable).
- AI 리포트 생성과 무관: 저장된 리포트 읽기 권한만 부여하며, 스케줄러/리포트 생성/쿨다운/비용을 일절 건드리지 않는다. 사용자 요청이 리포트 실시간 생성을 유발하지 않는다(AGENTS.md 섹션 14 준수).

## 검증 결과

- 백엔드(PowerShell, 비민감 env 주입 `PROJECT_NAME`/`API_V1_STR`/`DATABASE_URL=sqlite+aiosqlite:///:memory:`):
  ```powershell
  python -m pytest tests/test_subscription_api.py tests/test_payment_service.py tests/test_subscription_service.py -q
  ```
  → **26 passed** (경고는 기존 `datetime.utcnow()` DeprecationWarning으로 본 변경과 무관).
- 프론트엔드:
  ```powershell
  npm run lint   # 통과(에러 없음)
  npm run build  # ✓ built (청크 크기 경고만, 기존과 동일)
  ```

## 미실행 명령과 이유

- 전체 `pytest`: 본 변경 범위에 맞춰 billing/subscription/payment 관련 테스트만 실행. 일부 다른 테스트는 외부 네트워크/시크릿 의존이 있어 범위를 좁혔다.
- 실제 DB(PostgreSQL) 기동 검증: 단위/통합 테스트가 인메모리 SQLite로 충분히 경로를 덮으므로 생략. 수동 스모크는 운영자 환경에서 `PAYMENT_PROVIDER=mock`으로 확인 권장.

## 후속 위험

- **운영 오용 위험**: 운영에서 실수로 `PAYMENT_PROVIDER=mock`을 두면 누구나 무료로 유료 권한을 얻는다. mock은 개발/데모 전용이며 운영 배포 설정에서 mock을 사용하지 않도록 점검해야 한다.
- 가드: checkout 핸들러에서 mock 분기로만 진입하고, `activate_mock_subscription`은 유료 등급만 허용. toss/미설정 경로는 영향 없음.
