# Market Data Feature Notes

Date: 2026-05-30

## Current Behavior

Market data powers the home page, market snapshot route, category lists, asset detail header, chart history, latest-context panel, and news cache. The backend warms an in-memory cache on startup and refreshes broad price/news data on a scheduler instead of calling external providers for every user request.

Supported groups include major indices, US/Korean stocks, bonds, commodities, and crypto. Some ticker conventions are application-specific, such as `KTB_10Y` for Korean government bonds and `DGS10` for US Treasury yield data.

## Ownership Map

- App startup and public market endpoints: `backend/app/main.py`
- In-memory cache object: `backend/app/core/cache.py`
- Price/news collection and normalization: `backend/app/services/market_service.py`
- Free market provider routing, symbol mapping, history/news normalization, provider cache/cooldown: `backend/app/services/price_providers.py`
- Bond and commodity macro data: `backend/app/services/macro_service.py`
- Home page: `frontend/src/pages/Home.jsx`
- Main market snapshot page: `frontend/src/pages/MarketSnapshot.jsx`
- Category list: `frontend/src/pages/CategoryView.jsx`
- Detail chart and market summary: `frontend/src/pages/AssetDetail.jsx`
- Shared frontend asset-type mapping: `frontend/src/utils/assetCategories.js`
- Asset display names: `frontend/src/utils/constants.js`
- Price/yield formatting: `frontend/src/utils/formatters.js`
- Chatbot market explanation helpers: `backend/app/services/chat_service.py`, `backend/app/services/chat_tools.py`

## Data Flow

1. FastAPI lifespan initializes DB tables and warms price/news caches.
2. FastAPI lifespan warms price/news caches when `ENABLE_MARKET_WARMUP` is true. The default is true. The warm-up runs as a non-blocking background task (`asyncio.create_task`), so the server binds its port and passes health checks immediately while the in-memory cache fills in shortly after. Each asset/news fetch is bounded by a per-asset timeout (`MARKET_PRICE_FETCH_TIMEOUT_SECONDS` / `MARKET_NEWS_FETCH_TIMEOUT_SECONDS`) so a slow asset cannot block its group; timed-out assets are logged as `failed: timeout after Ns` and skipped. Most provider requests are serialized one-at-a-time per provider via `_provider_semaphore` (`Semaphore(1)`); `data_go_kr` is the exception and uses `DATA_GO_KR_MAX_CONCURRENCY` (default 2) because its calls are slow. The KR stock snapshot makes two data.go.kr calls (current-price row + history), so `MARKET_PRICE_FETCH_TIMEOUT_SECONDS` (default 55) is kept above `2 * DATA_GO_KR_FETCH_TIMEOUT_SECONDS` (default 25). data.go.kr snapshot queries are bounded to a recent date window (`_recent_basdt_window`); a date-less `getStockPriceInfo` query is slow. Provider failures are logged with `repr` so empty-message exceptions (e.g. `ReadTimeout('')`) reveal their class.
3. APScheduler refreshes prices and news when `ENABLE_SCHEDULER` is true (default true). The cadence is configurable in minutes via `MARKET_PRICES_REFRESH_MINUTES` (default 5) and `MARKET_NEWS_REFRESH_MINUTES` (default 60); both are clamped to a minimum of 1.
4. Scheduled AI report generation remains cost-controlled by default: it seeds and iterates only the representative report target list (`DGS10`, `XAU`, `BTC-USD`, `NVDA`, `005930.KS`), respects a per-run cap of 5, and runs on a 6-hour interval/cooldown.
5. `GET /api/market/prices` returns the cached category object.
6. `GET /api/market/news` returns the cached news object.
7. The home page renders S&P 500, Nasdaq 100, USD/KRW, and KOSPI from the `macro` cache and lists cached global news below the market cards.
8. Main market cards route to `/market/:ticker`, which shows provider-dated daily history and a link to the related dashboard instead of the AI report/community detail flow.
9. `GET /api/market/latest-context/{ticker}` fetches ticker-specific news and calendar events with a short per-ticker TTL cache. The TTL is configurable in minutes via `MARKET_LATEST_CONTEXT_TTL_MINUTES` (default 10, minimum 1); `_latest_context_ttl_seconds()` in `market_service.py` reads it at call time. `force_refresh=true` still respects a 5-minute minimum cooldown.
10. `GET /api/market/history/{ticker}?period=...` routes by ticker type:
   - Korean bonds use `fetch_kr_bond_history`.
   - US bonds use `fetch_us_bond_history` so FRED observation dates are preserved.
   - US stocks fetch the primary quote from Finnhub and use FMP EOD history/profile as optional support. Finnhub profile, FMP profile, FMP history, or opt-in Stooq fallback failures do not discard a successful Finnhub quote; market cap degrades to `0.0` and history falls back to the current price.
   - US indices and commodities use FMP quote/EOD history first. FMP responses are cached with a 12-hour TTL and guarded by a process-local daily call budget so the 5-minute scheduler does not burn through the free plan. If FMP is missing, over budget, or unavailable, they degrade to empty data unless `ENABLE_STOOQ_FALLBACK=true` provides a Stooq fallback.
   - Crypto uses CoinGecko Demo API.
   - Korean stocks and Korean indices use 공공데이터포털 금융위원회 stock/index price APIs. The index API matches `idxNm` by the Korean index name (`코스피`/`코스닥`); the English forms return empty results.
   - USD/KRW (`KRW=X`) uses open.er-api.com daily reference rate by default. Because the free public path does not provide a reliable previous close, snapshot `changePercent=0`, history falls back to a single provider-dated point, and `provider_meta.change_source=none`. Only `ENABLE_STOOQ_FALLBACK=true` allows Stooq daily `usdkrw` closes as opt-in fallback for change/history.
   - Stooq history calls are disabled by default. When `ENABLE_STOOQ_FALLBACK=true`, they use `STOOQ_FETCH_TIMEOUT_SECONDS` (default 12 seconds) and stale Stooq cache can be reused after refresh failure.
