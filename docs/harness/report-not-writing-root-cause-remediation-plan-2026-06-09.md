# AI 리포트 작성 미발화 원인 분석 및 복구 계획

Date: 2026-06-09
Status: Plan only - 코드/환경 변경 없음
Follow-up implementation:
- `docs/harness/report-data-as-of-naive-datetime-fix-2026-06-09.md`
Related features:
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/market-data.md`
- `docs/harness/features/deployment-runtime.md`

Related prior records:
- `docs/harness/report-backend-generation-failure-analysis-2026-06-08.md`
- `docs/harness/report-backend-generation-remediation-plan-2026-06-08.md`
- `docs/harness/report-generation-scheduler-not-firing-log-audit-2026-06-08.md`
- `docs/harness/demo-nvda-report-live-market-policy-2026-06-09.md`
- `docs/harness/demo-nvda-report-live-market-remediation-plan-2026-06-09.md`

## Objective

현재 증상인 "리포트 작성 자체가 시작되지 않음"을 현재 코드 기준으로 분해하고, 실제 운영/로컬 환경에서 어떤 순서로 확인해야 하는지 복구 계획을 남긴다.

이 문서는 리포트 생성 정책을 바꾸지 않는다. 사용자-facing 상세 페이지, 챗봇, `POST /api/ai/generate/{ticker}`는 새 리포트를 생성하지 않고, 저장된 scheduled report만 읽는 원칙을 유지한다.

## 결론 요약

### 첨부 로그 기준 후속 결론

첨부 로그에서는 `AI 리포트 생성 시작`, `NVDA 리포트 생성 시작`, graph node 실행, fact checker loop, 숫자 정제 fallback까지 모두 확인된다. 따라서 이 로그의 실제 원인은 scheduler 미발화가 아니라 **작성 완료 후 DB 저장 실패**다.

구체적으로 `AIReport.data_as_of`는 DB에서 `TIMESTAMP WITHOUT TIME ZONE`인데, 리포트 metadata의 `data_as_of`가 `+00:00` offset이 있는 timezone-aware datetime으로 파싱되어 asyncpg commit이 실패했다.

이 저장 실패는 `docs/harness/report-data-as-of-naive-datetime-fix-2026-06-09.md`에서 수정했다.

현재 코드에서 리포트가 작성되려면 아래 조건을 모두 통과해야 한다.

1. FastAPI lifespan이 실행된다.
2. `ENABLE_SCHEDULER=true`라서 APScheduler가 시작된다.
3. `ENABLE_AI_REPORT_GENERATION=true`라서 `generate_daily_reports` job이 등록된다.
4. 프로세스가 `REPORT_SCHEDULER_STARTUP_DELAY_SECONDS` 이후 첫 발화까지 살아 있다.
5. `REPORT_SCHEDULER_TARGET_TICKERS`가 비어 있지 않고, 대상 ticker가 포함되어 있다.
6. `REPORT_SCHEDULER_MAX_REPORTS_PER_RUN`이 1 이상이다.
7. 대상 ticker가 cooldown 기간 안에 이미 생성된 상태가 아니다.
8. market cache 또는 `ensure_price_cache_for_ticker()`가 0이 아닌 primary price/fact를 확보한다.
9. OpenAI writer/evaluator와 deterministic quality gate를 통과한다.
10. DB commit이 성공하고, 조회 API가 같은 DB와 같은 ticker로 조회한다.

사용자가 관찰한 "작성 자체를 안 함"은 우선 1-6번, 특히 **scheduler job 미등록/미발화**를 먼저 의심해야 한다. 로그에 `AI 리포트 생성 시작`이 없다면 provider나 quality gate까지 도달하지 않은 것이다.

## 현재 코드상 핵심 경로

### 사용자 요청은 생성 경로가 아님

- `backend/app/main.py`의 `POST /api/ai/generate/{ticker}`는 `ensure_report_generation_allowed()`를 호출하고 항상 HTTP 403을 반환한다.
- `GET /api/reports/{ticker}`는 저장된 `AIReport`만 조회하며 없으면 404를 반환한다.
- 따라서 상세 페이지에서 404가 보이는 것은 "프론트가 생성을 실패했다"가 아니라 "scheduler가 아직 저장하지 않았거나 저장 전 차단됐다"는 뜻이다.

### scheduler 등록 조건

- `backend/app/main.py` lifespan은 `settings.ENABLE_SCHEDULER`가 true일 때만 APScheduler를 만든다.
- 그 내부에서 `settings.ENABLE_AI_REPORT_GENERATION`이 true일 때만 `generate_daily_reports` job을 등록한다.
- 현재 구현은 interval job에 `next_run_time=datetime.now() + timedelta(seconds=REPORT_SCHEDULER_STARTUP_DELAY_SECONDS)`를 지정해 기동 직후 1회 발화를 보정한다.
- 그래도 프로세스가 startup delay보다 빨리 재시작되면 첫 발화가 없다.

### 대상/상한 조건

- `backend/app/services/ai_service.py`의 `_configured_scheduled_report_tickers()`는 `REPORT_SCHEDULER_TARGET_TICKERS`를 comma split하고 빈 값을 제거한다.
- `generate_daily_reports()`는 `ensure_scheduled_report_assets()`로 target asset을 만든 뒤 `REPORT_SCHEDULER_MAX_REPORTS_PER_RUN`까지 순회한다.
- target이 0개이거나 max가 0이면 리포트 생성 loop가 실질적으로 아무 일도 하지 않는다.

### readiness/quality 저장 조건

- `generate_report_for_ticker()`는 market cache에서 ticker payload를 찾고, 없으면 `ensure_price_cache_for_ticker()`를 한 번 시도한다.
- 가격 또는 primary fact가 0/누락이면 `ReportReadinessError`로 저장하지 않는다.
- readiness 이후에도 LangGraph writer/evaluator, format validator, numeric fact checker, qualitative checker를 통과해야 `AIReport`가 commit된다.

## 실패 분기표

| 증상/로그 | 의미 | 우선 조치 |
| --- | --- | --- |
| `[lifespan] scheduler skipped` | `ENABLE_SCHEDULER=false` | scheduler 스위치부터 true로 변경 검토 |
| `reports: disabled by ENABLE_AI_REPORT_GENERATION` | AI report job 미등록 | `ENABLE_AI_REPORT_GENERATION=true` 검토 |
| `scheduler started`는 있지만 `AI 리포트 생성 시작` 없음 | 첫 발화 전 재시작, startup delay 미도달, 로그 범위 부족 | 프로세스 생존 시간과 `REPORT_SCHEDULER_STARTUP_DELAY_SECONDS` 확인 |
| `AI 리포트 생성 시작`은 있지만 `리포트 생성 대상 자산 수: 0` | target parsing 결과 없음 | `REPORT_SCHEDULER_TARGET_TICKERS` 확인 |
| `스케줄러 회당 최대 리포트 수 도달 - max=0` | 회당 생성 상한 0 | `REPORT_SCHEDULER_MAX_REPORTS_PER_RUN>=1` |
| `{ticker} 오늘 리포트 이미 존재 - 건너뜀` | cooldown 내 기존 report 존재 | 정상 동작. smoke 시 cooldown 정책 확인 |
| `failure_type=provider_unavailable` | cache fill 또는 provider payload 없음 | provider key/allowlist/timeout 확인 |
| `failure_type=readiness_blocked` | 가격/primary fact 0 또는 누락 | `MARKET_LIVE_TICKERS`, provider 장애, stale cache 여부 확인 |
| `failure_type=quality_failed` | LLM 결과가 품질 gate 통과 실패 | feedback과 gate별 실패 원인 수집 |
| `{ticker} 리포트 생성 완료` 후 404 | DB/source/ticker/권한 mismatch | `/db-check`, migration, Plus/Pro 권한 확인 |

## 복구 계획

### Phase 0 - 시크릿 없는 환경 스위치 확인

목표: 리포트 job이 등록될 수 있는 상태인지 확인한다. `.env` 전체를 출력하지 않고 변수 이름과 기대 상태만 확인한다.

확인할 정책 변수:

```env
ENABLE_SCHEDULER=true
ENABLE_AI_REPORT_GENERATION=true
REPORT_SCHEDULER_TARGET_TICKERS=<생성 대상 ticker 포함>
REPORT_SCHEDULER_MAX_REPORTS_PER_RUN=1 이상
REPORT_SCHEDULER_STARTUP_DELAY_SECONDS=<프로세스가 버틸 수 있는 값>
REPORT_SCHEDULER_ASSET_COOLDOWN_HOURS=<운영 정책값>
```

NVDA 단일 데모라면 기대값:

```env
REPORT_SCHEDULER_TARGET_TICKERS=NVDA
REPORT_SCHEDULER_MAX_REPORTS_PER_RUN=1
MARKET_LIVE_TICKERS=DGS10,XAU,BTC-USD,NVDA,005930.KS,^GSPC,^NDX,KRW=X,^KS11
```

시크릿성 provider key는 값이 아니라 존재 여부만 확인한다.

- `OPENAI_API_KEY`
- `FINNHUB_API_KEY`
- `FMP_API_KEY`
- `FRED_API_KEY`
- `COINGECKO_DEMO_API_KEY`
- `DATA_GO_KR_API_KEY`

완료 기준:
- scheduler와 AI report generation 스위치가 모두 true다.
- target ticker가 1개 이상이고 max reports per run이 1 이상이다.
- `NVDA` 데모라면 `NVDA`가 `REPORT_SCHEDULER_TARGET_TICKERS`와 `MARKET_LIVE_TICKERS` 양쪽에 있다.

### Phase 1 - job 등록/발화 확인

목표: "작성 자체를 안 함"이 실제 job 미등록/미발화인지 확정한다.

확인 로그:

- `[lifespan] scheduler started`
- `reports: in ... then every ...`
- `AI 리포트 생성 시작`
- `리포트 생성 대상 자산 수: ...`
- `{ticker} 리포트 생성 시작`

판단:

- `scheduler skipped`면 `ENABLE_SCHEDULER=false`다.
- `reports: disabled by ENABLE_AI_REPORT_GENERATION`이면 report job이 등록되지 않는다.
- `scheduler started` 후 `AI 리포트 생성 시작`이 없으면 `REPORT_SCHEDULER_STARTUP_DELAY_SECONDS` 이전에 프로세스가 재시작되는지 확인한다.
- Render Standard처럼 상시 런타임이어도 배포 직후 재시작이 잦으면 첫 발화를 놓칠 수 있다.

완료 기준:
- 로그에서 `{ticker} 리포트 생성 시작`까지 확인된다.

### Phase 2 - target/cooldown 확인

목표: job은 발화했지만 생성 loop가 비어 있는지 분리한다.

확인:

1. `리포트 생성 대상 자산 수`가 1 이상인지 본다.
2. target ticker가 DB `Asset`으로 seed되는지 확인한다.
3. `REPORT_SCHEDULER_MAX_REPORTS_PER_RUN`이 1 이상인지 확인한다.
4. cooldown 내 기존 report 때문에 skip되는지 확인한다.

완료 기준:
- target별 `{ticker} 리포트 생성 시작` 로그가 남는다.

### Phase 3 - market readiness 확인

목표: 생성은 시작했지만 저장 전 readiness에서 차단되는지 분리한다.

확인:

1. `/api/market/prices`에서 target ticker의 `currentPrice` 또는 `price`가 0이 아닌지 확인한다.
2. `MARKET_LIVE_TICKERS` allowlist 때문에 target이 의도치 않게 `demo_mock` 또는 빈 payload로 가는지 확인한다.
3. `ensure_price_cache_for_ticker()` 로그에서 timeout/provider failure가 있는지 본다.
4. provider별 key 존재 여부와 무료 tier 제한을 확인한다.

NVDA 기준:

- `FINNHUB_API_KEY`가 primary quote에 필요하다.
- FMP는 fallback/history/profile 보조이며 무료 tier 402가 반복될 수 있다.
- 모든 provider가 실패하고 직전 stale snapshot이 없으면 콜드 스타트에서는 가격 0으로 readiness blocked가 날 수 있다.

완료 기준:
- `failure_type=readiness_blocked`가 사라지거나 blocking reason이 명확히 문서화된다.

### Phase 4 - LLM/quality gate 확인

목표: 리포트 작성은 시작됐지만 품질 gate 때문에 저장되지 않는지 분리한다.

확인:

1. `failure_type=quality_failed` 로그의 `revision_count`와 `feedback`을 수집한다.
2. 실패 gate가 format, numeric fact checker, qualitative checker, evaluator 중 어디인지 분리한다.
3. 반복 실패 gate에 대해서만 prompt 또는 deterministic fallback을 좁게 수정한다.
4. 일반 테스트에서는 실제 OpenAI 호출을 피하고, 단위 테스트/fixture로 검증한다.

운영 선택지:
- deterministic gates가 통과하고 evaluator만 반복 실패한다면, 데모 smoke에 한해 `ENABLE_REPORT_EVALUATOR=false`를 검토할 수 있다.
- 이 선택은 품질 기준을 낮추므로 기본값으로 두지 않고 별도 기록을 남긴다.

완료 기준:
- `{ticker} 리포트 생성 완료`가 로그에 남는다.

### Phase 5 - DB 저장/조회 정합성 확인

목표: 생성 완료 후에도 조회가 404인 경우를 분리한다.

확인:

1. `/db-check`로 backend가 연결한 DB source/scheme/host를 sanitized 응답으로 확인한다.
2. 운영 DB에서 `assets.ticker`와 `ai_reports.asset_id`의 최신 row가 있는지 확인한다.
3. Alembic migration이 적용되어 `AIReport` metadata columns가 존재하는지 확인한다.
4. `GET /api/reports/{ticker}`는 Plus/Pro 권한이 필요하므로 entitlement를 확인한다.
5. ticker 대소문자/alias mismatch가 있는지 확인한다.

완료 기준:
- Plus/Pro 권한으로 `GET /api/reports/{ticker}`가 200을 반환하고 상세 페이지가 저장 리포트를 렌더링한다.

## 권장 최소 운영 프로파일

NVDA 단일 데모를 먼저 살리는 경우:

```env
ENABLE_MARKET_WARMUP=true
ENABLE_SCHEDULER=true
ENABLE_AI_REPORT_GENERATION=true

