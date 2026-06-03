# 로컬 Docker DB에서 Vercel Supabase로 전환 계획

Date: 2026-06-03

## Objective

현재 `docker-compose.yml`의 로컬 PostgreSQL을 기본 개발/운영 DB로 쓰는 흐름에서 벗어나, Vercel Marketplace로 연결된 Supabase PostgreSQL을 `Project_Finance`의 주 데이터베이스로 사용하는 전환 계획을 정의한다.

이 계획은 실제 secret 값, DB password, JWT secret, Supabase service role key, provider token을 문서에 남기지 않는다.

## 현재 기준 결론

권장 구조는 아래와 같다.

```text
Browser
  -> Vercel frontend (`frontend/` React + Vite)
  -> `VITE_API_BASE_URL`
  -> persistent FastAPI backend
  -> Supabase PostgreSQL
```

Vercel Supabase integration은 Supabase project 생성, Vercel project 연결, Vercel 환경변수 동기화에 사용한다. 다만 현재 backend는 `APScheduler`, market warm-up, AI report scheduler처럼 오래 떠 있는 프로세스 전제를 갖고 있으므로, 1차 전환에서는 FastAPI backend를 Vercel serverless function으로 옮기지 않는다. Backend는 별도 persistent runtime에 배포하고, 그 runtime의 `DATABASE_URL`이 Supabase PostgreSQL을 가리키게 한다.

로컬 Docker PostgreSQL은 즉시 삭제하지 않는다. Supabase staging과 production 전환이 검증될 때까지 개발 fallback과 비교용으로 남기고, 제거는 별도 승인 후 진행한다.

## 공식 참고 확인

- Vercel Marketplace의 Supabase integration은 Supabase Postgres/Auth/Storage 등을 Vercel project와 연결하고, project env vars를 동기화할 수 있다.
- Supabase Vercel Marketplace 문서는 `POSTGRES_URL`, `POSTGRES_URL_NON_POOLING`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DATABASE`, `SUPABASE_URL`, Supabase key 계열 변수가 Vercel project에 동기화될 수 있다고 설명한다.
- Supabase Postgres connection guide는 persistent backend에는 pooler session mode 또는 direct connection을, serverless/edge에는 transaction mode를 검토하라고 안내한다.

참고 URL:

- `https://vercel.com/marketplace/supabase/supabase`
- `https://supabase.com/docs/guides/integrations/vercel-marketplace`
- `https://supabase.com/docs/reference/postgres/connection-strings`
- `https://vercel.com/docs/environment-variables`

## Phase 0. 전환 전 결정 사항

1. Vercel/Supabase billing owner를 확정한다.
2. Supabase project를 새로 만들지, 기존 project를 Vercel Marketplace에 연결할지 결정한다.
3. Backend hosting provider를 확정한다.
4. Staging 운영 방식을 정한다.
   - Vercel Preview branch + Supabase staging project
   - 또는 별도 Vercel environment/custom domain + Supabase staging project
5. Supabase connection mode를 정한다.
   - Persistent backend가 IPv6 direct connection을 지원하면 direct connection을 우선 검토한다.
   - Persistent backend가 IPv4-only이면 Supavisor pooler session mode를 검토한다.
   - Serverless backend 전환은 별도 프로젝트로 분리하고 transaction pooler와 prepared statement 설정을 검증한다.

## Phase 1. Supabase project와 Vercel project 연결

1. Vercel에 `frontend/`를 Root Directory로 하는 frontend project를 준비한다.
2. Vercel Marketplace에서 Supabase integration을 설치한다.
3. 새 Supabase project를 만들거나 기존 Supabase project를 연결한다.
4. 연결된 Vercel project의 Environment Variables에 Supabase/Postgres 관련 변수가 동기화되었는지 확인한다.
5. 로컬 CLI를 사용할 경우 project link 후 환경변수를 확인한다.

```powershell
vercel link
vercel integration list
vercel env ls
```