11. Frontend pages select the relevant group and normalize fallback fields such as `points`, `legacy`, `value`, `currentPrice`, and `changePercent`.
12. `CategoryView.jsx` and `AssetDetail.jsx` both use `getUiCategory` from `frontend/src/utils/assetCategories.js`, so Korean stocks, crypto, bonds, commodities, FX, and macro index tickers share the same display category rules.
13. Category lists let users favorite individual assets from the rightmost star button and open favorited assets through the right-side favorites panel.
14. The chatbot can summarize the existing `market_cache` and ticker latest-context data, using existing cache/TTL/cooldown behavior rather than adding a fresh report generation path.
15. Favorite asset notifications evaluate cached price/news data only. The evaluator does not call external market providers directly and does not generate AI reports.
16. Frontend market pages use the shared API client, so hosted API origin is controlled by `VITE_API_BASE_URL` instead of page-level localhost literals.
17. Scheduled AI report generation can request a ticker-level price cache fill through `ensure_price_cache_for_ticker()` when the startup report job beats the non-blocking market warm-up. This only fills the configured report target ticker and keeps the public market cache shape unchanged.

## Contracts

- Price endpoint: `GET /api/market/prices`
- News endpoint: `GET /api/market/news`
- Latest context endpoint: `GET /api/market/latest-context/{ticker}?force_refresh=false`
- History endpoint: `GET /api/market/history/{ticker}`
- Optional runtime controls for local smoke checks: `ENABLE_MARKET_WARMUP=false`, `ENABLE_SCHEDULER=false`
- Market data refresh cadence controls (minutes, report-independent): `MARKET_PRICES_REFRESH_MINUTES=5`, `MARKET_NEWS_REFRESH_MINUTES=60`, `MARKET_LATEST_CONTEXT_TTL_MINUTES=10`. Values are clamped to a minimum of 1 and loaded at process start (restart required after change).
- Per-asset fetch timeout controls (seconds, report-independent): `MARKET_PRICE_FETCH_TIMEOUT_SECONDS=55`, `MARKET_NEWS_FETCH_TIMEOUT_SECONDS=20`. Values are clamped to a minimum of 5 and loaded at process start. These bound each asset/news collection so a serialized provider queue can drain within one run. The price timeout default must stay above `2 * DATA_GO_KR_FETCH_TIMEOUT_SECONDS` because the KR stock snapshot makes two data.go.kr calls.
- data.go.kr (KR stock/index) provider tuning (report-independent): `DATA_GO_KR_FETCH_TIMEOUT_SECONDS=25` (per-call httpx timeout; data.go.kr can spike to ~20s), `DATA_GO_KR_MAX_CONCURRENCY=2` (provider semaphore size; default conservative because data.go.kr rate-limits with a `허용되지 않는 요청` gateway block under load — raise to 3 via env only if the deployment tolerates it). Both clamped (timeout min 5, concurrency min 1) and loaded at process start.
- FMP provider tuning (report-independent): `FMP_FETCH_TIMEOUT_SECONDS=10` (minimum 5), `FMP_DAILY_CALL_BUDGET=180` (minimum 0). FMP targets use 12-hour internal cache, 30-minute failed-call cooldown, `Semaphore(1)`, and `provider_meta.freshness=eod_or_delayed`.
- Stooq provider tuning (report-independent): `ENABLE_STOOQ_FALLBACK=false`, `STOOQ_FETCH_TIMEOUT_SECONDS=12` (minimum 5). Stooq is compatibility fallback only; do not enable it broadly on deployments where Stooq `ConnectTimeout('')` repeats.
- Market provider keys: `FMP_API_KEY` for US index/commodity/US stock EOD history/profile support, `FINNHUB_API_KEY` for US stock quote/news/events, `COINGECKO_DEMO_API_KEY` for crypto price/history, `DATA_GO_KR_API_KEY` for Korean stock/index price APIs, and optional `STOOQ_API_KEY` for explicit fallback only.
- USD/KRW uses open.er-api.com open access data as daily reference FX. It is not treated as realtime trading-grade FX, and ordinary user-facing requests do not trigger fresh report generation.
- Hosted deployment startup should keep `ENABLE_MARKET_WARMUP=false` and `ENABLE_SCHEDULER=false` for the first smoke release, then enable runtime jobs after API/DB checks and cost review.
- Optional report scheduler policy controls: `REPORT_SCHEDULER_COVERAGE=conservative`, `REPORT_SCHEDULER_INTERVAL_HOURS=6`, `REPORT_SCHEDULER_STARTUP_DELAY_SECONDS=180`, `REPORT_SCHEDULER_MAX_REPORTS_PER_RUN=5`, `REPORT_SCHEDULER_ASSET_COOLDOWN_HOURS=6`, `REPORT_SCHEDULER_TARGET_TICKERS=DGS10,XAU,BTC-USD,NVDA,005930.KS`
- Target report schedule rule: report generation is backend-scheduled every 6 hours and user/chatbot paths read stored reports only. The 2026-06-01 implementation limits scheduled coverage to five representative assets for API cost control; see `docs/harness/report-generation-schedule-alignment-implementation-2026-06-01.md`.
- Supported history periods: `1d`, `1mo`, `1y`, `5y`. Free-provider replacement paths return provider-dated daily points for all periods; `1d` is 7 daily points, `1mo` is 30 daily points, `1y` is 365 daily points, and `5y` is 1825 daily points. `1d` is no longer a 5-minute intraday chart.
- Main market snapshot route: `/market/:ticker`
- Chat market guidance endpoint: `POST /api/chat/message`
- Preferred history shape:
  - `ticker`
  - `series_type`
  - `unit`
  - `points: [{ date, value }]`
  - `legacy` compatibility array
  - optional `provider_meta`

