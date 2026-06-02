# 프로젝트 부족점 개선 실행 계획

작성일: 2026-06-02

## 목표

문서 검토에서 확인된 운영, 배포, 결제, 리포트 coverage, 알림, 프론트 API 구성, 문서 정합성 부족을 실제 개선 작업으로 전환하기 위한 단계별 계획을 남긴다.

이 계획은 코드 변경이 아니라 후속 구현 작업의 순서와 완료 기준을 정리한 것이다. 실제 구현 시에는 각 단계별 기능 문서와 현재 코드를 다시 확인해야 한다.

## 기준 문서

- `ARCHITECTURE.md`
- `PROJECT_STRUCTURE_ANALYSIS.md`
- `DEVELOPMENT_DIRECTION.md`
- `docs/harness/feature-documentation-guide.md`
- `docs/harness/feature-index.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/features/subscription-billing.md`
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/chatbot-assistant.md`
- `docs/harness/features/frontend-routing-shell.md`
- `docs/harness/features/favorite-asset-notifications.md`
- `docs/harness/features/favorites.md`
- `docs/harness/features/authentication.md`

## 핵심 부족점 요약

1. 운영 배포 설정과 `.env_example`이 현재 `backend/app/core/config.py`의 설정 전체를 충분히 반영하지 못한다.
2. 프론트 일부 페이지가 아직 `http://localhost:8000`을 직접 사용해 hosted 환경에서 API origin 관리가 취약하다.
3. 결제/구독은 DB-backed entitlement와 mock provider 경계는 있으나 실제 production payment provider, VAT, 환불, 실패 결제, downgrade 정책이 미정이다.
4. 유료 리포트 접근은 구현되어 있지만 scheduled report coverage가 대표 ticker 중심이라 유료 사용자도 많은 자산에서 pending 상태를 볼 수 있다.
5. AI 리포트 품질 게이트는 강화되었지만 raw provider payload persistence, full claim-evidence verification, independent LLM debate agent는 아직 의도적으로 제한되어 있다.
6. 알림 기능은 scheduler와 DB 모델은 있으나 Telegram 운영 webhook/polling, 실제 email verification delivery, unsubscribe/retry/rate-limit 정책이 부족하다.
7. `AssetDetail.jsx`가 시장 요약, 차트, 리포트, 권한, 댓글, 신고, 즐겨찾기를 함께 소유해 변경 리스크가 높다.
8. 일부 feature document의 Open Risks가 현재 구현과 어긋난다.
9. 프론트 컴포넌트 자동 테스트와 end-to-end smoke matrix가 충분하지 않다.

## 우선순위 원칙

- 먼저 배포와 설정처럼 모든 기능의 기반이 되는 부분을 안정화한다.
- 비용이 증가하는 scheduler coverage, LLM call, 외부 payment/email/Telegram provider 연동은 사용자 확인 후 진행한다.
- 사용자-facing report view, chatbot request, notification job은 새 AI 리포트 생성을 직접 트리거하지 않는다.
- DB schema 변경은 Alembic revision으로 표현하고, hosted runtime에서는 `ENABLE_DB_SCHEMA_BOOTSTRAP=false`를 전제로 검증한다.
- 문서 정합성 수정은 기능 구현과 분리해 먼저 처리할 수 있다.

## Phase 0: 문서와 설정 정합성 정리

### 목표

신규 실행자와 배포자가 현재 런타임 설정을 오해하지 않도록 `.env_example`, feature docs, Open Risks를 최신 코드 기준으로 맞춘다.

### 작업

1. `.env_example`에 현재 설정 이름을 빠짐없이 추가한다.
   - `VITE_API_BASE_URL`
   - `ENVIRONMENT`
   - `BACKEND_CORS_ORIGINS`
   - `BACKEND_CORS_ORIGIN_REGEX`
   - `LOCAL_CORS_ORIGINS`
   - `ENABLE_DB_SCHEMA_BOOTSTRAP`
   - `SQLALCHEMY_ECHO`
   - `DB_POOL_PRE_PING`
   - `DB_PREPARED_STATEMENT_CACHE_SIZE`
   - `REPORT_SCHEDULER_INTERVAL_HOURS`
   - `REPORT_SCHEDULER_TARGET_TICKERS`
   - `PAYMENT_PROVIDER`
   - `PAYMENT_WEBHOOK_SECRET`
   - `PAYMENT_PLUS_PLAN_ID`
   - `PAYMENT_PRO_PLAN_ID`
   - `PAYMENT_MOCK_CHECKOUT_BASE_URL`
