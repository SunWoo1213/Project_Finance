# Market Data Feature Notes

Date: 2026-05-30

## Current Behavior

Market data powers the home page, market snapshot route, category lists, asset detail header, chart history, latest-context panel, and news cache. The backend warms an in-memory cache on startup and refreshes broad price/news data on a scheduler instead of calling external providers for every user request.

Supported groups include major indices, US/Korean stocks, bonds, commodities, and crypto. Some ticker conventions are application-specific, such as `KTB_10Y` for Korean government bonds and `DGS10` for US Treasury yield data.

## Ownership Map

- App startup and public market endpoints: `backend/app/main.py`
- In-memory cache object: `backend/app/core/cache.py`
- Price/news collection and normalization: `backend/app/services/market_service.py`
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
3. APScheduler refreshes prices every 5 minutes and news every 1 hour when `ENABLE_SCHEDULER` is true. The default is true.
4. Scheduled AI report generation remains conservative by default: it iterates DB `Asset` rows only, respects a per-run cap, and does not seed every default market-cache ticker into the DB.
5. `GET /api/market/prices` returns the cached category object.
6. `GET /api/market/news` returns the cached news object.
7. The home page renders S&P 500, Nasdaq 100, USD/KRW, and KOSPI from the `macro` cache and lists cached global news below the market cards.
8. Main market cards route to `/market/:ticker`, which shows a 1-day time-based chart and a link to the related dashboard instead of the AI report/community detail flow.
9. `GET /api/market/latest-context/{ticker}` fetches ticker-specific news and calendar events with a short per-ticker TTL cache.
10. `GET /api/market/history/{ticker}?period=...` routes by ticker type:
   - Korean bonds use `fetch_kr_bond_history`.
   - US bonds use `fetch_us_bond_data`.
   - Commodities use `fetch_commodity_data`.
   - Other assets use yfinance history.
11. Frontend pages select the relevant group and normalize fallback fields such as `points`, `legacy`, `value`, `currentPrice`, and `changePercent`.
12. `CategoryView.jsx` and `AssetDetail.jsx` both use `getUiCategory` from `frontend/src/utils/assetCategories.js`, so Korean stocks, crypto, bonds, commodities, FX, and macro index tickers share the same display category rules.
13. Category lists let users favorite individual assets from the rightmost star button and open favorited assets through the right-side favorites panel.
14. The chatbot can summarize the existing `market_cache` and ticker latest-context data, using existing cache/TTL behavior rather than adding a new provider path.

## Contracts

- Price endpoint: `GET /api/market/prices`
- News endpoint: `GET /api/market/news`
- Latest context endpoint: `GET /api/market/latest-context/{ticker}?force_refresh=false`
- History endpoint: `GET /api/market/history/{ticker}`
- Optional runtime controls for local smoke checks: `ENABLE_MARKET_WARMUP=false`, `ENABLE_SCHEDULER=false`
- Optional report scheduler policy controls: `REPORT_SCHEDULER_COVERAGE=conservative`, `REPORT_SCHEDULER_MAX_REPORTS_PER_RUN=20`, `REPORT_SCHEDULER_ASSET_COOLDOWN_HOURS=24`
- Supported history periods: `1d`, `1mo`, `1y`, `5y`
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

## Open Risks

- Market routes still live in `backend/app/main.py`; growth may justify moving them to `backend/app/api/market.py`.
- Frontend API base URLs are hardcoded in several pages.
- External provider behavior can change without code changes.
- Full scheduled report coverage is intentionally not enabled; changing `REPORT_SCHEDULER_COVERAGE` away from `conservative` currently logs a warning and still avoids broad seeding because broader LLM/API usage needs product approval.
