# CODE_UNDERSTANDING.md — 코드 이해 문서

> 최초 작성: 2026-06-10
> 목적: `Project_Finance` 저장소를 처음 보는 사람(개발자·하네스 에이전트)이 **전체 구조와 데이터 흐름을 한 번에 이해**하도록 돕는 단일 안내 문서.
> 이 문서는 요약 지도이며, 세부 규칙과 최신 변경 이력은 [AGENTS.md](AGENTS.md), [docs/harness/feature-index.md](docs/harness/feature-index.md), 각 `docs/harness/features/*.md`가 진실의 소스이다. 문서와 코드가 충돌하면 **현재 코드가 우선**한다.

---

## 1. 프로젝트 한눈에 보기

글로벌 금융 데이터·AI 투자 리포트·인증·구독 결제·커뮤니티·알림을 제공하는 **풀스택 웹 애플리케이션**이다.

| 계층 | 기술 | 위치 |
|------|------|------|
| Frontend | React 19 + Vite + JavaScript + Tailwind CSS + Zustand + React Router v7 | [frontend/](frontend/) |
| Backend | Python + FastAPI + Async SQLAlchemy | [backend/](backend/) |
| AI 파이프라인 | LangGraph + LangChain + OpenAI (gpt-4o-mini) | [backend/app/services/graph/](backend/app/services/graph/) |
| Database | PostgreSQL (운영) / SQLite (일부 테스트), Alembic 마이그레이션 | [docker-compose.yml](docker-compose.yml), [backend/alembic/](backend/alembic/) |
| 스케줄링 | APScheduler (시장 데이터 갱신, AI 리포트 생성, 알림 발송) | [backend/app/main.py](backend/app/main.py) |
| 결제 | **Toss Payments 미구현** (현재 mock 즉시 활성화만 동작) | [backend/app/services/payment_service.py](backend/app/services/payment_service.py) |
| 챗봇 | 규칙 기반(기본) + LLM(gpt-4o-mini, 선택) | [backend/app/services/chat_service.py](backend/app/services/chat_service.py) |
| 알림 | Telegram Bot API + Gmail API(OAuth) + In-app | [backend/app/services/notification_service.py](backend/app/services/notification_service.py) |
| 배포 | Frontend → Vercel, Backend → Render/Supabase(시험 중) | [VERCEL_SUPABASE_INTEGRATION_GUIDE.md](VERCEL_SUPABASE_INTEGRATION_GUIDE.md) |

> ⚠️ 주의: [ARCHITECTURE.md](ARCHITECTURE.md)에는 Next.js/TypeScript 기반 설명이 일부 남아 있으나, **실제 프론트엔드는 React + Vite + JavaScript**이다. 옛 설계 설명은 배경 자료로만 취급한다.

핵심 가치 흐름: **금융 데이터 수집 → AI 분석/리포트 → 사용자 전달 → 커뮤니티 상호작용 → 구독 수익화 → 알림**.

---

## 2. 저장소 전체 구조

```text
Project_Finance/
├─ backend/                       # FastAPI 백엔드
│  ├─ app/
│  │  ├─ api/                     # 라우터 (auth, billing, chat, community, favorites, notifications, profile)
│  │  ├─ core/                    # config, security, cache, log_sanitizer
│  │  ├─ db/                      # base.py(Base), session.py(engine, get_db)
│  │  ├─ services/                # 비즈니스 로직 (market, macro, AI, chat, payment, notification ...)
│  │  │  └─ graph/                # LangGraph AI 리포트 워크플로우
│  │  ├─ main.py                  # FastAPI 진입점 + 스케줄러 + market 라우트
│  │  ├─ models.py                # SQLAlchemy ORM 모델
│  │  └─ schemas.py               # Pydantic 요청/응답 스키마
│  ├─ alembic/versions/           # DB 마이그레이션
│  ├─ tests/                      # pytest 테스트 (23개+)
│  └─ requirements.txt
├─ frontend/                      # React + Vite 프론트엔드
│  ├─ src/
│  │  ├─ pages/                   # 라우트 단위 화면
│  │  ├─ components/              # 공유/기능 컴포넌트
│  │  ├─ store/                   # Zustand 스토어 (auth, subscription, favorite, chat)
│  │  ├─ utils/                   # apiClient, constants, formatters 등
│  │  ├─ App.jsx                  # 라우트 정의
│  │  └─ main.jsx                 # React 진입점
│  └─ package.json
├─ docs/harness/                  # 하네스 운영 문서 (기능 문서 + 변경 기록)
├─ docker-compose.yml             # PostgreSQL 서비스
├─ AGENTS.md / CLAUDE.md          # 하네스 운영 규칙 (단일 진실 소스)
├─ ARCHITECTURE.md                # 아키텍처 개요 (일부 구식)
├─ DEVELOPMENT_DIRECTION.md       # 개발 방향/주의점 (폴더별로도 존재)
└─ test_api.py, test_db.py        # 루트 검증 헬퍼 (OpenAI 키, DB 조회)
```

