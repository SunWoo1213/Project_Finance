# Supabase 콘솔 작업 체크리스트

Date: 2026-06-03

## Objective

`Project_Finance`를 Supabase PostgreSQL에 연결하기 전에 Supabase 콘솔에서 해야 할 일을 정리한다. 이 문서는 실제 DB password, connection string, API key, JWT secret, service role key를 기록하지 않는다.

현재 권장 구조는 Vercel frontend, 별도 persistent FastAPI backend, Supabase PostgreSQL이다. 따라서 Supabase 콘솔 작업의 중심은 Supabase Auth 설정이 아니라 PostgreSQL project, connection mode, migration 준비, 보안/운영 확인이다.

## 먼저 처리할 보안 주의

이미 채팅, 문서, 스크린샷, 로그에 실제 `DATABASE_URL`, DB password, `SUPABASE_SERVICE_ROLE_KEY`, provider secret이 노출됐다면 해당 값은 노출된 것으로 간주하고 교체한다.

- 로컬 Docker DB password라도 다른 환경에서 재사용했다면 새 값으로 바꾼다.
- Supabase production/staging DB password가 노출됐다면 Supabase 콘솔에서 database password를 rotate하고 backend host secret도 갱신한다.
- Secret 교체 후에는 기존 deployment나 로컬 터미널 로그에 값이 남아 있지 않은지 확인한다.

## 1. Supabase project 생성 또는 선택

1. Supabase dashboard에서 새 project를 만들거나 Vercel Marketplace와 연결할 기존 project를 선택한다.
2. Organization, project name, region을 결정한다.
3. Region은 backend runtime과 가까운 위치를 우선한다. frontend 사용자의 위치보다 backend와 DB 사이 latency가 더 중요하다.
4. Database password는 새 랜덤 값으로 만든다. 로컬 DB, 다른 Supabase project, Vercel, Google, OpenAI secret과 재사용하지 않는다.
5. Project 생성 후 `Project Ref`, region, database name만 운영 메모에 남긴다. Password와 완성 connection string은 남기지 않는다.

## 2. Connection string 확인

Supabase project의 `Connect` 또는 database connection 화면에서 backend에 사용할 PostgreSQL connection string을 확인한다.

현재 프로젝트 기준 권장 선택:

| 상황 | Supabase 콘솔에서 선택할 연결 |
| --- | --- |
| Persistent backend host가 IPv6 direct connection을 지원함 | Direct connection 우선 |
| Persistent backend host가 IPv4-only임 | Shared pooler session mode 검토 |
| Backend를 serverless/edge function으로 옮김 | Transaction pooler 검토, prepared statement 비활성화 검증 필요 |
| Migration, dump, restore 같은 관리 작업 | Direct connection 권장 |

Backend host에는 가능하면 `DATABASE_URL` 이름으로 등록한다.

```dotenv
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:<port>/<database>
```

Supabase 콘솔의 원본 URL이 `postgresql://...` 또는 `postgres://...`로 표시되어도 backend 설정 로드 중 `postgresql+asyncpg://...`로 정규화된다. 다만 운영자가 환경변수를 직접 넣을 때는 async SQLAlchemy scheme으로 맞춰두는 편이 실수를 줄인다.

Supabase 콘솔의 connection string에 `?sslmode=require`가 붙어 있어도 최신 backend 설정은 이를 asyncpg가 이해하는 `ssl=require` query로 정규화한다. `connect() got an unexpected keyword argument 'sslmode'` 오류가 보이면 코드가 최신인지 확인한다.

`invalid literal for int() with base 10: ''` 오류가 보이면 connection string의 port가 비어 있거나 URL을 복사하는 과정에서 `host:/database` 같은 형태가 됐을 가능성이 높다. Supabase 콘솔에서 host, port, database name을 다시 확인하되, 완성 URL은 문서나 채팅에 붙여넣지 않는다.

Transaction pooler를 선택한 경우:

- Prepared statement 관련 오류가 날 수 있으므로 staging에서 먼저 검증한다.
- 필요할 때만 backend env에 `DB_PREPARED_STATEMENT_CACHE_SIZE=0` 후보를 넣고 `/db-check`, 주요 API, Alembic 동작을 확인한다.
- 오류가 없으면 `DB_PREPARED_STATEMENT_CACHE_SIZE`는 비워둔다.

