# Feature Implementation Fix Plan

Date: 2026-05-31

## Objective

Record the follow-up plan derived from `docs/harness/feature-implementation-verification-2026-05-31.md`.

The goal is to prioritize fixes that match the product purpose: a full-stack finance application for global market data, authenticated AI investment reports, and community discussion. This document is a plan only; no runtime code changes were made while creating it.

## Implementation Status

The low-risk implementation items from this plan were completed in `docs/harness/feature-implementation-fixes-2026-05-31.md`. That follow-up record includes the actual files changed, verification commands, backend smoke-check flags, and remaining risks.

## Source

- Verification report: `docs/harness/feature-implementation-verification-2026-05-31.md`
- Feature index: `docs/harness/feature-index.md`
- Relevant feature docs:
  - `docs/harness/features/market-data.md`
  - `docs/harness/features/asset-detail-ai-community.md`
  - `docs/harness/features/authentication.md`

## Planned Fix Priority

### 1. Fix asset category detection on the asset detail page

Affected files:

- `frontend/src/pages/AssetDetail.jsx`
- `frontend/src/pages/CategoryView.jsx`
- Candidate shared utility: `frontend/src/utils/formatters.js` or a new focused utility under `frontend/src/utils/`

Reason:

`AssetDetail.jsx` currently treats every non-bond and non-commodity asset as `US_STOCK`. That can make Korean stocks, crypto assets, FX, and KOSPI display with the wrong price or market-cap formatting. Since the product is a global finance app, accurate asset-type presentation is core behavior.

Planned approach:

- Extract the `CategoryView.jsx` UI category mapping into a shared helper.
- Reuse the same helper from `AssetDetail.jsx`.
- Ensure these mappings are covered:
  - `kr_top10` -> `KR_STOCK`
  - `cryptos` -> `CRYPTO`
  - `bonds` -> `KR_BOND` for `KTB_*`, otherwise `US_BOND`
  - `commodities` -> `COMMODITY`
  - `macro` + `KRW=X` -> `FX`
  - `macro` + `^KS11` -> `KR_STOCK`
  - default -> `US_STOCK`
- Extend formatting only if `CRYPTO` needs a distinct display policy.

Verification:

- Run `npm run build` from `frontend/`.
- Run `npm run lint` from `frontend/` when feasible.
- Manually check category list and detail formatting for a US stock, Korean stock, crypto, `KRW=X`, and `^KS11`.

### 2. Add structured provider API keys to backend settings

Affected files:

- `backend/app/core/config.py`
- `backend/app/services/external_api_service.py`

Reason:

`external_api_service.py` reads `FMP_API_KEY` and `FINNHUB_API_KEY`, but `Settings` does not define those fields. Because this project loads environment values through Pydantic settings, keys that exist only in `.env` may not become available through `settings`.

Planned approach:

- Add optional settings fields:
  - `FMP_API_KEY: str | None = None`
  - `FINNHUB_API_KEY: str | None = None`
- Keep provider usage optional.
- Do not inspect or print `.env` values.
- Document the provider keys as optional report-quality inputs, not required runtime secrets.

Verification:

- Run `py -m compileall backend\app`.
- Prefer a narrow provider-loading check without printing secret values.
- Do not make live FMP or Finnhub calls unless explicitly requested.

### 3. Harden JWT subject parsing

Affected files:

- `backend/app/api/deps.py`

Reason:

`get_current_user` decodes the JWT and calls `int(user_id_str)`. A signed token with a non-numeric `sub` can raise `ValueError` and produce a 500 instead of a 401 authentication failure.

Planned approach:

- Wrap the `int(user_id_str)` conversion in `try/except (TypeError, ValueError)`.
- Raise the existing `credentials_exception` on invalid values.
- Preserve the current valid-token behavior.

Verification:

- Run `py -m compileall backend\app`.
- Add or run a focused auth dependency test if the current test harness allows it.

### 4. Align Korean bond history tests with the current implementation

Affected files:

- `backend/tests/test_market_history_route.py`
- Related implementation: `backend/app/main.py`

Reason:

The current route uses `fetch_kr_bond_history`, but the test monkeypatches `fetch_kr_bond_data`. Once `pytest` is available, this test may fail or fail to validate the actual Korean bond history branch.

