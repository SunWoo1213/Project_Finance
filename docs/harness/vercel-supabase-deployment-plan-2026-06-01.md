# Vercel Supabase Deployment Plan

Date: 2026-06-01

## Objective

Vercel and Supabase를 사용해 `Project_Finance`를 배포하기 위한 실행 계획을 정리한다. 이 문서는 구현 계획서이며, 현재 요청 범위에서는 코드, 설정, 인프라를 변경하지 않는다.

목표 배포 형태는 다음과 같다.

- Frontend: `frontend/` React + Vite 앱을 Vercel에 배포한다.
- Database: Supabase PostgreSQL을 production/staging 데이터베이스로 사용한다.
- Backend: 현재 FastAPI 앱은 별도 persistent backend runtime에 배포하고 Supabase PostgreSQL에 연결하는 방식을 1차 권장안으로 둔다.
- Scheduler/AI report: 현재 `APScheduler`, market warm-up, AI report generation은 항상 켜져 있는 backend runtime에서 운영한다.

## Current Project Context

현재 저장소 기준의 실제 구조:

- Frontend는 `frontend/`의 React + Vite + JavaScript 앱이다.
- Vite build command는 `frontend/package.json`의 `npm run build`이고, 산출물은 기본 `dist/`이다.
- Frontend API base URL은 `frontend/src/utils/apiClient.js`에서 `VITE_API_BASE_URL`을 우선 사용하고, 없으면 `http://localhost:8000`으로 fallback한다.
- Backend는 `backend/app/main.py`의 FastAPI 앱이며, `backend/app/core/config.py`의 환경 변수 기반 settings를 사용한다.
- Database 연결은 `backend/app/db/session.py`에서 `DATABASE_URL`을 `create_async_engine()`에 직접 전달한다.
- Alembic 구성은 존재하며, `backend/alembic/env.py`가 `settings.DATABASE_URL`을 사용한다.
- 현재 startup lifespan은 `Base.metadata.create_all`과 일부 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`를 실행한다. Production에서는 이 방식을 migration 중심으로 정리해야 한다.
- CORS 허용 origin은 현재 local Vite origin만 포함한다.
- Report scheduler는 기본적으로 enabled이며, startup 시 report generation job도 등록된다.
- `docker-compose.yml`은 로컬 PostgreSQL 개발용이다. Production에서는 이 파일의 credential-like 값이나 local DB 설정을 재사용하지 않는다.

## Recommended Target Architecture

```text
User Browser
  -> Vercel CDN / Static Hosting
  -> Vite React app
  -> VITE_API_BASE_URL
  -> FastAPI backend on persistent runtime
  -> Supabase PostgreSQL

Payment Provider Webhook
  -> FastAPI backend webhook endpoint
  -> Supabase PostgreSQL subscription tables

Backend Scheduler
  -> market/news refresh
  -> scheduled AI report generation
  -> stored reports in Supabase PostgreSQL
