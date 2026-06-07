# Project Finance 환경변수 설정 절차

Date: 2026-06-02
Last updated: 2026-06-03

이 문서는 루트의 `.env_example`을 기준으로 로컬 개발, hosted smoke, 운영 배포 환경에 실제 환경변수 값을 채우는 절차를 설명한다. 실제 `.env` 값, API key, DB password, JWT secret, OAuth secret, webhook secret은 문서나 Git에 남기지 않는다.

이 문서의 목표는 세 가지다.

1. 어떤 값을 직접 정하고, 어떤 값은 외부 dashboard에서 발급받아야 하는지 구분한다.
2. 각 변수를 루트 `.env`, `frontend/.env`, 배포 플랫폼 환경변수 중 어디에 넣어야 하는지 알려준다.
3. 처음 실행할 때 비용이 발생하는 scheduler나 외부 API 호출을 켜지 않고도 backend/frontend가 뜨는지 확인할 수 있게 한다.

## 기본 원칙

- `.env_example`은 공개 예시 파일이다. 실제 값은 `.env`, `frontend/.env`, 배포 플랫폼의 환경변수 저장소에만 둔다.
- `.env`와 `frontend/.env`는 커밋하지 않는다.
- `<your_...>`, `<replace_...>`처럼 꺾쇠로 감싼 값은 placeholder다. 실제 `.env`에서는 자기 환경에 맞는 값으로 바꾼다.
- `VITE_`로 시작하는 값은 브라우저 번들에 노출된다. API key, password, JWT secret, provider secret을 `VITE_` 변수로 만들지 않는다.
- backend는 `backend/app/core/config.py`의 `settings`를 통해 루트 `.env`를 읽는다.
- frontend를 `frontend/`에서 직접 실행할 때 Vite는 `frontend/.env`를 읽는다. `VITE_API_BASE_URL`, `VITE_GOOGLE_CLIENT_ID`처럼 frontend가 필요한 공개 값은 `frontend/.env`에도 둔다.
- 외부 API, LLM, scheduler, 알림 발송은 비용과 rate limit이 생길 수 있다. 처음 검증할 때는 필요한 값만 채우고 background 작업은 보수적으로 끈다.

## 0. 처음 보는 사람을 위한 핵심 요약

환경변수는 "코드에는 넣지 않지만 실행할 때 필요한 설정값"이다. 이 프로젝트에서는 아래처럼 나누어 생각하면 쉽다.

| 종류 | 예시 변수 | 값은 어디서 얻나 | 어디에 저장하나 | 비밀값인가 |
| --- | --- | --- | --- | --- |
| 앱 기본값 | `PROJECT_NAME`, `API_V1_STR`, `ENVIRONMENT` | 직접 정함 | 루트 `.env`, 배포 backend env | 아님 |
| frontend 공개값 | `VITE_API_BASE_URL`, `VITE_GOOGLE_CLIENT_ID` | backend URL, Google OAuth client ID | `frontend/.env`, 배포 frontend env | 아님. 단, 브라우저에 노출됨 |
| DB 접속값 | `POSTGRES_*`, `DATABASE_URL` | 직접 만들거나 DB provider dashboard에서 확인 | 루트 `.env`, 배포 backend env | password와 URL은 비밀값 |
| 인증 secret | `SECRET_KEY` | 로컬에서 랜덤 생성 | 루트 `.env`, 배포 backend env | 비밀값 |
| 외부 provider key | `OPENAI_API_KEY`, `FRED_API_KEY`, `FINNHUB_API_KEY` | 각 provider dashboard에서 발급 | 루트 `.env`, 배포 backend env | 비밀값 |
| 운영 정책값 | `ENABLE_SCHEDULER`, `ENABLE_AI_REPORT_GENERATION`, `REPORT_SCHEDULER_*`, `NOTIFICATION_*` | 팀 운영 정책으로 결정 | 루트 `.env`, 배포 backend env | 보통 비밀값은 아니지만 운영 영향 있음 |

처음 로컬에서 앱이 뜨는지만 확인할 때는 모든 provider key를 한 번에 준비하지 않아도 된다. 우선 아래 묶음만 맞춘다.

