# Report Quality Follow-Up Implementation

Date: 2026-05-31

## Objective

Implement the remaining items from `docs/harness/report-quality-follow-up-plan-2026-05-31.md` without running verification commands.

## Files Changed

- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/app/main.py`
- `backend/app/core/config.py`
- `backend/app/services/ai_service.py`
- `backend/app/services/graph/state.py`
- `backend/app/services/graph/graph.py`
- `backend/app/services/graph/nodes.py`
- `backend/tests/test_ai_report_quality_gate.py`
- `frontend/src/components/ReportCard.jsx`
- `frontend/src/pages/AssetDetail.jsx`
- `.env_example`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/market-data.md`
- `docs/harness/feature-index.md`

## Behavior Changes

- Passing reports now persist quality/source metadata on `AIReport` through scalar columns plus `metadata_json`.
- FastAPI lifespan attempts startup-time `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` for the report metadata columns because this repo does not yet have a standalone migration workflow.
- Existing report fetches now return persisted `metadata`, and `ReportCard.jsx` can render readiness, source, validation, missing-fact, and risk-summary context.
- Report facts now receive a deterministic readiness grade: `ready`, `limited`, or `blocked`.
- Blocked readiness stops before the LangGraph/LLM pipeline and returns HTTP 422 metadata instead of saving a report.
- The fixed-format validator now requires asset-framework topics to appear inside the `자산군별 분석` section and to include minimal evidence or data-limit text.
- A deterministic qualitative claim checker now runs after numeric fact checking and before LLM evaluation for narrow high-risk claims around regulation/ETF events, institutional flow, earnings/guidance, policy shifts, supply/inventory, and on-chain/exchange flow.
- Writer instructions now require framework-topic evidence/limitations and warn against unsupported qualitative claims.
- Independent Bull/Bear/Risk LLM critics remain disabled by default. Metadata records `critic_mode` and `llm_report_critics_enabled`.
- Scheduled report generation remains conservative by default. It iterates DB assets only, applies a per-run cap and cooldown, and warns if broad coverage is requested.

## Verification Performed

- Not run by user request.

## Commands Not Run And Why

- Backend tests, compile checks, frontend lint, and frontend build were intentionally not run because the user requested implementation and records only.
- No live LLM generation was run to avoid provider calls and token cost.
- No broad scheduled generation was run.

## Follow-Up Risks

- The startup-time metadata column creation is not a substitute for a formal migration system.
- Existing running environments must restart the backend lifespan before persisted report metadata columns exist.
- The qualitative checker is intentionally narrow and deterministic; it may miss unsupported qualitative claims outside the configured trigger groups.
- Framework section depth validation checks minimal evidence/limitation text, not full professional analytical quality.
- `REPORT_SCHEDULER_COVERAGE` values outside `conservative` currently do not enable full default-ticker coverage; this remains a product/cost decision.
- Independent LLM critic agents are still not enabled because they would increase token cost and latency.

## Feature Docs

- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/market-data.md`
