# Deployment And Hosted Runtime Feature Notes

Date: 2026-06-01

## Current Behavior

The first supported hosted shape is Vercel for the React Vite frontend, Supabase PostgreSQL for the database, and a separate persistent FastAPI backend runtime. The backend keeps long-running process assumptions for `APScheduler`, market cache warm-up, and scheduled AI report generation. Scheduled AI report generation can be disabled independently with `ENABLE_AI_REPORT_GENERATION=false`.

Vercel serves the frontend from `frontend/` and uses `frontend/vercel.json` to rewrite direct SPA route refreshes to `index.html`.

Backend CORS is configured from environment variables instead of hardcoded production domains. Local Vite origins remain enabled by default for development, and production/staging origins should be supplied through hosted backend secrets.

The backend can still bootstrap local schemas with `Base.metadata.create_all` when `ENABLE_DB_SCHEMA_BOOTSTRAP=true`. Production-like deployments should set `ENABLE_DB_SCHEMA_BOOTSTRAP=false`, run Alembic migrations first, and let startup fail if required tables or AI report metadata columns are missing.

Local Docker PostgreSQL reads `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, and `POSTGRES_PORT` from `.env` through Compose interpolation. `DATABASE_URL` must be kept aligned with the same local DB values and must use an async SQLAlchemy scheme. PostgreSQL runtime uses `postgresql+asyncpg://`; tests may use `sqlite+aiosqlite://`.

`/health` is app liveness only and does not test the database. `/db-check` is the readiness check for DB connectivity and returns a sanitized source/scheme/host/port diagnostic without exposing credentials.

Runtime logging avoids leaking secrets in two layers. (1) Root logging stays at INFO, but `httpx`, `httpcore`, and `sqlalchemy.engine` loggers are forced to `WARNING` in `backend/app/main.py` so external request URLs (which carry provider API keys in their query strings) and SQL echo statements are not printed at INFO. (2) Because application loggers still emit external exceptions at WARNING/ERROR and those exception strings embed the full request URL, `backend/app/core/log_sanitizer.py` provides `redact_secrets()`, which masks sensitive query-param values (and literal secrets such as the ECOS key carried in the URL path) before logging. It is applied to provider/macro exception logs (`price_providers.py`, `macro_service.py`) and to the `/api/market/history` 500 handler `detail` in `main.py` so a FRED `HTTPStatusError` cannot leak `api_key` in the HTTP response body. `SQLALCHEMY_ECHO` defaults to false and should stay false in production. Any provider key that appeared in logs before these guards is treated as compromised and must be rotated at the issuer with Render env vars updated (operational task); the 2026-06-03 runtime logs confirmed the data.go.kr `serviceKey` was exposed.

## Ownership Map

- Deployment plan: `docs/harness/vercel-supabase-deployment-plan-2026-06-01.md`
- Vercel Supabase integration guide: `VERCEL_SUPABASE_INTEGRATION_GUIDE.md`
- Supabase console task checklist: `docs/harness/supabase-console-tasks-2026-06-03.md`
- Vercel Supabase next plan: `docs/harness/vercel-supabase-integration-next-plan-2026-06-03.md`
- Local Docker DB: `docker-compose.yml`, `.env_example`, `ENVIRONMENT_VARIABLE_SETUP.md`
- Environment variable acquisition guide: `ENVIRONMENT_VARIABLE_SETUP.md` section `2.1 변수값 확보를 시작하기 전에`
- Environment variable first-read summary: `ENVIRONMENT_VARIABLE_SETUP.md` section `0. 처음 보는 사람을 위한 핵심 요약`
- Vercel SPA routing: `frontend/vercel.json`
- Frontend API origin: `frontend/src/utils/apiClient.js`
- Backend runtime settings: `backend/app/core/config.py`
- Backend CORS, startup checks, and logger-level guard: `backend/app/main.py`
- Log/exception secret masking: `backend/app/core/log_sanitizer.py`
- Backend SQLAlchemy engine: `backend/app/db/session.py`
- Alembic schema baseline: `backend/alembic/versions/20260601_0001_add_subscription_billing_tables.py`
- Backend deployment guidance: `backend/DEVELOPMENT_DIRECTION.md`
- Frontend deployment guidance: `frontend/DEVELOPMENT_DIRECTION.md`

## Data Flow

