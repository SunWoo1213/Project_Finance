# Vercel Supabase 연동 가이드

Date: 2026-06-03

이 문서는 `Project_Finance`에서 Vercel을 통해 Supabase를 연결할 때의 절차와 주의점을 설명한다. 실제 Supabase password, database URL, service role key, JWT secret, API key는 이 문서나 Git에 남기지 않는다.

## 1. 현재 프로젝트 기준 결론

현재 권장 배포 구조는 아래와 같다.

```text
Browser
  -> Vercel frontend: frontend/ React + Vite
  -> VITE_API_BASE_URL
  -> persistent FastAPI backend
  -> Supabase PostgreSQL
```

Vercel Supabase Marketplace 연동은 Supabase project를 만들고 Vercel project에 관련 환경변수를 자동 동기화하는 데 유용하다. 다만 이 저장소의 현재 backend는 `APScheduler`, market warm-up, AI report generation처럼 오래 떠 있는 process를 전제로 한다. 그래서 1차 배포에서는 FastAPI backend를 Vercel serverless function으로 옮기기보다 별도 persistent backend runtime에 두는 것이 안전하다.

즉, Vercel은 frontend 배포와 Supabase project 연결 관리에 사용하고, backend는 별도 host에서 Supabase의 PostgreSQL connection string을 `DATABASE_URL`로 읽게 한다.

## 2. 먼저 알아야 할 것

Vercel Supabase 연동이 자동으로 넣어주는 변수와 이 프로젝트가 실제로 읽는 변수 이름이 완전히 같지는 않다.

| 구분 | Vercel/Supabase에서 흔히 제공되는 변수 | 이 프로젝트에서 필요한 변수 |
| --- | --- | --- |
| PostgreSQL 접속 | `POSTGRES_URL`, `POSTGRES_URL_NON_POOLING`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DATABASE` | `DATABASE_URL` 우선. 없으면 backend가 `POSTGRES_URL_NON_POOLING`, `POSTGRES_URL` 순서로 fallback |
| Supabase API | `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` 또는 `SUPABASE_SECRET_KEY` | 현재 frontend/backend 코드가 직접 사용하지 않음 |
| Frontend API 주소 | 직접 지정 필요 | `VITE_API_BASE_URL` |

따라서 Supabase가 제공한 PostgreSQL URL은 가능하면 backend용 `DATABASE_URL`로 명시 등록한다.

```dotenv
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:<port>/<database>
```

Supabase dashboard나 Vercel에 표시되는 원본 URL이 `postgresql://...` 또는 `postgres://...`로 시작하면, backend 설정 로드 중 `postgresql+asyncpg://`로 정규화된다. 운영 문서와 dashboard에는 여전히 `DATABASE_URL`을 명시하는 방식을 우선 권장하고, Vercel/Supabase env를 그대로 backend host에 주입하는 경우에는 `POSTGRES_URL_NON_POOLING` 또는 `POSTGRES_URL` fallback을 사용할 수 있다.

## 3. Vercel에서 Supabase 연결하기

### 3.1 Vercel project 준비

1. Vercel에서 Git repository를 import한다.
2. frontend project의 Root Directory를 `frontend`로 설정한다.
3. Framework Preset은 `Vite`를 선택한다.
4. Build Command는 `npm run build`, Output Directory는 `dist`로 둔다.
5. 배포 후 Vercel frontend URL을 확인한다.

현재 `frontend/vercel.json`에는 Vite SPA route refresh를 위한 rewrite가 이미 있다.

### 3.2 Supabase integration 설치

Vercel Dashboard 기준:

1. Vercel project 또는 team dashboard에서 Marketplace로 이동한다.
2. `Supabase` integration을 찾는다.
3. 새 Supabase project를 만들거나 기존 Supabase account/project를 연결한다.
4. 연결할 Vercel project를 선택한다.
5. integration 설치가 끝나면 Vercel Project Settings의 Environment Variables를 확인한다.

Vercel CLI를 쓴다면 먼저 project link를 확인한다.

```powershell
vercel link
vercel integration list
vercel integration add supabase
```

CLI 설치 과정이 dashboard 완료 단계로 넘겨질 수 있다. 이 경우 dashboard에서 provider 연결을 마친 뒤 다시 `vercel env ls`로 변수 동기화를 확인한다.

