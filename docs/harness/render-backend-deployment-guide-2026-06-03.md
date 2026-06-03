# Render 백엔드 배포 가이드 (프론트 Vercel + Supabase)

Date: 2026-06-03

## Objective

`Project_Finance`의 FastAPI 백엔드를 **Render**에 배포하는 단계별 가이드를 정리한다. 프론트엔드는 Vercel, DB는 Supabase PostgreSQL을 사용한다. 이 문서는 가이드/계획서이며, 이번 단계에서는 코드를 변경하지 않는다. 실제 배포는 사용자가 Render 대시보드에서 수행한다.

함께 참고:
- `docs/harness/backend-free-tier-deployment-plan-2026-06-03.md` (무료 티어 트레이드오프)
- `docs/harness/vercel-supabase-deployment-plan-2026-06-01.md` (환경변수 인벤토리)
- `docs/harness/features/deployment-runtime.md`

## 왜 Render인가 (요약)

현재 백엔드는 in-process 스케줄러([main.py:167-273](../../backend/app/main.py#L167-L273)), 전역 메모리 캐시([main.py:348-355](../../backend/app/main.py#L348-L355)), 장시간 LLM 리포트 파이프라인을 가진 **persistent 런타임** 구조다. Render Web Service는 항상 켜진 프로세스를 제공하므로 **코드 수정 없이** 이 구조가 동작한다. (Vercel serverless는 스케줄러·캐시·번들 한도 문제로 대규모 리팩터링이 필요하다.)

## 플랜 선택 (배포 전 결정)

| 플랜 | 비용 | sleep | 이 앱에서의 적합도 |
|---|---|---|---|
| Free | 0원 | 15분 idle 후 sleep | API 데모는 가능. 스케줄러 유지하려면 UptimeRobot로 5분마다 `/health` 핑 필요(편법). 리포트 생성은 무리. |
| Starter | 약 $7/월, RAM 약 512MB | 없음 | API·로그인·시장데이터·가격/뉴스 스케줄러 안정. **AI 리포트 생성은 메모리 빠듯(OOM 위험)** → 처음엔 리포트 OFF. |
| Standard | 약 $25/월, RAM 약 2GB | 없음 | LLM+pandas 리포트 파이프라인까지 여유 있게 운영. |

> 정확한 사양·가격은 Render 정책이 바뀌므로 배포 직전 대시보드에서 재확인한다.

권장: **Starter로 시작 + 리포트 OFF**. 리포트 생성을 상시 돌릴 계획이면 Standard. 비용 0원이 절대 조건이면 Free + UptimeRobot 핑(단점 감수).

## 사전 준비물

1. GitHub 저장소(`Project_Finance`)에 접근 권한.
2. Supabase 프로젝트와 connection string(secret은 문서/로그에 남기지 않음).
3. Google `GOOGLE_CLIENT_ID` 등 사용할 기능의 키(있을 때만, 단계적으로 추가).
4. `git status --short`로 미커밋 변경 확인.

## Phase 1. Supabase 준비

1. Supabase 프로젝트 생성(또는 기존 사용), 리전 선택.
2. `Connect` 화면에서 connection string 확보. backend는 `postgresql://`/`postgres://`를 `postgresql+asyncpg://`로 자동 정규화한다([config.py:13-37](../../backend/app/core/config.py#L13-L37)).
3. staging/production 분리 여부 결정. 가능하면 staging DB 먼저.
4. (마이그레이션은 Phase 4에서) 무료 Supabase는 미사용 시 일시중지·연결 수 제한이 있음을 인지.

## Phase 2. Render Web Service 생성

Render 대시보드에서:

1. **New → Web Service**, GitHub 저장소 연결.
2. **Root Directory**: `backend`
3. **Runtime**: Python 3 (Render가 자동 감지). 필요 시 Python 버전을 `backend/runtime.txt` 또는 환경변수 `PYTHON_VERSION`으로 고정.
4. **Build Command**:
   ```
   pip install -r requirements.txt
   ```
5. **Start Command**:
   ```
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
   - `$PORT`는 Render가 주입한다. 하드코딩 금지.
   - Root Directory가 `backend`이므로 `app.main:app`이 정상 해석된다.
6. **Instance Type**: 위 플랜 선택대로(Starter 권장).
7. Health Check Path를 설정할 수 있으면 `/health`로 둔다([main.py:305-312](../../backend/app/main.py#L305-L312)). `/health`는 DB를 검사하지 않으므로 liveness 용으로 적합.

## Phase 3. 환경변수 설정 (Render Environment)

Render 대시보드 **Environment**에 등록한다. **`.env` 파일 업로드 금지, 로컬 DB credential 재사용 금지.**

### 첫 배포(smoke) 단계 — 스케줄러/리포트 전부 OFF

| 변수 | 값 | 비고 |
|---|---|---|
| `PROJECT_NAME` | 임의 이름 | |
| `API_V1_STR` | 기존 값과 동일 | |
| `ENVIRONMENT` | `production` 또는 `staging` | |
| `DATABASE_URL` | Supabase connection string | secret |
| `SECRET_KEY` | 새로 생성한 강한 랜덤값 | secret, 로컬 기본값 재사용 금지 |
| `ALGORITHM` | `HS256` | |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 기존 값 | |
| `BACKEND_CORS_ORIGINS` | Vercel 프론트 origin (쉼표구분) | 와일드카드 금지 |
| `LOCAL_CORS_ORIGINS` | 필요 시 로컬 origin | |
| `ENABLE_DB_SCHEMA_BOOTSTRAP` | `false` | 스키마는 Alembic로 관리 |
| `SQLALCHEMY_ECHO` | `false` | |
| `DB_POOL_PRE_PING` | `true` | |
| `ENABLE_MARKET_WARMUP` | `false` | 첫 smoke |
| `ENABLE_SCHEDULER` | `false` | 첫 smoke |
| `ENABLE_AI_REPORT_GENERATION` | `false` | 첫 smoke |
| `ENABLE_NOTIFICATION_SCHEDULER` | `false` | |

### 기능 검증 시 추가 (단계적)

- 시장/리포트: `OPENAI_API_KEY`, `ALPHA_VANTAGE_API_KEY`, `FRED_API_KEY`, `ECOS_API_KEY`, `FMP_API_KEY`, `FINNHUB_API_KEY`, 그리고 `REPORT_SCHEDULER_*` 계열.
- 로그인: `GOOGLE_CLIENT_ID`.
- 결제: `PAYMENT_PROVIDER`, `PAYMENT_WEBHOOK_SECRET`, `PAYMENT_PLUS_PLAN_ID`, `PAYMENT_PRO_PLAN_ID` (백엔드 env only).
- 알림: `TELEGRAM_*`, `EMAIL_*`, `GMAIL_*` (백엔드 env only).

> Supabase pooler(transaction mode)를 쓰는 경우에만 `DB_PREPARED_STATEMENT_CACHE_SIZE=0`을 staging에서 검증한다([config.py:158-163](../../backend/app/core/config.py#L158-L163)). Render는 보통 direct connection이 가능하므로 기본은 미설정.

## Phase 4. DB 마이그레이션

production startup은 `ENABLE_DB_SCHEMA_BOOTSTRAP=false`이므로 스키마를 만들지 않고 검증만 한다([main.py:132-152](../../backend/app/main.py#L132-L152)). 따라서 **앱 시작 전에 migration을 먼저 적용**해야 한다.

방법(택1):
1. **로컬에서 Supabase 대상 실행(가장 단순, Free 플랜에서도 가능)**:
   ```powershell
   cd backend
   $env:DATABASE_URL = "<staging Supabase URL>"   # 세션 한정, 커밋 금지
   python -m alembic upgrade head
   ```
2. **Render Pre-Deploy Command(유료 플랜)**: `python -m alembic upgrade head`를 pre-deploy로 등록.
3. **Render Shell(유료)**: 배포된 인스턴스 셸에서 1회 실행.

baseline migration: `backend/alembic/versions/20260601_0001_add_subscription_billing_tables.py`. 적용 후 `users`, `assets`, `ai_reports`, `subscriptions` 등 필수 테이블이 생겼는지 확인([main.py:45-60](../../backend/app/main.py#L45-L60)).

## Phase 5. 배포 & 백엔드 smoke

1. Render가 자동 빌드·배포. 첫 빌드는 의존성(`langchain`, `pandas` 등)이 무거워 시간이 걸린다.
2. 배포 URL 확인 후:
   - `GET /health` → `status: ok`
   - `GET /db-check` → `db_connected` (DB 미연결 시 503 + sanitized 진단; connection string은 노출되지 않음 [main.py:315-345](../../backend/app/main.py#L315-L345))
   - `GET /api/market/prices` → 스케줄러 OFF면 빈 값일 수 있음(정상).
3. 로그에 secret/connection string이 찍히지 않는지 확인.

## Phase 6. Vercel 프론트 연결

1. Vercel 프로젝트: Root `frontend`, Framework `Vite`, Build `npm run build`, Output `dist`.
2. 환경변수 `VITE_API_BASE_URL` = Render 백엔드 origin. 변경 후 **재배포**(Vite는 빌드시 주입). API origin 로직은 [apiClient.js](../../frontend/src/utils/apiClient.js).
3. `/login`, `/pricing`, `/billing/success`, `/detail/:ticker` 직접 새로고침 시 404 아닌지 확인(`frontend/vercel.json` rewrite).
4. 백엔드 CORS가 Vercel origin만 허용하는지 확인([main.py:287-294](../../backend/app/main.py#L287-L294)).

## Phase 7. 스케줄러/리포트 점진 활성화

smoke 통과 후 순서대로:

1. `ENABLE_MARKET_WARMUP=true` → 시작 시 캐시 채움 확인.
2. `ENABLE_SCHEDULER=true` → 가격(5분)/뉴스(1시간) job 동작 확인.
   - Free 플랜이면 이 시점부터 **UptimeRobot로 5분마다 `/health` 핑**을 걸어 sleep을 막아야 스케줄러가 유지됨.
3. `ENABLE_AI_REPORT_GENERATION=true` → **비용/메모리/rate-limit 확인 후 마지막에.**
   - Starter(512MB)는 리포트 생성 중 OOM 위험 → 메모리 모니터링. 불안하면 Standard로 올리거나 리포트 OFF 유지.
   - `REPORT_SCHEDULER_INTERVAL_HOURS`, `REPORT_SCHEDULER_MAX_REPORTS_PER_RUN`, `REPORT_SCHEDULER_TARGET_TICKERS`를 보수적으로.
4. 사용자/챗봇 요청은 저장된 리포트만 읽고 생성 트리거 안 함([main.py:475-487](../../backend/app/main.py#L475-L487), AGENTS.md 섹션 14).

## Phase 8. 외부 연동

1. Google OAuth: Google Cloud Console에 Vercel 프론트 origin 등록, 백엔드 `GOOGLE_CLIENT_ID` 일치.
2. 결제: test mode부터. success/cancel은 Vercel route, webhook은 Render 백엔드 `/api/billing/webhook`, secret은 백엔드 env only.
3. provider key는 전부 백엔드 env only.

## 자주 겪는 Render 이슈 (트러블슈팅)

- **빌드 실패(의존성 무거움/시간 초과)**: 빌드 로그 확인. Python 버전 고정(`PYTHON_VERSION`)으로 휠 호환 문제 회피.
- **`app.main:app` import 에러**: Root Directory가 `backend`인지 확인. 아니라면 Start Command를 `uvicorn backend.app.main:app ...`로 조정하거나 working dir을 맞춘다.
- **포트 바인딩 실패/서비스 unhealthy**: Start Command에 `--port $PORT`가 있는지 확인. `--port 8000` 하드코딩 시 Render가 헬스체크 실패.
- **`/db-check` 503**: `DATABASE_URL` 정확성, Supabase 연결 수 한도, IPv4/IPv6(direct vs pooler) 확인.
- **startup에서 schema 검증 실패(RuntimeError)**: migration 미적용. Phase 4 먼저 수행([main.py:126-152](../../backend/app/main.py#L126-L152)).
- **Free 플랜 첫 요청 지연**: sleep 후 cold start. UptimeRobot 핑 또는 Starter 업그레이드로 해소.
- **리포트 중 프로세스 재시작**: 메모리 부족(OOM). 리포트 OFF 또는 Standard 업그레이드.

## 위험과 Risky Change 여부 (AGENTS.md 섹션 9)

이 가이드 문서는 코드를 변경하지 않는다. 실제 배포 단계에서 사용자 확인이 필요한 항목:

- **스케줄러/AI 리포트 비용**: 켜면 OpenAI·외부 API 비용 발생. 첫 배포 OFF, 점진 ON.
- **DB 마이그레이션**: production Supabase에 `alembic upgrade head`. forward-fix 우선, destructive rollback 금지.
- **인증/결제 콜백 URL**: 도메인 확정 후 Google OAuth·webhook URL 맞춤.
- **시크릿**: `.env` 업로드/로컬 credential 재사용 금지. 노출 시 즉시 rotate.
- **유료 플랜 전환(Starter/Standard)**: 비용 발생 결정은 사용자 몫.

## 검증 계획 (AGENTS.md 섹션 6)

### 로컬 / CI
- `git status --short`
- `frontend/`: `npm run lint`, `npm run build`
- `backend/`: 코드 변경이 있을 때만 관련 `pytest`. 이번 가이드는 코드 변경 없음 → 생략, 사유 기록.
- `backend/`: disposable staging Supabase 대상 `python -m alembic upgrade head`

### 배포 후
- `/health` ok, `/db-check` db_connected
- CORS가 Vercel origin만 허용
- 프론트가 `VITE_API_BASE_URL`로 호출 성공, SPA route 새로고침 동작
- 스케줄러 OFF 첫 smoke → 단계적 ON
- 로그에 secret/connection string 없음

## 갱신할 문서

실제 배포를 수행하면(구현 단계) 동기화한다(AGENTS.md 섹션 12·13).

- `docs/harness/features/deployment-runtime.md`: 백엔드가 Render Web Service에 배포된다는 Current Behavior/Ownership Map/Open Risks 갱신, 이 가이드를 Change Records에 추가.
- `docs/harness/feature-index.md`: "Deployment and hosted runtime" 행과 Deployment/runtime plans 목록에 이 문서 링크 추가.
- 배포·검증 결과는 별도 구현 기록(`render-backend-deployment-implementation-2026-XX-XX.md`)으로 남겨 연결.
- `render.yaml`(Blueprint) 또는 Python 버전 파일을 저장소에 추가하면 `backend/DEVELOPMENT_DIRECTION.md`에 배포 가이드 보강(신규 파일은 사용자 승인 후).

## References Checked

- 코드: `backend/app/main.py`, `backend/app/db/session.py`, `backend/app/core/config.py`, `backend/requirements.txt`, `backend/alembic/`, `frontend/vercel.json`, `frontend/src/utils/apiClient.js`
- 문서: `docs/harness/backend-free-tier-deployment-plan-2026-06-03.md`, `docs/harness/backend-persistent-host-deployment-plan-2026-06-03.md`, `docs/harness/vercel-supabase-deployment-plan-2026-06-01.md`, `docs/harness/features/deployment-runtime.md`, `docs/harness/feature-index.md`
- 외부(배포 직전 현재 약관 재확인 필요): Render Web Service 빌드/시작 명령, Render 인스턴스 사양·가격, Render Pre-Deploy Command, UptimeRobot 무료 모니터링, Supabase 무료 티어 제한