---

## 3. 백엔드 구조

### 3.1 진입점 — [backend/app/main.py](backend/app/main.py)

FastAPI 앱을 조립하고 lifespan에서 다음을 수행한다.

- **DB 스키마 부트스트랩** (`ENABLE_DB_SCHEMA_BOOTSTRAP`): 시작 시 필요한 테이블/컬럼 자동 생성.
- **시장 캐시 워밍업** (`ENABLE_MARKET_WARMUP`): 백그라운드에서 시세 사전 로드.
- **CORS 미들웨어**: 동적 origin 설정.
- **APScheduler (AsyncIOScheduler) 작업 등록** (아래 3.4 참고).

등록 라우터:

| Prefix | 모듈 | 담당 |
|--------|------|------|
| `/api/auth` | [auth.py](backend/app/api/auth.py) | Google OAuth 로그인 |
| `/api/profile` | [profile.py](backend/app/api/profile.py) | 프로필·닉네임 |
| `/api/billing` | [billing.py](backend/app/api/billing.py) | 구독·결제 |
| `/api/community` | [community.py](backend/app/api/community.py) | 댓글·좋아요·신고 |
| `/api/chat` | [chat.py](backend/app/api/chat.py) | 챗봇 |
| `/api/favorites` | [favorites.py](backend/app/api/favorites.py) | 즐겨찾기 |
| `/api/notifications` | [notifications.py](backend/app/api/notifications.py) | 알림 설정·채널 |

> 주의: **시장 데이터(`/api/market/*`)와 AI 리포트(`/api/reports/{ticker}`, `/api/ai/...`) 엔드포인트는 별도 라우터 파일이 아니라 [main.py](backend/app/main.py)에 직접 정의**되어 있다. 시장 데이터 라우트가 분산되어 있다는 점이 혼동 포인트다.

주요 직접 엔드포인트: `GET /health`, `GET /db-check`, `GET /api/market/prices`, `GET /api/market/news`, `GET /api/market/latest-context/{ticker}`, `GET /api/market/history/{ticker}`, `GET /api/reports/{ticker}`.

### 3.2 API 엔드포인트 요약

| 엔드포인트 | 메서드 | 인증 | 기능 |
|-----------|--------|------|------|
| `/api/auth/google` | POST | 불필요 | Google ID 토큰 검증 → JWT 발급, 신규 사용자 자동 생성 |
| `/api/profile/me` | GET | 필요 | 현재 사용자 정보 |
| `/api/profile/nickname` | PATCH | 필요 | 닉네임 설정/확정 |
| `/api/billing/plans` | GET | 불필요 | 요금제(FREE/PLUS/PRO) |
| `/api/billing/me` | GET | 필요 | 구독 상태·권한 |
| `/api/billing/checkout` | POST | 필요 | 결제 세션 생성 (mock=즉시 활성화 / toss=빌링 인증 페이지로 유도) |
| `/api/billing/checkout/{intent_id}` | GET | 필요 | Toss 빌링 인증 intent 조회 |
| `/api/billing/toss/billing-key` | POST | 필요 | **Toss 빌링키 최종화 — 현재 HTTP 501 NOT_IMPLEMENTED 반환(미구현)** |
| `/api/billing/cancel` | POST | 필요 | 구독 취소(기간 말 예약) |
| `/api/billing/webhook` | POST | 서명/검증 | 결제 웹훅 수신·기록 |
| `/api/community/{asset_id}/comments` | GET/POST | 조회 무, 작성 필요 | 댓글 (작성은 profile_complete 필요) |
| `/api/community/comments/{id}/like` | POST | 필요 | 좋아요 토글 |
| `/api/community/comments/{id}/report` | POST | 필요 | 신고 (임계치 초과 시 자동 삭제) |
| `/api/favorites` | GET/POST | 필요 | 즐겨찾기 목록/추가 |
| `/api/notifications/preferences` | GET/PUT | 필요 | 알림 수신 설정 |
| `/api/notifications/channels` | GET | 필요 | 연결된 채널 목록 |
| `/api/notifications/channels/telegram/connect`·`/verify`·(DELETE) | POST/DELETE | 필요 | Telegram 연결 코드 발급·검증·해제 |
| `/api/notifications/channels/email/verify`·`/confirm`·(DELETE) | POST/DELETE | 필요 | Email 인증코드 발송·검증·해제 |
| `/api/notifications/history` | GET | 필요 | 알림 발송 이력 |
| `/api/notifications/test` | POST | 필요 | 테스트 알림 발송 |
| `/api/chat/message` | POST | 필요 | 챗봇 메시지 (require_chatbot_access) |
| `/api/reports/{ticker}` | GET | 필요 | 저장된 AI 리포트 조회 (require_report_access) |