2. `.env_example`의 scheduler 기본 예시를 `backend/app/core/config.py`의 현재 기본값과 맞춘다.
3. `docs/harness/features/favorites.md`의 계정 동기화 관련 Open Risk를 현재 구현 기준으로 수정한다.
4. `docs/harness/features/authentication.md`의 Alembic 관련 stale 문구를 현재 migration workflow 기준으로 수정한다.
5. `docs/harness/features/deployment-runtime.md`에 `.env_example` 정합성 점검을 verification 항목으로 추가한다.

### 예상 변경 파일

- `.env_example`
- `docs/harness/features/favorites.md`
- `docs/harness/features/authentication.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/feature-index.md` if change-record links are updated
- 신규 change record under `docs/harness/`

### 검증

- Secret 값이 추가되지 않았는지 눈으로 확인한다.
- `backend/app/core/config.py`와 `.env_example`의 변수명이 일치하는지 `rg`로 비교한다.
- 문서 변경만이면 runtime test는 생략 가능하다.

## Phase 1: 프론트 API base URL 통일

### 목표

페이지별 hardcoded localhost API 호출을 `frontend/src/utils/apiClient.js` 또는 그 exported helper로 통일한다.

### 작업

1. `frontend/src/pages/Home.jsx`, `frontend/src/pages/Login.jsx`, `frontend/src/pages/MarketSnapshot.jsx`의 `http://localhost:8000` 직접 호출을 제거한다.
2. 기존 axios 사용 패턴을 보존하되 `API_BASE_URL` 또는 shared `apiClient`를 사용한다.
3. 응답 fallback과 error UI는 기존 동작을 유지한다.
4. `frontend/src/utils/apiClient.js`가 인증 토큰이 필요한 요청과 공개 요청 모두에 자연스럽게 쓰일 수 있는지 점검한다.

### 예상 변경 파일

- `frontend/src/utils/apiClient.js`
- `frontend/src/pages/Home.jsx`
- `frontend/src/pages/Login.jsx`
- `frontend/src/pages/MarketSnapshot.jsx`
- `docs/harness/features/frontend-routing-shell.md`
- `docs/harness/features/market-data.md`
- `docs/harness/features/authentication.md`
- 신규 change record under `docs/harness/`

### 검증

```powershell
cd frontend
npm run lint
npm run build
```

가능하면 dev server에서 `/`, `/login`, `/market/:ticker`를 열어 네트워크 요청 origin이 `VITE_API_BASE_URL` 또는 기본 `API_BASE_URL`을 따르는지 확인한다.

## Phase 2: 배포 런타임 smoke checklist 확정

### 목표

Vercel frontend, persistent FastAPI backend, Supabase PostgreSQL 조합에서 첫 smoke release를 반복 가능하게 만든다.

### 작업

1. hosted backend provider 후보와 production/staging origin 형식을 결정한다.
2. Supabase direct connection과 pooler mode를 각각 SQLAlchemy asyncpg로 검증한다.
3. `ENABLE_DB_SCHEMA_BOOTSTRAP=false` 상태에서 `python -m alembic upgrade head` 후 backend startup check를 수행한다.
4. 첫 smoke에서는 `ENABLE_MARKET_WARMUP=false`, `ENABLE_SCHEDULER=false`, `ENABLE_NOTIFICATION_SCHEDULER=false`로 시작한다.
5. `/health`, `/db-check`, CORS credentialed request, frontend route refresh를 smoke matrix에 넣는다.

### 예상 변경 파일

- `docs/harness/features/deployment-runtime.md`
- `backend/DEVELOPMENT_DIRECTION.md` if runtime commands change
- `frontend/DEVELOPMENT_DIRECTION.md` if Vercel setup steps change
- 신규 verification record under `docs/harness/`

### 검증

```powershell
cd backend
python -m alembic upgrade head
python -m pytest tests/test_subscription_service.py tests/test_subscription_api.py tests/test_report_access_api.py tests/test_chat_api.py
```

그리고 backend smoke:

- `GET /health`
- `GET /db-check`