```

### Why Not Put The Current Backend Fully On Vercel First?

Vercel can deploy Python/FastAPI as serverless functions, but the current backend is not shaped like a small request-only function app. It has:

- FastAPI lifespan database initialization.
- In-process `APScheduler`.
- Startup market cache warm-up.
- AI report jobs that may involve external data calls and LLM calls.
- SQLAlchemy async engine pooling.

Because of those runtime characteristics, the safer first production architecture is:

1. Vercel for the frontend.
2. Supabase for PostgreSQL.
3. A separate always-on backend runtime for FastAPI.

If the team later insists on Vercel for the backend too, treat that as a backend refactor project: split request handlers from scheduled jobs, remove in-process scheduler assumptions, configure Vercel Cron endpoints, and re-test database pooling behavior under serverless concurrency.

## Required Decisions Before Implementation

Do not implement deployment changes until these are confirmed.

1. Backend hosting provider:
   - Recommendation: use a persistent container/runtime host such as Render, Railway, Fly.io, AWS, GCP, Azure, or another always-on platform.
   - Reason: current scheduler and AI report pipeline expect a long-running process.

2. Environment strategy:
   - Use separate `staging` and `production` environments.
   - Do not copy local `.env` into hosted dashboards.
   - Re-enter only required environment variable names with new production values.

3. Supabase connection mode:
   - Recommended first pass for persistent backend: Supabase direct database connection with SQLAlchemy-managed pooling.
   - If serverless backend is chosen later: evaluate Supabase pooler mode and asyncpg prepared-statement compatibility before production traffic.

4. Migration policy:
   - Production schema changes should run through Alembic.
   - `Base.metadata.create_all` should not be the production schema-management mechanism.

5. Scheduler and AI cost policy:
   - Confirm whether production starts with `ENABLE_SCHEDULER=false` for first smoke deployment.
   - Confirm production values for `REPORT_SCHEDULER_INTERVAL_HOURS`, `REPORT_SCHEDULER_MAX_REPORTS_PER_RUN`, and target tickers before enabling scheduled report generation.
   - User-facing requests and chatbot requests must continue to read stored scheduled reports only; they must not trigger fresh report generation.

6. Production domains:
   - Confirm Vercel frontend domain.
   - Confirm backend API domain.
   - Add only those domains to backend CORS.

7. Auth/payment callback URLs:
   - Google OAuth allowed origins and redirect URIs must match production domains.
   - Payment provider success/cancel/webhook URLs must point to production frontend/backend routes.

## Environment Variable Inventory

### Vercel Frontend

Set these in the Vercel project for `frontend/`.

- `VITE_API_BASE_URL`: public backend API origin, for example `https://api.example.com`.

Do not put backend secrets, Supabase database passwords, JWT secrets, payment secrets, or OpenAI keys in Vercel frontend variables. Vite variables prefixed with `VITE_` are exposed to browser code.

### Backend Runtime

Set these only in the backend hosting provider.

- `PROJECT_NAME`
- `API_V1_STR`
- `DATABASE_URL`
- `SECRET_KEY`
- `GOOGLE_CLIENT_ID`
- `OPENAI_API_KEY`
- `ALPHA_VANTAGE_API_KEY`
- `FRED_API_KEY`
- `ECOS_API_KEY`
- `FMP_API_KEY`
- `FINNHUB_API_KEY`
- `ENABLE_MARKET_WARMUP`
- `ENABLE_SCHEDULER`
- `REPORT_SCHEDULER_COVERAGE`
- `REPORT_SCHEDULER_INTERVAL_HOURS`
- `REPORT_SCHEDULER_MAX_REPORTS_PER_RUN`
- `REPORT_SCHEDULER_ASSET_COOLDOWN_HOURS`
- `REPORT_SCHEDULER_TARGET_TICKERS`
- `ENABLE_LLM_REPORT_CRITICS`
- `REPORT_CRITIC_MODE`
- `PAYMENT_PROVIDER`
- `PAYMENT_WEBHOOK_SECRET`
- `PAYMENT_PLUS_PLAN_ID`
- `PAYMENT_PRO_PLAN_ID`
- Provider-specific secret keys, if selected later.

Production values must be created in the provider dashboards or secret manager. Do not document raw values in `docs/harness/`.

## Phase 1: Supabase Preparation

1. Create Supabase project.
   - Pick a region close to the primary user/backend region.
   - Use a separate staging project or separate staging database before production.

2. Collect connection strings safely.
   - Store only in backend hosting secrets.
   - Convert the URL to the SQLAlchemy async dialect format expected by the app, for example `postgresql+asyncpg://...`.
   - If using a Supabase pooler, test prepared-statement behavior with SQLAlchemy asyncpg before release.

3. Run migrations on staging.
   - From `backend/`, run Alembic against the staging Supabase database.
   - Verify subscription billing tables and existing app tables are created.
   - Avoid using production data for early smoke checks.

4. Seed or bootstrap required data.
   - Confirm whether `Asset` rows need a seed step.
   - Confirm whether existing local development data should be migrated. Default recommendation: do not migrate local dev data unless explicitly approved.

## Phase 2: Backend Production Readiness