- `PROJECT_NAME`, `API_V1_STR`, `ENVIRONMENT`
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT`, `DATABASE_URL`
- `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`
- `VITE_API_BASE_URL`, `LOCAL_CORS_ORIGINS`
- 비용 방지용으로 `ENABLE_MARKET_WARMUP=false`, `ENABLE_SCHEDULER=false`, `ENABLE_AI_REPORT_GENERATION=false`, `ENABLE_LLM_REPORT_CRITICS=false`, `ENABLE_NOTIFICATION_SCHEDULER=false`

기능별로 나중에 추가할 값은 아래 기준으로 보면 된다.

| 하고 싶은 기능 | 추가로 필요한 대표 변수 |
| --- | --- |
| Google 로그인 | `GOOGLE_CLIENT_ID`, `VITE_GOOGLE_CLIENT_ID` |
| AI 리포트/챗봇 실제 LLM 호출 | `OPENAI_API_KEY` |
| 시장/거시 데이터 품질 개선 | `ALPHA_VANTAGE_API_KEY`, `FRED_API_KEY`, `ECOS_API_KEY`, `FMP_API_KEY`, `FINNHUB_API_KEY` |
| 결제 provider 연동 | `PAYMENT_PROVIDER`, `PAYMENT_WEBHOOK_SECRET`, `PAYMENT_PLUS_PLAN_ID`, `PAYMENT_PRO_PLAN_ID` |
| 관심자산 알림 발송 | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `EMAIL_PROVIDER`, `GMAIL_*` |

비밀값인지 헷갈리면 이렇게 판단한다.

- URL 안에 password나 token이 들어 있으면 비밀값이다. `DATABASE_URL`이 대표적이다.
- `KEY`, `SECRET`, `TOKEN`, `PASSWORD`, `REFRESH_TOKEN`이 이름에 들어가면 대부분 비밀값이다.
- `VITE_`로 시작하는 값은 빌드된 frontend에서 볼 수 있으므로 비밀값을 넣으면 안 된다.
- 문서, 이슈, 채팅, 스크린샷에는 실제 값을 적지 않는다. 변수 이름과 placeholder만 적는다.

## 1. 예시 파일 복사

PowerShell을 루트 디렉토리에서 열고 다음을 실행한다.

```powershell
Copy-Item .env_example .env
```

frontend만 따로 실행하면서 Vite 환경변수가 필요하면 `frontend/.env`를 만들고 public 변수만 넣는다.

```dotenv
VITE_API_BASE_URL=http://localhost:8000
VITE_GOOGLE_CLIENT_ID=<your_google_client_id>
```

`frontend/.env`에는 `VITE_API_BASE_URL`, `VITE_GOOGLE_CLIENT_ID`처럼 브라우저에 공개되어도 되는 값만 둔다.

## 2. 실행 환경 결정

먼저 어떤 환경을 설정하는지 정한다.

| 환경 | 권장 설정 |
| --- | --- |
| 로컬 개발 | `ENVIRONMENT=development`, `ENABLE_DB_SCHEMA_BOOTSTRAP=true`, 필요한 provider key만 입력 |
| 첫 hosted smoke | `ENABLE_MARKET_WARMUP=false`, `ENABLE_SCHEDULER=false`, `ENABLE_AI_REPORT_GENERATION=false`, `ENABLE_DB_SCHEMA_BOOTSTRAP=false` |
| 운영 | migration 실행 후 `ENABLE_DB_SCHEMA_BOOTSTRAP=false`, CORS와 provider secret을 배포 환경변수로 관리 |

AI 리포트 scheduler나 알림 scheduler를 켜면 외부 API와 LLM 비용이 발생할 수 있다. 비용 승인 전에는 `ENABLE_AI_REPORT_GENERATION=false`를 포함해 scheduler 관련 값을 보수적으로 두고 API, DB, 인증부터 검증한다.

### 2.1 변수값 확보를 시작하기 전에

`.env_example`의 값은 한 번에 모두 발급받는 것이 아니라, 아래 순서대로 나누어 채우는 것이 읽기 쉽고 실수도 적다.

1. 로컬에서 직접 정하는 값부터 채운다.
2. 앱이 실행되는 주소를 확인해 frontend/backend URL 값을 채운다.
3. DB 값을 만들고 `DATABASE_URL`을 조립한다.
4. 인증에 필요한 Google OAuth client와 JWT secret을 준비한다.
5. AI, 시장 데이터, 결제, 알림 provider는 실제로 사용할 기능만 발급받는다.
6. 값을 넣은 뒤 scheduler를 끈 상태에서 backend와 frontend를 먼저 검증한다.

값을 저장할 위치도 먼저 나눈다.

| 저장 위치 | 넣을 수 있는 값 |
| --- | --- |
| 루트 `.env` | backend가 읽는 DB URL, API key, JWT secret, provider secret |
| `frontend/.env` | `VITE_API_BASE_URL`, `VITE_GOOGLE_CLIENT_ID`처럼 브라우저에 공개되어도 되는 값 |
| 배포 플랫폼 환경변수 | 운영/staging용 backend secret과 frontend public 값 |

`VITE_` 변수는 브라우저 번들에 들어간다. API key, DB password, JWT secret, webhook secret, provider token, refresh token은 `VITE_` 변수로 만들지 않는다.

값을 채울 때는 아래 질문을 변수마다 한 번씩만 던지면 된다.

1. 이 값은 브라우저에서 알아도 되는가?
2. 이 값은 외부 서비스 dashboard에서 발급받는가?
3. 이 값은 로컬 개발에서만 필요한가, 배포에서도 필요한가?
4. 이 값을 바꾸면 비용, 알림 발송, DB schema, 로그인 정책이 달라지는가?

답이 "브라우저에서 알면 안 된다"이면 루트 `.env` 또는 backend 배포 환경변수에만 둔다. 답이 "비용이나 발송이 달라진다"이면 기본값을 보수적으로 두고, 기능 검증이 끝난 뒤 켠다.

### 2.2 1단계: 로컬 기본값 정하기

먼저 외부 dashboard가 필요 없는 값을 채운다.

1. `PROJECT_NAME`은 앱 이름으로 둔다. 보통 `Project Finance`를 그대로 사용한다.
2. `API_V1_STR`은 기본값 `/api/v1`을 유지한다. 현재 앱은 `/api/...` 라우트도 함께 사용한다.
3. `ENVIRONMENT`는 현재 목적에 맞게 정한다.
   - 로컬 개발: `development`
   - 배포 검증: `staging`
   - 운영: `production`
4. `ALGORITHM`은 `HS256`을 유지한다.
5. `ACCESS_TOKEN_EXPIRE_MINUTES`는 로그인 유지 정책으로 정한다. 기본값 `10080`은 7일이다.

처음 실행에서는 `ENVIRONMENT=development`를 권장한다. `production`으로 바꾼다고 앱이 자동으로 배포 환경이 되는 것은 아니며, CORS, DB, migration, scheduler 정책까지 함께 맞아야 한다.

### 2.3 2단계: frontend와 backend 주소 확인

로컬 개발에서는 주소가 보통 고정되어 있다.

1. backend를 로컬에서 `8000` 포트로 실행할 예정이면 `VITE_API_BASE_URL=http://localhost:8000`을 사용한다.
2. frontend를 Vite 기본 포트로 실행할 예정이면 `LOCAL_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173`을 유지한다.
3. 배포 환경에서는 먼저 실제 frontend URL과 backend URL을 확보한다.
4. frontend URL의 origin을 `BACKEND_CORS_ORIGINS`에 넣는다. origin은 `https://example.com`처럼 scheme과 host만 포함하고 path는 넣지 않는다.
5. backend URL을 `VITE_API_BASE_URL`에 넣는다.

Vercel preview처럼 frontend URL이 매번 바뀌는 경우에만 `BACKEND_CORS_ORIGIN_REGEX`를 사용한다. 운영에서는 가능한 한 정확한 origin 목록을 쓰는 편이 안전하다.

주소를 넣을 때는 path를 붙이지 않는다.

