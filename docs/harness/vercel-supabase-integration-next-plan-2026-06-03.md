# Vercel Supabase 연동 실행 계획

Date: 2026-06-03

## Objective

Vercel Supabase Marketplace를 활용해 Supabase PostgreSQL을 준비하고, `Project_Finance`의 Vercel frontend와 persistent FastAPI backend가 안전하게 같은 Supabase DB를 사용하도록 앞으로 해야 할 일을 정리한다.

## Current Context

- Frontend는 `frontend/`의 React + Vite 앱이며 Vercel 배포 대상이다.
- `frontend/vercel.json`에는 SPA route refresh용 rewrite가 이미 있다.
- Backend는 FastAPI + Async SQLAlchemy이며 `backend/app/core/config.py`에서 루트 `.env` 또는 host env의 `DATABASE_URL`을 읽는다.
- PostgreSQL URL은 최종적으로 `postgresql+asyncpg://` scheme을 사용해야 한다. 설정 로드 중 `postgresql://` 또는 `postgres://`는 `postgresql+asyncpg://`로 정규화된다.
- `DATABASE_URL`이 없고 Vercel/Supabase env가 backend host에 들어온 경우 backend는 `POSTGRES_URL_NON_POOLING`, `POSTGRES_URL` 순서로 fallback한다.
- Production-like runtime은 `ENABLE_DB_SCHEMA_BOOTSTRAP=false`로 두고 Alembic migration을 먼저 실행해야 한다.
- 현재 backend는 in-process scheduler와 AI report pipeline이 있어 Vercel serverless backend보다 persistent runtime이 1차 권장 구조다.

## Phase 0. 결정해야 할 것

1. Vercel/Supabase billing owner를 확정한다.
2. Supabase project를 Vercel Marketplace로 새로 만들지, 기존 Supabase project를 연결할지 결정한다.
3. Backend hosting provider를 확정한다.
4. staging을 Vercel Preview branch-scoped 변수로 운영할지, Vercel Pro custom environment로 운영할지 정한다.
5. Supabase connection mode를 결정한다.
   - persistent backend + IPv6 가능: direct connection 우선
   - persistent backend + IPv4-only: shared pooler session mode 검토
   - serverless backend 전환 시: transaction pooler와 prepared statement 비활성화 검증 필요

## Phase 1. Vercel frontend project 연결

1. Vercel에서 repository를 import한다.
2. Root Directory를 `frontend`로 설정한다.
3. Framework Preset을 `Vite`로 설정한다.
4. Build Command는 `npm run build`, Output Directory는 `dist`로 둔다.
5. Preview deployment를 만들어 route refresh가 동작하는지 확인한다.
6. production domain 또는 preview URL을 기록한다.

## Phase 2. Supabase integration 설치

1. Vercel Marketplace에서 Supabase integration을 설치한다.
2. Vercel project와 Supabase project를 연결한다.
3. Vercel Project Settings에서 Supabase 관련 env가 들어왔는지 확인한다.
4. `vercel env ls` 또는 dashboard로 `POSTGRES_URL`, `POSTGRES_URL_NON_POOLING`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DATABASE`, `SUPABASE_URL`, Supabase key 계열 변수를 확인한다.
5. secret 값은 문서, 채팅, 로그에 남기지 않는다.

## Phase 3. Backend DB 연결값 준비

1. Supabase dashboard의 `Connect` 화면에서 backend에 쓸 connection string을 선택한다.
2. backend host secret에 `DATABASE_URL`을 등록한다. 원본 URL이 `postgresql://` 또는 `postgres://`여도 backend가 async scheme으로 정규화한다.
3. `DATABASE_URL`을 명시하기 어렵고 Vercel/Supabase env를 그대로 주입하는 환경이면 `POSTGRES_URL_NON_POOLING` 또는 `POSTGRES_URL` fallback을 사용할 수 있다.
4. `ENABLE_DB_SCHEMA_BOOTSTRAP=false`, `SQLALCHEMY_ECHO=false`, `DB_POOL_PRE_PING=true`를 등록한다.
5. Supabase pooler transaction mode를 쓰는 경우에만 `DB_PREPARED_STATEMENT_CACHE_SIZE=0` 후보를 staging에서 검증한다.

## Phase 4. Backend 기본 secret 등록

Backend host에 아래 값을 등록한다.

