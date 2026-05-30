# Latest Context And Report Quality

Date: 2026-05-30

## Objective

Improve report freshness without turning every asset-detail click into a new LLM generation. Add a ticker-level latest news/calendar context path and feed that context into report generation.

## Files Changed

- `backend/app/core/cache.py`
- `backend/app/main.py`
- `backend/app/services/market_service.py`
- `backend/app/services/ai_service.py`
- `backend/app/services/graph/state.py`
- `backend/app/services/graph/nodes.py`
- `backend/app/services/graph/graph.py`
- `frontend/src/pages/AssetDetail.jsx`
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`

## Behavior Changes

- Added `GET /api/market/latest-context/{ticker}` with a per-ticker TTL cache.
- Asset detail pages now load and display recent ticker-specific news plus yfinance calendar events.
- AI report generation now merges broad cached news with latest-context news before invoking LangGraph.
- Report writer prompts now ask for data 기준 시각, recent news/announcement highlights, and data limitations.
- Fixed LangGraph category checks to use the actual `AssetCategory.name` values such as `STOCK_US`, `BOND_US`, and `BOND_KR`.
- Fixed evaluator routing to stop on the structured `is_pass` flag instead of searching for `PASS` text in feedback.

## Verification Performed

- `py -m compileall backend\app` passed.
- `npm.cmd run build` passed. Vite reported the existing large chunk warning.
- `npm.cmd run lint` was run; it failed on the existing `frontend/tailwind.config.js` `require` / `no-undef` ESLint configuration issue. `AssetDetail.jsx` hook warnings were cleared.

## Commands Not Run And Why

- No LLM-backed report generation was run, to avoid real OpenAI calls during ordinary verification.
- No live latest-context external API smoke test was run, because provider availability/rate limits should be checked deliberately against the running app.

## Follow-Up Risks

- yfinance latest news/calendar coverage can be sparse for Korean stocks, bonds, commodities, and macro tickers.
- `POST /api/ai/generate/{ticker}` is still unauthenticated and should be protected before production use.
- Latest context freshness is provider-limited; UI should continue to present it as provider context, not guaranteed real-time market news.

## Feature Docs

- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`