Secret이나 원본 DB URL은 로그나 문서에 복사하지 않는다.

## Phase 3: 결제 provider와 구독 정책 확정

### 목표

Plus/Pro entitlement를 mock 경계에서 production 결제 흐름으로 전환할 수 있도록 product decision과 provider integration 계획을 확정한다.

### 먼저 필요한 결정

1. Provider: Toss Payments Billing, PortOne, Stripe 등 KRW recurring payment 가능 provider 중 선택.
2. Plus 1,000 KRW, Pro 3,000 KRW가 VAT 포함 최종 가격인지 결정.
3. 취소 시 `current_period_end`까지 권한을 유지할지 결정.
4. failed renewal, retry, grace period, refund, downgrade 정책을 결정.
5. local smoke는 provider sandbox, seed fixture, test-only DB row 중 어느 경로로 할지 결정.

### 작업

1. provider-specific adapter를 `payment_service.py` 또는 `backend/app/services/payments/` 하위로 분리한다.
2. webhook signature verification과 idempotent `BillingEvent` 처리를 provider별로 테스트한다.
3. `/billing/success`는 webhook 반영 전 pending state를 유지한다.
4. 취소, 실패 결제, downgrade, refund 정책을 backend entitlement service에 반영한다.

### 예상 변경 파일

- `backend/app/services/payment_service.py` or `backend/app/services/payments/`
- `backend/app/services/subscription_service.py`
- `backend/app/api/billing.py`
- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/alembic/versions/`
- `backend/tests/test_payment_service.py`
- `backend/tests/test_billing_webhook_api.py`
- `backend/tests/test_subscription_service.py`
- `frontend/src/pages/Pricing.jsx`
- `frontend/src/pages/BillingSuccess.jsx`
- `frontend/src/pages/BillingCancel.jsx`
- `frontend/src/store/subscriptionStore.js`
- `docs/harness/features/subscription-billing.md`

### 검증

```powershell
cd backend
python -m pytest tests/test_subscription_service.py tests/test_subscription_api.py tests/test_payment_service.py tests/test_billing_webhook_api.py tests/test_report_access_api.py tests/test_chat_api.py
```

```powershell
cd frontend
npm run lint
npm run build
```

Manual smoke:

- Free user checkout attempt
- Plus checkout success pending -> active
- Pro checkout success pending -> active
- duplicate webhook
- invalid webhook signature
- canceled at period end
- expired entitlement revoked

## Phase 4: 리포트 coverage 정책 결정과 유료 UX 개선

### 목표

유료 사용자가 보고서 권한을 가져도 저장 리포트가 없어 pending만 보는 상황을 product policy로 다룬다.

### 반드시 유지할 규칙

사용자-facing page load, button click, chatbot message, notification job은 `POST /api/ai/generate/{ticker}` 또는 LLM-backed generation을 직접 호출하지 않는다. 저장된 scheduled report만 읽는다.

### 선택지

1. Conservative 유지
   - 대표 ticker만 scheduled generation.
   - pending UI를 더 명확히 개선한다.
   - 비용과 rate limit 위험이 낮다.
2. Tier-aware coverage
   - paid 사용자들이 자주 조회하거나 즐겨찾기한 ticker를 scheduler target 후보로 올린다.
   - 사용자 요청이 직접 생성하지는 않고, 다음 scheduler run에서 처리한다.
   - 비용 증가와 privacy 정책 검토가 필요하다.
3. Full configured coverage
   - 기본 market cache ticker 전체를 주기적으로 생성한다.
   - LLM/API 비용과 provider quota 정책 승인 전에는 진행하지 않는다.

### 권장 접근

Phase 4의 첫 구현은 Conservative를 유지하면서 다음을 개선한다.

1. pending report UI에 scheduler coverage와 다음 생성 정책을 더 명확히 표시한다.
2. 저장 리포트가 없는 ticker 목록과 요청 빈도를 backend에서 관찰 가능한 metadata로 집계할지 결정한다.
3. 이후 별도 승인으로 Tier-aware coverage를 검토한다.

### 예상 변경 파일

- `backend/app/services/ai_service.py`
- `backend/app/main.py`
- `backend/app/core/config.py`
- `frontend/src/pages/AssetDetail.jsx`
- `frontend/src/components/ReportCard.jsx`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/market-data.md`
- `docs/harness/features/chatbot-assistant.md`