## Change Rules

- Keep ticker meaning aligned across backend service lists, DB `Asset` rows, `AssetCategory`, frontend route params, and `ASSET_NAMES`.
- Do not make user requests call slow external providers directly if cache-backed behavior is expected.
- Keep latest-context requests TTL-cached so asset-detail clicks do not hammer free providers.
- Treat empty provider responses, holidays, rate limits, and missing history as normal edge cases.
- Scheduler frequency changes can affect API cost and rate limits; ask for confirmation before increasing frequency materially.
- Report generation schedule, coverage, or cooldown changes must be documented in `docs/harness/` and linked from the affected feature docs.

## Verification

- Backend route/service checks should cover the changed provider path.
- If frontend display changes, run `npm run build` from `frontend/` when feasible.
- For ticker additions, manually check home/category/detail navigation for the new asset group.

## Change Records

- `docs/harness/harness-feature-documentation.md`
- `docs/harness/latest-context-report-quality.md`
- `docs/harness/main-market-snapshot-and-news.md`
- `docs/harness/asset-favorites.md`
- `docs/harness/feature-implementation-fixes-2026-05-31.md`
- `docs/harness/feature-implementation-fixes-verification-2026-05-31.md`
- `docs/harness/report-quality-follow-up-implementation-2026-05-31.md`
- `docs/harness/chatbot-feature-implementation-2026-05-31.md`
- `docs/harness/report-generation-schedule-alignment-plan-2026-06-01.md`
- `docs/harness/report-generation-schedule-alignment-implementation-2026-06-01.md`
- `docs/harness/report-writing-method-implementation-plan-2026-06-01.md`
- `docs/harness/report-writing-method-implementation-2026-06-01.md`
- `docs/harness/vercel-supabase-deployment-implementation-2026-06-01.md`
- `docs/harness/favorite-asset-notification-implementation-2026-06-02.md`
- `docs/harness/project-gap-remediation-plan-2026-06-02.md`
- `docs/harness/project-gap-remediation-phase0-1-implementation-2026-06-02.md`
- `docs/harness/project-defect-remediation-plan-2026-06-02.md`
- `docs/harness/report-scheduler-structured-output-error-fix-2026-06-02.md`
- `docs/harness/market-data-refresh-cadence-env-switch-2026-06-03.md`
- `docs/harness/market-data-provider-migration-plan-2026-06-03.md`
- `docs/harness/market-data-provider-migration-implementation-2026-06-03.md`
- `docs/harness/market-data-provider-response-format-audit-plan-2026-06-03.md`
- `docs/harness/market-data-warmup-provider-throttle-timeout-plan-2026-06-03.md`
- `docs/harness/market-data-warmup-provider-throttle-timeout-implementation-2026-06-04.md`
- `docs/harness/market-data-kr-data-go-index-name-throttle-fix-2026-06-04.md`
- `docs/harness/report-scheduler-market-cache-miss-fallback-2026-06-04.md`
- `docs/harness/fx-change-percent-from-stooq-2026-06-04.md`
- `docs/harness/render-standard-market-provider-timeout-remediation-2026-06-07.md`
- `docs/harness/stooq-timeout-fallback-2026-06-07.md`
- `docs/harness/market-data-free-plan-stooq-replacement-plan-2026-06-07.md`
- `docs/harness/market-data-free-plan-stooq-replacement-implementation-2026-06-07.md`
- `docs/harness/demo-free-tier-data-cadence-plan-2026-06-08.md`
- `docs/harness/data-io-pipeline-remediation-plan-2026-06-08.md`
- `docs/harness/data-io-pipeline-remediation-implementation-2026-06-08.md`
- `docs/harness/report-generation-scheduler-not-firing-log-audit-2026-06-08.md`
- `docs/harness/market-snapshot-price-fallback-and-stale-retention-implementation-2026-06-08.md`
- `docs/harness/asset-display-graph-removal-plan-2026-06-08.md`