주의: `vercel env pull`은 대상 파일을 덮어쓸 수 있으므로, 기존 로컬 override가 있으면 먼저 백업하거나 별도 `.env.*.local` 파일 전략을 정한다.

## Phase 2. Backend DB 연결 전략

현재 backend 설정은 `DATABASE_URL`을 최우선으로 읽고, 없을 때 `POSTGRES_URL_NON_POOLING`, `POSTGRES_URL` 순서로 fallback한다. 운영에서는 명시적인 `DATABASE_URL` 등록을 우선한다.

Backend host에 등록할 DB 변수:

```dotenv
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:<port>/<database>
```

Supabase나 Vercel에서 받은 원본 URL이 `postgresql://` 또는 `postgres://`로 시작해도 `backend/app/core/config.py`가 `postgresql+asyncpg://`로 정규화한다. 그래도 운영 문서와 host secret에는 async SQLAlchemy scheme을 명시해 두는 편이 가장 읽기 쉽다.

Pooler transaction mode를 쓰는 경우에는 staging에서 아래 후보 설정을 검증한다.

```dotenv
DB_PREPARED_STATEMENT_CACHE_SIZE=0
```

## Phase 3. 환경변수 배치 원칙

### Vercel frontend project

Frontend에는 브라우저에 노출되어도 되는 값만 둔다.

```dotenv
VITE_API_BASE_URL=https://<backend-origin>
VITE_GOOGLE_CLIENT_ID=<google-oauth-client-id>
```

`VITE_` 변수는 browser bundle에 들어간다. 아래 값은 frontend env로 두지 않는다.

- `DATABASE_URL`
- `POSTGRES_URL`
- `POSTGRES_URL_NON_POOLING`
- `POSTGRES_PASSWORD`
- `SUPABASE_SECRET_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_JWT_SECRET`
- `SECRET_KEY`
- `OPENAI_API_KEY`
- 결제 webhook secret

### Persistent backend host

초기 staging smoke에는 scheduler와 비용 유발 작업을 꺼 둔다.

```dotenv
ENVIRONMENT=staging
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:<port>/<database>
SECRET_KEY=<strong-random-secret>
BACKEND_CORS_ORIGINS=https://<vercel-frontend-origin>
ENABLE_DB_SCHEMA_BOOTSTRAP=false
SQLALCHEMY_ECHO=false
DB_POOL_PRE_PING=true
ENABLE_MARKET_WARMUP=false
ENABLE_SCHEDULER=false
ENABLE_LLM_REPORT_CRITICS=false
ENABLE_NOTIFICATION_SCHEDULER=false
```

OpenAI, 결제, Gmail/Telegram, 외부 market provider secret은 해당 기능 검증 단계에서만 추가한다.

## Phase 4. Schema migration

Production-like 환경에서는 runtime table bootstrap에 의존하지 않는다.

1. Supabase staging DB를 준비한다.
2. Backend 또는 안전한 로컬/CI 실행 환경에 staging `DATABASE_URL`을 주입한다.
3. Alembic migration을 실행한다.

```powershell
cd backend
python -m alembic upgrade head
```

4. Backend env에 `ENABLE_DB_SCHEMA_BOOTSTRAP=false`를 둔다.
5. Backend를 시작한다.
6. `/health`와 `/db-check`를 확인한다.

`/health`는 앱 생존 확인이고, DB readiness는 `/db-check`로 확인한다.

## Phase 5. Staging smoke 순서

1. Backend를 scheduler disabled 상태로 배포한다.
2. Backend `/health`가 응답하는지 확인한다.
3. Backend `/db-check`가 Supabase 연결을 통과하는지 확인한다.
4. `BACKEND_CORS_ORIGINS`에 Vercel frontend origin만 정확히 들어 있는지 확인한다.
5. Vercel frontend에 `VITE_API_BASE_URL`을 staging backend로 설정하고 새 deployment를 만든다.
6. Home, market page, asset detail route가 backend API를 호출하는지 확인한다.
7. Direct route refresh가 Vite SPA rewrite로 정상 동작하는지 확인한다.
8. Google login을 쓰는 경우 Google Cloud Console에 Vercel origin을 등록하고 로그인 smoke를 진행한다.
9. 결제 기능은 sandbox provider와 test webhook으로만 확인한다.
10. Scheduler는 DB/API/CORS/login/payment smoke 이후 별도 단계에서 켠다.