### 검증

- Mocked scheduler tests only.
- `POST /api/ai/generate/{ticker}`가 ordinary user path에서 호출되지 않는지 API/UI flow를 점검한다.
- No live broad report generation unless explicitly approved.

## Phase 5: AI 리포트 품질 추적 고도화

### 목표

현재 deterministic quality gate를 유지하면서, 사용자가 보는 저장 리포트의 출처, 한계, 검증 상태를 더 신뢰할 수 있게 만든다.

### 작업

1. raw provider payload를 저장할지 여부를 privacy/storage 관점에서 결정한다.
2. raw payload를 저장하지 않는다면 normalized evidence row 또는 hashed source reference 형태를 검토한다.
3. qualitative checker의 high-risk claim categories를 확장하되 과도한 false positive를 피한다.
4. asset framework section의 분석 깊이 검증을 section parser 기반으로 강화한다.
5. independent Bull/Bear/Risk LLM critics는 비용 승인 전까지 비활성 상태로 유지한다.

### 예상 변경 파일

- `backend/app/services/ai_service.py`
- `backend/app/services/graph/state.py`
- `backend/app/services/graph/nodes.py`
- `backend/app/services/graph/graph.py`
- `backend/tests/test_ai_report_quality_gate.py`
- `docs/harness/features/asset-detail-ai-community.md`
- 신규 change record under `docs/harness/`

### 검증

- LLM call 없는 unit tests 우선.
- blocked/limited/ready path regression test.
- qualitative unsupported claim fail/pass tests.
- live LLM smoke는 사용자 승인 후 단일 ticker로 제한한다.

## Phase 6: 알림 기능 운영화

### 목표

현재 prototype/manual 성격의 Telegram/email 연결을 운영 가능한 notification delivery로 개선한다.

### 작업

1. Telegram bot webhook 또는 polling 방식 중 하나를 선택한다.
2. Telegram `chat_id` 연결 flow를 사용자가 이해 가능한 방식으로 정리한다.
3. email verification code를 API 응답으로 돌려주는 prototype 흐름에서 실제 email 발송과 confirmation link/code 방식으로 전환한다.
4. delivery retry, rate limit, cooldown, unsubscribe, failed event retention 정책을 정한다.
5. notification scheduler를 hosted runtime에서 언제 켤지 smoke checklist에 연결한다.

### 예상 변경 파일

- `backend/app/api/notifications.py`
- `backend/app/services/notification_service.py`
- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/alembic/versions/` if schema changes
- `frontend/src/pages/MyPage.jsx`
- `frontend/src/pages/NotificationsSettings.jsx` if route split returns
- `docs/harness/features/favorite-asset-notifications.md`
- `docs/harness/features/mypage-profile.md`

### 검증

```powershell
cd backend
python -m pytest tests/test_notifications_api.py tests/test_notification_service.py
```

```powershell
cd frontend
npm run lint
npm run build
```

Provider sandbox 또는 test adapter로 channel verification, delivery success, delivery failure, retry suppression을 확인한다.

## Phase 7: `AssetDetail.jsx` 책임 분리

### 목표

자산 상세 화면의 변경 리스크를 낮추고, 리포트/커뮤니티/차트/시장 컨텍스트 수정이 서로 덜 얽히게 만든다.

### 권장 분리 단위

1. `AssetHeader`
   - 이름, ticker, category, favorite toggle, entitlement badge.
2. `AssetMarketSummary`
   - 가격, 변화율, market metadata.
3. `AssetHistoryPanel`
   - 기간 선택, chart loading/error.
4. `LatestContextPanel`
   - latest news/calendar context.
5. `ReportAccessPanel`
   - paywall, pending, stored report fetch state.
6. `CommunitySection`
   - comments, create/edit/delete/like/report flow.

### 예상 변경 파일

- `frontend/src/pages/AssetDetail.jsx`
- new components under `frontend/src/components/` or `frontend/src/components/asset-detail/`
- `frontend/src/components/ReportCard.jsx` if report panel contract changes
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/frontend-routing-shell.md`

### 검증

```powershell
cd frontend
npm run lint
npm run build
```

Manual smoke:

- `/detail/005930.KS`
- unauthenticated comment read
- nickname-required comment write
- Free report paywall
- Plus/Pro stored report fetch or pending state
- favorite toggle
- comment like/report

## Phase 8: 테스트와 smoke matrix 보강

### 목표

문서상 manual smoke에 의존하는 흐름을 자동화 가능한 최소 회귀 세트로 만든다.

### 작업

1. Backend focused tests는 기능별로 계속 유지한다.
2. Frontend는 최소한 다음 흐름을 component 또는 browser smoke로 검증한다.
   - login page renders GIS container and error state.
   - pricing CTA states by auth/subscription state.
   - chatbot launcher visible only for Pro.
   - asset detail paywall/pending/report states.
   - MyPage nickname and notification consent states.
3. Full smoke matrix를 `docs/harness/`에 별도 verification template로 만든다.

### 예상 변경 파일

- frontend test setup files if a frontend test framework is selected
- selected frontend component tests
- `docs/harness/features/frontend-routing-shell.md`
- `docs/harness/features/subscription-billing.md`
- `docs/harness/features/chatbot-assistant.md`
- `docs/harness/features/asset-detail-ai-community.md`

### 검증

테스트 도구 선택 전에는 `npm run lint`, `npm run build`를 기준으로 유지한다. 새 frontend test framework 도입은 dependency 변경이므로 사용자 확인 후 진행한다.

## 권장 실행 순서

1. Phase 0: 문서와 `.env_example` 정합성 정리.
2. Phase 1: 프론트 API base URL 통일.
3. Phase 2: DB 포함 hosted smoke checklist 확정.
4. Phase 3: 결제 provider와 구독 정책 확정 및 구현.
5. Phase 4: 유료 리포트 coverage 정책 결정.
6. Phase 6: 알림 delivery 운영화.
7. Phase 7: `AssetDetail.jsx` 분해.
8. Phase 8: frontend/browser smoke 자동화.
9. Phase 5: 리포트 품질 추적 고도화는 비용과 데이터 정책 승인 이후 병행한다.

## 승인 필요 항목

다음은 구현 전 사용자 또는 product owner 확인이 필요하다.

- Production payment provider 선택과 provider 계정/dashboard 설정.
- VAT, refund, downgrade, failed renewal, grace period 정책.
- Scheduler coverage를 대표 ticker 이상으로 넓히는 변경.
- LLM critics 또는 live broad report generation처럼 token/API 비용이 증가하는 변경.
- Telegram/email provider를 실제 운영 발송으로 연결하는 변경.
- Frontend test framework 신규 도입.
- DB schema 변경이 필요한 모든 작업.

## 완료 기준

- `.env_example`과 설정 문서가 현재 config와 일치한다.
- hosted smoke release checklist가 secret 없이 재현 가능하다.
- 프론트 API origin이 `VITE_API_BASE_URL`/shared client로 통일된다.
- production payment provider와 subscription lifecycle이 테스트된다.
- paid report pending UX와 scheduler coverage 정책이 명확해진다.
- notification verification/delivery가 prototype 응답 방식에서 운영 발송 방식으로 전환된다.
- `AssetDetail.jsx`의 주요 책임이 독립 컴포넌트로 분리된다.
- 백엔드 focused tests와 프론트 build/lint, 필요한 manual smoke 결과가 각 change record에 남는다.

## 이번 계획서 작성에서 수행한 검증

- `git status --short`
- `docs/harness/feature-documentation-guide.md` 확인
- `docs/harness/backend-verification-db-runtime-plan-2026-06-01.md` 확인
- `docs/harness/feature-index.md` 확인

코드 실행, lint, build, pytest는 수행하지 않았다. 이번 작업은 계획 문서 작성과 링크 갱신만 목표로 한다.

## 후속 위험

- 이 계획은 여러 기능 영역을 가로지르므로 한 번에 모두 구현하면 회귀 위험이 크다.
- 결제, scheduler coverage, LLM critics, notification provider는 비용과 운영 리스크가 있어 별도 승인 없이 구현하면 안 된다.
- `.env`나 provider dashboard 값은 문서화 대상이 아니다. 변수명만 기록해야 한다.
- 기존 데이터베이스는 Alembic migration 상태와 runtime bootstrap 설정이 다를 수 있으므로 hosted 검증 전에 반드시 migration 상태를 확인해야 한다.