권한 의존성 — [backend/app/api/deps.py](backend/app/api/deps.py): `get_current_user`, `get_optional_current_user`, `get_current_entitlements`, `require_report_access`(PLUS+), `require_chatbot_access`(PRO+).

### 3.3 서비스 계층 — [backend/app/services/](backend/app/services/)

| 영역 | 파일 | 역할 |
|------|------|------|
| 시장 데이터 | [market_service.py](backend/app/services/market_service.py) | 가격/뉴스 수집·캐싱, 자산 상세 컨텍스트 |
| 가격 프로바이더 | [price_providers.py](backend/app/services/price_providers.py) | Finnhub/FMP/Coingecko/Stooq/DATA.GO.KR 통합 |
| 거시경제 | [macro_service.py](backend/app/services/macro_service.py) | 한/미 채권(ECOS, FRED), 상품 데이터 |
| 외부 API | [external_api_service.py](backend/app/services/external_api_service.py) | FMP 재무, Finnhub 뉴스, Coingecko 정규화 |
| AI 리포트 | [ai_service.py](backend/app/services/ai_service.py) | 스케줄 리포트 생성, LangGraph 호출, 품질 검사 |
| 챗봇 | [chat_service.py](backend/app/services/chat_service.py), [chat_llm.py](backend/app/services/chat_llm.py), [chat_grounding.py](backend/app/services/chat_grounding.py), [chat_tools.py](backend/app/services/chat_tools.py) | 규칙/LLM 기반 응답, grounding, 의도 감지 |
| 구독 | [subscription_service.py](backend/app/services/subscription_service.py) | 구독·권한 조회, 요금제 |
| 결제 | [payment_service.py](backend/app/services/payment_service.py) | Mock(즉시 활성화)·Toss 프로바이더, 웹훅 기록. **Toss 결제는 미구현**(아래 §5.4) |
| 알림 | [notification_service.py](backend/app/services/notification_service.py) | 설정/채널/검증, 다이제스트 생성, Gmail/Telegram 발송 |
| 즐겨찾기 | [favorite_service.py](backend/app/services/favorite_service.py) | 목록·추가·삭제·대량 import |
| 프로필 | [profile_service.py](backend/app/services/profile_service.py) | 닉네임 검증·중복 확인·업데이트 |

> 규칙: **비즈니스 로직은 서비스에, 라우트 핸들러는 얇게 유지**한다 ([AGENTS.md](AGENTS.md) §4).

### 3.4 스케줄러 (APScheduler)

| 작업 | 주기/트리거 | 조건 |
|------|-------------|------|
| `update_prices_task` | `MARKET_PRICES_REFRESH_MINUTES` (기본 5분) | 항상 |
| `update_news_task` | `MARKET_NEWS_REFRESH_MINUTES` (기본 60분) | 항상 |
| `generate_daily_reports` | `REPORT_SCHEDULER_INTERVAL_HOURS` (기본 6시간), 시작 지연 60초 | `ENABLE_AI_REPORT_GENERATION=true` |
| 다이제스트 알림 | Cron `NOTIFICATION_DIGEST_SEND_TIMES` (09:00,13:00,18:00) | `ENABLE_NOTIFICATION_SCHEDULER=true` |
| 알림 즉시 발송 | Interval `NOTIFICATION_DELIVERY_INTERVAL_MINUTES` (1분) | `ENABLE_NOTIFICATION_SCHEDULER=true` |

