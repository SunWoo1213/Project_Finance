# Vercel Supabase 연동 구현 시작 기록

Date: 2026-06-03

## Objective

`docs/harness/vercel-supabase-integration-next-plan-2026-06-03.md`와 `VERCEL_SUPABASE_INTEGRATION_GUIDE.md`를 기준으로, 실제 Vercel/Supabase 계정 연결 전에 저장소에서 준비할 수 있는 backend 설정과 문서 계약을 보강한다.

## Files Changed

- `backend/app/core/config.py`
- `.gitignore`
- `.env_example`
- `ENVIRONMENT_VARIABLE_SETUP.md`
- `VERCEL_SUPABASE_INTEGRATION_GUIDE.md`
- `docs/harness/vercel-supabase-integration-next-plan-2026-06-03.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/feature-index.md`
- `docs/harness/vercel-supabase-integration-start-2026-06-03.md`

## Behavior Changes

- Backend 설정이 `DATABASE_URL`을 우선 사용하되, 값이 없으면 Vercel/Supabase에서 흔히 제공하는 `POSTGRES_URL_NON_POOLING`, `POSTGRES_URL` 순서로 fallback할 수 있게 했다.
- Backend 설정 로드 중 `postgresql://...` 또는 `postgres://...` PostgreSQL URL을 `postgresql+asyncpg://...`로 정규화한다.
- `DATABASE_URL`, `POSTGRES_URL_NON_POOLING`, `POSTGRES_URL`은 모두 backend-only secret으로 취급해야 하며 frontend `VITE_` 변수로 만들지 않는다는 안내를 강화했다.
- Hosted smoke 시작 시 `ENABLE_DB_SCHEMA_BOOTSTRAP=false`, `ENABLE_MARKET_WARMUP=false`, `ENABLE_SCHEDULER=false`, `ENABLE_LLM_REPORT_CRITICS=false`, `ENABLE_NOTIFICATION_SCHEDULER=false`를 권장하는 preset 설명을 `.env_example`에 추가했다.
- Vercel env pull 또는 local override 과정에서 생길 수 있는 `.env.local`, `.env.*.local` 파일이 Git에 추적되지 않도록 `.gitignore`를 보강했다.

## Verification Performed

- 사용자가 검증 금지를 명시했으므로 lint, build, test, Alembic, backend smoke, Vercel CLI, Supabase 연결 검증은 실행하지 않았다.
- `.env` 값은 읽거나 출력하지 않았다.

## Commands Not Run

- `npm run lint`: 검증 금지 요청 때문에 실행하지 않았다.
- `npm run build`: 검증 금지 요청 때문에 실행하지 않았다.
- `pytest`: 검증 금지 요청 때문에 실행하지 않았다.
- `python -m alembic upgrade head`: 실제 DB 변경과 검증 금지 요청 때문에 실행하지 않았다.
- `vercel env ls`, `vercel env pull`: 실제 Vercel 계정/env 조회가 필요하고 검증 금지 요청이 있으므로 실행하지 않았다.

## Follow-up Risks

- Vercel/Supabase billing owner, backend hosting provider, staging 운영 방식, Supabase connection mode는 아직 외부 의사결정이 필요하다.
- Supabase pooler transaction mode를 쓸 경우 `DB_PREPARED_STATEMENT_CACHE_SIZE=0` 후보는 staging에서 별도 검증 후 확정해야 한다.
- 실제 hosted deployment 전에는 Alembic migration을 먼저 실행하고 `ENABLE_DB_SCHEMA_BOOTSTRAP=false`로 backend startup schema check가 통과하는지 확인해야 한다.
- Scheduler와 AI report generation은 첫 smoke 이후 비용과 rate limit 정책을 확인한 뒤 단계적으로 켜야 한다.