| 값 | 좋은 예 | 피해야 할 예 |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `http://localhost:8000` | `http://localhost:8000/api` |
| `BACKEND_CORS_ORIGINS` | `https://project-finance.example.com` | `https://project-finance.example.com/login` |

### 2.4 3단계: 로컬 Docker DB 값 만들기

로컬 PostgreSQL은 직접 이름과 비밀번호를 정해서 만든다.

1. `POSTGRES_USER`를 정한다. 예: `finance_user`
2. `POSTGRES_DB`를 정한다. 예: `finance_db`
3. `POSTGRES_PORT`는 다른 PostgreSQL과 충돌하지 않으면 `5432`를 유지한다.
4. `POSTGRES_PASSWORD`는 새 랜덤 문자열로 만든다. 운영 DB 비밀번호와 재사용하지 않는다.
5. 위 값을 조합해 `DATABASE_URL`을 만든다.

형식:

```dotenv
DATABASE_URL=postgresql+asyncpg://<POSTGRES_USER>:<POSTGRES_PASSWORD>@localhost:<POSTGRES_PORT>/<POSTGRES_DB>
```

예시의 placeholder는 실제 `.env`에서만 바꾼다. 문서, 이슈, 채팅에는 완성된 `DATABASE_URL`을 붙여넣지 않는다.

로컬 DB를 처음 만들 때만 `POSTGRES_*` 값이 Docker volume 초기화에 반영된다. 이미 `postgres_data` volume이 만들어진 뒤 `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`를 바꾸면 기존 DB가 자동으로 바뀌지 않는다.

`DATABASE_URL`을 만들 때 가장 흔한 실수는 아래 세 가지다.

- `postgresql://`로 시작하는 sync driver URL을 넣는 것. 이 backend는 `postgresql+asyncpg://`를 사용한다.
- `POSTGRES_PASSWORD`는 바꿨지만 `DATABASE_URL` 안의 password는 그대로 두는 것.
- 이미 만들어진 Docker volume이 예전 user/password를 계속 쓰고 있는데 `.env`만 바꾸는 것.

### 2.5 4단계: hosted DB URL 확보

Supabase 같은 hosted PostgreSQL을 사용할 때는 provider dashboard에서 접속 정보를 확인한다.

1. provider에서 프로젝트 또는 database를 만든다.
2. connection string 또는 database settings에서 host, port, database name, user, password를 확인한다.
3. provider가 준 URL이 `postgresql://...`이면 앱 설정에서는 `postgresql+asyncpg://...` 형식으로 바꾼다.
4. Vercel/Supabase integration이 `POSTGRES_URL_NON_POOLING` 또는 `POSTGRES_URL`을 제공하고 `DATABASE_URL`이 비어 있으면 backend가 그 값을 fallback으로 읽어 `postgresql+asyncpg://...` 형식으로 정규화한다.
   `/db-check`의 `database.source`는 선택된 변수명만 보여 주므로 secret을 노출하지 않고 fallback 동작을 확인할 수 있다.
5. 그래도 운영에서는 backend host에 명시적인 `DATABASE_URL`을 두는 방식을 우선 권장한다. fallback은 Vercel/Supabase env를 그대로 주입하는 환경에서의 안전장치로 본다.
6. pooler를 사용할 때 prepared statement 관련 오류가 나면 그때 `DB_PREPARED_STATEMENT_CACHE_SIZE`를 조정한다. 오류가 없으면 비워둔다.
7. staging/production에서는 `ENABLE_DB_SCHEMA_BOOTSTRAP=false`로 두고, backend 시작 전에 Alembic migration을 실행한다.

Hosted DB의 connection string은 전체가 비밀값이다. host와 DB 이름만 따로 말하는 것은 가능할 수 있지만, password가 포함된 완성 URL은 문서나 채팅에 붙여넣지 않는다.

Vercel/Supabase가 제공하는 `POSTGRES_URL`, `POSTGRES_URL_NON_POOLING`, `POSTGRES_PASSWORD`도 backend-only secret으로 취급한다. 현재 frontend는 Supabase client를 직접 쓰지 않으므로 이 값을 `frontend/.env`, Vercel frontend public env, 또는 `VITE_` 변수에 넣지 않는다.

### 2.6 5단계: JWT secret 생성

`SECRET_KEY`는 앱이 JWT를 서명할 때 쓰는 backend-only secret이다.

1. PowerShell에서 아래 명령으로 랜덤 문자열을 만든다.
2. 출력된 값은 루트 `.env` 또는 배포 환경변수에만 저장한다.
3. 이미 노출된 값은 재사용하지 않고 새로 생성한다.

```powershell
$bytes = New-Object byte[] 48
[Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
[Convert]::ToBase64String($bytes)
```

### 2.7 6단계: Google 로그인 client ID 발급

Google 로그인은 frontend와 backend가 같은 OAuth client ID를 사용한다.

1. Google Cloud Console에서 프로젝트를 만들거나 기존 프로젝트를 선택한다.
2. Google Auth Platform 또는 OAuth consent screen을 설정한다.
3. OAuth client를 새로 만들고 application type은 `Web application`을 선택한다.
4. Authorized JavaScript origins에 로컬 frontend origin을 추가한다. 예: `http://localhost:5173`
5. 배포 frontend가 있으면 배포 origin도 추가한다. 예: `https://project-finance.example.com`
6. client를 생성한 뒤 client ID를 복사한다.
7. backend용 `GOOGLE_CLIENT_ID`와 frontend용 `VITE_GOOGLE_CLIENT_ID`에 같은 client ID를 넣는다.

이 프로젝트의 현재 Google 로그인 흐름에는 Google client secret을 넣지 않는다.

`GOOGLE_CLIENT_ID`와 `VITE_GOOGLE_CLIENT_ID`는 같은 값을 쓰지만 저장 위치가 다르다. backend는 token 검증에 쓰고, frontend는 Google 로그인 버튼 초기화에 쓴다.

### 2.8 7단계: OpenAI API key 발급

AI 리포트 또는 챗봇에서 실제 OpenAI API를 호출하려면 `OPENAI_API_KEY`가 필요하다.