### 3.5 AI 리포트 파이프라인 — [backend/app/services/graph/](backend/app/services/graph/)

LangGraph 워크플로우로 다단계 분석·검증을 수행한다. 상태 정의는 [state.py](backend/app/services/graph/state.py)(`AgentState`), 노드는 [nodes.py](backend/app/services/graph/nodes.py), 그래프 조립은 [graph.py](backend/app/services/graph/graph.py), LLM은 [llm.py](backend/app/services/graph/llm.py).

```text
START
├─ financial_agent  ┐
├─ news_agent       │ (병렬 데이터 수집)
└─ macro_agent      ┘
        ↓
synthesizer_node → (bull / bear / risk_officer 병렬) → research_packet_node
        ↓
writer_node → report_format_validator → fact_checker → qualitative_claim_checker → evaluator → END
                       │ (검증 실패 시)
                       └──→ writer_node 재작성 (최대 REPORT_MAX_REVISIONS, 기본 7회)
```

품질 게이트: 포맷 검증 → 숫자 사실 검증(근거 없는 숫자 차단) → 정성적 주장 검증 → 최종 평가. 결과는 `AIReport` 테이블에 품질 메타데이터와 함께 저장된다.

> **중요 규칙** ([AGENTS.md](AGENTS.md) §14): 사용자/챗봇 요청은 리포트를 **실시간 생성하지 않는다**. 스케줄러가 만든 **저장된 리포트만 읽는다.**

### 3.6 데이터 모델 — [backend/app/models.py](backend/app/models.py)

핵심 테이블: `User`, `Asset`(category Enum), `AIReport`(품질 메타 포함), `Comment`/`CommentLike`/`CommentReport`, `Subscription`/`BillingEvent`, `UserFavoriteAsset`, `NotificationPreference`/`NotificationChannelConnection`/`NotificationRule`/`AssetNotificationSnapshot`/`NotificationEvent`.

- DB 세션/엔진: [backend/app/db/session.py](backend/app/db/session.py) (`engine`, `AsyncSessionLocal`, `get_db`).
- 선언적 Base: [backend/app/db/base.py](backend/app/db/base.py).
- 요청/응답 계약: [backend/app/schemas.py](backend/app/schemas.py) (Pydantic).

### 3.7 Core — [backend/app/core/](backend/app/core/)

- [config.py](backend/app/core/config.py): Pydantic `Settings`. DB, 인증(JWT), 시장 데이터, AI 리포트, 챗봇, 결제(Toss), 알림, 외부 API 키 등 모든 환경 변수 정의.
- [security.py](backend/app/core/security.py): `create_access_token` (JWT, HS256, 7일 만료).
- [cache.py](backend/app/core/cache.py): `market_cache` 인메모리 딕셔너리(prices, news, latest_context).
- [log_sanitizer.py](backend/app/core/log_sanitizer.py): 로그에서 민감정보 제거.

### 3.8 챗봇 — [chat_service.py](backend/app/services/chat_service.py), [chat_llm.py](backend/app/services/chat_llm.py)

엔드포인트 `POST /api/chat/message`는 `require_chatbot_access`(PRO 이상)로 보호된다. 응답은 두 경로로 생성된다.

- **LLM 경로 (선택)** — `ENABLE_LLM_CHATBOT=true`이고 `OPENAI_API_KEY`가 있을 때만 사용. [chat_llm.py](backend/app/services/chat_llm.py)가 gpt-4o-mini(`CHATBOT_LLM_MODEL`)를 structured output(`LlmChatPlan`: answer/intent/confidence/action_indices)으로 호출한다. **실패하면 무조건 규칙 경로로 폴백**한다.
- **규칙 경로 (기본)** — `is_financial_query`로 금융 질문 여부를 거르고, `detect_feature`로 의도(auth/report/community/favorite/current_page/market_summary)를 분류한 뒤 자산 후보·카테고리를 매칭해 결정적으로 답한다.

