# 백엔드 무료 티어 배포 계획 (프론트 Vercel + Supabase)

Date: 2026-06-03

## Objective

`Project_Finance`의 FastAPI 백엔드를 **무료(free tier) 호스팅**으로 배포하는 방법을 정리한다. 프론트엔드는 Vercel(무료), 데이터베이스는 Supabase(무료 티어)를 그대로 쓴다. 이 문서는 계획서이며, 이번 단계에서는 코드·설정·인프라를 변경하지 않는다.

사용자 결정(2026-06-03): 백엔드를 **무료 티어에서 배포 가능한 방법**으로 구성한다. 앞선 옵션 A(persistent 호스트)의 방향은 유지하되, 비용 0원 제약을 추가한다.

함께 참고할 문서:
- `docs/harness/backend-persistent-host-deployment-plan-2026-06-03.md` (옵션 A 전체 절차)
- `docs/harness/vercel-supabase-deployment-plan-2026-06-01.md` (환경변수 인벤토리)
- `docs/harness/features/deployment-runtime.md`

## 무료 티어의 핵심 제약 (반드시 먼저 이해)

현재 백엔드는 **항상 켜진 프로세스**를 전제로 만들어졌다. 코드 근거:

- in-process 스케줄러 `AsyncIOScheduler`: `backend/app/main.py:167-273` (가격 5분, 뉴스 1시간, AI 리포트 주기).
- 시작 시 market warm-up: `backend/app/main.py:159-163`.
- 전역 메모리 캐시 `market_cache`: `backend/app/main.py:348-355`, `backend/app/core/cache.py`.
- 장시간 LLM 리포트 파이프라인: `backend/app/services/ai_service.py`, `backend/app/services/graph/`.

무료 호스팅은 크게 두 부류이고, 각각 위 구조와 충돌하는 지점이 다르다.

| 부류 | 대표 | 무료 동작 | 스케줄러 영향 |
|---|---|---|---|
| Sleep형 무료 웹서비스 | Render Free, Koyeb Free, HF Spaces | 일정 시간 무요청이면 sleep, 요청 오면 cold start | sleep 동안 in-process 스케줄러 **정지** |
| Always-Free VM | Oracle Cloud Always Free | VM이 24시간 상시 가동 | 스케줄러 **그대로 동작** |
| Scale-to-zero 함수 | Google Cloud Run 무료 | 무요청이면 0 인스턴스 | in-process 스케줄러 동작 안 함, 외부 트리거 필요 |

> 참고: Railway는 상시 무료 티어가 없어졌고(체험 크레딧 위주), Fly.io의 무료 허용량은 정책이 자주 바뀌므로 배포 직전 현재 약관을 확인한다. 아래 권장안은 이 두 곳에 의존하지 않는다.

결론: 무료 + 스케줄러 유지를 동시에 만족하려면 **Always-Free VM**이 가장 자연스럽고, 그게 부담되면 **Sleep형 무료 웹 + 외부 무료 cron**으로 스케줄러를 대체한다.

## 권장안 비교 (의사결정 필요)

### 권장 A — Oracle Cloud "Always Free" VM (코드 수정 없음, 스케줄러 유지)

