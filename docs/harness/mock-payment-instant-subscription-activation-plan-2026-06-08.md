# Mock 결제 즉시 구독 활성화 계획

Date: 2026-06-08
Feature area: Subscription billing and tier entitlements
Read first: `docs/harness/features/subscription-billing.md`

## 1. 목적 (Objective)

결제 시스템이 **mock 상태**(`PAYMENT_PROVIDER=mock`)일 때, 요금제 페이지에서 "구독 시작"을 누르면 실제 결제 제공자(Toss 등) 연동 없이 **즉시 해당 등급(Plus/Pro) 구독이 활성화**되도록 한다. 데모·개발 환경에서 결제 흐름을 막힘 없이 체험·검증하기 위한 것이다.

이 변경은 **mock provider 한정**이다. `PAYMENT_PROVIDER`가 `toss`이거나 미설정인 경우의 동작은 일절 바뀌지 않는다.

## 2. 현재 동작 / 목표 동작

### 현재 동작 (mock)
1. 사용자가 `Pricing.jsx`에서 "구독 시작" 클릭 → `POST /api/billing/checkout` 호출.
2. 백엔드 `MockPaymentProvider.create_checkout_session`는 `PAYMENT_MOCK_CHECKOUT_BASE_URL`(없으면 `success_url`)에 쿼리스트링을 붙인 리다이렉트 URL만 반환한다. **구독 행은 생성하지 않는다.**
3. 프론트엔드는 `window.location.assign(checkout_url)`로 이동한다.
4. 실제 권한 부여(`Subscription` ACTIVE 행)는 오직 `POST /api/billing/webhook` 처리(`apply_subscription_transition`)를 통해서만 일어난다.
5. mock 환경에서는 이 webhook이 자동으로 호출되지 않으므로, `/billing/success` 페이지가 `GET /api/billing/me`를 6회 폴링해도 계속 `FREE / NONE`으로 남는다. → **사실상 구독이 되지 않는다.**

### 목표 동작 (mock)
1. "구독 시작" 클릭 → `POST /api/billing/checkout`.
2. mock provider인 경우, 백엔드가 즉시 해당 사용자에게 요청 등급의 **ACTIVE 구독 행을 생성/갱신**한다(기간 1개월, 기존 활성 구독은 만료 처리).
3. 응답으로 성공 페이지 URL과 즉시 활성화 플래그를 돌려준다.
4. 프론트엔드는 `/billing/success`로 이동하고, 첫 `GET /api/billing/me` 응답에서 곧바로 `PLUS/PRO · ACTIVE`를 받아 권한이 반영된다.
5. Toss/미설정 provider 동작은 변경 없음(기존 checkout/intent/webhook 흐름 유지).

## 3. 변경 대상 파일

### Backend
- `backend/app/services/payment_service.py`
  - `MockPaymentProvider`에 즉시 활성화 의도를 표현하는 진입점을 추가하거나, 신규 서비스 함수 `activate_mock_subscription(db, user, tier)`를 추가한다.
  - `grant_subscription.py`의 부여 로직과 `apply_subscription_transition`의 "기존 활성 구독 만료" 로직을 참고하여 일관된 단일 활성 행을 유지한다.
  - mock 활성화 시 `provider="mock"`, `provider_subscription_id=f"mock_{user_id}"`(사용자당 단일 행 유지), `status=ACTIVE`, `tier`, `provider_plan_id=get_plan_id(tier)`, `current_period_start=now`, `current_period_end=now+30일`, `cancel_at_period_end=False`로 설정.
- `backend/app/api/billing.py`
  - `POST /api/billing/checkout` 핸들러에서 `provider.provider_name == "mock"`인 분기를 추가하여 즉시 활성화 함수를 호출하고, `checkout_url`(success_url)과 활성화 플래그를 반환한다.
- `backend/app/schemas.py`
  - `BillingCheckoutResponse`에 선택적 필드 `activated: bool = False`를 추가(기존 toss/미설정 응답은 기본값 `False`로 호환 유지).

### Frontend
- `frontend/src/pages/Pricing.jsx`
  - 체크아웃 응답에 `activated === true`가 있으면, 토스트로 즉시 안내하고 `/billing/success`로 이동(또는 구독 스토어 `fetchMe` 후 안내). 최소 변경으로는 기존 `window.location.assign(checkout_url)` 그대로 두어도 success 페이지 폴링이 ACTIVE를 잡으므로 동작하지만, UX 개선을 위해 즉시 토스트를 권장.
- `frontend/src/pages/BillingSuccess.jsx`
  - 변경 불필요(기존 폴링이 첫 호출에서 ACTIVE를 받음). mock 활성화 메시지를 더 명확히 하고 싶으면 안내 문구만 보강(선택).

