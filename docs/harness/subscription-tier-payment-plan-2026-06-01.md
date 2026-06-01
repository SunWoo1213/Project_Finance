# 티어별 구독 및 월 결제 구현 계획서

작성일: 2026-06-01

## 목적

Project Finance에 월 구독 기반 티어 권한을 도입한다.

| 티어 | 월 결제 금액 | AI 리포트 | 챗봇 |
| --- | ---: | --- | --- |
| Free | 0원 | 이용 불가 | 보이지 않음 |
| Plus | 1,000원 / 월 | 이용 가능 | 보이지 않음 |
| Pro | 3,000원 / 월 | 이용 가능 | 이용 가능 |

이 문서는 구현 계획서이며, 작성 시점에는 런타임 코드를 변경하지 않았다.

## 현재 변경해야 할 동작

- 현재 리포트는 로그인 사용자가 `GET /api/reports/{ticker}`로 조회할 수 있다.
- 현재 자산 상세 화면은 비로그인 사용자에게만 리포트를 흐리게 보여주고 로그인 버튼을 표시한다.
- 현재 챗봇 런처는 `frontend/src/App.jsx`에 전역으로 마운트되어 모든 라우트에서 보일 수 있다.
- 현재 `POST /api/chat/message`는 public 엔드포인트이며 JWT를 선택적으로 해석한다.
- AI 리포트 생성은 계속 스케줄러 전용이어야 한다. 사용자 화면 진입, 챗봇 질문, 결제 상태 변경이 새 리포트 생성을 트리거하면 안 된다.

## 제품 규칙

1. Free 사용자는 공개 시장 데이터와 커뮤니티 읽기는 사용할 수 있지만, AI 리포트와 챗봇은 사용할 수 없다.
2. Plus 사용자는 저장된 스케줄 AI 리포트를 볼 수 있지만, 챗봇은 사용할 수 없다.
3. Pro 사용자는 저장된 스케줄 AI 리포트와 챗봇을 모두 사용할 수 있다.
4. Plus와 Pro는 1개월마다 자동 결제되는 구독 상품이다.
5. 결제 성공 리다이렉트만으로 권한을 부여하지 않는다. 결제 제공자의 webhook으로 확인된 서버 상태가 권한의 기준이다.
6. 프론트엔드에서 버튼이나 런처를 숨기는 것은 UX 보조 수단일 뿐이다. 실제 권한은 백엔드가 항상 강제해야 한다.

## 구현 전 확정해야 할 사항

- 결제 제공자: Toss Payments Billing, PortOne, Stripe 등 KRW 월 구독을 지원하는 제공자 중 하나를 선택한다.
- 부가세 정책: 1,000원과 3,000원이 VAT 포함 최종 결제 금액인지 확정한다.
- 해지 정책: 해지 시 즉시 Free로 내릴지, 현재 결제 기간 종료일까지 이용 가능하게 할지 결정한다. 권장안은 기간 종료일까지 유지이다.
- 결제 실패 정책: 갱신 실패 후 유예 기간을 둘지 결정한다. 권장안은 제공자의 재시도 정책이 끝나고 canceled, expired, unpaid 상태가 확정되면 Free로 내리는 것이다.
- 환불 및 관리자 정책: 초기 버전에 관리자 수동 조정 기능이 필요한지 결정한다.

## 백엔드 설계

### 데이터 모델

카드 정보는 저장하지 않고, 구독 상태와 결제 이벤트만 저장한다.

권장 enum:

- `SubscriptionTier`: `FREE`, `PLUS`, `PRO`
- `SubscriptionStatus`: `NONE`, `ACTIVE`, `PAST_DUE`, `CANCELED`, `EXPIRED`

권장 모델:

- `Subscription`
  - `id`
  - `user_id`
  - `tier`
  - `status`
  - `provider`
  - `provider_customer_id`
  - `provider_subscription_id`
  - `current_period_start`
  - `current_period_end`
  - `cancel_at_period_end`
  - `created_at`
  - `updated_at`
