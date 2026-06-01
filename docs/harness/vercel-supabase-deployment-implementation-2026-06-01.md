# Vercel Supabase Deployment Implementation

Date: 2026-06-01

## Objective

`docs/harness/vercel-supabase-deployment-plan-2026-06-01.md`의 후속 구현으로, Vercel frontend, Supabase PostgreSQL, persistent FastAPI backend 배포에 필요한 코드/설정 기반을 추가했다.

## Files Changed

- `frontend/vercel.json`
- `backend/app/core/config.py`
- `backend/app/db/session.py`
- `backend/app/main.py`
- `backend/alembic/versions/20260601_0001_add_subscription_billing_tables.py`
- `backend/DEVELOPMENT_DIRECTION.md`
- `frontend/DEVELOPMENT_DIRECTION.md`
- `docs/harness/feature-index.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/features/subscription-billing.md`
- `docs/harness/features/frontend-routing-shell.md`
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/vercel-supabase-deployment-plan-2026-06-01.md`

## Behavior Changes

- Vercel direct route refresh를 지원하기 위해 `frontend/vercel.json`에 SPA rewrite를 추가했다.
- Backend CORS origin을 `BACKEND_CORS_ORIGINS`, `BACKEND_CORS_ORIGIN_REGEX`, `LOCAL_CORS_ORIGINS` 설정으로 분리했다.
- SQLAlchemy engine의 SQL echo 기본값을 `false`로 바꾸고 `pool_pre_ping` 및 asyncpg prepared-statement cache override 설정을 추가했다.
- `ENABLE_DB_SCHEMA_BOOTSTRAP`를 추가했다. 기본값은 local bootstrap 편의를 위해 `true`이며, production-like runtime에서는 `false`로 설정해 Alembic migration 기반 스키마만 허용한다.
- `ENABLE_DB_SCHEMA_BOOTSTRAP=false`일 때 backend startup은 DB 연결과 필수 테이블/AI report metadata column 존재 여부를 확인하며, 누락 시 startup 실패로 드러나게 했다.
- `/db-check` 실패 응답이 raw DB exception 문자열을 노출하지 않도록 일반 메시지로 바꿨다.
- Alembic 리비전을 새 Supabase DB에서도 core table, comment table, AI report metadata column, subscription/billing table을 생성할 수 있는 baseline으로 보강했다.

## Verification Performed

검증 명령은 실행하지 않았다.

## Commands Not Run And Why

- `npm run lint`: 사용자가 검증 금지를 명시했다.
- `npm run build`: 사용자가 검증 금지를 명시했다.
- `pytest`: 사용자가 검증 금지를 명시했다.
- `python -m alembic upgrade head`: 사용자가 검증 금지를 명시했고 실제 DB 변경을 수행하지 않기 위해 실행하지 않았다.

## Follow-Up Risks

- Production/staging Vercel domain과 backend API domain이 확정되면 backend host에 `BACKEND_CORS_ORIGINS`를 실제 origin 목록으로 설정해야 한다.
- Supabase pooler mode를 사용할 경우 `DB_PREPARED_STATEMENT_CACHE_SIZE=0` 같은 설정은 staging에서 별도 검증 후 확정해야 한다.
- 첫 smoke deployment에서는 `ENABLE_MARKET_WARMUP=false`, `ENABLE_SCHEDULER=false`로 시작하고, API/DB 확인 후 scheduler를 단계적으로 켜는 것이 안전하다.
- 이 구현은 secrets 값을 추가하거나 출력하지 않았다. 실제 값은 Vercel/backend provider dashboard 또는 secret manager에서만 관리해야 한다.

## Feature Links

- `docs/harness/features/deployment-runtime.md`
- `docs/harness/features/subscription-billing.md`
- `docs/harness/features/frontend-routing-shell.md`
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`