### 3.3 환경변수 동기화 확인

Supabase Marketplace integration은 연결된 Vercel project에 PostgreSQL URL, Supabase URL/key 계열 환경변수를 동기화할 수 있다.

```powershell
vercel env ls
```

로컬에서 Vercel development 환경변수를 받아 보고 싶다면 `frontend/` 기준으로 아래를 실행한다.

```powershell
vercel env pull .env.development.local
```

주의할 점:

- Vercel 환경변수를 바꾸면 이전 deployment에는 적용되지 않고, 새 deployment부터 적용된다.
- Vercel의 `Production`, `Preview`, `Development` 환경은 서로 다르다.
- staging branch를 써도 별도 environment를 만들지 않으면 보통 `Preview` 환경으로 배포된다.
- `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_SECRET_KEY`, `POSTGRES_PASSWORD`, `POSTGRES_URL`은 브라우저에 노출하면 안 된다.
- 현재 frontend는 Supabase client를 직접 쓰지 않으므로 Vercel frontend public env에는 Supabase key나 DB URL을 추가하지 않는다.

## 4. 이 프로젝트에 맞게 변수 배치하기

### 4.1 Vercel frontend project에 둘 값

현재 frontend에서 필요한 공개 변수는 아래 정도다.

```dotenv
VITE_API_BASE_URL=https://<deployed-backend-origin>
VITE_GOOGLE_CLIENT_ID=<google-oauth-client-id>
```

`VITE_` 변수는 browser bundle에 들어간다. Supabase DB URL, service role key, OpenAI key, payment webhook secret, JWT secret은 절대 `VITE_` 변수로 만들지 않는다.

Supabase integration이 Vercel project에 DB 관련 secret을 자동 추가할 수 있지만, 현재 Vite frontend 코드는 그 값을 사용하지 않는다. frontend에서 Supabase client를 직접 쓰는 기능을 새로 만들기 전까지는 Supabase secret을 browser 코드와 연결하지 않는다.

### 4.2 Persistent backend host에 둘 값

FastAPI backend host에는 최소한 아래 값을 넣는다.

```dotenv
PROJECT_NAME=Project Finance
API_V1_STR=/api/v1
ENVIRONMENT=staging
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:<port>/<database>
SECRET_KEY=<strong-random-secret>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080
BACKEND_CORS_ORIGINS=https://<vercel-frontend-origin>
ENABLE_DB_SCHEMA_BOOTSTRAP=false
SQLALCHEMY_ECHO=false
DB_POOL_PRE_PING=true
ENABLE_MARKET_WARMUP=false
ENABLE_SCHEDULER=false
ENABLE_LLM_REPORT_CRITICS=false
ENABLE_NOTIFICATION_SCHEDULER=false
```

`DATABASE_URL`을 명시하지 않고 Vercel/Supabase가 제공한 env를 backend host에 그대로 주입하는 환경에서는 `POSTGRES_URL_NON_POOLING` 또는 `POSTGRES_URL`이 fallback으로 사용된다. 우선순위는 `DATABASE_URL`, `POSTGRES_URL_NON_POOLING`, `POSTGRES_URL` 순서다. 다만 `POSTGRES_URL` 계열 값도 완성 DB URL이므로 backend-only secret으로 관리한다. `/db-check`의 database 진단은 선택된 변수명(`source`), scheme, host, port만 반환하고 credential은 반환하지 않는다.

처음 hosted smoke에서는 scheduler를 끈다. DB 연결, CORS, 로그인, 기본 API가 안정적으로 확인된 뒤 market warm-up과 report scheduler를 단계적으로 켠다.

### 4.3 Supabase connection mode 선택

Supabase는 connection mode를 여러 개 제공한다. 현재 backend가 별도 persistent runtime에 올라간다는 전제에서는 아래 순서를 권장한다.

| 상황 | 권장 연결 |
| --- | --- |
| backend host가 IPv6 direct connection을 지원함 | Supabase direct connection |
| backend host가 IPv4-only이고 Supabase IPv4 add-on이 없음 | Supavisor shared pooler session mode |
| backend를 serverless/edge function으로 바꾸는 경우 | transaction pooler 검토, prepared statement 비활성화 검증 필요 |
| Alembic migration, backup, `pg_dump` | direct connection 권장 |