- `BillingEvent`
  - `id`
  - `provider`
  - `provider_event_id`
  - `event_type`
  - `processed_at`
  - `payload_summary`

`BillingEvent.provider_event_id`는 unique로 두어 webhook 중복 수신을 안전하게 처리한다.

현재 저장소에는 Alembic migration 흐름이 없다. 구독 테이블 추가는 DB schema 변경이므로 구현 전 승인이 필요하다. 가능하면 Alembic을 먼저 도입하고, 어렵다면 임시 startup migration을 명확히 문서화한 뒤 운영 배포 전 별도 migration 계획을 세운다.

### 권한 서비스

`backend/app/services/subscription_service.py`를 추가한다.

핵심 함수:

- `get_user_subscription(user_id, db)`
- `get_user_entitlements(user, db)`
- `has_active_paid_access(subscription)`
- `can_view_reports`: active Plus 또는 active Pro
- `can_use_chatbot`: active Pro만 허용

JWT에는 사용자 식별자만 유지하고, 실제 티어 권한은 DB 구독 상태로 판단하는 것이 안전하다. 프론트의 localStorage, `context.authenticated`, JWT custom claim만 믿고 권한을 열면 안 된다.

### 권한 dependency

`backend/app/api/deps.py`에 재사용 가능한 dependency를 추가한다.

- `require_report_access`
- `require_chatbot_access`
- 필요 시 `get_current_entitlements`

응답 정책:

- 로그인 토큰이 없거나 유효하지 않으면 `401`
- 로그인은 되었지만 티어 권한이 없으면 `403`

### API 변경

`backend/app/api/billing.py` 라우터를 추가한다.

- `GET /api/billing/plans`
  - public
  - Free, Plus 1,000원/월, Pro 3,000원/월 메타데이터 반환
- `GET /api/billing/me`
  - 로그인 필요
  - 현재 티어, 구독 상태, 결제 기간, 권한 반환
- `POST /api/billing/checkout`
  - 로그인 필요
  - body: `{ "tier": "PLUS" | "PRO" }`
  - 결제 제공자의 checkout URL 또는 billing session 반환
- `POST /api/billing/cancel`
  - 로그인 필요
  - 확정된 해지 정책에 따라 구독 해지 요청
- `POST /api/billing/webhook`
  - 결제 제공자 callback
  - signature 검증 후 구독 상태 upsert
  - `BillingEvent`에 처리 기록 저장

기존 API 권한 변경:

- `GET /api/reports/{ticker}`는 Plus 또는 Pro만 허용한다.
- `POST /api/chat/message`는 Pro만 허용한다.
- `POST /api/ai/generate/{ticker}`는 지금처럼 일반 사용자에게 비활성화 상태를 유지한다. 유료 티어는 리포트 조회 권한이지 생성 권한이 아니다.

### 결제 provider adapter

`backend/app/services/payment_service.py` 또는 `backend/app/services/payments/` 하위에 provider 경계를 둔다.

책임:

- 월 구독 checkout 또는 billing session 생성
- 로컬 티어와 provider plan id 매핑
- webhook signature 검증
- provider 이벤트를 로컬 `Subscription` 상태로 정규화
- provider secret key를 프론트엔드에 절대 노출하지 않음

환경변수 이름만 문서화하고 실제 값은 남기지 않는다.

- `PAYMENT_PROVIDER`
- `PAYMENT_WEBHOOK_SECRET`
- `PAYMENT_PLUS_PLAN_ID`
- `PAYMENT_PRO_PLAN_ID`
- provider별 secret/client key

## 프론트엔드 설계

### 구독 권한 상태

기존 `authStore.js`를 확장하거나 `frontend/src/store/subscriptionStore.js`를 새로 만든다.

권장 동작:

- 로그인 후, 그리고 토큰이 있는 앱 부팅 시 `GET /api/billing/me`를 호출한다.
- 권한을 불러오는 동안에는 paid-only 권한을 기본 false로 둔다. 챗봇이나 리포트가 잠깐 보였다가 사라지는 현상을 막기 위해서다.
- 로그아웃 시 구독 권한 상태도 초기화한다.
- 결제 성공 페이지에서는 권한을 다시 조회하되, webhook 반영 전이면 “결제 확인 중” 상태를 보여준다.