## 3. Supabase API key 확인

`Project Settings`의 API 영역에서 `SUPABASE_URL`, anon key, service role key가 보일 수 있다.

현재 앱은 브라우저에서 Supabase client를 직접 사용하지 않는다. 따라서:

- `SUPABASE_SERVICE_ROLE_KEY`는 frontend, `VITE_` 변수, Git, 문서에 절대 넣지 않는다.
- `SUPABASE_ANON_KEY`도 현재 frontend 기능에는 필요하지 않으므로 추가하지 않는다.
- Vercel/Supabase integration이 key를 자동 동기화하더라도 현재 Vite frontend public env로 노출하지 않는다.
- 나중에 Supabase client를 직접 쓰는 기능을 만들 때는 별도 설계와 RLS 정책을 먼저 문서화한다.

## 4. Database schema와 migration 준비

Supabase SQL Editor에서 임의로 schema를 손수 만들기보다, 이 저장소의 Alembic migration을 backend 또는 CI에서 실행한다.

작업 순서:

1. Supabase project가 staging인지 production인지 확인한다.
2. Backend host 또는 안전한 로컬/CI 환경에 해당 Supabase `DATABASE_URL`을 backend-only secret으로 넣는다.
3. `ENABLE_DB_SCHEMA_BOOTSTRAP=false`를 사용한다.
4. `backend/`에서 migration을 실행한다.

```powershell
cd backend
python -m alembic upgrade head
```

5. Supabase 콘솔의 Table Editor 또는 SQL Editor에서 필요한 table이 생성됐는지 이름만 확인한다.
6. 수동으로 column을 추가하거나 table을 고치지 않는다. 필요한 schema 변경은 새 Alembic revision으로 만든다.

Supabase SQL Editor에서 확인만 할 때는 secret이 출력되는 쿼리를 실행하지 않는다. 예를 들어 `select now();`, `select current_database();` 같은 무해한 진단만 사용한다.

## 5. RLS와 public Data API 정책

현재 backend가 SQLAlchemy로 직접 DB에 접속하고, frontend는 backend API만 호출한다. 이 구조에서는 Supabase Data API를 브라우저에서 직접 호출하지 않는다.

콘솔에서 지킬 기준:

- Frontend용 anon key를 사용하는 table access 정책을 만들지 않는다.
- RLS policy를 급하게 열어 public read/write를 허용하지 않는다.
- `auth.uid()` 기반 Supabase Auth policy는 현재 앱 인증 모델과 바로 맞지 않는다. 현재 앱은 Google Identity Services와 backend JWT를 사용한다.
- Supabase client를 도입하기 전까지 user-facing DB access는 FastAPI route와 service layer를 통과하게 둔다.

나중에 Supabase Auth 또는 Supabase client를 도입하면, feature 문서와 migration 계획을 먼저 갱신하고 table별 RLS policy를 staging에서 검증한다.

## 6. Supabase Auth는 현재 필수 작업 아님

현재 로그인 흐름은 Google Identity Services에서 받은 ID token을 FastAPI backend가 검증하고 자체 JWT를 발급하는 구조다. Supabase Auth 콘솔 설정은 지금 당장 필수가 아니다.

Supabase Auth를 별도로 쓰기로 결정한 경우에만 아래를 진행한다.

1. Authentication URL Configuration에서 Site URL과 Redirect URLs를 등록한다.
2. Google provider를 켜는 경우 Google Cloud Console의 OAuth redirect URI에 Supabase callback URL을 추가한다.
3. Frontend callback route와 backend JWT 발급 흐름을 다시 설계한다.
4. 기존 `GOOGLE_CLIENT_ID`, `VITE_GOOGLE_CLIENT_ID` 흐름과 충돌하지 않도록 feature 문서를 갱신한다.

## 7. Vercel Marketplace 연동을 쓸 때

Vercel Marketplace에서 Supabase integration을 설치했다면 Supabase 콘솔과 Vercel project가 연결됐는지 확인한다.

확인할 것:

1. 연결된 Supabase project가 staging/production 중 의도한 project인지 확인한다.
2. Vercel Project Settings에 `POSTGRES_URL`, `POSTGRES_URL_NON_POOLING`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DATABASE`, `SUPABASE_URL` 계열 값이 생겼는지 확인한다.
3. 해당 값이 frontend public env로 쓰이지 않는지 확인한다.
4. Persistent backend host에도 별도로 `DATABASE_URL`을 등록한다. Vercel frontend에 생긴 DB env가 backend host로 자동 전달된다고 가정하지 않는다.

## 8. 운영 보안 설정 확인

Supabase 콘솔에서 운영 전에 아래를 확인한다.

- Organization과 project 접근 권한이 필요한 사람에게만 부여됐는지 확인한다.
- Production project와 staging project를 구분한다.
- Service role key는 backend secret store에서만 사용한다.
- Database password와 service role key는 노출 시 즉시 rotate한다.
- 가능한 경우 backup, PITR, database log retention, network restriction 또는 allowlist 정책을 plan과 조직 정책에 맞게 설정한다.
- 운영 DB에 destructive SQL을 실행하기 전에는 별도 승인과 backup 확인을 거친다.

## 9. 첫 smoke 전 Supabase 콘솔 확인

Migration 실행 후 backend를 띄우기 전에 콘솔에서 확인한다.

1. Project status가 healthy인지 확인한다.
2. Database connection info가 의도한 region/project를 가리키는지 확인한다.
3. Table Editor에서 migration 결과가 보이는지 확인한다.
4. Logs에서 connection/authentication 오류가 반복되지 않는지 확인한다.
5. Connection pooler를 쓴다면 connection count와 pooler 관련 오류를 확인한다.

Backend smoke에서는 `/health`와 `/db-check`를 사용한다. `/health`는 앱 생존 확인이고, DB 연결 확인은 `/db-check`다. `/db-check`는 선택된 변수명, scheme, host, port만 반환해야 하며 credential을 노출하지 않아야 한다.

## 10. Production 전 최종 체크리스트

- Supabase production project와 staging project를 혼동하지 않는다.
- Production DB password는 로컬/스테이징과 다르다.
- Backend production env에 `DATABASE_URL`, `SECRET_KEY`, `BACKEND_CORS_ORIGINS`, scheduler 정책값이 등록돼 있다.
- `ENABLE_DB_SCHEMA_BOOTSTRAP=false`다.
- Alembic migration이 production DB에 적용됐다.
- Vercel frontend에는 `VITE_API_BASE_URL`, 필요한 경우 `VITE_GOOGLE_CLIENT_ID`만 public env로 둔다.
- Supabase DB URL, password, service role key, provider secret은 frontend env에 없다.
- 첫 production smoke에서는 `ENABLE_MARKET_WARMUP=false`, `ENABLE_SCHEDULER=false`, `ENABLE_AI_REPORT_GENERATION=false`, `ENABLE_NOTIFICATION_SCHEDULER=false`로 시작한다.
- Scheduler와 AI report generation은 비용/rate limit 확인 후 단계적으로 켠다.

## 공식 참고 자료

- Supabase Postgres connection strings: `https://supabase.com/docs/reference/postgres/connection-strings`
- Supabase Auth redirect URLs: `https://supabase.com/docs/guides/auth/redirect-urls`
- Supabase Google login: `https://supabase.com/docs/guides/auth/social-login/auth-google`
- Supabase secure data: `https://supabase.com/docs/guides/database/secure-data/`

## Verification Performed

- 문서 작성만 수행했다.
- Supabase 콘솔, Vercel dashboard, backend host에는 접속하지 않았다.
- Secret 값은 문서에 기록하지 않았다.

## Follow-up Risks

- Supabase 콘솔 UI 이름과 메뉴 위치는 시간이 지나며 바뀔 수 있다. 실제 작업 전에는 공식 문서와 dashboard의 현재 표시명을 확인한다.
- Backend hosting provider가 확정되지 않았으므로 direct connection과 pooler mode는 staging에서 최종 검증해야 한다.
- Supabase Auth를 도입할 경우 현재 Google login/backend JWT 흐름과 인증 모델이 달라지므로 별도 설계가 필요하다.