이 프로젝트의 `DATABASE_URL`은 항상 SQLAlchemy async scheme으로 맞춘다.

```text
postgresql://...      -> postgresql+asyncpg://...
postgres://...        -> postgresql+asyncpg://...
```

Transaction pooler는 prepared statement 제약이 있을 수 있으므로, 사용할 경우 `DB_PREPARED_STATEMENT_CACHE_SIZE=0` 같은 설정을 staging에서 검증한 뒤 확정한다.

## 5. Migration 적용 순서

Production-like 환경에서는 backend startup이 schema를 자동 생성하게 두지 않는다.

1. Supabase staging project 또는 staging database를 준비한다.
2. backend host 또는 안전한 로컬/CI 환경에 staging `DATABASE_URL`을 주입한다.
3. `backend/`에서 Alembic migration을 실행한다.

```powershell
cd backend
python -m alembic upgrade head
```

4. backend 환경변수에 `ENABLE_DB_SCHEMA_BOOTSTRAP=false`를 둔다.
5. backend를 시작한다.
6. `/health`와 `/db-check`를 확인한다.

`/health`는 앱 생존 확인이고, DB 연결 확인은 `/db-check`로 한다. `/db-check` 응답의 `database.source`는 `DATABASE_URL`, `POSTGRES_URL_NON_POOLING`, `POSTGRES_URL` 중 어떤 변수가 선택됐는지만 알려 주며 secret 값을 포함하지 않는다.

## 6. 배포 후 확인 순서

1. Vercel frontend deployment가 성공했는지 확인한다.
2. frontend의 `VITE_API_BASE_URL`이 backend origin을 가리키는지 확인한다.
3. backend `BACKEND_CORS_ORIGINS`에 Vercel frontend origin이 들어 있는지 확인한다.
4. backend `/health`가 응답하는지 확인한다.
5. backend `/db-check`가 Supabase 연결을 통과하는지 확인한다.
6. frontend에서 market page가 backend API를 호출하는지 확인한다.
7. Google login을 쓴다면 Google Cloud Console의 Authorized JavaScript origins에 Vercel frontend origin을 추가한다.
8. 결제 provider를 쓴다면 success/cancel URL은 Vercel frontend로, webhook URL은 backend로 설정한다.
9. scheduler는 마지막에 켠다.

## 7. 자주 헷갈리는 지점

| 질문 | 답 |
| --- | --- |
| Supabase integration이 `POSTGRES_URL`을 만들어 줬는데 끝인가? | 아니다. backend host에는 가능하면 `DATABASE_URL`을 명시한다. 단, `DATABASE_URL`이 비어 있으면 backend가 `POSTGRES_URL_NON_POOLING`, `POSTGRES_URL` 순서로 fallback한다. |
| Supabase env가 Vercel에 자동으로 들어오면 backend도 자동으로 쓰나? | 아니다. 현재 backend는 Vercel이 아닌 별도 persistent runtime 권장 구조다. backend host에도 secret을 넣어야 한다. |
| `SUPABASE_ANON_KEY`를 frontend에 넣어도 되나? | anon key 자체는 public client 용도로 쓰일 수 있지만, 현재 앱은 Supabase client를 browser에서 직접 쓰지 않는다. 새 기능 없이 추가하지 않는다. |
| `SUPABASE_SERVICE_ROLE_KEY`를 frontend에 넣어도 되나? | 절대 안 된다. backend-only secret이다. |
| staging branch는 Vercel staging environment인가? | 별도 environment를 만들지 않으면 보통 Preview deployment다. 환경변수 scope를 확인해야 한다. |
| env 값을 바꿨는데 배포가 그대로다 | Vercel env 변경은 새 deployment부터 적용된다. 재배포가 필요하다. |

## 8. 공식 참고 자료

- Vercel Supabase Marketplace: `https://vercel.com/marketplace/supabase/supabase`
- Supabase Vercel Marketplace guide: `https://supabase.com/docs/guides/integrations/vercel-marketplace`
- Vercel environment variables: `https://vercel.com/docs/environment-variables`
- Supabase Postgres connection guide: `https://supabase.com/docs/guides/database/connecting-to-postgres`
- Supabase Vercel environment troubleshooting: `https://supabase.com/docs/guides/troubleshooting/vercel-integration-environment-variables-not-syncing-for-persistent-git-branches-b9191e`