1. Browser traffic reaches the Vercel-hosted Vite app.
2. The frontend reads `VITE_API_BASE_URL` at build time and sends API requests to the deployed backend origin.
3. The backend accepts credentialed requests only from local origins plus configured `BACKEND_CORS_ORIGINS` or `BACKEND_CORS_ORIGIN_REGEX`.
4. The persistent backend connects to Supabase PostgreSQL through `DATABASE_URL`.
5. Hosted releases should run `python -m alembic upgrade head` before app startup.
6. With `ENABLE_DB_SCHEMA_BOOTSTRAP=false`, backend startup checks for required tables and AI report metadata columns without creating or altering schema.
7. Scheduler and market warm-up remain controlled by `ENABLE_SCHEDULER`, `ENABLE_MARKET_WARMUP`, `ENABLE_AI_REPORT_GENERATION`, and report scheduler environment variables.
8. Favorite notification scheduler is controlled separately by `ENABLE_NOTIFICATION_SCHEDULER`, which defaults to false. Provider secrets for Telegram/Gmail email delivery are backend-only environment variables.
9. AI report generation is separated from scheduler startup through `ENABLE_AI_REPORT_GENERATION`. Hosted smoke can run `ENABLE_SCHEDULER=true`, `ENABLE_AI_REPORT_GENERATION=false` to verify price/news jobs while skipping LLM-backed report generation.

Local Docker flow:

1. `.env` supplies `POSTGRES_*` variables for the `db` service.
2. The same local DB identity is represented in `DATABASE_URL`.
3. `docker compose up -d db` initializes a new `postgres_data` volume only on first creation.
4. Existing `postgres_data` volumes keep their original DB identity until explicitly migrated or deleted.

## Contracts

- Frontend public env:
  - `VITE_API_BASE_URL`