REPORT_SCHEDULER_COVERAGE=conservative
REPORT_SCHEDULER_TARGET_TICKERS=NVDA
REPORT_SCHEDULER_MAX_REPORTS_PER_RUN=1
REPORT_SCHEDULER_INTERVAL_HOURS=6
REPORT_SCHEDULER_STARTUP_DELAY_SECONDS=60
REPORT_SCHEDULER_ASSET_COOLDOWN_HOURS=6

MARKET_LIVE_TICKERS=DGS10,XAU,BTC-USD,NVDA,005930.KS,^GSPC,^NDX,KRW=X,^KS11
```

주의:
- 위 설정은 OpenAI와 market provider 호출 비용을 발생시킬 수 있다.
- `REPORT_SCHEDULER_STARTUP_DELAY_SECONDS`를 더 낮추면 첫 발화 가능성은 높아지지만 market warm-up과 provider queue가 준비되기 전에 report job이 시작될 수 있다. 현재 코드는 ticker-level cache fill로 보강하지만 provider key/장애는 해결하지 못한다.
- `MARKET_LIVE_TICKERS=*`는 데모 정책과 맞지 않고 무료 API quota를 빠르게 소모할 수 있다.

## 구현 후보

### 후보 A - 설정/운영만 조정

코드 변경 없이 environment와 로그 확인으로 복구한다.

적합한 경우:
- report job이 미등록 또는 미발화 상태다.
- target/cooldown/max 설정이 잘못되어 있다.
- provider key 존재 여부가 문제다.

검증:
- backend 재시작 후 scheduler log 확인.
- startup delay 이후 `{ticker} 리포트 생성 시작/완료` 확인.

### 후보 B - 관측성 보강

구조화 로그를 추가해 scheduler run id, ticker, stage, failure_type, blocking_reasons, quality feedback을 한 줄로 남긴다.

적합한 경우:
- 운영 로그에서 같은 404의 원인을 빠르게 구분하기 어렵다.
- 실패를 DB에 남기기 전 낮은 위험으로 진단성을 높이고 싶다.

검증:
- 실제 LLM 호출 없이 mocked service path로 stage 로그가 남는지 확인한다.

### 후보 C - 실패 시도 저장 테이블

`ai_report_generation_attempts` 같은 read-only 진단 테이블을 추가한다.

적합한 경우:
- 운영자가 배포 로그에 접근하지 않아도 최근 실패 원인을 봐야 한다.

주의:
- DB schema 변경과 Alembic migration이 필요하므로 구현 전 확인이 필요하다.
- 일반 사용자/챗봇이 생성을 trigger하지 않도록 diagnostics는 조회 전용이어야 한다.

### 후보 D - 외부 cron/task endpoint

웹 lifespan에 의존하지 않고 token-protected 내부 task endpoint나 외부 cron으로 `generate_daily_reports()`를 호출한다.

적합한 경우:
- 프로세스 재시작/배포가 잦아 in-process startup delay 방식이 불안정하다.

주의:
- 일반 사용자-facing endpoint가 아니어야 한다.
- token, rate limit, 중복 실행 방지, 비용 한도 정책이 필요하다.

## Verification Plan

문서 작성 단계에서는 실제 리포트 생성, OpenAI 호출, provider 호출, DB 변경을 실행하지 않았다.

계획 구현 시 권장 검증:

- Backend import check: `python -m compileall backend/app`
- Existing scheduler switch tests: `python -m pytest backend/tests/test_ai_report_generation_switch.py`
- Provider/readiness 관련 변경 시: `python -m pytest backend/tests/test_price_providers.py`
- Quality gate 관련 변경 시: `python -m pytest backend/tests/test_ai_report_quality_gate.py`
- Hosted smoke:
  - backend restart 후 `scheduler started` 확인.
  - startup delay 이후 `AI 리포트 생성 시작` 확인.
  - target별 `리포트 생성 완료` 또는 `failure_type` 확인.
  - Plus/Pro 권한으로 `GET /api/reports/{ticker}` 200 확인.

## Risks

- `ENABLE_AI_REPORT_GENERATION=true`는 OpenAI 비용을 발생시킨다.
- `ENABLE_SCHEDULER=true`는 report뿐 아니라 market/news scheduler도 활성화한다.
- startup delay 단축, interval 단축, target 확대는 비용과 provider rate limit 위험을 높인다.
- provider key가 없거나 무료 tier가 막혀 있으면 코드만으로 live report를 만들 수 없다.
- readiness/quality gate를 우회해 실패 리포트를 저장하면 제품 신뢰성이 떨어진다.
- `.env`, provider key, DB URL, JWT secret 값은 문서/로그/응답에 남기지 않는다.

## Files Inspected

- `ARCHITECTURE.md`
- `PROJECT_STRUCTURE_ANALYSIS.md`
- `DEVELOPMENT_DIRECTION.md`
- `docs/harness/feature-index.md`
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/demo-nvda-report-live-market-policy-2026-06-09.md`
- `docs/harness/demo-nvda-report-live-market-remediation-plan-2026-06-09.md`
- `docs/harness/report-backend-generation-failure-analysis-2026-06-08.md`
- `docs/harness/report-backend-generation-remediation-plan-2026-06-08.md`
- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/app/services/ai_service.py`
- `backend/app/services/market_service.py`
- `backend/app/services/demo_market_data.py`
- `backend/app/services/graph/llm.py`
- `backend/tests/test_ai_report_generation_switch.py`

## User-facing generation policy

사용자-facing 요청은 새 리포트 생성을 trigger하지 않는다. 상세 페이지, 챗봇, 일반 API 호출은 저장된 scheduled report만 읽는다. 이 계획의 목표는 backend scheduled/background 경로가 target ticker에 대해 저장 리포트를 만들 수 있게 하는 것이며, 수동 생성 endpoint를 다시 여는 것이 아니다.