핵심 안전장치 (모두 [chat_service.py](backend/app/services/chat_service.py)·[chat_llm.py](backend/app/services/chat_llm.py)·[chat_grounding.py](backend/app/services/chat_grounding.py)):

1. **리포트 생성 금지** — 챗봇에는 리포트 생성 도구가 없다. 저장된 리포트 요약(`_summarize_report`)만 전달하며, 없으면 "아직 저장된 리포트가 없다"고 안내한다([AGENTS.md](AGENTS.md) §14 준수).
2. **Grounding 한정** — LLM은 호출부가 모은 grounding(자산 후보, 카테고리, 캐시 시세, 시장 스냅샷, 저장 리포트 요약)에 있는 사실만 쓰도록 시스템 프롬프트로 강제한다. 모르면 모른다고 답한다.
3. **수치 가드** (`CHATBOT_GROUNDING_GUARD`) — `chat_grounding.guard_answer`가 근거 없는 가격/퍼센트 수치를 감지하면 답을 다시 쓰지 않고 confidence를 낮추고 "참고용" 경고 문구를 덧붙인다.
4. **네비게이션 계약** — 액션 URL은 백엔드(호출부)가 결정적으로 만들고, LLM은 노출할 액션 인덱스만 고른다. 백엔드는 직접 화면 이동을 하지 않고 actions만 반환한다.
5. **멀티턴** — 최근 `CHATBOT_HISTORY_MAX_TURNS`(기본 10턴) 히스토리를 프롬프트에 포함. 매수·매도 단정/권유 금지, `DISCLAIMER` 부착.

비금융 질문은 `intent="non_financial"`로 정중히 거절한다.

### 3.9 알림 채널 — Gmail / Telegram / In-app

모든 알림은 [notification_service.py](backend/app/services/notification_service.py)에서 처리한다. 발송 채널은 `in_app`(즉시 sent 처리), `telegram`, `email` 세 가지다.

**채널 연결·검증 흐름** (`NotificationChannelConnection`, 코드 30분 유효):
- **Telegram** — `POST /api/notifications/channels/telegram/connect`로 인증 코드 발급 → 사용자가 봇과 대화 후 자신의 숫자 `chat_id`를 확인 → `/verify`에 코드+chat_id 제출(`verification_mode="manual_chat_id"`). 검증 성공 시 환영 알림 발송.
- **Email(Gmail)** — `POST /api/notifications/channels/email/verify`가 인증 코드를 **Gmail로 발송** → `/confirm`에 코드 제출. 검증 성공 시 환영 알림 발송.

**발송 구현**:
- **Telegram**: `https://api.telegram.org/bot<token>/sendMessage` 호출(`TELEGRAM_BOT_TOKEN` 필요).
- **Gmail**: `GMAIL_REFRESH_TOKEN`으로 OAuth access token을 갱신(`oauth2.googleapis.com/token`)한 뒤 `gmail.googleapis.com/.../messages/send`로 발송. 필요 설정: `EMAIL_FROM_ADDRESS`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, `EMAIL_PROVIDER=gmail`.
- 미설정 시 `get_delivery_configuration_status`가 누락 키를 알려주고 발송은 실패로 기록된다.

**알림 생성 로직** (`evaluate_notifications`): 즐겨찾기 자산마다 가격 변동(임계치·쿨다운), 새 뉴스(지문 비교), 새 리포트(report_id 변경)를 평가해 `NotificationEvent`를 만든다. dedupe_key로 중복을 막고, `send_pending_notifications`가 pending 이벤트를 발송하며 실패 시 최대 3회·지수 백오프로 재시도한다. 정시 다이제스트(`create_scheduled_digest_notifications`)는 즐겨찾기 요약을 묶어 보낸다.
- 발송 직전 `_normalize_app_links`가 본문의 localhost 링크를 운영 `FRONTEND_BASE_URL`로 보정한다(비개발 환경에서만).
- 한국어+English 이중 본문으로 작성된다.

> 주의: 위 평가·발송은 스케줄러(`ENABLE_NOTIFICATION_SCHEDULER=true`)가 켜졌을 때만 자동 동작한다(§3.4).