- Backend deployment env:
  - `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT`: local docker-compose PostgreSQL initialization values. These are local runtime values and must not be committed with real secrets.
  - `DATABASE_URL`: async SQLAlchemy database URL. PostgreSQL URLs are normalized from `postgresql://` or `postgres://` to `postgresql+asyncpg://`; tests may use `sqlite+aiosqlite://`. Surrounding quotes and leading/trailing whitespace are stripped before scheme detection, and an unsupported scheme is reported with the detected scheme in the error (no credentials). Set the DB connection string here, not the Supabase `https://` API URL.
  - `POSTGRES_URL_NON_POOLING`, `POSTGRES_URL`: optional Vercel/Supabase fallback database URLs used only when `DATABASE_URL` is absent. `POSTGRES_URL_NON_POOLING` is preferred before `POSTGRES_URL`. `/db-check` returns the selected variable name as `database.source` without exposing the URL value.
  - `ENVIRONMENT`: runtime label such as `development`, `staging`, or `production`.
  - `BACKEND_CORS_ORIGINS`: comma-separated exact origins such as a Vercel production domain and staging domain.
  - `BACKEND_CORS_ORIGIN_REGEX`: optional regex for approved preview-origin policy.
  - `LOCAL_CORS_ORIGINS`: comma-separated local dev origins, defaults to Vite localhost origins.
  - `ENABLE_DB_SCHEMA_BOOTSTRAP`: keep true for local convenience; set false for migration-managed hosted runtime.
  - `SQLALCHEMY_ECHO`: default false so production does not log SQL statements.
  - `DB_POOL_PRE_PING`: default true for connection health checks.
  - `DB_PREPARED_STATEMENT_CACHE_SIZE`: optional asyncpg prepared-statement cache override for pooler compatibility testing.
  - `ENABLE_NOTIFICATION_SCHEDULER`: enables favorite notification evaluation/delivery jobs when true.
  - `ENABLE_AI_REPORT_GENERATION`: backend-only switch for scheduled/background AI report generation. When false, report scheduler jobs are not registered and direct service calls return before DB/provider/LLM generation work; stored report reads still work.
  - `NOTIFICATION_EVALUATION_INTERVAL_MINUTES`, `NOTIFICATION_DELIVERY_INTERVAL_MINUTES`, `NOTIFICATION_DEFAULT_PRICE_THRESHOLD_PERCENT`, `NOTIFICATION_DEFAULT_COOLDOWN_MINUTES`: notification scheduler and default rule controls.
  - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `EMAIL_PROVIDER`, `EMAIL_FROM_ADDRESS`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`: backend-only delivery configuration names. Email delivery supports Gmail API only.

## Change Rules

- Do not place backend secrets in Vercel frontend variables. Only `VITE_` values intended for browser exposure belong in the frontend host.
- Do not use wildcard CORS origins with credentials enabled.
- Do not enable production scheduler or AI report generation broadly until cost and rate-limit policy are confirmed.
- Do not rely on `create_all` for production schema changes. Add Alembic revisions for schema changes and run migrations before deploying.
- Do not expose database URLs, provider secrets, access tokens, or webhook secrets in logs or harness records.
- Do not raise `httpx`/`httpcore`/`sqlalchemy.engine` logger levels back to INFO/DEBUG in production, because external request URLs carry provider API keys in query strings and SQL echo can expose sensitive queries.
- Do not treat `/health` as database readiness. Use `/db-check` for DB connectivity.
- Do not delete or recreate Docker volumes without explicit confirmation because named volumes can contain local data.

## Verification

- User explicitly requested no verification for the 2026-06-01 implementation pass.
- User explicitly requested no verification for the 2026-06-02 Docker database compatibility implementation pass.
- For configuration-only updates, compare `.env_example` variable names against `backend/app/core/config.py` and confirm only placeholders, not secrets, are documented.
- When `.env_example` gains a variable, update `ENVIRONMENT_VARIABLE_SETUP.md` with how to obtain or decide that value, including whether it is backend-only, frontend-public, generated locally, or provider-issued.
- Future checks should include frontend lint/build, backend tests, Alembic migration against a disposable database, `/health`, `/db-check`, and CORS smoke checks.

## Change Records

- `docs/harness/vercel-supabase-deployment-plan-2026-06-01.md`
- `docs/harness/vercel-supabase-deployment-implementation-2026-06-01.md`
- `docs/harness/vercel-supabase-integration-next-plan-2026-06-03.md`
- `docs/harness/vercel-supabase-integration-documentation-2026-06-03.md`
- `docs/harness/vercel-supabase-integration-start-2026-06-03.md`
- `docs/harness/vercel-supabase-db-diagnostics-2026-06-03.md`
- `docs/harness/supabase-console-tasks-2026-06-03.md`
- `docs/harness/supabase-asyncpg-url-normalization-2026-06-03.md`
- `docs/harness/render-database-url-quote-normalization-2026-06-03.md`
- `docs/harness/favorite-asset-notification-implementation-2026-06-02.md`
- `docs/harness/project-gap-remediation-plan-2026-06-02.md`
- `docs/harness/project-gap-remediation-phase0-1-implementation-2026-06-02.md`
- `docs/harness/project-defect-remediation-plan-2026-06-02.md`
- `docs/harness/env-setup-guide-documentation-2026-06-02.md`
- `docs/harness/env-setup-guide-detail-improvement-2026-06-03.md`
- `docs/harness/docker-database-compatibility-remediation-plan-2026-06-02.md`
- `docs/harness/docker-database-compatibility-implementation-2026-06-02.md`
- `docs/harness/gmail-only-email-notification-implementation-2026-06-02.md`
- `docs/harness/report-generation-env-switch-plan-2026-06-03.md`
- `docs/harness/report-generation-env-switch-implementation-2026-06-03.md`
- `docs/harness/report-404-and-secret-log-leak-remediation-plan-2026-06-04.md`
- `docs/harness/report-404-and-secret-log-leak-remediation-implementation-2026-06-04.md`

## Open Risks

- Hosted backend provider and exact production/staging domains still need to be chosen before final environment values can be set.
- Supabase direct connection versus pooler mode must be tested with SQLAlchemy asyncpg before production traffic.
- Scheduler should start disabled for the first smoke release and be enabled only after API, DB, cost, and rate-limit checks.
- Existing local `postgres_data` volumes can preserve old DB user/password/name values. Resetting a volume is a data-loss action and needs explicit confirmation.
- The data.go.kr `serviceKey` was confirmed exposed in 2026-06-03 runtime WARNING logs and must be rotated at the issuer with Render env vars updated. Other provider keys (Finnhub token, FRED `api_key`, ECOS key, Stooq `apikey`) that may have appeared in logs are also treated as compromised; the code guards only prevent future re-exposure.