### DB / 설정
- **DB 스키마 변경 없음.** 기존 `subscriptions` 테이블 컬럼만 사용한다.
- 설정 변경 없음. 동작은 기존 `PAYMENT_PROVIDER=mock` 값으로 분기한다.

## 4. 단계별 구현 계획

1. `payment_service.py`에 `activate_mock_subscription(db, user, tier)` 추가:
   - `get_plan_id(tier)`로 plan 확인(없으면 `PaymentProviderUnavailable`).
   - `provider="mock"`, `provider_subscription_id=f"mock_{user.id}"` 행을 조회/생성.
   - 등급·상태·기간 설정 후, 동일 사용자의 다른 ACTIVE/CANCELED 구독을 EXPIRED 처리(`apply_subscription_transition` 패턴 재사용).
   - `commit` 후 갱신된 구독 반환.
2. `billing.py`의 checkout 핸들러에 mock 분기 추가: mock이면 `activate_mock_subscription` 호출 후 `BillingCheckoutResponse(checkout_url=success_url, activated=True)` 반환. toss/기타는 기존 흐름 유지.
3. `schemas.py`의 `BillingCheckoutResponse`에 `activated: bool = False` 추가.
4. `Pricing.jsx`에서 `data.activated`가 true면 성공 토스트 후 `/billing/success` 이동(없으면 기존 redirect 유지).
5. 백엔드 테스트 추가/갱신: mock checkout이 즉시 ACTIVE 구독을 만들고 `GET /api/billing/me`가 해당 등급을 반환하는지, toss/미설정에서는 기존 동작이 유지되는지.
6. 문서 동기화(아래 9절).

## 5. 위험과 Risky Change 여부 (AGENTS.md 섹션 9)

- **결제/권한 부여 동작 변경**: "결제 없이 유료 권한을 부여"하는 경로를 추가하므로 민감한 변경이다. 단, **`PAYMENT_PROVIDER=mock`에서만** 작동하도록 엄격히 가드한다. mock은 개발·데모 전용 설정이며 운영(Toss) 동작은 그대로다. → 구현 전 사용자 확인 필요(이 계획서로 승인 요청).
- **운영 환경 오용 위험**: 운영에서 실수로 `PAYMENT_PROVIDER=mock`을 두면 누구나 무료로 유료 권한을 얻는다. 완화책: (a) checkout 핸들러에 mock-only 가드 명시, (b) 변경 기록과 feature 문서에 "mock은 운영 금지" 명기, (c) 선택적으로 mock 활성화 시 로그 경고 출력.
- **DB 스키마 변경 없음** → 마이그레이션 불필요.
- **AI 리포트 생성과 무관**: 이 변경은 저장된 리포트 읽기 권한만 부여하며, 리포트 스케줄러/생성 동작이나 비용을 일절 건드리지 않는다(AGENTS.md 섹션 14 준수).
- **시크릿 미노출**: Toss 키 등 시크릿을 다루지 않는다.

## 6. 검증 계획 (AGENTS.md 섹션 6 — 최소 검증)

```powershell
docker compose up -d db   # DB 의존 테스트가 필요한 경우
cd backend
pytest tests/ -k "billing or subscription or payment"
```

- 신규/갱신 백엔드 테스트:
  - mock provider + `POST /api/billing/checkout` → 즉시 ACTIVE 구독 생성 + `activated=True`.
  - 이후 `GET /api/billing/me`가 요청 등급(PLUS/PRO)·ACTIVE 반환.
  - 동일 사용자가 PLUS→PRO 재구독 시 단일 활성 행 유지(이전 행 EXPIRED).
  - toss/미설정 provider에서는 기존 동작(리다이렉트 또는 503) 유지(회귀 방지).
- 프론트엔드(가능 시):
  ```powershell
  cd frontend
  npm run lint
  npm run build
  ```
- 수동 스모크: 로컬에서 `PAYMENT_PROVIDER=mock`로 "구독 시작" → 즉시 권한 반영(리포트 게이트/챗봇 노출) 확인.

## 7. 갱신할 문서

- `docs/harness/features/subscription-billing.md`
  - "Current Behavior"와 "Data Flow"에 mock 즉시 활성화 경로를 명시하고, mock은 개발/데모 전용임을 강조.
  - "Change Records"에 본 계획서 및 후속 구현 기록 링크 추가.
- `docs/harness/feature-index.md`
  - Subscription billing 행의 Change records에 본 계획서/구현 기록 추가.
  - 상단 목록에 항목 추가.
- 구현 단계에서 `docs/harness/mock-payment-instant-subscription-activation-implementation-2026-06-08.md` 변경 기록 작성.

## 8. 미실행 / 후속

- 본 단계는 계획만 작성. 구현·검증은 사용자 승인 후 진행.
- 후속 위험: 운영 환경에서 mock 설정 금지 강제(배포 설정 점검) 필요.
