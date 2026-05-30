# Main Market Snapshot And News

Date: 2026-05-30

## Objective

Make the home dashboard show the requested major assets and prevent those cards from opening the AI report/community detail page. Add a lighter market snapshot route for time-based movement and related dashboard navigation, and surface cached global market news on the home page.

## Files Changed

- `frontend/src/App.jsx`
- `frontend/src/pages/Home.jsx`
- `frontend/src/pages/MarketSnapshot.jsx`
- `frontend/src/pages/CategoryView.jsx`
- `frontend/src/pages/DEVELOPMENT_DIRECTION.md`
- `frontend/src/components/SparklineChart.jsx`
- `frontend/src/utils/constants.js`
- `frontend/src/utils/formatters.js`
- `docs/harness/feature-index.md`
- `docs/harness/features/market-data.md`
- `docs/harness/features/frontend-routing-shell.md`

## Behavior Changes

- The home market cards now target S&P 500, Nasdaq 100, USD/KRW, and KOSPI.
- Home market cards route to `/market/:ticker` instead of `/detail/:ticker`.
- `/market/:ticker` shows a 1-day time-based chart and a related dashboard link without AI report, comments, or latest-context panels.
- USD/KRW values use a won-prefixed FX formatter.
- The home page now renders a global news section from the existing cached `GET /api/market/news` data.
- `/category/macro` has an explicit route title for the USD/KRW dashboard link.

## Verification Performed

- `npm.cmd run build` passed. Vite reported the existing large chunk warning.
- `npm.cmd run lint` passed.
- Started the Vite dev server at `http://127.0.0.1:5173/`.
- HTTP checks returned 200 for `/`, `/market/%5ENDX`, and `/category/macro`.

## Commands Not Run And Why

- `npm run build` and `npm run lint` through PowerShell `npm.ps1` were blocked by the local execution policy, so `npm.cmd` was used instead.
- Browser automation with `agent-browser` was not run because the CLI was not available in PATH.
- Backend API smoke checks were not run because the backend server and PostgreSQL were not started for this frontend-focused change.

## Follow-Up Risks

- The home global news section currently relies on the existing yfinance-backed news cache, whose coverage can be sparse and inconsistent by ticker.
- A dedicated FX dashboard does not exist yet; USD/KRW links to the broader major index/FX category page.
- External news API selection is still a product decision because most richer free providers require an API key and have attribution/rate-limit constraints.

## Feature Docs

- `docs/harness/features/market-data.md`
- `docs/harness/features/frontend-routing-shell.md`