---

## 4. 프론트엔드 구조

### 4.1 진입점·라우트 — [frontend/src/main.jsx](frontend/src/main.jsx), [frontend/src/App.jsx](frontend/src/App.jsx)

| 경로 | 페이지 | 설명 |
|------|--------|------|
| `/` | [Home.jsx](frontend/src/pages/Home.jsx) | 주요 지수 + 글로벌 뉴스 대시보드 |
| `/category/:type` | [CategoryView.jsx](frontend/src/pages/CategoryView.jsx) | 카테고리별 자산 목록·검색·즐겨찾기 |
| `/market/:ticker` | [MarketSnapshot.jsx](frontend/src/pages/MarketSnapshot.jsx) | 지수 상세 스냅샷 |
| `/detail/:ticker` | [AssetDetail.jsx](frontend/src/pages/AssetDetail.jsx) | 시세 + 뉴스 + AI 리포트(구독) + 커뮤니티 |
| `/login` | [Login.jsx](frontend/src/pages/Login.jsx) | Google OAuth 로그인 |
| `/pricing` | [Pricing.jsx](frontend/src/pages/Pricing.jsx) | 요금제·구독 시작 |
| `/mypage`, `/settings/notifications` | [MyPage.jsx](frontend/src/pages/MyPage.jsx) | 프로필·수신 동의·즐겨찾기·알림 |
| `/billing/success`, `/billing/cancel`, `/billing/toss/auth` | [BillingSuccess.jsx](frontend/src/pages/BillingSuccess.jsx) 등 | 결제 결과/Toss 인증 |

App.jsx는 Header + main + ChatbotLauncher 레이아웃을 구성하고, 토큰 존재 시 구독·즐겨찾기·프로필을 동기화한다. ChatbotLauncher는 `can_use_chatbot` 권한이 있을 때만 렌더링된다.

### 4.2 상태 관리 — [frontend/src/store/](frontend/src/store/) (Zustand)

| 스토어 | 관리 상태 |
|--------|-----------|
| [authStore.js](frontend/src/store/authStore.js) | JWT token(localStorage), user 정보, login/logout |
| [subscriptionStore.js](frontend/src/store/subscriptionStore.js) | tier, status, entitlements, `fetchMe()` |
| [favoriteStore.js](frontend/src/store/favoriteStore.js) | favorites(로컬+서버 동기화), toggle/add/remove |
| [chatStore.js](frontend/src/store/chatStore.js) | 챗봇 패널 상태, messages, `sendMessage()` (최근 10턴 포함) |

### 4.3 유틸 — [frontend/src/utils/](frontend/src/utils/)

- [apiClient.js](frontend/src/utils/apiClient.js): axios 인스턴스(`API_BASE_URL = VITE_API_BASE_URL || http://localhost:8000`), `authHeader(token)`. **인터셉터 없음 — 요청마다 수동으로 인증 헤더 추가**.
- [constants.js](frontend/src/utils/constants.js): 자산명 매핑(`ASSET_NAMES`, `resolveAssetName`).
- [formatters.js](frontend/src/utils/formatters.js): 가격·백분율·시가총액·티커 포맷.
- [assetCategories.js](frontend/src/utils/assetCategories.js): UI 카테고리 결정.
- [chatContext.js](frontend/src/utils/chatContext.js): 현재 경로/ticker 기반 챗봇 컨텍스트.
- [tossPayments.js](frontend/src/utils/tossPayments.js): Toss SDK 로더.

### 4.4 주요 컴포넌트 — [frontend/src/components/](frontend/src/components/)

`Header`, `ChatbotLauncher`/`ChatbotPanel`/`ChatMessageList`/`ChatActionCard`, `ReportCard`(markdown 렌더), `Paywall`, `PlanBadge`, `SparklineChart`, `TickerChips`, `ProtectedRoute`.

### 4.5 환경 변수 (프론트)

- `VITE_API_BASE_URL`: 백엔드 주소.
- `VITE_GOOGLE_CLIENT_ID`: Google OAuth 클라이언트 ID.

---

## 5. 핵심 데이터 흐름

### 5.1 인증
```
Login.jsx (Google GSI) → credential → POST /api/auth/google
  → 백엔드: Google 토큰 검증 → 사용자 생성/조회 → JWT 발급
  → authStore.login() → localStorage 저장 → 구독/즐겨찾기/프로필 동기화
```