### 라우트와 UI

`frontend/src/App.jsx`에 다음 라우트를 추가한다.

- `/pricing`: 요금제 비교 및 결제 CTA
- `/billing/success`: 결제 완료 후 확인 중/성공 안내
- `/billing/cancel`: 결제 취소 또는 중단 안내

추가 후보 파일:

- `frontend/src/pages/Pricing.jsx`
- `frontend/src/pages/BillingSuccess.jsx`
- `frontend/src/pages/BillingCancel.jsx`
- `frontend/src/components/PlanBadge.jsx`
- `frontend/src/components/Paywall.jsx`

`Header.jsx`에는 요금제 링크 또는 현재 플랜 뱃지를 추가한다.

### 리포트 gate

`frontend/src/pages/AssetDetail.jsx`를 수정한다.

- 비로그인: 로그인 유도
- 로그인 Free: Plus/Pro 업그레이드 paywall 표시, `/api/reports/{ticker}` 호출하지 않음
- 로그인 Plus 또는 Pro: `/api/reports/{ticker}` 호출 후 `ReportCard` 표시
- 백엔드가 `403`을 반환하면 리포트 내용을 지우고 업그레이드 paywall 표시

리포트 조회는 계속 저장된 리포트만 읽는다. 저장된 리포트가 없으면 기존 scheduled-report-pending 상태를 유지한다.

### 챗봇 gate

`frontend/src/App.jsx` 또는 `ChatbotLauncher.jsx`를 수정한다.

- `can_use_chatbot === true`일 때만 `ChatbotLauncher`를 렌더링한다.
- Free와 Plus에서는 챗봇 버튼이 보이지 않아야 한다.
- 직접 API 호출을 막기 위해 백엔드 `POST /api/chat/message`도 Pro 권한을 검사한다.

### API client 정리

신규 billing API는 `frontend/src/utils/apiClient.js`를 통해 호출한다.

다만 기존 `AssetDetail.jsx`에는 `http://localhost:8000` 직접 호출이 남아 있으므로, 이번 구현에서 전체 API 호출 정리를 과하게 확장하지 않는다. 결제/권한 변경 범위에 필요한 부분만 정리한다.

## 구현 단계

### 0단계: 정책 확정

- 결제 제공자 선택
- VAT, 해지, 유예 기간, 환불 정책 확정
- 구독 테이블 migration 방식 확정

### 1단계: 권한 기반 구축

- 구독 enum, 모델, 스키마 추가
- 구독 권한 서비스 추가
- `require_report_access`, `require_chatbot_access` 추가
- `GET /api/billing/plans`, `GET /api/billing/me` 추가
- Free, Plus, Pro 권한 계산 테스트 작성

### 2단계: 실제 결제 전 리소스 gate 적용

- `GET /api/reports/{ticker}`를 Plus/Pro로 제한
- `POST /api/chat/message`를 Pro로 제한
- 프론트에서 Free/Plus/Pro별 리포트와 챗봇 노출 제어
- `/pricing`과 paywall UI 추가
- 테스트용 구독 row로 결제 연동 전 검증

### 3단계: 월 결제 연동

- Plus와 Pro checkout 생성 구현
- webhook signature 검증 구현
- webhook 중복 처리 구현
- provider 구독 상태를 로컬 DB에 저장
- 성공/취소 페이지 연결
- provider sandbox로 성공, 중복 webhook, 해지, 결제 실패 상태 검증

### 4단계: 플랜 변경과 해지

- Plus에서 Pro 업그레이드
- Pro에서 Plus 다운그레이드
- 구독 해지 API와 UI
- 변경/해지 시 현재 결제 기간 권한 유지 정책 반영

### 5단계: 문서와 배포 정리

- 인증, 리포트, 챗봇, 구독 billing feature 문서 갱신
- provider 환경변수와 webhook URL 배포 문서화
- 백엔드/프론트 검증 실행
- Free, Plus, Pro 계정으로 수동 smoke test

