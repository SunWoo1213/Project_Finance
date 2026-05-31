# Report Quality Phase 1

Date: 2026-05-30

## Objective

Implement the first safety and quality-gate steps from `docs/harness/report-quality-improvement-plan.md` without requiring a database schema migration.

## Files Changed

- `backend/app/main.py`
- `backend/app/services/ai_service.py`
- `backend/app/services/graph/state.py`
- `backend/app/services/graph/nodes.py`
- `backend/tests/test_ai_report_quality_gate.py`
- `frontend/src/pages/AssetDetail.jsx`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/report-quality-improvement-plan.md`

## Behavior Changes

- `POST /api/ai/generate/{ticker}` now requires an authenticated user.
- Manual report generation currently allows any authenticated app user; this is the explicit first authorization policy until user roles/admin flags exist.
- `AssetDetail.jsx` sends the bearer token when it triggers report generation after a missing-report response.
- The report service now builds normalized report facts before invoking the graph, including price source context, data timestamps, latest-context source status, news URLs, event data, and data limitations.
- The synthesizer and writer prompts now receive structured facts and a stable Korean Markdown report template.
- Evaluator failure after the revision loop raises a quality failure before any `AIReport` is saved.
- Successful generation responses expose metadata: `is_pass`, `feedback`, `revision_count`, `generated_at`, `data_as_of`, `source_status`, and `risk_summary`.
- Saved `bull_summary` and `bear_summary` are now derived from structured bull and bear factors rather than using the full draft and a fixed placeholder.

## Verification Performed

- `py -m compileall backend\app` passed.
- `py -m compileall backend\app backend\tests` passed.
- `npm.cmd run lint` passed.
- `npm.cmd run build` passed. Vite reported the existing large chunk warning.

## Commands Not Run And Why

- `pytest backend\tests\test_ai_report_quality_gate.py` could not run because `pytest` is not available on PATH.
- `py -m pytest backend\tests\test_ai_report_quality_gate.py` could not run because the active Python environment does not have the `pytest` module installed.
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_ai_report_quality_gate.py` could not run because the project virtualenv also does not have the `pytest` module installed.
- No live LLM generation was run, to avoid real OpenAI calls and costs during ordinary verification.

## Follow-Up Risks

- Rich generation metadata is not persisted yet because adding `ai_reports` fields requires a migration strategy.
- The authorization policy is authenticated-only, not admin-only, because the current user model has no role or permission field.
- The evaluator still uses the same configured LLM family as the writer. A stronger independent evaluator remains a later phase.
- Structured facts now exist before writing, but the graph is not yet fully redesigned into separate Bull, Bear, Risk, and Fact Checker nodes.

## Feature Docs

- `docs/harness/features/asset-detail-ai-community.md`
