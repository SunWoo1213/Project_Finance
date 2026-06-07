# 배포 환경 AI 리포트 미생성 원인 분석 및 해결 계획

Date: 2026-06-07
Status: Plan only - 코드/배포 설정 미변경
Feature:
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/deployment-runtime.md`

## Objective

현재 배포 환경에서 AI 리포트가 전혀 작성되지 않는 문제를 해결하기 위한 원인 분석과 단계별 조치 계획을 정리한다. 이번 문서는 저장소 코드와 기존 harness 문서를 기준으로 한 계획서이며, 실제 Render/Vercel/Supabase 대시보드 값이나 배포 로그는 직접 확인하지 않았다.

목표 동작은 그대로 유지한다.

- 사용자 화면, 챗봇, 결제 상태 변경은 새 리포트 생성을 트리거하지 않는다.
- AI 리포트는 backend scheduler 또는 별도 운영용 cron/task 경로에서만 생성된다.
- 저장된 `AIReport` 행만 `GET /api/reports/{ticker}`로 조회된다.

## Current Code Facts

1. 수동 생성 API는 의도적으로 닫혀 있다.
   - `backend/app/main.py`의 `POST /api/ai/generate/{ticker}`는 항상 HTTP 403을 반환한다.
   - 따라서 배포 화면에서 리포트가 404여도 페이지 조회만으로 새 리포트가 생기지 않는 것은 정상 정책이다.

2. scheduled report job은 두 스위치가 모두 켜져야 등록된다.
   - `ENABLE_SCHEDULER=true`: APScheduler 자체를 시작한다.
   - `ENABLE_AI_REPORT_GENERATION=true`: `generate_daily_reports` interval job과 startup job을 등록한다.
   - 둘 중 하나라도 false이면 가격/뉴스만 돌거나 scheduler 전체가 생략되어 AI 리포트는 작성되지 않는다.

3. `generate_report_for_ticker()`도 `ENABLE_AI_REPORT_GENERATION=false`이면 DB 세션, provider, LLM workflow에 들어가기 전 `RuntimeError`로 차단된다.

4. 기본 scheduled target은 `DGS10,XAU,BTC-USD,NVDA,005930.KS`다. `REPORT_SCHEDULER_TARGET_TICKERS`를 비워 두거나 지원되지 않는 ticker만 넣으면 생성 범위가 사실상 없어지거나 반복 실패한다.

5. 리포트가 DB에 저장되는 조건은 엄격하다.
   - 시장 데이터 cache 또는 ticker-level cache fill이 필요하다.
   - readiness가 `blocked`이면 LLM을 호출하지 않고 저장하지 않는다.
   - format/numeric/qualitative/evaluator quality gate가 실패하면 저장하지 않는다.
   - 즉 scheduler가 실행되어도 ticker별 실패가 모두 발생하면 `GET /api/reports/{ticker}`는 계속 404다.

6. 현재 배포 문서들은 첫 smoke 단계에서 `ENABLE_SCHEDULER=false`, `ENABLE_AI_REPORT_GENERATION=false`를 권장한다. 이 값을 운영 단계에서 다시 켜지 않았다면 "전혀 작성되지 않음"은 코드 결함이 아니라 운영 스위치 상태와 일치한다.

7. Render Free 같은 sleep형 배포는 in-process scheduler와 맞지 않는다. sleep 중에는 APScheduler가 멈추므로 `/health`를 사용자가 간헐적으로 호출하는 정도로는 리포트 생성을 보장할 수 없다.

## Most Likely Root Causes

우선순위는 "배포에서 전혀 안 됨"이라는 증상과 현재 코드 구조를 기준으로 정했다.

### 1. AI report scheduler가 배포에서 꺼져 있음

가장 가능성이 높다. 배포 가이드의 smoke preset이 다음 값을 요구했기 때문이다.

```dotenv
ENABLE_MARKET_WARMUP=false
ENABLE_SCHEDULER=false
ENABLE_AI_REPORT_GENERATION=false
```

운영 전환 시 이 중 `ENABLE_SCHEDULER=true`와 `ENABLE_AI_REPORT_GENERATION=true`를 모두 켜고 재배포하지 않았다면 리포트 job은 등록되지 않는다.

확인할 로그:

- `[lifespan] scheduler skipped`
- `AI report generation scheduler skipped because ENABLE_AI_REPORT_GENERATION=false`
- `[lifespan] scheduler started (... reports: every ... hours)`
- `AI 리포트 생성 시작`
- `리포트 생성 대상 자산 수: ...`

### 2. Render Free 또는 sleep형 런타임에서 in-process scheduler에 의존

현재 백엔드는 persistent process 전제다. Render Free는 idle sleep이 있으므로 sleep 동안 scheduler가 정지한다. startup job이 한 번 실행되더라도 cold start, provider latency, memory pressure, timeout으로 안정적인 report cadence를 보장하기 어렵다.

해결 방향은 둘 중 하나다.

- 상시 가동 런타임으로 전환: Render Standard급 이상, Oracle Always Free VM, Fly/Railway 등 sleep 없는 환경.
- 무료/sleep형을 유지: in-process scheduler를 끄고, token-protected task endpoint와 외부 cron으로 작업을 작게 쪼개 호출한다.

### 3. OpenAI 또는 market provider env 미설정으로 모든 target이 readiness/quality 실패

`OPENAI_API_KEY`가 없으면 LangGraph LLM path에서 실패할 수 있다. `FINNHUB_API_KEY`, `STOOQ_API_KEY`, `FRED_API_KEY`, `ECOS_API_KEY`, `FMP_API_KEY` 등 provider key가 부족하면 가격/뉴스/거시 context가 빈 payload로 degrade되고 readiness가 `blocked`가 될 수 있다.

특히 scheduled 대표 target은 asset class가 섞여 있어서 provider별 영향이 다르다.

- `NVDA`: Finnhub/FMP 계열 context 중요.
- `XAU`: Stooq/commodity context 중요.
- `DGS10`: FRED/US bond macro context 중요.
- `005930.KS`: data.go.kr/local provider context 중요.
- `BTC-USD`: crypto provider/news context 중요.

모든 target이 provider 부족 또는 timeout으로 blocked되면 저장 행이 0개일 수 있다.

### 4. DB migration 또는 schema 상태 문제

`ENABLE_DB_SCHEMA_BOOTSTRAP=false`인 hosted runtime에서는 startup이 schema를 검증한다. 필수 table 또는 `ai_reports` metadata columns가 없으면 앱 시작 자체가 실패해야 한다. 앱이 정상 기동 중이라면 가능성은 낮지만, 다음은 확인해야 한다.

- `python -m alembic upgrade head`가 production/staging DB에 적용됐는지.
- `/db-check`가 `db_connected`인지.
- Render/Supabase 로그에 `Database schema is not migration-ready`가 없는지.

### 5. Quality gate 실패가 계속 저장을 막음

2026-06-04에 NVDA의 fact checker 루프 문제는 보완되었지만, 모든 ticker와 모든 provider 상태에서 저장 성공을 보장하는 구조는 아니다. 현재 코드는 품질 실패 시 저장하지 않는 정책이므로, scheduler 로그에서 ticker별로 다음 에러를 분류해야 한다.

- `ReportReadinessError`: 필수 데이터 부족, LLM 호출 전 차단.
- `ReportQualityError`: 생성은 됐지만 quality gate 실패, DB 미저장.
- provider timeout/error: cache fill 또는 latest context 실패.
- DB commit error: schema/connection/transaction 문제.

## Remediation Plan

### Phase 0. 운영 상태를 secret 없이 확인

배포 로그와 환경변수 이름만 확인한다. 값 자체는 출력하거나 문서화하지 않는다.

1. 배포 backend의 `/health`와 `/db-check`를 확인한다.
   - `/health`: 앱 liveness.
   - `/db-check`: DB readiness. `/health`만 통과해도 DB 연결은 실패할 수 있다.
2. 배포 로그에서 lifespan/scheduler 문구를 찾는다.
   - scheduler skipped인지, reports disabled인지, reports interval이 등록됐는지 확인.
3. host env에 아래 변수들이 존재하는지만 확인한다.
   - `ENABLE_SCHEDULER`
   - `ENABLE_AI_REPORT_GENERATION`
   - `REPORT_SCHEDULER_TARGET_TICKERS`
   - `REPORT_SCHEDULER_MAX_REPORTS_PER_RUN`
   - `REPORT_SCHEDULER_ASSET_COOLDOWN_HOURS`
   - `OPENAI_API_KEY`
   - 필요한 market provider key들
4. 최근 배포가 어떤 플랜인지 확인한다.
   - Render Free/sleep형이면 in-process scheduler만으로는 해결하지 않는다.
   - Render Starter도 AI report memory는 빠듯할 수 있으므로 실패 로그를 확인한다.

### Phase 1. 스위치 상태를 바로잡는 최소 운영 조치

상시 가동 backend라면 아래 순서로 켠다.

1. DB migration과 `/db-check` 통과를 먼저 확인한다.
2. `ENABLE_MARKET_WARMUP=true`로 시작 cache 채움을 확인한다.
3. `ENABLE_SCHEDULER=true`, `ENABLE_AI_REPORT_GENERATION=false`로 가격/뉴스 scheduler만 검증한다.
4. 로그에서 가격/뉴스 job이 반복 실행되는지 확인한다.
5. 비용 승인 후 `ENABLE_AI_REPORT_GENERATION=true`로 변경하고 재배포한다.
6. 초기에는 다음처럼 보수적으로 제한한다.

```dotenv
REPORT_SCHEDULER_TARGET_TICKERS=NVDA
REPORT_SCHEDULER_MAX_REPORTS_PER_RUN=1
REPORT_SCHEDULER_INTERVAL_HOURS=6
REPORT_SCHEDULER_ASSET_COOLDOWN_HOURS=6
ENABLE_LLM_REPORT_CRITICS=false
```

7. `NVDA 리포트 생성 완료`와 `/api/reports/NVDA` 200을 확인한 뒤 target을 2개, 3개로 늘린다.

Risk: `ENABLE_AI_REPORT_GENERATION=true`는 OpenAI/API 비용을 발생시킨다. 사용자 승인 후 진행한다.

### Phase 2. sleep형 배포라면 구조를 선택

#### Option A - 상시 가동 런타임으로 전환

가장 코드 변경이 적다.

- Render Standard 또는 sleep 없는 호스트로 전환한다.
- 기존 `backend/app/main.py` in-process scheduler를 그대로 사용한다.
- `ENABLE_SCHEDULER=true`, `ENABLE_AI_REPORT_GENERATION=true`를 운영 정책에 따라 켠다.

권장 상황:

- "배포 환경에서 자동 리포트가 안정적으로 생성"되는 것이 중요하다.
- 월 비용을 일부 감수할 수 있다.
- 운영 복잡도를 낮추고 싶다.

#### Option B - 무료/sleep형 유지 + 외부 cron/task endpoint 추가

코드 변경이 필요하지만 free-tier 현실에 맞다.

변경 대상:

- 신규 `backend/app/api/tasks.py`
  - `POST /api/tasks/market/prices`
  - `POST /api/tasks/market/news`
  - `POST /api/tasks/reports`
  - 공유 secret header 검증.
- `backend/app/core/config.py`
  - `TASK_TRIGGER_TOKEN` 추가.
  - 필요 시 task당 max ticker 설정 추가.
- `backend/app/main.py`
  - tasks router 등록.
- tests
  - token 없거나 틀릴 때 401/403.
  - token이 맞으면 기존 `update_prices_task`, `update_news_task`, `generate_daily_reports`가 호출되는지 mock 검증.

운영:

- `ENABLE_SCHEDULER=false` 유지.
- GitHub Actions scheduled workflow 또는 cron-job.org가 token header로 task endpoint 호출.
- report cron은 1회 1 ticker 또는 1~2개 target으로 제한.

중요: 이 endpoint는 일반 사용자/챗봇 경로가 아니며, AGENTS.md 섹션 14 규칙을 유지한다.

Risk: 새 운영 endpoint와 scheduler cadence 변경이므로 구현 전 사용자 확인이 필요하다.

### Phase 3. 실패 원인을 저장/관측 가능하게 개선

현재는 실패한 리포트가 DB에 남지 않으므로 "404"만 보고는 readiness 실패인지 quality 실패인지 알기 어렵다. 다음 중 하나를 선택한다.

#### 3-A. 로그 기반 최소 개선

- ticker별 실패 로그에서 `ReportReadinessError`, `ReportQualityError`, provider error를 구분해 메시지를 명확히 한다.
- secret redaction은 기존 `redact_secrets()` 정책을 유지한다.

장점: DB 변경 없음.
단점: 배포 로그를 놓치면 이력 추적이 어렵다.

#### 3-B. `report_generation_runs` 감사 테이블 추가

- scheduler run id, ticker, status, started_at, finished_at, failure_type, sanitized failure_summary, metadata summary를 저장한다.
- 실제 리포트 본문이 아닌 운영 진단 메타만 저장한다.
- Alembic migration 필요.

장점: `/api/reports/{ticker}` 404와 별개로 "왜 생성 실패했는지" 추적 가능.
단점: DB schema 변경이므로 사용자 승인과 migration 필요.

### Phase 4. provider readiness를 target별로 검증

AI report를 한꺼번에 전체 target으로 켜지 않는다.

1. `REPORT_SCHEDULER_TARGET_TICKERS=NVDA`, max 1로 시작.
2. 성공하면 `DGS10`, `XAU`, `BTC-USD`, `005930.KS`를 하나씩 추가한다.
3. target 추가마다 다음을 확인한다.
   - ticker-level cache fill 성공.
   - latest context fetch 성공 또는 제한 metadata.
   - readiness not blocked.
   - quality gate 통과.
   - DB 저장 후 `/api/reports/{ticker}` 200.

### Phase 5. 사용자 화면 확인

생성 성공 후 frontend는 새 리포트를 만드는 것이 아니라 저장 리포트를 읽는지 확인한다.

1. Plus 또는 Pro entitlement 계정으로 `/detail/NVDA` 접근.
2. `GET /api/reports/NVDA`가 200인지 확인.
3. Free 계정은 report fetch를 호출하지 않거나 paywall로 제한되는지 확인.
4. 저장 리포트가 없을 때는 pending 상태가 보이고 `POST /api/ai/generate/{ticker}`가 호출되지 않는지 확인.

## Recommended Immediate Path

현 상태에서 가장 빠른 해결 순서는 다음이다.

1. 배포 로그에서 scheduler 상태 문구를 확인한다.
2. host env가 smoke preset으로 남아 있으면 `ENABLE_SCHEDULER=true`, `ENABLE_AI_REPORT_GENERATION=true`를 켜되, `REPORT_SCHEDULER_TARGET_TICKERS=NVDA`, `REPORT_SCHEDULER_MAX_REPORTS_PER_RUN=1`로 시작한다.
3. Render Free/sleep형이면 in-process scheduler로 계속 버티지 말고 Option A(상시 가동) 또는 Option B(task endpoint + cron)를 결정한다.
4. 첫 성공 기준은 `NVDA 리포트 생성 완료` 로그와 `/api/reports/NVDA` 200이다.
5. 이후 target을 하나씩 늘린다.

## Verification Plan

계획서 작성 단계에서는 코드 변경이 없으므로 build/test는 필수 실행하지 않는다. 구현 단계에서는 선택한 경로에 따라 다음을 실행한다.

### Operational checks

```powershell
# secret 출력 금지. URL만 배포 backend origin으로 바꿔 실행.
Invoke-RestMethod https://<backend-origin>/health
Invoke-RestMethod https://<backend-origin>/db-check
```

배포 로그에서 확인:

- `[lifespan] scheduler started`
- `reports: every ... hours`
- `AI 리포트 생성 시작`
- `리포트 생성 대상 자산 수`
- `{ticker} 리포트 생성 완료`
- 실패 시 `{ticker} 리포트 실패: ...`

### Code verification if Option B is implemented

```powershell
cd backend
py -m compileall app
.\.venv\Scripts\python.exe -m pytest tests\test_ai_report_generation_switch.py tests\test_ai_report_quality_gate.py
```

task endpoint를 추가하면 별도 `tests/test_tasks_api.py`를 만들고 token/auth 및 service call mock을 검증한다.

### Frontend verification

코드 변경이 없으면 생략 가능하다. report UI 변경이 있으면:

```powershell
cd frontend
npm run lint
npm run build
```

## Risks And Approvals

- `ENABLE_AI_REPORT_GENERATION=true`, target 확대, interval 축소는 OpenAI/provider 비용을 증가시킨다. 사용자 승인 필요.
- task endpoint + external cron은 새 운영 트리거를 추가한다. 사용자/챗봇 트리거는 아니지만 scheduler behavior 변경이므로 사용자 승인 필요.
- audit table 추가는 DB schema migration이다. 사용자 승인과 migration plan 필요.
- provider secret 값은 문서/로그/응답에 절대 남기지 않는다.
- Render Free에서 sleep을 막기 위한 ping은 임시 완화일 뿐 안정적 report generation 해법으로 보지 않는다.

## Documentation Follow-up

구현 또는 운영 조치를 수행하면 다음을 갱신한다.

- `docs/harness/report-generation-deployment-failure-remediation-implementation-2026-06-07.md` 또는 실제 수행 날짜의 구현 기록.
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/feature-index.md`
- Option B를 구현하면 `docs/harness/features/chatbot-assistant.md`에도 "챗봇은 생성 endpoint를 호출하지 않음" 규칙을 재확인한다.
