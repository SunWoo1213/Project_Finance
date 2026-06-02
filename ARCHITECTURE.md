# Project Finance 아키텍처

Date: 2026-06-02

`Project_Finance`는 시장 데이터, 저장된 AI 투자 리포트, 인증, 구독 권한, 커뮤니티 댓글, 인앱 챗봇을 제공하는 풀스택 금융 웹 애플리케이션이다. 현재 구현이 기준이며, 프론트엔드는 React + Vite + JavaScript, 백엔드는 FastAPI + async SQLAlchemy 구조로 동작한다.

이전 계획 문서에는 Next.js, TypeScript, `uv`가 언급될 수 있지만, 현재 활성 애플리케이션 구조는 아니다.

## 런타임 구조

```text
Browser
  -> React/Vite frontend (`frontend/`)
  -> FastAPI backend (`backend/app/`)
  -> PostgreSQL (`docker-compose.yml` for local DB)
  -> external data and AI services
```

- Frontend: React 19, Vite, JavaScript, Tailwind CSS, Zustand, React Router, Axios, Recharts, React Markdown.
- Backend: Python, FastAPI, async SQLAlchemy, Alembic, APScheduler, Pydantic settings.
- AI/report pipeline: LangGraph, LangChain, OpenAI 호환 설정, deterministic quality checks, optional LLM critics.
- Data sources: `yfinance`, macro/bond/commodity helpers, 설정된 경우 search/context providers.
- Database: 일반 런타임은 PostgreSQL을 사용하며, 일부 테스트는 SQLite를 사용한다.

## 저장소 구조

