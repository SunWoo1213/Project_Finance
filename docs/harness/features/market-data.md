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
2. FastAPI lifespan warms price/news caches when `ENABLE_MARKET_WARMUP` is true. The default is true.
3. APScheduler refreshes prices and news when `ENABLE_SCHEDULER` is true (default true). The cadence is configurable in minutes via `MARKET_PRICES_REFRESH_MINUTES` (default 5) and `MARKET_NEWS_REFRESH_MINUTES` (default 60); both are clamped to a minimum of 1.
4. Scheduled AI report generation remains cost-controlled by default: it seeds and iterates only the representative report target list (`DGS10`, `XAU`, `BTC-USD`, `NVDA`, `005930.KS`), respects a per-run cap of 5, and runs on a 6-hour interval/cooldown.
5. `GET /api/market/prices` returns the cached category object.
6. `GET /api/market/news` returns the cached news object.
7. The home page renders S&P 500, Nasdaq 100, USD/KRW, and KOSPI from the `macro` cache and lists cached global news below the market cards.
8. Main market cards route to `/market/:ticker`, which shows provider-dated daily history and a link to the related dashboard instead of the AI report/community detail flow.
9. `GET /api/market/latest-context/{ticker}` fetches ticker-specific news and calendar events with a short per-ticker TTL cache. The TTL is configurable in minutes via `MARKET_LATEST_CONTEXT_TTL_MINUTES` (default 10, minimum 1); `_latest_context_ttl_seconds()` in `market_service.py` reads it at call time. `force_refresh=true` still respects a 5-minute minimum cooldown.
10. `GET /api/market/history/{ticker}?period=...` routes by ticker type:
   - Korean bonds use `fetch_kr_bond_history`.
   - US bonds use `fetch_us_bond_data`.
   - US stocks, US indices, and commodities use Stooq daily CSV only when `STOOQ_API_KEY` is configured; otherwise they degrade to empty daily history.
   - Crypto uses CoinGecko Demo API.
   - Korean stocks and Korean indices use 공공데이터포털 금융위원회 stock/index price APIs.
   - USD/KRW uses open.er-api.com as daily reference FX and returns a single provider-dated point when no historical provider is configured.
11. Frontend pages select the relevant group and normalize fallback fields such as `points`, `legacy`, `value`, `currentPrice`, and `changePercent`.
12. `CategoryView.jsx` and `AssetDetail.jsx` both use `getUiCategory` from `frontend/src/utils/assetCategories.js`, so Korean stocks, crypto, bonds, commodities, FX, and macro index tickers share the same display category rules.
13. Category lists let users favorite individual assets from the rightmost star button and open favorited assets through the right-side favorites panel.
14. The chatbot can summarize the existing `market_cache` and ticker latest-context data, using existing cache/TTL/cooldown behavior rather than adding a fresh report generation path.
15. Favorite asset notifications evaluate cached price/news data only. The evaluator does not call external market providers directly and does not generate AI reports.
16. Frontend market pages use the shared API client, so hosted API origin is controlled by `VITE_API_BASE_URL` instead of page-level localhost literals.

## Contracts

- Price endpoint: `GET /api/market/prices`
- News endpoint: `GET /api/market/news`
- Latest context endpoint: `GET /api/market/latest-context/{ticker}?force_refresh=false`
- History endpoint: `GET /api/market/history/{ticker}`
- Optional runtime controls for local smoke checks: `ENABLE_MARKET_WARMUP=false`, `ENABLE_SCHEDULER=false`
- Market data refresh cadence controls (minutes, report-independent): `MARKET_PRICES_REFRESH_MINUTES=5`, `MARKET_NEWS_REFRESH_MINUTES=60`, `MARKET_LATEST_CONTEXT_TTL_MINUTES=10`. Values are clamped to a minimum of 1 and loaded at process start (restart required after change).
- Market provider keys: `FINNHUB_API_KEY` for US stock quote/news/events, `COINGECKO_DEMO_API_KEY` for crypto price/history, `DATA_GO_KR_API_KEY` for Korean stock/index price APIs, and optional `STOOQ_API_KEY` for US stock/index/commodity daily CSV history.
- USD/KRW uses open.er-api.com open access data as daily reference FX. It is not treated as realtime trading-grade FX.
- Hosted deployment startup should keep `ENABLE_MARKET_WARMUP=false` and `ENABLE_SCHEDULER=false` for the first smoke release, then enable runtime jobs after API/DB checks and cost review.
- Optional report scheduler policy controls: `REPORT_SCHEDULER_COVERAGE=conservative`, `REPORT_SCHEDULER_INTERVAL_HOURS=6`, `REPORT_SCHEDULER_MAX_REPORTS_PER_RUN=5`, `REPORT_SCHEDULER_ASSET_COOLDOWN_HOURS=6`, `REPORT_SCHEDULER_TARGET_TICKERS=DGS10,XAU,BTC-USD,NVDA,005930.KS`
- Target report schedule rule: report generation is backend-scheduled every 6 hours and user/chatbot paths read stored reports only. The 2026-06-01 implementation limits scheduled coverage to five representative assets for API cost control; see `docs/harness/report-generation-schedule-alignment-implementation-2026-06-01.md`.
- Supported history periods: `1d`, `1mo`, `1y`, `5y`. Free-provider replacement paths return provider-dated daily points for all periods; `1d` is no longer a 5-minute intraday chart.
- Main market snapshot route: `/market/:ticker`
- Chat market guidance endpoint: `POST /api/chat/message`
- Preferred history shape:
  - `ticker`
  - `series_type`
  - `unit`
  - `points: [{ date, value }]`
  - `legacy` compatibility array

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

## Open Risks

- Market routes still live in `backend/app/main.py`; growth may justify moving them to `backend/app/api/market.py`.
- New market page API calls should continue to use `frontend/src/utils/apiClient.js`; avoid reintroducing page-level API origin literals.
- External provider behavior can change without code changes.
- Free provider constraints remain: Stooq daily CSV currently requires `STOOQ_API_KEY`, open.er-api.com is daily reference FX with attribution requirements, 공공데이터포털 data can be T+1 despite realtime metadata, and Naver Finance News is a non-contractual page-based source.
- Missing provider keys intentionally degrade affected asset classes to empty snapshots/history/news instead of retrying aggressively.
- Full scheduled report coverage is intentionally not enabled; changing `REPORT_SCHEDULER_COVERAGE` away from `conservative` currently logs a warning and still avoids broad seeding because broader LLM/API usage needs product approval.
- The report scheduler now wakes every 6 hours and uses a 6-hour per-asset cooldown, but coverage is limited to the configured representative ticker list.
