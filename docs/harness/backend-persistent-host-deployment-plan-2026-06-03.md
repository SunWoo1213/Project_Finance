# 백엔드 Persistent 호스트 배포 계획 (프론트 Vercel + Supabase)

Date: 2026-06-03

## Objective

`Project_Finance`의 FastAPI 백엔드를 **항상 켜진(persistent) 호스트**에 배포하고, 프론트엔드는 Vercel, 데이터베이스는 Supabase PostgreSQL을 사용하는 1차 프로덕션 형태를 정리한다. 이 문서는 계획서이며, 이번 단계에서는 코드·설정·인프라를 변경하지 않는다.

사용자 결정(2026-06-03): **옵션 A — 백엔드는 Render / Railway / Fly.io 같은 persistent 호스트에 배포, 프론트만 Vercel.** 이유는 현재 백엔드가 persistent 런타임을 전제로 만들어져 있어 코드 수정이 최소이기 때문이다.

이 문서는 기존 배포 문서를 대체하지 않고, 그 위에서 "백엔드 호스트 선택과 배포 절차"에 초점을 둔다. 환경변수 전체 인벤토리와 Supabase 연동 세부는 다음 문서를 함께 참고한다.

- `docs/harness/vercel-supabase-deployment-plan-2026-06-01.md`
- `docs/harness/vercel-supabase-integration-next-plan-2026-06-03.md`
- `docs/harness/features/deployment-runtime.md`

## 현재 동작 (코드 기준)

현재 백엔드는 persistent 런타임 가정을 그대로 갖고 있다. 코드 근거:

- in-process 스케줄러: `backend/app/main.py:167-273`에서 `AsyncIOScheduler`로 가격(5분)·뉴스(1시간)·AI 리포트(주기) job을 등록한다.
- 시작 시 market warm-up: `backend/app/main.py:159-163`의 lifespan에서 `update_prices_task()`/`update_news_task()`를 실행한다.
- 전역 메모리 캐시: `backend/app/main.py:348-355`의 `/api/market/prices`, `/api/market/news`가 in-process `market_cache` dict를 읽는다(`backend/app/core/cache.py`).
- 장시간 AI 리포트 파이프라인: `backend/app/services/ai_service.py`, `backend/app/services/graph/`가 LangGraph/LLM 호출을 수행한다.
- DB 엔진: `backend/app/db/session.py`가 `settings.DATABASE_URL`로 async 엔진을 만들고 pool을 유지한다.
- startup 스키마 처리: `backend/app/main.py:132-152`의 `prepare_database_on_startup()`이 `ENABLE_DB_SCHEMA_BOOTSTRAP`에 따라 `create_all` 또는 migration-ready 검증을 수행한다.
- 설정 로드: `backend/app/core/config.py`가 루트 `.env` 또는 host env를 읽고, PostgreSQL URL을 `postgresql+asyncpg://`로 정규화하며, `DATABASE_URL` 부재 시 `POSTGRES_URL_NON_POOLING` → `POSTGRES_URL` 순으로 fallback한다.

배포 대상은 아직 결정되지 않은 상태이며, 로컬은 `docker-compose.yml`의 PostgreSQL과 `uvicorn app.main:app --reload`로 동작한다.

## 목표 동작

```text
User Browser
  -> Vercel CDN (frontend/, Vite React 정적 호스팅)
  -> VITE_API_BASE_URL
  -> FastAPI backend on persistent host (Render/Railway/Fly.io)
  -> Supabase PostgreSQL
       ^
Payment Webhook -> persistent backend /api/billing/webhook
Backend Scheduler (host process 안에서 상시 구동)
  -> 가격/뉴스 갱신, 예약 AI 리포트 생성 -> Supabase 저장 리포트
```

- 백엔드는 persistent 프로세스로 떠 있어 스케줄러·캐시·리포트 파이프라인이 **코드 수정 없이** 동작한다.
- 프론트엔드는 Vercel에서 정적으로 서빙되고 `VITE_API_BASE_URL`로 배포된 백엔드 origin을 호출한다.
- DB는 Supabase PostgreSQL이며, 스키마는 Alembic migration으로 관리한다(`ENABLE_DB_SCHEMA_BOOTSTRAP=false`).
- 사용자/챗봇 요청은 저장된 예약 리포트만 읽고, 실시간 리포트 생성을 트리거하지 않는다(AGENTS.md 섹션 14).

