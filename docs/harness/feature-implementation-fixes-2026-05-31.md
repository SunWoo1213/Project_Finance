# Feature Implementation Fixes

Date: 2026-05-31

## Objective

Fix the low-risk gaps identified in `docs/harness/feature-implementation-verification-2026-05-31.md` while keeping automatic LLM/report scheduling scope unchanged.

## Files Changed

- `frontend/src/utils/assetCategories.js`
- `frontend/src/utils/formatters.js`
- `frontend/src/pages/CategoryView.jsx`
- `frontend/src/pages/AssetDetail.jsx`
- `backend/app/core/config.py`
- `backend/app/services/external_api_service.py`
- `backend/app/api/deps.py`
- `backend/app/main.py`
- `backend/requirements.txt`
- `backend/tests/test_market_history_route.py`
- `backend/tests/test_macro_service.py`
- `backend/tests/test_auth_deps.py`
- `docs/harness/latest-context-report-quality.md`
- `docs/harness/feature-index.md`
- `docs/harness/features/authentication.md`
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`

## Behavior Changes

- `CategoryView.jsx` and `AssetDetail.jsx` now share `getUiCategory`, so Korean stocks, crypto assets, bonds, commodities, FX, and KOSPI use the same display-category rules.
- Crypto prices now display as USD values through `formatPrice(..., "CRYPTO")`.
- `AssetDetail.jsx` uses `ReportCard.jsx` for authenticated report display, so bull and bear summaries appear alongside the final Markdown report.
- `Settings` now exposes optional `FMP_API_KEY` and `FINNHUB_API_KEY` fields. Missing keys still leave the providers optional and produce limitation metadata.
- JWTs with non-numeric `sub` claims now return the existing 401 credentials error instead of escaping as a server error.
- Korean bond history route tests now patch `fetch_kr_bond_history`, matching the current route implementation.
- A focused auth dependency test covers invalid JWT subject handling.
- Backend test dependencies now include `pytest` and `pytest-asyncio`, matching the repository's documented `pytest` verification workflow.
- The KR bond macro-service fixture now includes ECOS `TIME` fields, matching the current history parser contract.
- Backend lifespan now supports optional `ENABLE_MARKET_WARMUP=false` and `ENABLE_SCHEDULER=false` runtime controls for short local smoke checks. Defaults remain true, so normal startup behavior is unchanged.

## Verification Performed

- `py -m compileall backend\app backend\tests` passed.
- `npm.cmd run lint` from `frontend/` passed.
- `npm.cmd run build` from `frontend/` passed. Vite reported the existing large chunk warning.
- `backend\.venv\Scripts\python.exe -m ensurepip --upgrade` passed after approval because the existing backend venv did not include `pip`.
- `backend\.venv\Scripts\python.exe -m pip install pytest pytest-asyncio` passed after approval because the sandboxed attempt could not resolve packages.
- `backend\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\test_ai_report_quality_gate.py tests\test_macro_service.py tests\test_market_history_route.py tests\test_auth_deps.py` passed from `backend/`: 24 passed.
- Final repeat verification also passed: `py -m compileall backend\app backend\tests`, `backend\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\test_ai_report_quality_gate.py tests\test_macro_service.py tests\test_market_history_route.py tests\test_auth_deps.py`, `npm.cmd run lint`, and `npm.cmd run build`.
- `npm.cmd run dev -- --host 127.0.0.1` initially failed in the sandbox with Vite `spawn EPERM`, then started successfully after approval.
- `Invoke-WebRequest -Uri http://127.0.0.1:5173/ -UseBasicParsing` returned HTTP 200 while the Vite dev server was running.
- The Vite dev server was stopped after the smoke check.
- A normal backend server start was interrupted after it had already started; logs showed DB connection refusal was handled, market warm-up completed with provider failures, and the scheduler kept running until the process was stopped.
- `ENABLE_MARKET_WARMUP=false` and `ENABLE_SCHEDULER=false` backend smoke start completed quickly without market provider warm-up or scheduler startup.
- `Invoke-WebRequest -Uri http://127.0.0.1:8000/health -UseBasicParsing` returned HTTP 200 with `{"status":"ok","project":"AI Financial Intelligence"}` during the backend smoke check.
- The backend smoke server was stopped after the health check.

## Commands Not Run And Why

- Root-level `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_market_history_route.py backend\tests\test_auth_deps.py` was superseded by running pytest from `backend/`, where the `app` package import path resolves correctly.
- Browser automation was not run because no browser automation tool or local Playwright/Puppeteer package is currently available in this session.
- No live FMP, Finnhub, Google login, DB-backed scheduler, or LLM generation smoke tests were run to avoid external provider, secret, database, and token-cost dependencies.

## Follow-Up Risks

- Scheduled report generation still covers DB `Asset` rows only. Broadening it to every default market-cache ticker could increase LLM/API cost and needs explicit approval.
- Provider keys are optional and were documented by name only; `.env` values were not inspected.
- Report metadata is still not persisted as first-class DB fields because that would require a separate schema/migration decision.

## Feature Docs

- `docs/harness/features/authentication.md`
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/feature-implementation-fix-plan-2026-05-31.md` now points to this implementation record.