1. OpenAI Platform에 로그인한다.
2. 사용할 project를 선택한다.
3. API keys 화면에서 새 secret key를 만든다.
4. 생성 직후 값을 안전한 비밀번호 관리자나 배포 secret store에 저장한다.
5. 루트 `.env` 또는 backend 배포 환경변수에만 넣는다.
6. 비용 검증 전에는 `ENABLE_SCHEDULER=false`, `ENABLE_AI_REPORT_GENERATION=false`, `ENABLE_LLM_REPORT_CRITICS=false`를 유지한다.

### 2.9 8단계: 시장/거시 데이터 provider key 발급

아래 key들은 모두 backend-only 값이다. 처음에는 꼭 필요한 provider만 발급받고, 나머지는 placeholder 또는 빈 값으로 둘 수 있다.

| 변수 | 진행 과정 |
| --- | --- |
| `ALPHA_VANTAGE_API_KEY` | Alpha Vantage 계정 생성 또는 API key 신청 화면으로 이동한다. free key를 발급받고 rate limit을 확인한 뒤 backend 환경변수에 저장한다. |
| `FRED_API_KEY` | FRED 계정을 만든 뒤 API key request/view 화면에서 앱용 key를 발급한다. 앱별로 별도 key를 쓰는 것이 좋다. |
| `ECOS_API_KEY` | 한국은행 ECOS Open API 사이트에서 회원가입/로그인 후 인증키를 신청한다. 발급 후 Open API 화면 또는 MyPage에서 인증키를 확인한다. |
| `FMP_API_KEY` | Financial Modeling Prep에 가입한 뒤 dashboard의 API Keys 영역에서 key를 복사한다. Basic 무료 플랜은 EOD/delayed 데이터와 250 calls/day 한도를 전제로 쓰며, 공개 상용 표시/재배포 전에는 license를 재확인한다. |
| `FMP_FETCH_TIMEOUT_SECONDS` | FMP quote/history/profile 단일 호출 timeout. 기본 `10`, 최소 `5`. |
| `FMP_DAILY_CALL_BUDGET` | FMP 무료 한도 초과를 피하기 위한 process-local 일일 호출 budget. 기본 `180`, `0`이면 FMP 호출을 skip한다. 서버 재시작 시 counter는 초기화된다. |
| `FINNHUB_API_KEY` | Finnhub 가입 후 dashboard 또는 registration flow에서 token을 발급받는다. free tier의 뉴스/호가 endpoint 제한을 확인한다. |
| `COINGECKO_DEMO_API_KEY` | CoinGecko Demo API key를 발급받아 암호화폐 현재가/히스토리 수집에 사용한다. |
| `DATA_GO_KR_API_KEY` | 공공데이터포털 금융위원회 주식시세정보/지수시세정보 serviceKey를 발급받는다. |
| `STOOQ_API_KEY` | Stooq daily CSV key. 기본 경로에서는 쓰지 않고 `ENABLE_STOOQ_FALLBACK=true`일 때만 opt-in fallback으로 사용한다. |
| `ENABLE_STOOQ_FALLBACK` | Stooq fallback 사용 여부. 기본 `false`. Render에서 Stooq `ConnectTimeout('')`가 반복된 이력 때문에 production 기본값은 비활성이다. |
| `STOOQ_FETCH_TIMEOUT_SECONDS` | opt-in Stooq daily CSV 단일 호출 timeout. 기본 `12`, 최소 `5`. |

scheduler를 켜면 이 provider들을 반복 호출할 수 있다. rate limit과 비용 정책을 확인하기 전에는 `ENABLE_MARKET_WARMUP=false`, `ENABLE_SCHEDULER=false`, `ENABLE_AI_REPORT_GENERATION=false`로 smoke test를 먼저 끝낸다.

provider key가 비어 있으면 일부 기능은 fallback, cache, 또는 제한된 데이터로 동작할 수 있다. 이 경우 앱 실행 자체보다 데이터 품질과 coverage가 먼저 영향을 받는다.

시장 데이터는 무료 provider의 quota를 보호하기 위해 scheduler/cache 경유로 수집한다. 미국 지수/원자재/미국 주식 history는 FMP EOD 경로를 먼저 사용하고, FMP key가 없거나 일일 budget을 초과하면 빈 history 또는 stale cache로 degrade한다. USD/KRW는 open.er-api.com daily reference rate를 기본값으로 사용하며, 공개 화면에서 trading-grade realtime FX로 표현하지 않는다.

Stooq는 기본 provider가 아니다. `ENABLE_STOOQ_FALLBACK=true`로 명시한 경우에만 미국 지수/원자재/미국 주식 history와 USD/KRW change/history의 보조 fallback으로 호출한다. Render 로그에서 Stooq `ConnectTimeout('')`가 반복되면 fallback을 다시 끄거나 `STOOQ_FETCH_TIMEOUT_SECONDS`를 조정한 뒤 backend를 재시작한다.

### 2.10 9단계: 리포트 scheduler 정책 정하기

리포트 scheduler 변수는 provider에서 발급받는 값이 아니라 비용과 운영 정책으로 정하는 값이다.

1. 첫 hosted smoke에서는 아래처럼 둔다.

```dotenv
ENABLE_MARKET_WARMUP=false
ENABLE_SCHEDULER=false
ENABLE_AI_REPORT_GENERATION=false
ENABLE_LLM_REPORT_CRITICS=false
```

2. 가격/뉴스 scheduler만 먼저 검증하려면 `ENABLE_SCHEDULER=true`, `ENABLE_AI_REPORT_GENERATION=false` 조합을 사용한다.
3. AI 리포트를 켜기로 결정한 뒤 `ENABLE_AI_REPORT_GENERATION=true`로 바꾸고 `REPORT_SCHEDULER_INTERVAL_HOURS`로 실행 간격을 정한다.
4. 한 번에 생성할 최대 리포트 수를 `REPORT_SCHEDULER_MAX_REPORTS_PER_RUN`으로 제한한다.
5. 같은 자산을 너무 자주 생성하지 않도록 `REPORT_SCHEDULER_ASSET_COOLDOWN_HOURS`를 정한다.
6. `REPORT_SCHEDULER_TARGET_TICKERS`에는 backend가 지원하는 ticker만 쉼표로 넣는다. 예: `DGS10,XAU,BTC-USD,NVDA,005930.KS`
7. `REPORT_CRITIC_MODE=deterministic`을 유지하고, 추가 LLM critic은 비용 승인 후 `ENABLE_LLM_REPORT_CRITICS=true`로 켠다.