## 호스트 선택 가이드 (의사결정)

옵션 A 안에서 어떤 persistent 호스트를 쓸지 확정해야 한다. 셋 다 long-running 프로세스를 지원하므로 코드 수정은 거의 없다.

| 호스트 | 장점 | 주의점 |
|---|---|---|
| Render | Web Service + Cron/Background 분리가 쉬움, 배포 단순, 무료/저가 티어 | 무료 티어는 idle 시 sleep → 스케줄러가 멈출 수 있어 유료 티어 필요 |
| Railway | 설정 간단, 사용량 기반 과금 | 비용이 사용량에 따라 변동 |
| Fly.io | 리전 선택 자유, IPv6 기본 | 설정이 상대적으로 저수준(`fly.toml`, 머신 관리) |

권장 기본값: **Render Web Service 유료(상시 가동) 티어**. idle sleep이 없는 플랜이어야 in-process 스케줄러가 끊기지 않는다. (무료 티어는 sleep 때문에 스케줄러 용도로 부적합.)

> 비고: Supabase 연결 모드는 persistent backend 기준 **direct connection** 우선. 호스트가 IPv4-only이면 Supabase shared pooler(session mode)를 검토한다. 이때만 `DB_PREPARED_STATEMENT_CACHE_SIZE=0` 후보를 staging에서 검증한다.

## 변경 대상 파일

이번 배포 형태(옵션 A)는 **코드 변경이 거의 없고 대부분 호스트 설정·문서 작업**이다.

### 설정 / 인프라 (호스트 대시보드, 저장소 외부)
- 백엔드 호스트(Render 등) 환경변수: `PROJECT_NAME`, `API_V1_STR`, `ENVIRONMENT`, `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `BACKEND_CORS_ORIGINS`, `LOCAL_CORS_ORIGINS`, `ENABLE_DB_SCHEMA_BOOTSTRAP=false`, `SQLALCHEMY_ECHO=false`, `DB_POOL_PRE_PING=true`, 그리고 첫 smoke에서는 `ENABLE_MARKET_WARMUP=false`, `ENABLE_SCHEDULER=false`, `ENABLE_AI_REPORT_GENERATION=false`, `ENABLE_NOTIFICATION_SCHEDULER=false`. provider/결제/OpenAI/Gmail·Telegram secret은 해당 기능 검증 시에만 추가.
- Build: `pip install -r requirements.txt` (working dir `backend/`)
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Release(가능하면): `python -m alembic upgrade head`

### 저장소 설정 파일 (선택, 호스트별)
- 호스트가 IaC 파일을 요구하면 추가: Render `render.yaml`, Fly.io `fly.toml` (또는 `Procfile`). **신규 파일이므로 사용자 승인 후 추가.**
- 루트 `vercel.json`의 `experimentalServices.backend` 블록: 옵션 A에서는 **불필요**하다. 이 블록은 백엔드를 Vercel에 올리려는 실험적 설정이므로, 옵션 A로 확정되면 혼동을 막기 위해 제거를 검토한다. (파일 삭제·수정은 사용자 확인 후 — AGENTS.md 섹션 9.) 프론트 SPA rewrite는 `frontend/vercel.json`에 이미 있으므로 프론트 배포에는 영향 없음.

### Frontend (Vercel)
- 코드 변경 없음. Vercel 프로젝트 설정만: Root Directory `frontend`, Framework `Vite`, Build `npm run build`, Output `dist`.
- 환경변수 `VITE_API_BASE_URL` = 배포된 백엔드 origin. `VITE_GOOGLE_CLIENT_ID`는 Google 로그인 사용 시.
- API origin 기본값 로직은 `frontend/src/utils/apiClient.js` 참고(없으면 `http://localhost:8000` fallback). 코드 수정 불필요.