Planned code/config changes for a future implementation pass:

1. Add production CORS origins.
   - Include the Vercel production domain and any preview/staging domain policy that the team approves.
   - Avoid wildcard origins when credentials are enabled.

2. Move schema creation to Alembic-only production behavior.
   - Keep local bootstrap convenient if needed, but gate it behind an explicit development flag.
   - Production startup should fail visibly on schema mismatch instead of silently creating partial schema.

3. Tune SQLAlchemy engine behavior for Supabase.
   - Set `echo=False` outside local debugging.
   - Add connection health options such as `pool_pre_ping` if needed.
   - If using transaction pooler mode, explicitly test prepared-statement cache settings and document the final connection mode.

4. Harden scheduler rollout.
   - First production smoke: `ENABLE_MARKET_WARMUP=false`, `ENABLE_SCHEDULER=false`.
   - After API and DB health pass, enable market warm-up.
   - Enable AI report scheduler last, with conservative coverage and max reports per run.

5. Confirm health endpoints.
   - `/health` should not require DB.
   - `/db-check` should verify Supabase connectivity without exposing connection strings or credentials.

6. Confirm payment webhook behavior.
   - Webhook endpoint should verify provider signatures.
   - Webhook logs must not include raw secrets or full payment payloads.

## Phase 3: Backend Deployment

Use a persistent backend runtime.

1. Configure build/start commands.
   - Install: `pip install -r backend/requirements.txt`
   - Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Working directory should be `backend/`, or the host must set Python path so `app.main:app` resolves.

2. Configure secrets.
   - Add backend environment variables in the host dashboard.
   - Do not upload `.env`.
   - Do not reuse local development database credentials.

3. Run migration step.
   - Preferred deployment gate: run `python -m alembic upgrade head` against the target Supabase database before starting the new release.
   - If the platform supports release commands, run migrations there.
   - Otherwise run migrations from a trusted local/CI environment with production secrets injected securely.

4. Smoke test backend.
   - `GET /health`
   - `GET /db-check`
   - `GET /api/market/prices`
   - Auth-protected endpoint with a test user when available.
   - Billing endpoints in provider-unconfigured or sandbox mode, depending on release stage.

## Phase 4: Vercel Frontend Deployment

1. Create Vercel project from the repository.
   - Root directory: `frontend`
   - Framework preset: Vite
   - Install command: `npm install`
   - Build command: `npm run build`
   - Output directory: `dist`

2. Configure frontend environment variable.
   - `VITE_API_BASE_URL` must point to the deployed FastAPI backend origin.
   - Rebuild after changing this value because Vite exposes it at build time.

3. Configure SPA routing.
   - Verify direct navigation to routes such as `/login`, `/pricing`, `/billing/success`, and `/detail/:ticker`.
   - If direct route refresh returns 404 on Vercel, add the appropriate Vercel rewrite to serve `index.html`.

4. Validate frontend behavior.
   - Login page loads.
   - Header auth state behaves correctly.
   - Market pages fetch from production backend.
   - Pricing page calls production backend.
   - Asset detail report paywall and stored report access behave according to subscription tier.

## Phase 5: External Integrations

1. Google OAuth
   - Add production frontend origin to Google OAuth settings.
   - Confirm backend verification uses the same `GOOGLE_CLIENT_ID`.
   - Test login on production domain.

2. Payment provider
   - Choose production provider before enabling real checkout.
   - Configure provider plan IDs and webhook secret only on backend runtime.
   - Set checkout success URL to Vercel `/billing/success`.
   - Set checkout cancel URL to Vercel `/billing/cancel`.
   - Set webhook URL to backend `/api/billing/webhook`.

3. OpenAI and market data providers
   - Add production API keys only to backend runtime.
   - Start scheduler with conservative limits.
   - Monitor startup and scheduled job logs for cost and rate-limit issues.

## Verification Checklist

Run the smallest meaningful checks before production promotion.

### Local/CI

- `git status --short`
- From `frontend/`: `npm run lint`
- From `frontend/`: `npm run build`
- From `backend/`: relevant `pytest` tests for auth, billing, chat, reports, and DB access.
- From `backend/`: `python -m alembic upgrade head` against a disposable staging database.