```text
Project_Finance/
|-- backend/
|   |-- app/
|   |   |-- api/               # Auth, billing, community, chatbot routers and dependencies
|   |   |-- core/              # Settings, security, cache
|   |   |-- db/                # Async engine/session and SQLAlchemy Base
|   |   |-- services/          # Market, macro, AI report, chatbot, billing logic
|   |   |-- services/graph/    # LangGraph report workflow nodes/state/tools
|   |   |-- main.py            # FastAPI app, lifespan, scheduler, market/report routes
|   |   |-- models.py          # SQLAlchemy ORM models
|   |   `-- schemas.py         # Pydantic request/response models
|   |-- alembic/               # Migration environment and revisions
|   |-- tests/                 # Backend tests
|   |-- requirements.txt
|   `-- alembic.ini
|-- frontend/
|   |-- src/
|   |   |-- pages/             # Route-level screens
|   |   |-- components/        # Shared UI and feature components
|   |   |-- components/ui/     # Small reusable primitives
|   |   |-- store/             # Zustand stores
|   |   |-- utils/             # API client, constants, formatters, asset metadata
|   |   |-- App.jsx            # React Router composition and shell
|   |   `-- main.jsx           # React entrypoint
|   |-- public/                # Static public assets
|   |-- package.json
|   `-- vercel.json
|-- docs/harness/              # Harness feature docs and change records
|-- docker-compose.yml         # Local PostgreSQL service
|-- DEVELOPMENT_DIRECTION.md   # Root development guidance
|-- PROJECT_FUNCTION_DETAIL_SPEC.md
`-- test_api.py, test_db.py    # Root-level helper scripts
```

## 프론트엔드 아키텍처

`frontend/src/App.jsx`는 라우트 맵과 공통 애플리케이션 shell을 소유한다.

- `/`: 홈 대시보드.
- `/category/:type`: 카테고리별 자산 목록.
- `/market/:ticker`: 시장 스냅샷 화면.
- `/detail/:ticker`: 자산 상세, 저장된 AI 리포트, 커뮤니티 댓글.
- `/login`: Google 로그인 흐름.
- `/pricing`: 구독 플랜과 checkout UI.
- `/billing/success`, `/billing/cancel`: checkout 결과 화면.

상태는 Zustand store에 보관된다.

- `authStore.js`: 인증 토큰과 사용자 identity.
- `subscriptionStore.js`: 결제 상태와 기능 권한.
- `favoriteStore.js`: 브라우저 localStorage 기반 즐겨찾기.
- `chatStore.js`: 챗봇 대화 상태.

`frontend/src/utils/apiClient.js`는 `VITE_API_BASE_URL`을 통해 API base URL을 중앙화한다. 개발 환경에서는 기본값으로 로컬 FastAPI 서버를 사용한다.

## 백엔드 아키텍처

`backend/app/main.py`는 FastAPI app을 생성하고, CORS를 설정하며, startup check를 실행한다. 설정에 따라 market cache를 warm-up하고 APScheduler job을 시작한다.

`backend/app/api/` 아래의 router module은 기능별 API 그룹을 소유한다.

- `auth.py`: `/api/auth/google`.
- `billing.py`: `/api/billing/plans`, `/api/billing/me`, `/api/billing/checkout`, `/api/billing/cancel`, `/api/billing/webhook`.
- `community.py`: `/api/community/...` comment, like, report endpoints.
- `chat.py`: `/api/chat/message`.
- `deps.py`: authentication and entitlement dependencies.

현재 `main.py`도 market/report route를 일부 직접 소유한다.

- `/health`, `/db-check`.
- `/api/market/prices`, `/api/market/news`.
- `/api/market/latest-context/{ticker}`.
- `/api/market/history/{ticker}`.
- `/api/ai/generate/{ticker}`는 `403`을 반환한다. 사용자-facing 수동 리포트 생성은 비활성화되어 있다.
- `/api/reports/{ticker}`는 report access 권한이 있는 사용자에게 최신 저장 scheduled report를 반환한다.

비즈니스 로직은 `backend/app/services/`에 둔다. Route handler는 입력 검증, auth/entitlement 적용, service 호출, response shaping에 집중해야 한다.

## 데이터베이스 모델

주요 ORM model은 `backend/app/models.py`에 있다.

- `User`: Google 인증 기반 애플리케이션 사용자.
- `Asset`: 추적 대상 자산 metadata와 category.
- `AIReport`: 저장된 scheduled report와 품질 metadata.
- `Comment`: 자산별 커뮤니티 댓글.
- `CommentLike`: 사용자별 댓글 좋아요.
- `CommentReport`: 사용자별 댓글 신고.
- `Subscription`: payment provider 기반 구독 상태.
- `BillingEvent`: billing webhook의 idempotent processing record.

Alembic migration은 `backend/alembic/` 아래에 있다. 로컬 개발에서는 `ENABLE_DB_SCHEMA_BOOTSTRAP=true`일 때 startup 시 table bootstrap을 계속 사용할 수 있지만, production-like 환경에서는 migration을 실행하고 runtime schema bootstrap을 비활성화해야 한다.

## 백그라운드 작업과 AI 리포트

`ENABLE_SCHEDULER=true`이면 백엔드는 APScheduler job을 시작한다.

- 가격 cache refresh: 5분마다.
- 뉴스 cache refresh: 1시간마다.
- scheduled AI report generation: `REPORT_SCHEDULER_INTERVAL_HOURS`마다.
- startup 시 1회 report-generation job.

사용자-facing 요청과 챗봇 요청은 저장된 scheduled report를 읽어야 한다. 새로운 report 생성을 직접 트리거하면 안 된다. 수동 생성 endpoint는 남아 있지만, `403`을 반환하는 blocked route로만 존재한다.

## 설정 경계

백엔드 설정은 `backend/app/core/config.py`에 선언되어 있으며 환경변수에서 로드된다.

- app/runtime: `PROJECT_NAME`, `API_V1_STR`, `ENVIRONMENT`.
- database: `DATABASE_URL`, DB pool/bootstrap settings.
- CORS: `LOCAL_CORS_ORIGINS`, `BACKEND_CORS_ORIGINS`, `BACKEND_CORS_ORIGIN_REGEX`.
- auth: `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `GOOGLE_CLIENT_ID`.
- reports/scheduler: `ENABLE_MARKET_WARMUP`, `ENABLE_SCHEDULER`, `REPORT_*`, `ENABLE_LLM_REPORT_CRITICS`.
- payment boundary: `PAYMENT_PROVIDER`, `PAYMENT_*`.
- optional external APIs: `OPENAI_API_KEY`, `FRED_API_KEY`, `ECOS_API_KEY` 및 관련 provider key.

실제 secret은 commit된 파일이나 frontend 환경변수에 넣지 않는다. Frontend 설정에는 `VITE_API_BASE_URL`처럼 브라우저에 노출되어도 안전한 값만 사용해야 한다.

## 문서 맵

Harness 중심 기능 문서는 `docs/harness/` 아래에 있다.

- `docs/harness/feature-index.md`: 기능 ownership map과 필수 읽기 순서.
- `docs/harness/features/authentication.md`.
- `docs/harness/features/market-data.md`.
- `docs/harness/features/asset-detail-ai-community.md`.
- `docs/harness/features/frontend-routing-shell.md`.
- `docs/harness/features/favorites.md`.
- `docs/harness/features/chatbot-assistant.md`.
- `docs/harness/features/subscription-billing.md`.
- `docs/harness/features/deployment-runtime.md`.

기능 동작을 변경할 때는 해당 feature document를 갱신하고 `docs/harness/` 아래에 focused change record를 추가한다.