## Phase 6. Production 전환

1. Staging smoke 결과와 남은 위험을 문서화한다.
2. Production Supabase DB를 준비한다.
3. Production DB에 Alembic migration을 적용한다.
4. Production backend를 scheduler disabled 상태로 배포한다.
5. Production Vercel frontend의 `VITE_API_BASE_URL`을 production backend origin으로 설정하고 재배포한다.
6. `/health`, `/db-check`, market data, asset detail, login, billing route를 확인한다.
7. `ENABLE_MARKET_WARMUP`을 먼저 켜고, 안정성을 본 뒤 `ENABLE_SCHEDULER`와 AI report generation 관련 설정을 단계적으로 켠다.
8. 사용자-facing 요청과 chatbot 요청은 저장된 scheduled report만 읽어야 하며 fresh report generation을 직접 트리거하지 않아야 한다.

## Phase 7. 로컬 Docker DB에서 벗어나는 방식

전환 완료 전:

- `docker-compose.yml`은 유지한다.
- `.env_example`과 `ENVIRONMENT_VARIABLE_SETUP.md`에는 local Docker와 Supabase hosted DB의 차이를 명확히 둔다.
- 개발자는 기본적으로 Supabase staging을 쓰되, 네트워크나 provider 문제 때만 local Docker DB를 fallback으로 사용한다.

전환 완료 후:

1. 팀이 Supabase staging을 기본 개발 DB로 사용해도 되는지 확인한다.
2. Local Docker DB가 필요한 테스트 범위가 남아 있는지 확인한다.
3. 남아 있지 않다면 `docker-compose.yml` 제거 또는 optional local-only 문서화 중 하나를 선택한다.
4. Docker volume 삭제는 데이터 손실 작업이므로 별도 명시 승인 전까지 하지 않는다.

## Verification Commands

전환 작업 중 최소 검증 명령은 아래와 같다.

```powershell
git status --short
cd frontend
npm run lint
npm run build
cd ..\backend
python -m alembic upgrade head
pytest
```

환경 의존 smoke:

- Backend `/health`
- Backend `/db-check`
- Vercel frontend direct route refresh
- Vercel frontend origin에서 backend API 호출
- Google login smoke, 사용 시
- Payment sandbox smoke, 사용 시

## Rollback Plan

- Frontend 문제: Vercel previous deployment를 promote하거나 `VITE_API_BASE_URL`을 이전 backend로 되돌리고 재배포한다.
- Backend 문제: 이전 backend release로 rollback하고 `ENABLE_SCHEDULER=false`를 유지한다.
- DB migration 문제: production에서는 destructive rollback보다 forward fix를 우선한다.
- Supabase 연결 문제: backend host의 `DATABASE_URL`을 이전 DB로 되돌릴 수 있도록 전환 직전 백업과 이전 connection 정보를 안전한 secret manager에 보관한다.
- Secret 노출: 노출된 값은 즉시 rotate하고 문서/로그/채팅에서 재사용하지 않는다.

## Open Risks

- Backend hosting provider가 확정되어야 direct connection과 pooler session mode 중 무엇이 맞는지 최종 판단할 수 있다.
- Supabase staging/production project를 분리하지 않으면 preview 배포가 production data에 접근할 위험이 있다.
- Scheduler와 AI report generation을 너무 일찍 켜면 비용과 rate limit 위험이 있다.
- Local Docker DB 제거는 로컬 재현성과 오프라인 개발 편의성을 낮출 수 있다.
- Vercel Supabase env sync는 Vercel frontend project 기준이므로, 별도 backend host에는 secret을 별도로 등록해야 한다.