사용자 화면과 챗봇 요청은 저장된 scheduled report를 읽는 것이 목표 규칙이다. 일반 사용자 요청이 fresh report 생성을 직접 트리거하지 않도록 유지한다.

처음에는 scheduler를 끄는 것이 안전하다. `ENABLE_SCHEDULER=true`는 단순히 UI 기능을 켜는 값이 아니라, backend process가 주기적으로 외부 API 작업을 실행하게 만드는 운영 스위치다. 단, `ENABLE_AI_REPORT_GENERATION=false`이면 scheduler가 켜져 있어도 AI 리포트 생성 job과 서비스 진입부는 건너뛴다.

### 2.11 10단계: 결제 provider 값 준비

결제 provider가 아직 확정되지 않았으면 결제 변수는 비워두고 mock 흐름만 사용할 수 있다.

mock 검증:

1. `PAYMENT_PROVIDER=mock`을 설정한다.
2. `PAYMENT_MOCK_CHECKOUT_BASE_URL`에 frontend billing base URL을 넣는다. 로컬은 `http://localhost:5173/billing`이다.
3. mock에서는 plan ID가 비어 있어도 backend가 mock 기본값을 사용할 수 있다.

실제 provider 검증:

1. 결제 provider dashboard에서 Plus/Pro 상품을 만든다.
2. 각 상품에 recurring price 또는 plan을 만든다.
3. Plus 가격 ID를 `PAYMENT_PLUS_PLAN_ID`, Pro 가격 ID를 `PAYMENT_PRO_PLAN_ID`에 넣는다. Stripe를 쓰는 경우 Product ID가 아니라 Price ID를 사용한다.
4. provider dashboard에서 webhook endpoint를 만든다.
5. endpoint URL은 backend의 billing webhook URL로 등록한다.
6. webhook signing secret을 복사해 `PAYMENT_WEBHOOK_SECRET`에 넣는다.
7. test mode와 live mode의 plan ID, webhook secret은 서로 다르므로 환경별로 분리한다.

결제 값은 실제 돈과 연결될 수 있으므로 test mode와 live mode를 섞지 않는다. live secret이나 live price ID를 로컬 실험용 `.env`에 넣었다면, 의도하지 않은 결제가 일어나지 않도록 provider dashboard에서 test mode 상태를 다시 확인한다.

### 2.12 11단계: 알림 provider 값 준비

알림은 실제 사용자에게 메시지를 보낼 수 있으므로, 발송 정책이 정해지기 전에는 꺼둔다.

```dotenv
ENABLE_NOTIFICATION_SCHEDULER=false
```

공통 정책값:

1. 가격 변동을 얼마나 자주 평가할지 `NOTIFICATION_EVALUATION_INTERVAL_MINUTES`로 정한다.
2. 발송 큐를 얼마나 자주 처리할지 `NOTIFICATION_DELIVERY_INTERVAL_MINUTES`로 정한다.
3. 기본 가격 변동 임계치를 `NOTIFICATION_DEFAULT_PRICE_THRESHOLD_PERCENT`로 정한다.
4. 같은 알림을 다시 보내기 전 대기 시간을 `NOTIFICATION_DEFAULT_COOLDOWN_MINUTES`로 정한다.

Telegram:

1. Telegram에서 `@BotFather`를 연다.
2. `/newbot` 명령으로 bot 이름과 username을 정한다.
3. BotFather가 발급한 token을 `TELEGRAM_BOT_TOKEN`에 저장한다.
4. `TELEGRAM_WEBHOOK_SECRET`은 직접 만든 랜덤 문자열을 사용한다.
5. webhook URL과 secret header 정책이 backend 구현과 맞는지 확인한 뒤 scheduler를 켠다.

SMTP email:

현재 알림 발송 구현은 SMTP를 지원하지 않는다. 이메일 알림은 Gmail API 단일 provider로 발송하므로 `EMAIL_SMTP_*` 값은 설정하지 않는다.

Gmail API:

1. Google Cloud에서 Gmail API를 활성화한다.
2. OAuth client를 만들고 발송 전용 scope인 `https://www.googleapis.com/auth/gmail.send`를 설정한다.
3. 사용자 동의를 통해 refresh token을 발급받는다.
4. `EMAIL_PROVIDER=gmail`로 설정한다.
5. Gmail API 발신 계정 주소를 `EMAIL_FROM_ADDRESS`에 저장한다.
6. `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`에 저장한다.
7. 실제 수신 테스트 전까지 `ENABLE_NOTIFICATION_SCHEDULER=false`를 유지하고 이메일 채널 인증/테스트 알림부터 좁게 검증한다.

### 2.13 12단계: 값을 넣은 뒤 검증 순서

값을 다 넣었다면 곧바로 scheduler를 켜지 말고 좁게 검증한다.

1. `git status --short`로 `.env`와 `frontend/.env`가 추적되지 않는지 확인한다.
2. Docker DB를 실행한다.
3. backend는 `ENABLE_MARKET_WARMUP=false`, `ENABLE_SCHEDULER=false`, `ENABLE_AI_REPORT_GENERATION=false`를 현재 PowerShell 세션에 지정하고 실행한다.
4. `/health`로 앱 liveness를 확인한다.
5. `/db-check`로 DB 연결을 확인한다. 이 endpoint는 선택된 DB 변수명, scheme, host, port처럼 credential을 노출하지 않는 진단만 반환해야 한다.
6. frontend build를 확인한다.
7. Google login, payment, notification처럼 provider 값이 필요한 기능은 해당 provider test mode에서 좁게 검증한다.