- `PROJECT_NAME`
- `API_V1_STR`
- `ENVIRONMENT`
- `DATABASE_URL`
- `SECRET_KEY`
- `ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `BACKEND_CORS_ORIGINS`
- `LOCAL_CORS_ORIGINS`
- `ENABLE_DB_SCHEMA_BOOTSTRAP`
- `SQLALCHEMY_ECHO`
- `DB_POOL_PRE_PING`
- `ENABLE_MARKET_WARMUP=false`
- `ENABLE_SCHEDULER=false`
- `ENABLE_LLM_REPORT_CRITICS=false`
- `ENABLE_NOTIFICATION_SCHEDULER=false`

Provider key, 결제 secret, Gmail/Telegram secret은 해당 기능을 검증할 때만 추가한다.

## Phase 5. Migration과 backend smoke

1. staging Supabase DB를 대상으로 Alembic migration을 실행한다.

```powershell
cd backend
python -m alembic upgrade head
```

2. backend를 staging host에 배포한다.
3. `/health`를 확인한다.
4. `/db-check`를 확인한다.
5. `/api/market/prices`처럼 공개 API를 좁게 확인한다.
6. CORS가 Vercel frontend origin만 허용하는지 확인한다.

## Phase 6. Vercel frontend env와 smoke

Vercel frontend project에 아래 공개 변수만 설정한다.

- `VITE_API_BASE_URL`
- `VITE_GOOGLE_CLIENT_ID` if Google login is enabled

검증한다.

1. Vercel env 변경 후 새 deployment를 만든다.
2. Home/market page가 backend API를 호출하는지 확인한다.
3. `/login`, `/pricing`, `/billing/success`, asset detail route를 직접 새로고침해도 404가 아닌지 확인한다.
4. Google OAuth origin에 Vercel frontend origin이 들어 있는지 확인한다.

## Phase 7. 기능별 provider 연결

1. Google login
   - Google Cloud Console에 production/staging frontend origin을 등록한다.
   - backend host에 `GOOGLE_CLIENT_ID`를 등록한다.

2. Payment
   - test mode provider부터 연결한다.
   - success/cancel URL은 Vercel frontend route로 둔다.
   - webhook URL은 persistent backend route로 둔다.
   - webhook secret은 backend-only env로 둔다.

3. AI/report scheduler
   - OpenAI와 market provider key는 backend-only env로 둔다.
   - 첫 smoke 이후 `ENABLE_MARKET_WARMUP`부터 켠다.
   - report scheduler는 비용/rate limit 확인 후 마지막에 켠다.
   - 사용자 요청과 chatbot 요청은 stored scheduled report를 읽어야 하며 fresh report generation을 직접 트리거하지 않는다.

4. Favorite notifications
   - Gmail/Telegram secret은 backend-only env로 둔다.
   - 실제 발송 전까지 `ENABLE_NOTIFICATION_SCHEDULER=false`를 유지한다.

## Phase 8. Production promotion

1. staging smoke 결과를 기록한다.
2. production Supabase DB에 migration을 적용한다.
3. production backend를 scheduler disabled 상태로 배포한다.
4. production Vercel frontend의 `VITE_API_BASE_URL`을 production backend로 설정하고 재배포한다.
5. `/health`, `/db-check`, market, login, pricing, asset detail을 확인한다.
6. scheduler를 단계적으로 켠다.
7. secret 또는 connection string이 로그에 노출되지 않았는지 확인한다.

## Verification Checklist

- `git status --short`
- `frontend/`: `npm run lint`
- `frontend/`: `npm run build`
- `backend/`: relevant `pytest`
- `backend/`: `python -m alembic upgrade head` against staging Supabase
- backend `/health`
- backend `/db-check`
- frontend deployment direct route refresh
- CORS smoke from Vercel frontend origin
- Google login smoke if enabled
- Payment sandbox smoke if enabled
- Scheduler disabled first smoke

## Rollback Plan

- Frontend 문제: Vercel previous deployment를 promote하거나 env를 되돌리고 재배포한다.
- Backend 문제: 이전 backend release로 rollback하고 `ENABLE_SCHEDULER=false`를 유지한다.
- DB migration 문제: production에서는 destructive rollback보다 forward fix를 우선한다. 데이터 삭제나 volume reset은 명시 승인 전까지 하지 않는다.
- Secret 노출: 노출된 값은 즉시 폐기하고 provider dashboard에서 rotate한다.

## References Checked

- Vercel Supabase Marketplace: `https://vercel.com/marketplace/supabase/supabase`
- Supabase Vercel Marketplace guide: `https://supabase.com/docs/guides/integrations/vercel-marketplace`
- Vercel environment variables: `https://vercel.com/docs/environment-variables`
- Supabase Postgres connection guide: `https://supabase.com/docs/guides/database/connecting-to-postgres`
- Supabase Vercel environment troubleshooting: `https://supabase.com/docs/guides/troubleshooting/vercel-integration-environment-variables-not-syncing-for-persistent-git-branches-b9191e`
