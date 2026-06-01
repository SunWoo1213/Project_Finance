# Report Generation Schedule Alignment Plan

Date: 2026-06-01

## Objective

Verify whether AI reports are generated automatically on a deployment-time schedule and then reused by users and the chatbot, instead of being generated on each user request. The required target behavior is:

- Report generation is a backend background job only.
- After deployment starts, the backend keeps reports pre-generated on a 6-hour cadence.
- Users view the latest stored `AIReport`.
- The chatbot reads and summarizes the same stored `AIReport`.
- User-facing report views and chat messages must not call a report-generation endpoint.
- Any future verification, plan, or implementation that changes this flow must be documented under `docs/harness/` and linked from the relevant feature docs.

## Files Inspected

- `backend/app/main.py`
- `backend/app/services/ai_service.py`
- `backend/app/services/chat_service.py`
- `backend/app/core/config.py`
- `frontend/src/pages/AssetDetail.jsx`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/chatbot-assistant.md`
- `docs/harness/features/market-data.md`
- `docs/harness/feature-index.md`
- `docs/harness/feature-documentation-guide.md`

## Current Implementation Findings

The current implementation is only partially aligned with the target behavior.

### Aligned Areas

- FastAPI lifespan starts `AsyncIOScheduler` when `ENABLE_SCHEDULER` is true.
- The scheduler registers `generate_daily_reports` with an interval of `hours=6` in `backend/app/main.py`.
- `GET /api/reports/{ticker}` reads the latest stored `AIReport` by ticker and does not generate a report.
- The chatbot report path in `backend/app/services/chat_service.py` calls `_fetch_saved_report`, summarizes the stored report, and does not call `generate_report_for_ticker` or `POST /api/ai/generate/{ticker}`.

### Gaps Against Target Behavior

- `frontend/src/pages/AssetDetail.jsx` calls `POST /api/ai/generate/{ticker}` when `GET /api/reports/{ticker}` returns 404. That means an authenticated user's page visit can trigger new report generation.
- `POST /api/ai/generate/{ticker}` remains a user-authenticated manual generation endpoint in `backend/app/main.py`.
- `generate_daily_reports` only iterates existing DB `Asset` rows. It does not seed or cover every default market-cache ticker on deployment.
- `REPORT_SCHEDULER_ASSET_COOLDOWN_HOURS` defaults to `24`, so each asset is not regenerated every 6 hours even though the scheduler job wakes up every 6 hours.
- The scheduler job is interval-based, but there is no explicit startup catch-up run that guarantees reports are created immediately when deployment starts.

## Required Modification Plan

1. Define the report catalog that must be pre-generated.
   - Decide whether the scheduled job should cover all default market-cache tickers from `market_service.py`, only DB `Asset` rows, or a curated production list.
   - If all user-visible detail assets should have reports, create or reuse a deterministic seed list and ensure matching `Asset` rows exist before scheduled generation.

2. Make scheduled generation the only generation path.
   - Remove the frontend 404 fallback that calls `POST /api/ai/generate/{ticker}` from `AssetDetail.jsx`.
   - On 404, show a stored-report-unavailable state such as "scheduled report is not ready yet" without starting generation.
   - Consider disabling, removing, or admin-gating `POST /api/ai/generate/{ticker}` so ordinary authenticated users cannot trigger LLM-backed generation.

3. Align the scheduler cadence with the product rule.
   - Keep the scheduler interval at 6 hours.
   - Change the per-asset cooldown from 24 hours to 6 hours, or replace the cooldown logic with "one report per asset per scheduler window."
   - Add a clear setting name if needed, for example `REPORT_SCHEDULER_INTERVAL_HOURS=6`, so the interval and cooldown cannot drift silently.

4. Add deployment-start behavior.
   - Decide whether deployment should generate immediately on startup or only after the first 6-hour interval.
   - If immediate availability is required, trigger a bounded startup generation pass after market cache warm-up.
   - Preserve caps, rate-limit sleeps, and failure isolation so one ticker failure does not block the rest.

5. Preserve chatbot stored-report behavior.
   - Keep `_fetch_saved_report` as the chatbot's report data source.
   - Add or update tests proving chatbot report requests do not call generation.
   - If no stored report exists, return a clear "scheduled report not ready" answer and navigation action only.

6. Update tests and verification.
   - Backend tests should cover scheduler cooldown/cadence, no manual generation for public user paths, and stored-report fetch behavior.
   - Frontend verification should cover that opening a detail page only calls `GET /api/reports/{ticker}`, not `POST /api/ai/generate/{ticker}`.
   - Chatbot tests should cover stored-report summary and no generation call.

7. Keep documentation mandatory for this flow.
   - Any future work touching report generation, report viewing, chatbot report responses, scheduler frequency, report coverage, or manual generation must update the feature docs and add a `docs/harness/` change record or plan before code changes are considered complete.

## Suggested Implementation Files

- `frontend/src/pages/AssetDetail.jsx`
- `backend/app/main.py`
- `backend/app/services/ai_service.py`
- `backend/app/core/config.py`
- `backend/tests/test_ai_report_quality_gate.py` or a new scheduler-focused backend test file
- `backend/tests/test_chat_service.py`
- Relevant feature docs under `docs/harness/features/`

## Verification Performed

- Static code inspection with `rg`, `Get-Content`, and `Select-String`.
- No runtime tests were run because this task requested verification and a documentation plan, not implementation.
- No `.env` contents were inspected.

## Follow-Up Risks

- Broad scheduled coverage can increase LLM/API cost and should be explicitly approved before implementation.
- Generating reports on startup may slow deployment or make startup dependent on provider and LLM availability unless bounded carefully.
- Removing manual generation can expose empty report states until the scheduler successfully creates initial reports.
- The project currently does not have a formal migration workflow; report schema changes should remain separate from this scheduling correction unless required.

## Feature Docs

- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/chatbot-assistant.md`
- `docs/harness/features/market-data.md`

## Implementation Follow-Up

- Implemented in `docs/harness/report-generation-schedule-alignment-implementation-2026-06-01.md`.
- The implementation intentionally limits scheduled generation to `DGS10`, `XAU`, `BTC-USD`, `NVDA`, and `005930.KS` for API cost control.