### 5.2 시장 데이터
```
APScheduler → market_service.update_prices_task/update_news_task → price_providers (외부 API)
  → core/cache.market_cache (인메모리)
  → GET /api/market/prices · /news · /history → 프론트 Home/CategoryView/AssetDetail
```

### 5.3 AI 리포트 (읽기 전용 소비)
```
APScheduler(6h) → ai_service.generate_daily_reports → graph_app.ainvoke (LangGraph 품질 게이트)
  → AIReport 테이블 저장
사용자: AssetDetail → GET /api/reports/{ticker} (require_report_access, PLUS+) → 저장된 리포트 표시
```

### 5.4 구독·결제 (⚠️ Toss 미구현)
```
[현재 동작하는 경로 = mock]
Pricing → POST /api/billing/checkout
  → provider=mock → activate_mock_subscription (결제 없이 즉시 Subscription ACTIVE)
  → /billing/success

[Toss 경로 = 미구현 / 미완성]
Pricing → POST /api/billing/checkout (provider=toss)
  → /billing/toss/auth 페이지로 유도 → Toss SDK requestBillingAuth
  → POST /api/billing/toss/billing-key
  → ✗ HTTP 501 NOT_IMPLEMENTED 반환 (billing.py:151-157)
```

**Toss 결제 시스템은 아직 미구현이다.** 현재 상태:
- `TossPaymentsProvider`에 빌링키 발급/청구 호출(`issue_billing_key`, `charge_billing_key`) **코드 골격은 존재**하나, 실제 구독 활성화로 이어지지 않는다.
- 빌링키 최종화 엔드포인트 `POST /api/billing/toss/billing-key`는 **HTTP 501 NOT_IMPLEMENTED**를 반환한다("승인된 billing 스키마 마이그레이션이 필요"). 즉 Toss로 카드 인증을 마쳐도 구독이 등록되지 않는다.
- Toss 웹훅(`normalize_event`)은 tier/status/subscription_id를 채우지 않아 **구독 상태 전이가 일어나지 않는다**.
- 정기 청구 스케줄러(`ENABLE_BILLING_SCHEDULER`)는 기본 비활성.
- 따라서 실사용 결제 경로는 **mock(즉시 활성화)뿐**이며, 운영에서 `PAYMENT_PROVIDER`를 비워 두면 누구나 무료로 유료 권한을 얻으므로 주의([payment_service.py](backend/app/services/payment_service.py) `resolve_payment_provider_name` 주석).
- 구독 취소(`POST /api/billing/cancel`)는 기간 말 취소 예약으로 동작한다.

> 향후 Toss 결제를 완성하려면 billingKey·갱신 상태 저장용 스키마 마이그레이션 → `billing-key` 최종화 구현 → 웹훅 정규화·구독 전이 연결 순으로 작업해야 한다.

### 5.5 알림 (Gmail / Telegram / In-app)
```
APScheduler(ENABLE_NOTIFICATION_SCHEDULER=true) →
  evaluate_notifications: 즐겨찾기별 가격변동/뉴스/리포트 평가 → NotificationEvent(pending)
  create_scheduled_digest_notifications: 정시 요약 묶음
        ↓
  send_pending_notifications →
    Telegram Bot API (sendMessage)
    Gmail API (OAuth refresh → messages/send)
    In-app (즉시 sent)
  실패 시 최대 3회·지수 백오프 재시도, dedupe_key로 중복 차단
사용자: MyPage → 채널 연결·검증(코드 30분), 수신 동의(preferences) 설정
```
세부 구현은 §3.9 참고.

---

## 6. 빌드·실행·검증 명령

저장소 루트에서 실행한다 (Windows + PowerShell).

```powershell
# DB
docker compose up -d db

# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
pytest

# Frontend
cd frontend
npm install
npm run lint
npm run build
npm run dev
```

변경 범위에 맞는 최소 검증 세트를 사용한다([AGENTS.md](AGENTS.md) §6):
- 백엔드 API/서비스 → 관련 `pytest`.
- 프론트 → `npm run lint`, `npm run build`.
- 교차 변경 → 양쪽 모두.
- DB 의존 → PostgreSQL 먼저 기동.

