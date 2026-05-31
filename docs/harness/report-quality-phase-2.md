# Report Quality Phase 2

Date: 2026-05-30

## Objective

Strengthen the structured report facts contract so the graph receives normalized facts, asset-category requirements, provider metadata, source timestamps, and explicit data limitations before the final writing step.

## Files Changed

- `backend/app/services/ai_service.py`
- `backend/app/services/external_api_service.py`
- `backend/app/services/graph/state.py`
- `backend/app/services/graph/nodes.py`
- `backend/tests/test_ai_report_quality_gate.py`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/report-quality-improvement-plan.md`

## Behavior Changes

- Added `ASSET_FACT_REQUIREMENTS` for US stocks, Korean stocks, indices, US/Korean bonds, commodities, and crypto.
- Report facts now include `requirements`, `market`, `missing_required_facts`, expanded `source_status`, and asset-specific data limitations.
- Market cache facts preserve `as_of`, `source`, and `confidence` context for price, market cap, and history coverage.
- Added structured provider functions for FMP, Finnhub, and CoinGecko while keeping the existing string-format helpers for compatibility.
- Financial, news, and macro graph nodes now pass provider facts separately as `financial_facts`, `news_facts`, and `macro_facts`.
- The synthesizer prompt now receives both normalized report facts and structured provider facts before producing `structured_facts`.
- Mocked tests now assert asset-specific limitations, missing required facts, and no-network provider missing/unsupported states.

## Verification Performed

- `py -m compileall backend\app backend\tests` passed.

## Commands Not Run And Why

- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_ai_report_quality_gate.py` could not run because the project virtualenv does not have the `pytest` module installed.
- No live provider or LLM generation was run, to avoid network-dependent behavior and LLM costs during ordinary verification.

## Follow-Up Risks

- Provider facts are available to the graph but not persisted in `ai_reports` yet because schema expansion needs migration confirmation.
- FMP, Finnhub, and CoinGecko structured facts are still provider-limited and may be sparse.
- Asset-category requirements currently identify missing facts; they do not yet enforce hard rejection before LLM generation.
- Full Bull/Bear/Risk/Fact Checker node separation remains a later phase.

## Feature Docs

- `docs/harness/features/asset-detail-ai-community.md`