검증 중 오류가 나면 실제 secret 값을 출력하지 말고 아래 정보만 공유한다.

- 어떤 명령을 실행했는지
- 어떤 변수 이름과 기능 영역에서 문제가 의심되는지
- 오류 메시지 중 secret이 포함되지 않은 부분
- `/health`, `/db-check` 같은 endpoint의 상태 코드와 sanitized 응답

공식 참고 링크:

- OpenAI API authentication: `https://platform.openai.com/docs/api-reference/authentication`
- Google OAuth/Web client credentials: `https://developers.google.com/workspace/guides/create-credentials`
- Vercel Vite environment variables: `https://vercel.com/docs/frameworks/frontend/vite`
- Vercel project environment variables: `https://vercel.com/docs/projects/environment-variables`
- Alpha Vantage documentation/API key: `https://www.alphavantage.co/documentation/`
- FRED API keys: `https://fred.stlouisfed.org/docs/api/fred/v2/api_key.html`
- ECOS Open API: `https://ecos.bok.or.kr/api/#/`
- Financial Modeling Prep quickstart: `https://site.financialmodelingprep.com/developer/docs/quickstart`
- Finnhub API docs/register: `https://finnhub.io/`, `https://finnhub.io/register`
- Telegram BotFather guide: `https://core.telegram.org/bots/features`
- Stripe webhooks/signatures and prices: `https://docs.stripe.com/webhooks/signatures`, `https://docs.stripe.com/api/prices/create`

## 3. App metadata

대부분 기본값을 유지한다.

- `PROJECT_NAME`: FastAPI 앱 이름.
- `API_V1_STR`: v1 API prefix. 현재 앱은 `/api/...` 라우트도 함께 사용한다.
- `ENVIRONMENT`: `development`, `staging`, `production` 중 현재 런타임 구분값.

## 4. Frontend public runtime

`VITE_API_BASE_URL`에는 브라우저가 호출할 backend origin을 넣는다.

- 로컬 backend: `http://localhost:8000`
- 배포 backend: 실제 FastAPI backend의 HTTPS origin

이 값은 public 값이다. API key나 secret을 넣으면 안 된다.

## 5. Database

`DATABASE_URL`에는 async SQLAlchemy가 사용할 PostgreSQL URL을 넣는다.

로컬 Docker DB를 사용할 때는 다음 순서로 맞춘다.

1. `.env`에 `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT`를 채운다.
2. `DATABASE_URL`을 같은 값 묶음에 맞춰 `postgresql+asyncpg://<user>:<password>@localhost:<port>/<db>` 형식으로 채운다.
3. DB를 실행한다.

```powershell
docker compose up -d db
```

`docker-compose.yml`은 `POSTGRES_*` 값을 직접 저장하지 않고 `.env`에서 읽는다. `docker compose config`는 병합된 설정을 보여주므로 로컬에서 실행할 때 실제 credential이 터미널에 출력될 수 있다. 출력 결과를 문서, 이슈, 채팅에 붙여넣지 않는다.

Hosted DB를 사용할 때는 provider가 제공한 PostgreSQL 접속 정보를 `postgresql+asyncpg://...` 형식으로 변환해 넣는다. Supabase URL에 `?sslmode=require` 같은 query가 포함돼도 backend는 asyncpg가 이해하는 `ssl=require` 형태로 정규화한다. Supabase pooler처럼 prepared statement 문제가 생기는 환경에서는 `DB_PREPARED_STATEMENT_CACHE_SIZE` 조정이 필요할 수 있다.

backend는 `DATABASE_URL`의 async driver scheme을 설정 로드 시 검증한다. PostgreSQL은 최종적으로 `postgresql+asyncpg://`, 테스트용 SQLite는 `sqlite+aiosqlite://`를 사용한다. Supabase dashboard나 Vercel integration에서 받은 `postgresql://...` 또는 `postgres://...` 값은 설정 로드 중 `postgresql+asyncpg://...`로 정규화된다.

`DATABASE_URL`이 비어 있고 `POSTGRES_URL_NON_POOLING` 또는 `POSTGRES_URL`이 있으면 backend는 그 값을 fallback으로 사용한다. 우선순위는 `DATABASE_URL`, `POSTGRES_URL_NON_POOLING`, `POSTGRES_URL` 순서다. `POSTGRES_URL` 계열 값도 password가 포함된 secret이므로 browser public env에 넣지 않는다. `/db-check` 응답에는 선택된 변수명인 `source`만 포함되고 URL 전체, username, password는 포함되지 않는다.

운영 또는 운영 유사 환경에서는 schema를 startup에서 자동 생성하지 않도록 `ENABLE_DB_SCHEMA_BOOTSTRAP=false`로 두고, backend 배포 전에 migration을 실행한다.

```powershell
cd backend
python -m alembic upgrade head
```

## 6. CORS

frontend origin을 backend CORS 설정에 등록한다.

- `LOCAL_CORS_ORIGINS`: 로컬 Vite origin. 보통 기본값을 유지한다.
- `BACKEND_CORS_ORIGINS`: 배포 frontend origin을 쉼표로 구분해 넣는다.
- `BACKEND_CORS_ORIGIN_REGEX`: Vercel preview URL 같은 패턴 허용이 필요할 때만 사용한다.

credentialed 요청을 쓰는 앱이므로 운영에서 wildcard origin을 쓰지 않는다.

## 7. AI / LLM

`OPENAI_API_KEY`는 AI 리포트 또는 챗봇에서 OpenAI API를 호출할 때 필요한 backend-only key다.

절차:

1. OpenAI dashboard에서 API key를 발급한다.
2. 루트 `.env` 또는 backend 배포 환경변수에만 저장한다.
3. frontend `.env`나 `VITE_` 변수에는 저장하지 않는다.
4. 비용 검증 전에는 `ENABLE_SCHEDULER=false`, `ENABLE_AI_REPORT_GENERATION=false`, `ENABLE_LLM_REPORT_CRITICS=false`를 유지한다.

일반 테스트와 smoke 검증에서는 실제 LLM 호출이 필요하지 않도록 좁은 검증을 먼저 수행한다.