## 테스트 계획

백엔드:

- Free: 리포트 불가, 챗봇 불가
- Plus active: 리포트 가능, 챗봇 불가
- Pro active: 리포트 가능, 챗봇 가능
- expired/canceled/past_due: 정책에 따라 권한 차단 또는 유예 적용
- `/api/reports/{ticker}`: 토큰 없음 `401`, Free `403`, Plus/Pro `200` 또는 저장 리포트 없음 `404`
- `/api/chat/message`: 토큰 없음 `401`, Free/Plus `403`, Pro `200`
- webhook 중복 이벤트가 구독 상태를 중복 변경하지 않음

프론트엔드:

- Free 로그인: 챗봇 런처 없음, 리포트 paywall 표시, 리포트 fetch 시도 없음
- Plus 로그인: 리포트 표시 가능, 챗봇 런처 없음
- Pro 로그인: 리포트 표시 가능, 챗봇 런처 있음
- 비로그인: 리포트는 로그인 유도, 챗봇 런처 없음

권장 검증 명령:

```powershell
cd backend
python -m pytest tests/test_subscription_service.py tests/test_subscription_api.py tests/test_chat_api.py
```

```powershell
cd frontend
npm run lint
npm run build
```

## 구현 시 예상 변경 파일

백엔드:

- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/app/api/deps.py`
- `backend/app/api/billing.py`
- `backend/app/api/chat.py`
- `backend/app/main.py`
- `backend/app/services/subscription_service.py`
- `backend/app/services/payment_service.py`
- `backend/tests/test_subscription_service.py`
- `backend/tests/test_subscription_api.py`
- `backend/tests/test_chat_api.py`

프론트엔드:

- `frontend/src/App.jsx`
- `frontend/src/components/Header.jsx`
- `frontend/src/components/ChatbotLauncher.jsx`
- `frontend/src/pages/AssetDetail.jsx`
- `frontend/src/pages/Pricing.jsx`
- `frontend/src/pages/BillingSuccess.jsx`
- `frontend/src/pages/BillingCancel.jsx`
- `frontend/src/store/authStore.js` 또는 `frontend/src/store/subscriptionStore.js`
- `frontend/src/utils/apiClient.js`

문서:

- `docs/harness/features/subscription-billing.md`
- `docs/harness/features/authentication.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/chatbot-assistant.md`
- `docs/harness/features/frontend-routing-shell.md`
- `docs/harness/feature-index.md`

## 배포 체크리스트

- 결제 제공자 dashboard에 Plus 1,000원/월, Pro 3,000원/월 상품 생성
- provider dashboard에 webhook URL 등록
- 배포 환경에 provider env var 등록
- DB migration 실행
- 백엔드 먼저 배포
- `/api/billing/me` 동작 확인 후 프론트 배포
- sandbox 계정으로 Free, Plus, Pro 전체 흐름 확인
- 사용자 리포트 조회와 챗봇 질문이 새 AI 리포트 생성을 트리거하지 않는지 확인

## 남은 위험

- 현재 프로젝트에는 formal migration 도구가 없어 구독 테이블 배포 방식이 중요하다.
- 결제 webhook은 signature 검증이 필수인 보안 민감 영역이다.
- 갱신 실패 후 클라이언트 권한 상태가 오래 남을 수 있으므로 백엔드 권한 검사가 항상 최종 기준이어야 한다.
- 챗봇 버튼을 숨기는 것만으로는 충분하지 않다. API도 반드시 Pro만 허용해야 한다.
- 유료 리포트 제공은 사용자가 리포트 커버리지를 더 기대하게 만들 수 있지만, 현재 리포트 생성 스케줄러는 비용 관리를 위해 보수적으로 제한되어 있다.

## 연결된 기능 문서

- `docs/harness/features/subscription-billing.md`
- `docs/harness/features/authentication.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/chatbot-assistant.md`
- `docs/harness/features/frontend-routing-shell.md`
