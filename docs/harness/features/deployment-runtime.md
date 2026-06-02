# Deployment And Hosted Runtime Feature Notes

Date: 2026-06-01

## Current Behavior

The first supported hosted shape is Vercel for the React Vite frontend, Supabase PostgreSQL for the database, and a separate persistent FastAPI backend runtime. The backend keeps long-running process assumptions for `APScheduler`, market cache warm-up, and scheduled AI report generation.

Vercel serves the frontend from `frontend/` and uses `frontend/vercel.json` to rewrite direct SPA route refreshes to `index.html`.

Backend CORS is configured from environment variables instead of hardcoded production domains. Local Vite origins remain enabled by default for development, and production/staging origins should be supplied through hosted backend secrets.

The backend can still bootstrap local schemas with `Base.metadata.create_all` when `ENABLE_DB_SCHEMA_BOOTSTRAP=true`. Production-like deployments should set `ENABLE_DB_SCHEMA_BOOTSTRAP=false`, run Alembic migrations first, and let startup fail if required tables or AI report metadata columns are missing.

## Ownership Map

- Deployment plan: `docs/harness/vercel-supabase-deployment-plan-2026-06-01.md`
- Vercel SPA routing: `frontend/vercel.json`
- Frontend API origin: `frontend/src/utils/apiClient.js`
- Backend runtime settings: `backend/app/core/config.py`
- Backend CORS and startup checks: `backend/app/main.py`
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
7. Scheduler and market warm-up remain controlled by `ENABLE_SCHEDULER`, `ENABLE_MARKET_WARMUP`, and report scheduler environment variables.
8. Favorite notification scheduler is controlled separately by `ENABLE_NOTIFICATION_SCHEDULER`, which defaults to false. Provider secrets for Telegram/email are backend-only environment variables.

## Contracts

- Frontend public env:
  - `VITE_API_BASE_URL`
- Backend deployment env:
  - `ENVIRONMENT`: runtime label such as `development`, `staging`, or `production`.
  - `BACKEND_CORS_ORIGINS`: comma-separated exact origins such as a Vercel production domain and staging domain.
  - `BACKEND_CORS_ORIGIN_REGEX`: optional regex for approved preview-origin policy.
  - `LOCAL_CORS_ORIGINS`: comma-separated local dev origins, defaults to Vite localhost origins.
  - `ENABLE_DB_SCHEMA_BOOTSTRAP`: keep true for local convenience; set false for migration-managed hosted runtime.
  - `SQLALCHEMY_ECHO`: default false so production does not log SQL statements.
  - `DB_POOL_PRE_PING`: default true for connection health checks.
  - `DB_PREPARED_STATEMENT_CACHE_SIZE`: optional asyncpg prepared-statement cache override for pooler compatibility testing.
  - `ENABLE_NOTIFICATION_SCHEDULER`: enables favorite notification evaluation/delivery jobs when true.
  - `NOTIFICATION_EVALUATION_INTERVAL_MINUTES`, `NOTIFICATION_DELIVERY_INTERVAL_MINUTES`, `NOTIFICATION_DEFAULT_PRICE_THRESHOLD_PERCENT`, `NOTIFICATION_DEFAULT_COOLDOWN_MINUTES`: notification scheduler and default rule controls.
  - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `EMAIL_PROVIDER`, `EMAIL_FROM_ADDRESS`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, `EMAIL_SMTP_HOST`, `EMAIL_SMTP_PORT`, `EMAIL_SMTP_USERNAME`, `EMAIL_SMTP_PASSWORD`, `EMAIL_SMTP_USE_TLS`: backend-only delivery configuration names.

## Change Rules

- Do not place backend secrets in Vercel frontend variables. Only `VITE_` values intended for browser exposure belong in the frontend host.
- Do not use wildcard CORS origins with credentials enabled.
- Do not enable production scheduler or AI report generation broadly until cost and rate-limit policy are confirmed.
- Do not rely on `create_all` for production schema changes. Add Alembic revisions for schema changes and run migrations before deploying.
- Do not expose database URLs, provider secrets, access tokens, or webhook secrets in logs or harness records.

## Verification

- User explicitly requested no verification for the 2026-06-01 implementation pass.
- For configuration-only updates, compare `.env_example` variable names against `backend/app/core/config.py` and confirm only placeholders, not secrets, are documented.
- Future checks should include frontend lint/build, backend tests, Alembic migration against a disposable database, `/health`, `/db-check`, and CORS smoke checks.

## Change Records

- `docs/harness/vercel-supabase-deployment-plan-2026-06-01.md`
- `docs/harness/vercel-supabase-deployment-implementation-2026-06-01.md`
- `docs/harness/favorite-asset-notification-implementation-2026-06-02.md`
- `docs/harness/project-gap-remediation-plan-2026-06-02.md`
- `docs/harness/project-gap-remediation-phase0-1-implementation-2026-06-02.md`

## Open Risks

- Hosted backend provider and exact production/staging domains still need to be chosen before final environment values can be set.
- Supabase direct connection versus pooler mode must be tested with SQLAlchemy asyncpg before production traffic.
- Scheduler should start disabled for the first smoke release and be enabled only after API, DB, cost, and rate-limit checks.
