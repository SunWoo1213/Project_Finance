# Report Quality Asset Frameworks

Date: 2026-05-31

## Objective

Add asset-category analysis frameworks so the fixed report template adapts to US stocks, Korean stocks, indices, bonds, commodities, and crypto without relying on the writer to invent the correct analytical structure.

## Files Changed

- `backend/app/services/ai_service.py`
- `backend/app/services/graph/nodes.py`
- `backend/tests/test_ai_report_quality_gate.py`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/feature-index.md`
- `docs/harness/report-quality-improvement-plan.md`

## Behavior Changes

- Added `ASSET_ANALYSIS_FRAMEWORKS` for US stocks, Korean stocks, indices, US bonds, Korean bonds, commodities, and crypto.
- `_build_report_facts` now attaches `analysis_framework` beside the existing asset fact requirements.
- `StructuredFacts` can preserve the framework during synthesis.
- The writer prompt receives `analysis_framework` and must use its required sections and interpretation rules in the "자산군별 분석" section.
- Generation metadata now exposes the selected `analysis_framework` for newly generated reports.

## Verification Performed

- `py -m compileall backend\app backend\tests` passed.
- `.\.venv\Scripts\python.exe -c "from app.services.graph.graph import app; from app.services.ai_service import ASSET_ANALYSIS_FRAMEWORKS; print(ASSET_ANALYSIS_FRAMEWORKS['CRYPTO']['label'])"` passed from `backend/`.
- `git diff --check` passed with only Git line-ending conversion warnings.

## Commands Not Run And Why

- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_ai_report_quality_gate.py` could not run because the project virtualenv does not have the `pytest` module installed.
- No live provider or LLM generation was run, to avoid network-dependent behavior and LLM costs during ordinary verification.

## Follow-Up Risks

- The framework is prompt guidance, not a deterministic validator for final Markdown section compliance.
- Missing category-specific required facts are still reported as limitations rather than hard-failing before LLM generation.
- Framework metadata is exposed in the generation response but not persisted to `ai_reports`.

## Feature Docs

- `docs/harness/features/asset-detail-ai-community.md`