## 8. Market and macro data providers

시장/거시 데이터 provider key는 모두 backend-only 값이다.

- `ALPHA_VANTAGE_API_KEY`
- `FRED_API_KEY`
- `ECOS_API_KEY`
- `FMP_API_KEY`
- `FINNHUB_API_KEY`

각 provider dashboard에서 key를 발급받아 루트 `.env` 또는 backend 배포 환경변수에 넣는다. 일부 값이 비어 있어도 fallback 또는 무료 경로로 동작할 수 있지만, 데이터 품질과 coverage가 제한될 수 있다.

## 9. Google login

Google Cloud Console에서 Web application OAuth client를 만든다.

1. OAuth consent screen을 설정한다.
2. OAuth client type은 `Web application`으로 만든다.
3. Authorized JavaScript origins에 현재 frontend origin을 추가한다.
4. 발급된 client ID를 `GOOGLE_CLIENT_ID`와 `VITE_GOOGLE_CLIENT_ID`에 넣는다.

`GOOGLE_CLIENT_ID`는 backend가 Google ID token audience를 검증하는 값이고, `VITE_GOOGLE_CLIENT_ID`는 frontend Google Identity Services 버튼에 쓰는 public identifier다. Google client secret은 현재 이 로그인 흐름에 넣지 않는다.

## 10. JWT authentication

`SECRET_KEY`는 JWT 서명용 긴 랜덤 문자열로 바꾼다.

PowerShell 예시:

```powershell
$bytes = New-Object byte[] 48
[Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
[Convert]::ToBase64String($bytes)
```

생성한 값은 `.env` 또는 배포 환경변수에만 저장한다.

- `ALGORITHM`: backend 코드와 맞춰 `HS256` 유지.
- `ACCESS_TOKEN_EXPIRE_MINUTES`: access token 만료 시간. 기본값 `10080`은 7일이다.

이미 노출된 secret을 사용했다면 새 값으로 교체하고 기존 token은 폐기된 것으로 취급한다.

## 11. Runtime tasks

background 작업은 비용과 부하를 만들 수 있으므로 단계적으로 켠다.

- `ENABLE_MARKET_WARMUP`: backend 시작 시 시장 데이터 cache warm-up 실행 여부.
- `ENABLE_SCHEDULER`: APScheduler 기반 가격, 뉴스, 알림, 리포트 작업 실행 여부.
- `ENABLE_AI_REPORT_GENERATION`: 전체 scheduler가 켜져 있어도 AI 리포트 생성 job과 서비스 진입부를 허용할지 여부. 저장된 리포트 조회에는 영향을 주지 않는다.
- `MARKET_PRICES_REFRESH_MINUTES`: 사용자 화면에 노출되는 시세 cache를 scheduler가 갱신하는 간격(분). 기본값 `5`. AI 리포트와 무관한 일반 데이터 주기.
- `MARKET_NEWS_REFRESH_MINUTES`: 뉴스 cache 갱신 간격(분). 기본값 `60`(=1시간).
- `MARKET_LATEST_CONTEXT_TTL_MINUTES`: 종목 상세 `latest-context` cache 유효시간(분). 기본값 `10`. 만료 전에는 cache를 재사용하고 만료 후 첫 요청에서 다시 가져온다.
- 위 세 값은 모두 분 단위이며 최소 `1`로 강제된다(0/음수 입력 시 1로 보정). 간격을 줄이면 yfinance 등 외부 API 호출 빈도와 부하가 늘어난다.
- `REPORT_SCHEDULER_*`: 저장형 AI 리포트 생성 주기와 대상 ticker.
- `REPORT_SCHEDULER_STARTUP_DELAY_SECONDS`: backend 시작 직후 등록되는 1회성 startup 리포트 job 지연 시간(초). 기본값 `180`. Render 같은 hosted runtime에서는 market warm-up과 provider queue가 먼저 돌도록 180~300초를 권장한다. 0/음수 입력 시 0으로 보정된다.
- `ENABLE_LLM_REPORT_CRITICS`: 추가 LLM critic agent 사용 여부.
- `REPORT_CRITIC_MODE`: 기본값 `deterministic` 유지 권장.

첫 hosted smoke에서는 다음처럼 시작하는 것을 권장한다.

```dotenv
ENABLE_MARKET_WARMUP=false
ENABLE_SCHEDULER=false
ENABLE_AI_REPORT_GENERATION=false
ENABLE_LLM_REPORT_CRITICS=false
```

가격/뉴스 scheduler만 먼저 확인하려면 `ENABLE_SCHEDULER=true`, `ENABLE_AI_REPORT_GENERATION=false`로 둔다. 이 조합에서는 `generate_daily_reports`와 startup 리포트 job이 등록되지 않고, 서비스 함수가 직접 호출되어도 즉시 건너뛴다.

사용자 화면과 챗봇 요청은 저장된 scheduled report를 읽는 것이 목표 규칙이다. 일반 사용자 요청이 fresh report 생성을 직접 트리거하지 않도록 유지한다.

## 12. Payment provider boundary

결제 provider가 확정되지 않았으면 provider 값은 비워둘 수 있다.

- `PAYMENT_PROVIDER`: 실제 provider 이름.
- `PAYMENT_WEBHOOK_SECRET`: provider webhook 서명 검증 secret.
- `PAYMENT_PLUS_PLAN_ID`, `PAYMENT_PRO_PLAN_ID`: provider에 생성한 상품 또는 요금제 ID.
- `PAYMENT_MOCK_CHECKOUT_BASE_URL`: mock checkout redirect base URL.

운영 결제 연동 전에는 VAT, 환불, 실패 결제, downgrade 정책을 먼저 확정한다. Webhook secret은 backend-only 값이다.

## 13. Favorite asset notifications

알림 발송은 실제 사용자에게 메시지를 보낼 수 있으므로 운영 정책 확정 전에는 꺼둔다.

```dotenv
ENABLE_NOTIFICATION_SCHEDULER=false
```

Telegram을 사용할 때는 BotFather에서 bot token을 발급받고 webhook 검증 secret을 별도로 만든다.