### Backend (코드)
- **이번 단계 코드 변경 없음**을 목표로 한다. 기존 환경변수 스위치(`ENABLE_*`, CORS, DB bootstrap)로 프로덕션 동작을 제어 가능하기 때문.
- 후속(별도 단계, 선택): startup의 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`(`backend/app/main.py:81-104`) 경로는 `ENABLE_DB_SCHEMA_BOOTSTRAP=false`에서는 타지 않으므로 그대로 둔다. 스키마 변화가 필요하면 Alembic revision으로 처리.

### DB (Supabase)
- 스키마 변경은 없음(배포 작업). staging/production Supabase DB에 `python -m alembic upgrade head`만 적용.
- baseline migration: `backend/alembic/versions/20260601_0001_add_subscription_billing_tables.py`.

## 단계별 구현 계획

### Phase 0. 결정 사항 확정
1. 백엔드 호스트 확정(권장: Render 상시 가동 유료 티어).
2. Supabase project: 신규 생성 vs 기존 연결, staging/production 분리 방식.
3. Supabase connection mode: direct vs shared pooler(IPv4-only일 때).
4. 프로덕션/스테이징 도메인(프론트, 백엔드) 확정.
5. 스케줄러·AI 리포트 비용 정책: 첫 배포는 스케줄러 OFF로 시작.

### Phase 1. Supabase 준비
1. Supabase project 생성, 리전 선택.
2. `Connect` 화면에서 connection string 확보(secret은 호스트 secret에만 저장, 문서/로그 금지).
3. staging Supabase DB에 Alembic migration 적용 후 테이블 생성 확인.
4. `Asset` seed 필요 여부 확인. 로컬 dev 데이터는 기본적으로 마이그레이션하지 않음.

### Phase 2. 백엔드 호스트 배포 (staging)
1. 호스트에서 저장소 연결, working dir `backend/`.
2. Build/Start 명령 설정(위 "변경 대상 파일" 참고).
3. 환경변수 등록(첫 smoke는 스케줄러/warm-up/리포트/알림 전부 OFF).
4. Release 단계 또는 신뢰된 CI/로컬에서 `python -m alembic upgrade head` 실행(프로덕션 secret 안전 주입).
5. 배포 후 smoke: `/health`, `/db-check`, `/api/market/prices`(스케줄러 OFF면 빈 값일 수 있음 — 정상), 인증 보호 엔드포인트(테스트 유저).

### Phase 3. Vercel 프론트 배포
1. Vercel 프로젝트 import, Root `frontend`, Framework `Vite`.
2. `VITE_API_BASE_URL`을 staging 백엔드 origin으로 설정 후 재배포(Vite는 빌드시 주입).
3. `/login`, `/pricing`, `/billing/success`, `/detail/:ticker` 직접 새로고침 시 404 아닌지 확인(`frontend/vercel.json` rewrite).
4. 백엔드 CORS가 Vercel origin만 허용하는지 확인(`BACKEND_CORS_ORIGINS`).

### Phase 4. 외부 연동
1. Google OAuth: Google Cloud Console에 프론트 origin 등록, 백엔드 `GOOGLE_CLIENT_ID` 일치.
2. 결제: test mode부터. success/cancel은 Vercel 프론트 route, webhook은 백엔드 `/api/billing/webhook`, webhook secret은 백엔드 env only.
3. OpenAI/마켓 provider key는 백엔드 env only. smoke 통과 후 `ENABLE_MARKET_WARMUP` → 마지막에 리포트 스케줄러 순으로 점진 활성화.
4. 알림: Gmail/Telegram secret은 백엔드 env only, 실제 발송 전까지 `ENABLE_NOTIFICATION_SCHEDULER=false` 유지.

### Phase 5. Production promotion
1. staging smoke 결과 기록.
2. production Supabase에 migration 적용.
3. production 백엔드를 스케줄러 OFF로 배포.
4. production Vercel `VITE_API_BASE_URL`을 production 백엔드로 설정·재배포.
5. `/health`, `/db-check`, market, login, pricing, asset detail smoke.
6. 비용/rate-limit 검토 후 스케줄러 단계적 ON.
7. secret/connection string 로그 노출 없음 확인.

## 위험과 Risky Change 여부

이 작업은 AGENTS.md 섹션 9의 Risky Change 항목과 맞닿아 있어 **사용자 확인이 필요**하다.

- **배포 아키텍처 변경**: 기존 문서들은 동일하게 persistent 백엔드를 권장했으므로 방향은 일관됨. 다만 루트 `vercel.json`의 backend 블록 제거는 파일 수정이므로 별도 승인 필요.
- **스케줄러 / AI 리포트 비용**: 스케줄러와 리포트 생성을 켜면 OpenAI·외부 API 비용과 rate limit이 발생. 첫 배포는 OFF로 시작하고, 비용 정책 확정 후 점진 활성화.
- **DB 마이그레이션**: production Supabase에 `alembic upgrade head` 적용은 스키마 변경. forward-only fix 우선, destructive rollback은 금지(명시 승인 + 백업 필요).
- **인증/결제 콜백 URL**: 도메인 변경 시 Google OAuth·결제 webhook URL을 프로덕션에 맞춰야 로그인/결제가 동작.
- **시크릿 취급**: `.env` 업로드 금지, 로컬 DB credential 재사용 금지, secret은 호스트 대시보드/secret manager에만. 노출 시 즉시 rotate.

이번 계획 문서 자체는 코드/설정/인프라를 변경하지 않으므로 즉시 위험은 없다. 구현 단계로 넘어갈 때 위 항목별 승인을 받는다.

## 검증 계획 (AGENTS.md 섹션 6)

배포 형태이므로 코드 검증은 최소, 호스트 smoke 중심.

### 로컬 / CI
- `git status --short`
- `frontend/`: `npm run lint`, `npm run build`
- `backend/`: 변경이 있을 때만 관련 `pytest` (auth/billing/chat/reports/DB). 이번엔 코드 변경이 없으면 생략 가능, 그 사유를 기록.
- `backend/`: disposable staging Supabase DB 대상 `python -m alembic upgrade head`

### Staging
- `/health` ok, `/db-check` db_connected
- CORS가 Vercel origin만 허용/그 외 거부
- 프론트가 `VITE_API_BASE_URL`로 백엔드 호출 성공
- SPA route 직접 새로고침 동작
- Google 로그인 smoke(사용 시), 결제 sandbox smoke(사용 시)
- 스케줄러 OFF 상태 첫 smoke

### Production
- migration 적용 성공
- 스케줄러 OFF 배포 → `/health`, `/db-check`, market, login, pricing, asset detail smoke
- market warm-up → 리포트 스케줄러 순으로 점진 활성화
- 로그에 secret/connection string 없음 확인

## 갱신할 문서

구현 단계에서 다음을 동기화한다(AGENTS.md 섹션 12·13).

- `docs/harness/features/deployment-runtime.md`: 백엔드가 persistent 호스트(Render 등)에 배포된다는 Current Behavior/Ownership Map/Open Risks 갱신, 이 계획서를 Change Records에 추가.
- `docs/harness/feature-index.md`: "Deployment and hosted runtime" 행 Change Records에 이 문서 링크 추가, Deployment/runtime plans 목록에도 추가.
- 호스트 IaC 파일(`render.yaml` 등)을 추가하면 `backend/DEVELOPMENT_DIRECTION.md`에 배포 가이드 보강.
- 실제 배포·검증을 수행하면 별도 구현 기록(`backend-persistent-host-deployment-implementation-2026-XX-XX.md`)을 만들어 연결.

## References Checked

- 코드: `backend/app/main.py`, `backend/app/db/session.py`, `backend/app/core/config.py`, `backend/requirements.txt`, `frontend/vercel.json`, 루트 `vercel.json`
- 문서: `docs/harness/features/deployment-runtime.md`, `docs/harness/vercel-supabase-deployment-plan-2026-06-01.md`, `docs/harness/vercel-supabase-integration-next-plan-2026-06-03.md`, `DEVELOPMENT_DIRECTION.md`, `docs/harness/feature-index.md`