- Oracle Cloud의 Always Free ARM(Ampere) 인스턴스는 상시 가동이며 무료다.
- VM 위에서 `uvicorn app.main:app`을 systemd 서비스로 띄우면 **현재 스케줄러·캐시·리포트 파이프라인이 코드 수정 없이 그대로 동작**한다.
- 장점: 기존 구조 보존, 진짜 0원, sleep 없음.
- 단점: VM을 직접 운영(OS 업데이트, 방화벽/보안 그룹, systemd, 도메인/TLS는 Caddy 또는 Nginx + Let's Encrypt). 계정 생성 시 카드 등록이 필요할 수 있음(과금 아님).
- DB 연결: Oracle VM은 IPv6/IPv4 모두 가능하므로 Supabase **direct connection** 우선.

### 권장 B — Render Free 웹서비스 + 외부 무료 cron (운영 간단, 스케줄러 대체)

- Render Free 웹서비스에 백엔드를 배포한다. 단, 무요청 15분 후 sleep + cold start가 있다.
- in-process 스케줄러는 신뢰할 수 없으므로 **끈다**(`ENABLE_SCHEDULER=false`, `ENABLE_MARKET_WARMUP=false`).
- 대신 **외부 무료 cron**(GitHub Actions scheduled workflow, 또는 cron-job.org)이 백엔드의 작업용 HTTP 엔드포인트를 주기적으로 호출해 가격/뉴스/리포트 갱신을 트리거한다.
- 장점: VM 운영 불필요, 배포 단순.
- 단점: **코드 변경이 필요**하다(작업 트리거용 엔드포인트 신설 + 토큰 보호). cold start로 첫 요청이 느리고, AI 리포트 생성은 무료 티어 타임아웃을 넘길 수 있어 트리거 1회당 작업량을 작게 쪼개야 한다.

### 권장하지 않음 — Cloud Run scale-to-zero 단독

- 무요청 시 인스턴스가 0이라 in-process 스케줄러가 아예 동작하지 않음. Cloud Scheduler로 외부 트리거를 붙여야 하므로 복잡도가 권장 B와 비슷하면서 GCP 설정이 더 많다. 1차로는 보류.

**기본 권장: 권장 A(Oracle Always Free VM).** 기존 코드를 건드리지 않고 스케줄러를 살릴 수 있기 때문이다. VM 운영이 부담되면 권장 B로 간다.

## 변경 대상 파일

### 공통 (frontend / DB)
- Frontend(Vercel): 코드 변경 없음. Root `frontend`, Framework `Vite`, Build `npm run build`, Output `dist`. 환경변수 `VITE_API_BASE_URL` = 배포된 백엔드 origin, 필요 시 `VITE_GOOGLE_CLIENT_ID`. SPA rewrite는 `frontend/vercel.json`에 이미 있음.
- DB(Supabase 무료): 스키마는 Alembic migration으로만. `python -m alembic upgrade head`. baseline `backend/alembic/versions/20260601_0001_add_subscription_billing_tables.py`.
- 루트 `vercel.json`의 `experimentalServices.backend` 블록은 무료 외부 호스트 사용 시 불필요 → 제거 검토(파일 수정이므로 사용자 승인 후).

### 권장 A 선택 시 (Oracle VM)
- 백엔드 코드 변경: **없음**.
- 신규 운영 파일(선택, 승인 후): systemd unit 파일, 리버스 프록시 설정(Caddyfile 등). 저장소에 둘지 VM에만 둘지 결정.
- 환경변수: VM의 서비스 env 또는 `/etc/`의 env 파일(권한 600). `.env` 커밋 금지.

### 권장 B 선택 시 (Render Free + 외부 cron)
- 백엔드 코드 변경: **작업 트리거 엔드포인트 신설**이 필요하다.
  - 신규 라우터(예: `backend/app/api/tasks.py`)에 가격/뉴스/리포트 갱신을 호출하는 POST 엔드포인트 추가, 공유 secret(예: `TASK_TRIGGER_TOKEN`) 헤더 검증.
  - `backend/app/main.py`에 라우터 등록, `backend/app/core/config.py`에 `TASK_TRIGGER_TOKEN` 설정 추가.
  - 기존 `update_prices_task`/`update_news_task`/`generate_daily_reports`를 재사용(중복 로직 금지).
- 신규 파일(선택): GitHub Actions cron workflow(`.github/workflows/*.yml`)로 무료 트리거.
- 주의: 이 변경은 별도 implement 단계에서 진행하고, AI 리포트는 사용자/챗봇이 아니라 cron만 트리거하도록 유지한다(AGENTS.md 섹션 14).

## 단계별 구현 계획

### Phase 0. 호스팅 방식 확정
1. 권장 A(Oracle VM) vs 권장 B(Render Free + cron) 선택.
2. Supabase 무료 project 준비 방식, staging/production 분리 여부.
3. 프론트/백엔드 도메인(무료 도메인 또는 서비스 제공 URL) 확정.
4. 첫 배포는 스케줄러/리포트 비용 0 정책(OpenAI 키 미설정 또는 리포트 OFF)으로 시작.

### Phase 1. Supabase 준비
1. Supabase 무료 project 생성, 리전 선택.
2. connection string 확보(secret은 호스트 secret에만, 문서/로그 금지).
3. staging DB에 `python -m alembic upgrade head` 적용 후 테이블 확인.

### Phase 2-A. Oracle VM 배포 (권장 A)
1. Always Free ARM 인스턴스 생성, 보안 그룹에서 HTTP/HTTPS 포트 개방.
2. Python, 의존성 설치: `pip install -r backend/requirements.txt`.
3. systemd 서비스로 `uvicorn app.main:app --host 0.0.0.0 --port 8000` 등록(working dir `backend/`).
4. 환경변수 설정: `DATABASE_URL`, `SECRET_KEY`, `BACKEND_CORS_ORIGINS`(Vercel origin), `ENABLE_DB_SCHEMA_BOOTSTRAP=false`, 첫 smoke는 `ENABLE_SCHEDULER=false`/`ENABLE_MARKET_WARMUP=false`/`ENABLE_AI_REPORT_GENERATION=false`.
5. 리버스 프록시(Caddy/Nginx) + Let's Encrypt로 HTTPS 적용.
6. smoke: `/health`, `/db-check`, `/api/market/prices`.
7. 안정화 후 `ENABLE_MARKET_WARMUP` → 스케줄러 → 리포트 순으로 점진 ON. **VM은 sleep이 없으므로 in-process 스케줄러 그대로 사용.**

### Phase 2-B. Render Free + 외부 cron 배포 (권장 B)
1. Render Free 웹서비스 생성, working dir `backend/`, Start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
2. 환경변수: 위와 동일하되 `ENABLE_SCHEDULER=false`, `ENABLE_MARKET_WARMUP=false` 유지(스케줄러는 외부 cron으로 대체), `TASK_TRIGGER_TOKEN` 설정.
3. (구현 단계) 작업 트리거 엔드포인트 추가 후 배포.
4. 외부 무료 cron(GitHub Actions/cron-job.org)이 토큰 헤더로 트리거 엔드포인트 호출:
   - 가격 갱신: 5~15분 간격(무료 cron 최소 간격 확인).
   - 뉴스 갱신: 1시간.
   - AI 리포트: 비용 정책 확정 후, 1회 작업량을 작게.
5. cold start와 타임아웃을 고려해 리포트 트리거는 자산 수를 제한.

### Phase 3. Vercel 프론트 배포
1. Vercel import, Root `frontend`, Framework `Vite`.
2. `VITE_API_BASE_URL` = 배포된 백엔드 origin 설정 후 재배포.
3. `/login`, `/pricing`, `/billing/success`, `/detail/:ticker` 직접 새로고침 404 아닌지 확인.
4. 백엔드 CORS가 Vercel origin만 허용하는지 확인.

### Phase 4. 외부 연동
1. Google OAuth origin에 Vercel 프론트 origin 등록, 백엔드 `GOOGLE_CLIENT_ID` 일치.
2. 결제: test mode부터. success/cancel은 Vercel route, webhook은 백엔드 route, secret은 백엔드 env only.
3. OpenAI/마켓 provider key는 백엔드 env only. 무료 운영 중 비용 발생 가능성이 있으므로 리포트 생성은 마지막에, 보수적으로 ON.

### Phase 5. Production promotion
1. staging smoke 결과 기록.
2. production Supabase migration 적용.
3. production 백엔드 배포(스케줄러/트리거 보수적 설정).
4. production Vercel `VITE_API_BASE_URL` 설정·재배포.
5. `/health`, `/db-check`, market, login, pricing, asset detail smoke.
6. secret/connection string 로그 노출 없음 확인.

## 무료 티어 한계와 주의 (정직한 트레이드오프)

- **Sleep/cold start**: 권장 B는 첫 요청이 느리고, sleep 중 외부 cron 트리거가 cold start를 유발한다. 사용자 체감 지연이 있을 수 있음.
- **함수/요청 타임아웃**: AI 리포트 생성은 길어서 무료 티어 타임아웃을 넘길 수 있다. 권장 B에서는 트리거 1회당 자산 1~2개로 쪼개는 설계가 필요.
- **메모리 캐시 휘발**: 권장 B에서 cold start마다 `market_cache`가 비므로 `/api/market/prices`가 빈 값일 수 있음. 트리거가 먼저 채워야 함(또는 후속으로 DB 캐시화 검토).
- **리소스 제한**: 무료 Supabase는 용량/연결 수 제한이 있고, 미사용 시 일시중지될 수 있다. 무료 VM도 사양이 낮아 LLM 동시 처리에 한계.
- **비용 0의 의미**: 호스팅은 무료여도 OpenAI·일부 외부 데이터 API는 유료일 수 있다. 리포트/스케줄러를 켜기 전 비용 정책을 확인한다.

## 위험과 Risky Change 여부 (AGENTS.md 섹션 9)

이 계획 문서 자체는 코드/설정/인프라를 변경하지 않는다. 구현 단계에서 아래 항목은 사용자 확인이 필요하다.

- **백엔드 코드 변경(권장 B)**: 작업 트리거 엔드포인트 신설은 새 라우트/설정/스케줄링 동작 변경 → 승인 필요. 사용자/챗봇은 여전히 저장된 리포트만 읽어야 함(섹션 14).
- **스케줄러/AI 리포트 비용**: 트리거 간격·자산 수에 따라 OpenAI·외부 API 비용 발생. 첫 배포는 OFF.
- **DB 마이그레이션**: production Supabase에 `alembic upgrade head` 적용. forward-fix 우선, destructive rollback 금지.
- **루트 `vercel.json` 수정**: backend 블록 제거는 파일 수정 → 승인 후.
- **시크릿**: `.env` 업로드 금지, VM env 파일은 권한 제한, secret 노출 시 즉시 rotate.

## 검증 계획 (AGENTS.md 섹션 6)

### 로컬 / CI
- `git status --short`
- `frontend/`: `npm run lint`, `npm run build`
- `backend/`: 권장 B에서 엔드포인트를 추가하면 관련 `pytest`(트리거 엔드포인트 인증/동작) 작성·실행. 권장 A에서 코드 변경이 없으면 생략하고 사유 기록.
- `backend/`: disposable staging Supabase 대상 `python -m alembic upgrade head`

### Staging
- `/health` ok, `/db-check` db_connected
- CORS가 Vercel origin만 허용
- 프론트가 `VITE_API_BASE_URL`로 호출 성공, SPA route 새로고침 동작
- 권장 B: 외부 cron 트리거가 토큰으로만 동작하고, 가격/뉴스 캐시가 채워지는지 확인
- 권장 A: VM 재시작 후 systemd가 백엔드를 자동 기동하고 스케줄러가 도는지 확인
- 스케줄러/리포트는 비용 검토 후 점진 ON

### Production
- migration 적용 성공, smoke 통과, 로그에 secret 없음

## 갱신할 문서

구현 단계에서 동기화(AGENTS.md 섹션 12·13).

- `docs/harness/features/deployment-runtime.md`: 무료 티어 배포 형태(Oracle VM 또는 Render Free + 외부 cron)와 스케줄러 운영 방식, Open Risks 갱신. 이 계획서를 Change Records에 추가.
- `docs/harness/feature-index.md`: "Deployment and hosted runtime" 행과 Deployment/runtime plans 목록에 이 문서 링크 추가.
- 권장 B 채택 시 트리거 엔드포인트는 chatbot/AI 리포트 feature 문서(`docs/harness/features/asset-detail-ai-community.md`, `chatbot-assistant.md`)의 "사용자 요청은 리포트 생성을 트리거하지 않는다" 규칙과 충돌하지 않음을 명시.
- 운영 파일(systemd/Caddy/GitHub Actions) 추가 시 `backend/DEVELOPMENT_DIRECTION.md`에 배포 가이드 보강.

## References Checked

- 코드: `backend/app/main.py`, `backend/app/db/session.py`, `backend/app/core/config.py`, `backend/requirements.txt`, `frontend/vercel.json`, 루트 `vercel.json`
- 문서: `docs/harness/backend-persistent-host-deployment-plan-2026-06-03.md`, `docs/harness/vercel-supabase-deployment-plan-2026-06-01.md`, `docs/harness/features/deployment-runtime.md`, `docs/harness/feature-index.md`
- 외부(배포 직전 현재 약관 재확인 필요): Oracle Cloud Always Free, Render Free web service sleep 동작, GitHub Actions scheduled workflows, cron-job.org, Supabase 무료 티어 제한