Email을 사용할 때는 실제 구현에서 지원하는 provider를 기준으로 설정한다.

- Gmail API: OAuth client, client secret, refresh token 필요.
- SMTP: 현재 알림 발송 구현에서 지원하지 않음.

provider token과 Gmail refresh token은 backend-only 값이다.

## 14. 배포 환경변수 등록

배포에서는 `.env` 파일을 서버에 직접 복사하기보다 플랫폼의 환경변수 저장소를 사용한다.

Frontend 배포:

- `VITE_API_BASE_URL`
- `VITE_GOOGLE_CLIENT_ID`

Backend 배포:

- `DATABASE_URL`
- `SECRET_KEY`
- `GOOGLE_CLIENT_ID`
- 필요한 provider API key
- scheduler, CORS, payment, notification 관련 backend-only 변수

운영 DB를 쓰는 backend는 시작 전 migration을 실행하고 `ENABLE_DB_SCHEMA_BOOTSTRAP=false`를 유지한다.

## 15. 검증 절차

값을 채운 뒤 다음 순서로 확인한다.

1. `.env`와 `frontend/.env`가 Git에 추적되지 않는지 확인한다.

```powershell
git status --short
```

2. DB를 실행한다.

```powershell
docker compose up -d db
```

3. backend 설정 로드와 health endpoint를 확인한다. 출력에 secret을 찍는 임의 스크립트는 사용하지 않는다.

```powershell
cd backend
$env:ENABLE_MARKET_WARMUP="false"
$env:ENABLE_SCHEDULER="false"
$env:ENABLE_AI_REPORT_GENERATION="false"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

`uvicorn`이 인식되지 않는 오류가 나면 전역 PATH에 설치된 실행 파일이 없다는 뜻이다. 위처럼 가상환경 Python으로 module 실행을 사용한다. 가상환경에 의존성이 아직 설치되지 않았다면 먼저 다음을 실행한다.

위의 `$env:...` 값은 현재 PowerShell 세션에서만 적용된다. 설정 로드와 `/health` 확인만 할 때는 startup market warm-up, APScheduler, AI report generation이 실행되지 않도록 끄고 검증하는 것이 안전하다.

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

다른 터미널에서:

```powershell
Invoke-WebRequest http://localhost:8000/health -UseBasicParsing
```

4. frontend build를 확인한다.

```powershell
cd frontend
npm run build
```

5. 로그인, 자산 상세, 결제 mock, 알림 설정처럼 provider 값이 필요한 기능은 해당 provider key를 넣은 뒤 좁게 검증한다.

## 16. 흔한 문제

| 증상 | 확인할 것 |
| --- | --- |
| backend가 시작 시 설정 오류를 낸다 | `.env`에 필수값 `PROJECT_NAME`, `API_V1_STR`, `DATABASE_URL`이 있는지 확인 |
| DB URL scheme 설정 오류 | PostgreSQL은 `postgresql+asyncpg://`, 테스트용 SQLite는 `sqlite+aiosqlite://`를 쓰는지 확인 |
| DB 연결 실패 | `POSTGRES_*`와 `DATABASE_URL`의 user, password, DB name, host, port가 실제 DB와 맞는지 확인 |
| `connect() got an unexpected keyword argument 'sslmode'` | Supabase/libpq URL의 `sslmode`가 asyncpg에 맞지 않는 증상이다. 최신 코드에서는 `sslmode`를 `ssl`로 정규화하므로 코드를 갱신한 뒤 다시 실행한다 |
| `invalid literal for int() with base 10: ''` | DB URL의 port 구간이 비어 있을 수 있다. Supabase 콘솔에서 host, port, database name을 다시 확인하고 URL 전체를 채팅/문서에 붙여넣지 않는다 |
| `POSTGRES_*`를 바꿨는데 접속이 계속 실패한다 | 기존 `postgres_data` volume은 최초 초기화된 user, password, DB name을 유지한다. 데이터 보존이 필요하면 새 user/DB 생성 또는 dump/restore를 검토한다 |
| frontend에서 API 호출 실패 | `VITE_API_BASE_URL`과 backend CORS origin 설정 확인 |
| Google 로그인 실패 | `GOOGLE_CLIENT_ID`, `VITE_GOOGLE_CLIENT_ID`, Google Console authorized origin 확인 |
| hosted smoke가 느리거나 외부 API 오류가 많다 | `ENABLE_MARKET_WARMUP=false`, `ENABLE_SCHEDULER=false`, `ENABLE_AI_REPORT_GENERATION=false`로 시작했는지 확인 |
| scheduler는 켰지만 AI 리포트 비용은 막고 싶다 | `ENABLE_SCHEDULER=true`, `ENABLE_AI_REPORT_GENERATION=false`, `ENABLE_LLM_REPORT_CRITICS=false` 조합인지 확인 |
| 결제 webhook 검증 실패 | provider dashboard의 webhook secret과 backend 환경변수 일치 여부 확인 |

## 17. 로컬 Docker DB volume 재초기화 주의

`docker-compose.yml`의 `postgres_data` named volume은 컨테이너를 지워도 DB 데이터를 보존한다. 이 volume이 이미 만들어진 뒤에는 `.env`의 `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`를 바꿔도 기존 DB가 새 값으로 자동 재초기화되지 않는다.

로컬 데이터가 필요 없어서 volume을 삭제해야 하는 경우는 데이터 손실 작업이다. 실행 전 사용자 확인을 받고, 삭제 대상 volume 이름을 먼저 확인한 뒤 진행한다. 문서나 하네스 응답에 실제 DB password 또는 `DATABASE_URL` 전체를 남기지 않는다.

## 18. 환경변수 변경 시 문서 갱신

새 환경변수를 추가하거나 기존 변수 의미를 바꾸면 함께 갱신한다.

- `.env_example`
- `backend/app/core/config.py`
- 관련 feature document under `docs/harness/features/`
- 변경 기록 under `docs/harness/`
- 필요하면 이 문서

문서에는 변수 이름, 용도, 공개 여부, 검증 방법만 남기고 실제 값은 쓰지 않는다.
