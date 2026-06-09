# 데모 NVDA 단일 리포트와 제한 live market 복구 계획

Date: 2026-06-09
Status: Plan only - 구현/환경 변경 전 운영 확인 필요
Related documentation:
- `docs/harness/demo-nvda-report-live-market-policy-2026-06-09.md`

Related features:
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/deployment-runtime.md`

## Objective

데모 운영 정책을 다음 상태로 고정하고, 환경변수 변경 후 `NVDA` 리포트가 저장되지 않는 문제를 단계적으로 복구한다.

- 리포트 생성 target: `NVDA` only.
- live market target: `DGS10`, `XAU`, `BTC-USD`, `NVDA`, `005930.KS`, `^GSPC`, `^NDX`, `KRW=X`, `^KS11`.
- 나머지 자산: `demo_mock`.
- 사용자-facing 요청과 챗봇: 저장된 scheduled report만 읽고 생성은 트리거하지 않음.

## Phase 0 - 현재 환경 스위치 확인

목표: 리포트 job이 등록될 수 있는 상태인지 시크릿을 출력하지 않고 확인한다.

확인할 변수 이름과 기대값:

```env
ENABLE_SCHEDULER=true
ENABLE_AI_REPORT_GENERATION=true
REPORT_SCHEDULER_TARGET_TICKERS=NVDA
REPORT_SCHEDULER_MAX_REPORTS_PER_RUN=1
REPORT_SCHEDULER_COVERAGE=conservative
REPORT_SCHEDULER_INTERVAL_HOURS=6
REPORT_SCHEDULER_STARTUP_DELAY_SECONDS=180
REPORT_SCHEDULER_ASSET_COOLDOWN_HOURS=6
MARKET_LIVE_TICKERS=DGS10,XAU,BTC-USD,NVDA,005930.KS,^GSPC,^NDX,KRW=X,^KS11
```

시크릿은 값이 아닌 존재 여부만 확인한다.

- `OPENAI_API_KEY`
- `FINNHUB_API_KEY`
- `FMP_API_KEY`
- `FRED_API_KEY`
- `COINGECKO_DEMO_API_KEY`
- `DATA_GO_KR_API_KEY`

완료 기준:
- `NVDA`가 `REPORT_SCHEDULER_TARGET_TICKERS`와 `MARKET_LIVE_TICKERS` 양쪽에 모두 있다.
- scheduler와 AI report generation 스위치가 모두 true다.
- max reports per run이 1 이상이다.

## Phase 1 - scheduler 등록과 첫 발화 확인

목표: 환경변수는 맞지만 job이 실제로 등록/발화하지 않는 경우를 분리한다.

확인 로그:

- `[lifespan] scheduler started`
- `reports: in 180s then every 6 hours`
- `AI 리포트 생성 시작`
- `리포트 생성 대상 자산 수: 1`
- `NVDA 리포트 생성 시작`

판단:

- `scheduler skipped`면 `ENABLE_SCHEDULER`부터 수정한다.
- `reports: disabled by ENABLE_AI_REPORT_GENERATION`이면 `ENABLE_AI_REPORT_GENERATION`부터 수정한다.
- scheduler started 이후 `AI 리포트 생성 시작`이 없으면 startup delay 이전에 프로세스가 재시작되었는지 확인한다.
- `리포트 생성 대상 자산 수: 0`이면 `REPORT_SCHEDULER_TARGET_TICKERS` 값을 다시 확인한다.

완료 기준:
- 로그에서 `NVDA 리포트 생성 시작`까지 확인된다.

## Phase 2 - NVDA market readiness 확인

목표: report readiness가 가격 0/누락으로 차단되는지 분리한다.

확인 순서:

1. `/api/market/prices`에서 `us_top10` 그룹의 `NVDA` payload가 0이 아닌지 확인한다.
2. provider metadata 또는 로그에서 `NVDA`가 `demo_mock`이 아닌 live provider 경로를 탔는지 확인한다.
3. `MARKET_LIVE_TICKERS`에 `NVDA`가 없으면 즉시 추가한다.
4. Finnhub quote 실패가 반복되면 FMP fallback key와 budget을 확인한다.
5. FMP 402 또는 budget 초과가 반복되면 `NVDA` 현재가는 Finnhub primary를 우선 복구한다. Stooq fallback은 opt-in이며 별도 판단 전 기본 false를 유지한다.

완료 기준:
- `NVDA` price/currentPrice가 0이 아니다.
- readiness blocked 로그가 없어지거나, blocking reason이 provider readiness가 아닌 다른 gate로 이동한다.

## Phase 3 - 리포트 저장 성공 확인

목표: `NVDA` 단일 리포트가 DB에 저장되는지 확인한다.

확인 로그:

- `NVDA 리포트 생성 완료`
- `AI 리포트 생성 종료`

확인 API/DB:

- Plus/Pro 권한으로 `GET /api/reports/NVDA`가 200을 반환한다.
- 운영 DB의 `ai_reports`에 `NVDA` asset_id의 최신 row가 있다.
- 생성 완료 로그 후 404면 `/db-check`의 sanitized DB host/source와 실제 조회 DB가 같은지 확인한다.

완료 기준:
- 저장된 `AIReport` row가 생성되고 상세 페이지가 저장 리포트를 렌더링한다.

## Phase 4 - 실패 유형별 후속 조치

### readiness_blocked

조치:

- `MARKET_LIVE_TICKERS`에 `NVDA` 포함 여부 확인.
- `FINNHUB_API_KEY` 존재 여부 확인.
- `FMP_API_KEY`, `FMP_DAILY_CALL_BUDGET`, `FMP_FETCH_TIMEOUT_SECONDS` 확인.
- provider 장애가 일시적이면 cooldown 후 재시도한다.

주의:
- 가격이 0인데 리포트를 저장하도록 gate를 낮추지 않는다.
- mock 데이터를 live report처럼 가장하지 않는다.

### quality_failed

조치:

- 로그의 `feedback`과 `revision_count`를 수집한다.
- format, numeric fact checker, qualitative checker, evaluator 중 어느 단계인지 분리한다.
- 반복 실패 gate에 한해 prompt 또는 deterministic fallback을 좁게 수정한다.
- 실제 LLM 호출 없는 backend 단위 테스트를 먼저 작성한다.

임시 선택지:
- evaluator만 반복 실패하고 deterministic gates가 통과하는 경우 `ENABLE_REPORT_EVALUATOR=false`를 데모 smoke에서만 검토할 수 있다.
- 이 선택은 품질 기준을 낮추므로 문서화와 운영 승인 없이 기본값으로 두지 않는다.

### provider_unavailable

조치:

- provider key 존재 여부만 확인한다.
- FMP 402, Finnhub 5xx, rate limit, timeout을 로그에서 분리한다.
- `MARKET_PRICE_FETCH_TIMEOUT_SECONDS=55`보다 더 올리는 것은 broad warm-up 시간을 늘리므로 로그 기반으로만 검토한다.

### cooldown skip

조치:

- `REPORT_SCHEDULER_ASSET_COOLDOWN_HOURS` 안에 이미 저장된 리포트가 있으면 정상이다.
- 반복 smoke가 필요할 때 cooldown을 낮추는 변경은 생성 비용을 늘리므로 테스트 환경에서만 제한적으로 한다.

## Phase 5 - 문서와 샘플 env 정합성 보강

목표: 다음 하네스가 같은 혼선을 반복하지 않게 한다.

1. `.env.example` 주석을 데모 정책 기준으로 더 명확히 한다.
   - `MARKET_LIVE_TICKERS`는 live/mock 경계.
   - `REPORT_SCHEDULER_TARGET_TICKERS`는 리포트 생성 경계.
   - NVDA 단일 리포트 데모에서는 두 값이 의도적으로 다르다.
2. `docs/harness/features/market-data.md`에 데모 live allowlist 정책을 유지한다.
3. `docs/harness/features/asset-detail-ai-community.md`에 NVDA-only report target 정책을 연결한다.
4. 변경이 실제 코드/env 예시에 들어가면 별도 implementation record를 추가한다.

완료 기준:
- feature index와 관련 feature docs에서 이 문서와 policy 문서를 찾을 수 있다.

## Verification Plan

문서 작성 단계에서는 실행하지 않았다. 구현 또는 환경 반영 단계에서 다음을 수행한다.

- Backend import check: `python -m compileall backend/app`
- Targeted tests if code changes occur:
  - `python -m pytest backend/tests/test_ai_report_generation_switch.py`
  - `python -m pytest backend/tests/test_ai_report_quality_gate.py`
  - `python -m pytest backend/tests/test_price_providers.py`
- Runtime smoke:
  - backend restart 후 scheduler registration log 확인.
  - startup delay 이후 `NVDA 리포트 생성 시작/완료` 확인.
  - `GET /api/market/prices`에서 `NVDA`, `DGS10`, `XAU`, `BTC-USD`, `005930.KS`, `^GSPC`, `^NDX`, `KRW=X`, `^KS11` 확인.
  - allowlist 밖 ticker가 `demo_mock` provider metadata를 반환하는지 확인.
  - Plus/Pro 권한으로 `GET /api/reports/NVDA` 200 확인.

## Risks

- `ENABLE_AI_REPORT_GENERATION=true`는 OpenAI 비용을 발생시킬 수 있다.
- `ENABLE_SCHEDULER=true`는 market provider 호출도 활성화한다.
- `MARKET_LIVE_TICKERS=*`는 데모 정책과 맞지 않고 free-tier quota를 빠르게 소모할 수 있다.
- provider key가 없거나 provider free tier가 제한되면 코드 변경 없이 live target을 모두 복구할 수 없다.
- 품질 gate를 낮추면 잘못된 리포트가 저장될 수 있으므로 readiness/quality 실패를 억지로 성공 처리하지 않는다.