## Open Risks

- Market routes still live in `backend/app/main.py`; growth may justify moving them to `backend/app/api/market.py`.
- Data I/O remediation on 2026-06-08 fixed open.er-api.com RFC date parsing, data.go.kr serviceKey decoding/history row ordering, `period=1d` point-count policy, US bond provider-date preservation, and history `provider_meta` passthrough. Broader provider failure/cooldown tests and real-key smoke remain.
- STOCK_US 현재가 폴백(Finnhub→FMP→Stooq 종가)과 스냅샷 stale 유지가 2026-06-08 구현됨(`market-snapshot-price-fallback-and-stale-retention-implementation-2026-06-08.md`). 다만 **콜드 스타트에서 직전 유효 스냅샷이 한 번도 없고 모든 provider가 실패하면** 여전히 가격 0이 될 수 있어, 최초 1회 provider 성공과 키/플랜 점검은 필요하다.
- New market page API calls should continue to use `frontend/src/utils/apiClient.js`; avoid reintroducing page-level API origin literals.
- External provider behavior can change without code changes.
- Free provider constraints remain: FMP Basic is EOD/delayed and limited by daily quota/licensing, Stooq daily CSV is opt-in fallback only, open.er-api.com is daily reference FX with attribution requirements, 공공데이터포털 data can be T+1 despite realtime metadata, and Naver Finance News is a non-contractual page-based source.
- Follow-up audit items remain for provider response format hardening: open.er-api.com RFC date parsing, 공공데이터포털 serviceKey encoding/row ordering, `period=1d` point-count policy, US bond provider-date preservation, and broader provider failure/cooldown tests. See `docs/harness/market-data-provider-response-format-audit-plan-2026-06-03.md`.
- Missing provider keys intentionally degrade affected asset classes to empty snapshots/history/news instead of retrying aggressively.
- Most provider requests are serialized per provider (`Semaphore(1)`). When many assets share one provider (e.g. `fmp` for US EOD history, `naver_news`), the queue can be slow; assets that exceed the per-asset timeout are skipped for that run. Raising concurrency for those is deferred because it risks free-tier rate limits / IP blocks on FMP, optional Stooq fallback, and Naver. See `docs/harness/market-data-warmup-provider-throttle-timeout-plan-2026-06-03.md`.
- `data_go_kr` uses `DATA_GO_KR_MAX_CONCURRENCY` (default 2) rather than `Semaphore(1)`. data.go.kr `getStockPriceInfo` can spike to ~20s and the snapshot makes two calls; the concurrency bump + date-window queries + longer internal timeout (`DATA_GO_KR_FETCH_TIMEOUT_SECONDS`) let the KR queue drain across cycles. data.go.kr rate-limits aggressively and returns a `오류발생 알림화면(허용되지 않는 요청)` 404 HTML gateway block under load; the code degrades to DEFAULT + cooldown, but raising concurrency too high increases block frequency. The `getStockMarketIndex` endpoint is slower/flakier than the stock endpoint and may intermittently 404. Use `backend/scripts/probe_data_go.py` to classify data.go.kr reachability. See `docs/harness/market-data-kr-data-go-index-name-throttle-fix-2026-06-04.md`.
- Full scheduled report coverage is intentionally not enabled; changing `REPORT_SCHEDULER_COVERAGE` away from `conservative` currently logs a warning and still avoids broad seeding because broader LLM/API usage needs product approval.
- The report scheduler now wakes every 6 hours and uses a 6-hour per-asset cooldown, but coverage is limited to the configured representative ticker list.
- Startup report jobs are delayed by `REPORT_SCHEDULER_STARTUP_DELAY_SECONDS` so broad market warm-up and provider queues can begin first. `ensure_price_cache_for_ticker()` still fills a single report target on cache miss, and US stock snapshots keep successful Finnhub quotes when optional profile/Stooq history calls fail. Provider key absence or primary quote outage still degrades to empty data/readiness block.