루트 헬퍼: [test_api.py](test_api.py)(OpenAI 키/LangChain 연결), [test_db.py](test_db.py)(DB 조회·ORM 동작).

---

## 7. 작업 시 반드시 지킬 규칙 (요약)

상세는 [AGENTS.md](AGENTS.md)·[CLAUDE.md](CLAUDE.md)가 진실의 소스다.

1. `.env` 및 모든 시크릿(API 키, DB 비밀번호, JWT secret)을 출력·복사·커밋하지 않는다.
2. 사용자 변경을 되돌리거나 파괴적 git 명령, 파일 삭제, DB/볼륨 드롭을 임의로 하지 않는다.
3. 사용자/챗봇 요청은 AI 리포트를 실시간 생성하지 않는다. 저장된 스케줄 리포트만 읽는다([AGENTS.md](AGENTS.md) §14).
4. 문서와 코드가 충돌하면 현재 코드를 기준으로 판단하고 구식 문서를 갱신한다.
5. 비즈니스 로직은 서비스에, 라우트는 얇게. 기존 비동기 SQLAlchemy 패턴과 React+Vite 스타일을 유지한다.
6. 코드를 의미 있게 바꾸면 `docs/harness/`에 한국어 변경 기록을 남기고 관련 feature 문서·`feature-index.md`를 갱신한다.

---

## 8. 이 문서의 유지보수 규칙 (하네스 엔지니어링 연동)

**이 문서(`CODE_UNDERSTANDING.md`)는 저장소의 구조·데이터 흐름을 설명하는 상위 지도이므로, 코드 구조가 바뀌면 반드시 함께 최신화한다.** 하네스 워크플로우(plan → implement → verify → 문서화)의 문서화 단계에서 다음을 점검한다.

다음 변경이 발생하면 **이 문서를 갱신해야 한다**:

- **라우트/엔드포인트 추가·삭제·경로 변경** → §3.1, §3.2, §4.1 갱신.
- **서비스/모듈 추가·이동·삭제** → §3.3, §3.5 및 §2 구조 트리 갱신.
- **데이터 모델(테이블/주요 필드) 변경** → §3.6 갱신.
- **스케줄러 작업/주기 변경** → §3.4 갱신.
- **Zustand 스토어·핵심 유틸·페이지 변경** → §4 갱신.
- **데이터 흐름(인증/시장/리포트/결제/알림)의 동작 방식 변경** → §5 갱신.
- **기술 스택·빌드/실행 명령 변경** → §1, §6 갱신.

갱신 절차 (기존 하네스 규율과 동일하게 동작):

1. 코드 변경과 함께 이 문서의 해당 절을 수정한다. **문서화 없이 의미 있는 코드 변경을 끝내지 않는다.**
2. 같은 변경에 대해 [docs/harness/](docs/harness/)에 한국어 변경 기록을 남기고, 관련 `docs/harness/features/*.md`와 [docs/harness/feature-index.md](docs/harness/feature-index.md)를 갱신한다(상세: [docs/harness/feature-documentation-guide.md](docs/harness/feature-documentation-guide.md)).
3. 이 문서 상단의 "최초 작성" 줄 아래에 필요하면 마지막 갱신일을 적고, 변경 기록 링크를 §9에 추가한다.
4. 시크릿·환경 변수 실제 값은 적지 않는다. 변수 이름만 문서화한다.

> 이 규칙은 [CLAUDE.md](CLAUDE.md)의 "문서 동기화 규율" 절에도 연결되어 있다.

---

## 9. 변경 기록 (이 문서의 이력)

- 2026-06-10: 최초 작성. 전체 구조·데이터 흐름 정리. (변경 기록: [docs/harness/code-understanding-doc-2026-06-10.md](docs/harness/code-understanding-doc-2026-06-10.md))
- 2026-06-10: 챗봇(§3.8)·알림 Gmail/Telegram(§3.9) 상세 보강, Toss 결제 미구현 상태 명시(§1, §3.2, §3.3, §5.4). (변경 기록: [docs/harness/code-understanding-doc-chatbot-notification-toss-2026-06-10.md](docs/harness/code-understanding-doc-chatbot-notification-toss-2026-06-10.md))
