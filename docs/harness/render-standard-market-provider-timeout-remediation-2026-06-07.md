# Render Standard 전환 후 시장 provider timeout 보완

Date: 2026-06-07
Status: Implemented
Feature:
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/deployment-runtime.md`

## Objective

Render Standard 전환 후 배포 로그에서 AI 리포트 scheduler는 정상 등록되었지만, startup 리포트 생성 중 `NVDA` 가격 캐시가 채워지지 않아 `No cached market data found for ticker: NVDA`로 중단된 문제를 완화한다.

## Observed Deployment Log

- Render build/deploy는 성공했다.
- `ENABLE_SCHEDULER=true`, `ENABLE_AI_REPORT_GENERATION=true` 상태로 `generate_daily_reports_startup` job이 즉시 실행되었다.
- `ENABLE_MARKET_WARMUP=true` warm-up도 동시에 background task로 시작되었다.
- Stooq 계열 index/commodity snapshot에서 `ConnectTimeout('')`가 발생했다.
- `NVDA market cache miss before report generation; attempting ticker-level cache fill` 이후 `No cached market data found for ticker: NVDA`가 발생했다.

## Root Cause

Render Standard 자체의 런타임 실패가 아니라, Standard 전환으로 scheduler가 정상 상시 실행되면서 기존 provider/시작 순서 리스크가 드러난 것이다.

1. startup report job은 app startup 직후 실행된다.
2. market warm-up은 서버 health check를 빨리 통과시키기 위해 background task로 동시에 실행된다.
3. 따라서 첫 리포트가 broad market cache보다 먼저 실행될 수 있다.
4. `ensure_price_cache_for_ticker("NVDA")`가 단일 ticker cache fill을 시도하지만, 미국 주식 snapshot 내부의 부가 데이터인 Finnhub profile 또는 Stooq history가 timeout되면 현재가까지 버려질 수 있었다.
5. 이후 Render 로그에서 `MARKET_PRICES_REFRESH_MINUTES=30`, `REPORT_SCHEDULER_INTERVAL_HOURS=12`, `REPORT_SCHEDULER_TARGET_TICKERS=NVDA`는 반영됐지만 startup job은 여전히 app startup 즉시 실행되어 warm-up/provider queue와 경쟁했다.

## Files Changed

- `backend/app/services/price_providers.py`
  - `_fetch_finnhub_stock_snapshot()`에서 Finnhub quote 수집 후 부가 데이터인 profile market cap 또는 Stooq history가 실패해도 현재가 snapshot을 유지하도록 변경했다.
  - profile 실패 시 `marketCap=0.0`으로 degrade한다.
  - Stooq history 실패 시 `history_prices=[current_price]`로 degrade한다.
  - 실패 로그는 `redact_secrets()`를 통해 민감 query 값을 마스킹한다.
- `backend/app/core/config.py`
  - `REPORT_SCHEDULER_STARTUP_DELAY_SECONDS`를 추가했다. 기본값은 `180`초이며 음수는 0으로 보정한다.
- `backend/app/main.py`
  - `generate_daily_reports_startup` date job을 `datetime.now()` 즉시 실행에서 `datetime.now() + REPORT_SCHEDULER_STARTUP_DELAY_SECONDS`로 변경했다.
- `backend/tests/test_price_providers.py`
  - Finnhub quote는 성공하고 profile/Stooq history가 실패해도 stock snapshot이 현재가를 유지하는 테스트를 추가했다.
- `.env.example`
- `ENVIRONMENT_VARIABLE_SETUP.md`
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/feature-index.md`

## Behavior Changes

- `NVDA`, `AAPL` 같은 미국 주식은 Stooq history 또는 Finnhub profile이 일시 실패해도 Finnhub quote만 있으면 가격 캐시에 저장될 수 있다.
- 앱 시작 직후 1회성 startup report job은 기본 180초 지연되어 market warm-up과 provider queue가 먼저 실행될 시간을 확보한다.
- 이 변경은 user-facing request가 AI 리포트를 생성하게 만들지 않는다.
- 이 변경은 scheduler 빈도, coverage, cooldown, LLM 호출량을 늘리지 않는다.
- Stooq index/commodity timeout 자체를 해결하지는 않는다. 해당 자산군은 여전히 provider key/네트워크 상태와 scheduler refresh 성공에 의존한다.

## Recommended Render Env Follow-Up

배포 직후 안정화 중에는 다음 값이 보수적이다.

```dotenv
ENABLE_MARKET_WARMUP=true
ENABLE_SCHEDULER=true
ENABLE_AI_REPORT_GENERATION=true
REPORT_SCHEDULER_TARGET_TICKERS=NVDA
REPORT_SCHEDULER_MAX_REPORTS_PER_RUN=1
REPORT_SCHEDULER_INTERVAL_HOURS=12
REPORT_SCHEDULER_STARTUP_DELAY_SECONDS=180
REPORT_SCHEDULER_ASSET_COOLDOWN_HOURS=12
MARKET_PRICES_REFRESH_MINUTES=30
MARKET_NEWS_REFRESH_MINUTES=60
MARKET_PRICE_FETCH_TIMEOUT_SECONDS=55
```

확인 순서:

1. `/db-check`가 `db_connected`인지 확인한다.
2. Render logs에서 `NVDA 리포트 생성 완료` 또는 readiness/quality 실패 유형을 확인한다.
3. `GET /api/reports/NVDA`가 200이 되는지 확인한다.
4. 이후 target을 `NVDA,BTC-USD`처럼 1개씩 늘린다.

## Verification

- Added focused provider fallback test in `backend/tests/test_price_providers.py`.
- Verification command:
  - `..\backend\.venv\Scripts\python.exe -m pytest tests\test_price_providers.py` from `backend/`: 13 passed.
  - `.\backend\.venv\Scripts\python.exe -m compileall backend\app` from repository root: passed.
- Note: pytest emitted a cache warning because `.pytest_cache` could not be written in this sandboxed run; test collection and assertions completed successfully.

## Follow-Up Risks

- `FINNHUB_API_KEY`가 없거나 Finnhub quote 자체가 timeout되면 미국 주식 snapshot은 여전히 비어 있을 수 있다.
- `STOOQ_API_KEY`가 없거나 Stooq가 느리면 index/commodity history와 snapshot은 계속 비거나 timeout될 수 있다.
- startup report job과 background market warm-up의 race는 완전히 제거하지 않았다. 이번 변경은 ticker-level fallback이 더 잘 살아남게 하는 보완이다.
- 일반 사용자와 챗봇은 여전히 저장된 scheduled report만 읽어야 하며, 새 리포트 생성 트리거가 되어서는 안 된다.