Planned approach:

- Change the monkeypatch target to `main.fetch_kr_bond_history`.
- Return a `points`-style list from the fake service.
- Keep expectations aligned with the route response shape: `series_type`, `unit`, `points`, and `legacy`.

Verification:

- Run `pytest backend\tests\test_market_history_route.py` if `pytest` is installed.
- If `pytest` is unavailable, report the missing dependency and run compile checks.

### 5. Decide and implement the AI report display path

Affected files:

- `frontend/src/pages/AssetDetail.jsx`
- `frontend/src/components/ReportCard.jsx`
- `docs/harness/features/asset-detail-ai-community.md`

Reason:

The feature docs list `ReportCard.jsx` as report display support, but `AssetDetail.jsx` currently renders only `report.final_content` directly with `ReactMarkdown`. This creates a documentation and implementation mismatch.

Preferred approach:

- Use `ReportCard` from `AssetDetail.jsx` so bull and bear summaries appear with the final Markdown report.
- Keep the visual change focused and avoid broad UI restructuring.

Alternative:

- If the current single Markdown view is the intended final UI, update the docs to mark `ReportCard.jsx` as legacy or unused.

Verification:

- Run `npm run build` from `frontend/`.
- Run `npm run lint` from `frontend/` when feasible.
- Check authenticated report view and unauthenticated report fallback behavior.

### 6. Keep scheduled report generation scope conservative unless approved

Affected files if documenting only:

- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/market-data.md`

Affected files if behavior is changed later:

- `backend/app/services/ai_service.py`
- Potentially `backend/app/services/market_service.py`

Reason:

`generate_daily_reports()` currently generates reports only for assets already present in the DB. Expanding this to all default market-cache assets may increase LLM calls and cost.

Planned approach:

- First document the current constraint clearly: scheduled generation covers DB `Asset` rows, not every default market-cache ticker.
- Ask for explicit confirmation before broadening automatic report generation to all default assets.

Verification:

- Documentation-only change needs no runtime verification.
- Any behavior change must avoid real LLM calls in ordinary tests and use mocks or narrow service checks.

## Documentation Updates To Make With The Fixes

When the implementation fixes are made, update these documents in the same change:

- `docs/harness/latest-context-report-quality.md`
  - Replace the stale risk that says `POST /api/ai/generate/{ticker}` is unauthenticated.
  - Note that later auth work protects report generation.
- `docs/harness/feature-index.md`
  - Add missing AI report quality records to the Asset detail change-record list:
    - `docs/harness/report-quality-phase-1.md`
    - `docs/harness/report-quality-phase-2.md`
    - `docs/harness/report-quality-fact-checker.md`
- `docs/harness/features/market-data.md`
  - Reflect the shared UI category mapping if implemented.
- `docs/harness/features/asset-detail-ai-community.md`
  - Reflect the chosen `ReportCard` or Markdown-only report display path.
  - Clarify scheduled report generation scope if not broadened.
- Add a new implementation change record for the actual code fixes.

## Verification Plan For The Full Fix Set

Backend:

```powershell
py -m compileall backend\app backend\tests
```

Run focused tests if dependencies are available:

```powershell
pytest backend\tests\test_market_history_route.py
```

Frontend:

```powershell
cd frontend
npm run lint
npm run build
```

Do not run these by default without explicit intent:

- Real LLM-backed report generation
- Live Google login
- Live FMP/Finnhub provider calls
- Scheduler changes that broaden automatic report generation

## Follow-Up Risks

- `pytest` may not be installed in the current backend virtual environment.
- Some verification requires running services, configured secrets, or external provider availability.
- Expanding scheduled AI report generation can materially increase token/API cost.
- Report metadata is still generated but not fully persisted as first-class DB fields; schema changes would need separate migration planning.

## Files Changed By This Planning Step

- `docs/harness/feature-implementation-fix-plan-2026-05-31.md`

## Verification Performed For This Planning Step

- Read `docs/harness/feature-implementation-verification-2026-05-31.md`.
- Read `docs/harness/feature-index.md`.
- Read `docs/harness/feature-documentation-guide.md`.
- Checked `git status --short` before writing.

No runtime tests were run because this step only records a follow-up implementation plan.