### Staging Deployment

- Backend `/health` returns ok.
- Backend `/db-check` returns DB connected.
- Backend CORS accepts the staging Vercel origin and rejects unknown origins.
- Frontend deployed on Vercel can call backend through `VITE_API_BASE_URL`.
- Direct route refresh works for Vite SPA routes.
- Google login succeeds on staging domain.
- Billing checkout remains disabled or sandbox-only until provider is confirmed.
- Free/Plus/Pro access gates work against staging data.
- User-facing report and chatbot requests do not trigger report generation.

### Production Deployment

- Production migration applied successfully.
- Backend deployed with scheduler disabled for initial smoke.
- Frontend production build points to production backend.
- `/health`, `/db-check`, market pages, login, pricing, and asset detail pass smoke checks.
- Enable market warm-up after API smoke.
- Enable report scheduler only after cost/rate-limit review.
- Confirm logs do not print secrets, raw connection strings, access tokens, or webhook secrets.

## Rollback Plan

1. Frontend rollback:
   - Promote the previous Vercel deployment if frontend routing or API URL configuration breaks.

2. Backend rollback:
   - Redeploy the previous backend image/release.
   - Keep `ENABLE_SCHEDULER=false` during incident response unless scheduler behavior is known safe.

3. Database rollback:
   - Prefer forward-only Alembic fixes for production.
   - If destructive rollback is required, stop and get explicit approval with backup/restore steps.

4. Secret incident response:
   - If any credential is exposed in logs, chat, committed files, screenshots, or deployment output, rotate it before continuing.

## Follow-Up Implementation Tasks

These tasks are intentionally not performed by this planning document.

1. Add production/staging CORS configuration.
2. Add `vercel.json` rewrite for Vite SPA routes if direct route refresh needs it.
3. Add production-safe database startup mode that relies on Alembic rather than `create_all`.
4. Tune `backend/app/db/session.py` for Supabase connection mode.
5. Add deployment notes to `backend/DEVELOPMENT_DIRECTION.md` and `frontend/DEVELOPMENT_DIRECTION.md`.
6. Add CI workflow for frontend lint/build and backend tests/migrations.
7. Add release checklist for enabling scheduler and AI report generation.

## Implementation Status

2026-06-01 구현 기록: `docs/harness/vercel-supabase-deployment-implementation-2026-06-01.md`

Implemented in code/config:

- `frontend/vercel.json` SPA rewrite for Vercel route refreshes.
- Environment-driven backend CORS settings through `BACKEND_CORS_ORIGINS`, `BACKEND_CORS_ORIGIN_REGEX`, and `LOCAL_CORS_ORIGINS`.
- `ENABLE_DB_SCHEMA_BOOTSTRAP` runtime switch so production-like startup can rely on Alembic-managed schema instead of `create_all`.
- SQLAlchemy deployment settings for `SQLALCHEMY_ECHO`, `DB_POOL_PRE_PING`, and optional `DB_PREPARED_STATEMENT_CACHE_SIZE`.
- Alembic baseline coverage for current core tables, AI report metadata columns, comments, subscriptions, and billing events.

Not executed in this implementation pass:

- No lint, build, pytest, Alembic upgrade, smoke test, or hosted deployment verification was run because the user explicitly requested implementation only and no verification.

## References Checked

- Vercel Vite framework docs: https://vercel.com/docs/frameworks/vite
- Vercel FastAPI framework docs: https://vercel.com/docs/frameworks/backend/fastapi
- Vercel Functions limits: https://vercel.com/docs/functions/limitations
- Vercel Cron Jobs docs: https://vercel.com/docs/cron-jobs
- Supabase database connection strings: https://supabase.com/docs/reference/postgres/connection-strings
- Supabase connection management: https://supabase.com/docs/guides/database/connection-management
- Supabase prepared statement troubleshooting: https://supabase.com/docs/guides/troubleshooting/disabling-prepared-statements-qL8lEL
