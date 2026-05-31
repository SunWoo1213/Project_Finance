# Report Quality Fact Checker

Date: 2026-05-30

## Objective

Begin the LangGraph role redesign with a low-cost fact checker node that runs before the LLM evaluator and blocks drafts containing unsupported numeric claims.

## Files Changed

- `backend/app/services/ai_service.py`
- `backend/app/services/graph/state.py`
- `backend/app/services/graph/nodes.py`
- `backend/app/services/graph/graph.py`
- `backend/tests/test_ai_report_quality_gate.py`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/report-quality-improvement-plan.md`

## Behavior Changes

- Added `fact_checker_node` between `writer_node` and `evaluator_node`.
- The fact checker compares numeric tokens in the draft report against numbers present in `report_facts`, `structured_facts`, and structured provider facts.
- Unsupported numeric claims add feedback and route the graph back to `writer_node` until the revision limit is reached.
- If the fact checker still fails at the revision limit, the graph ends with `is_pass=false`; the service quality gate prevents saving the report.
- Successful generation metadata now includes `fact_check_pass` and `fact_check_feedback`.
- Added node-level tests for passing supported numbers, rejecting unsupported numbers, and ending after the revision limit.

## Verification Performed

- `py -m compileall backend\app backend\tests` passed.
- `backend\.venv\Scripts\python.exe -c "from app.services.graph.graph import app, route_fact_check; print('graph import ok')"` passed from `backend/`.

## Commands Not Run And Why

- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_ai_report_quality_gate.py` could not run because the project virtualenv does not have the `pytest` module installed.
- No live LLM generation was run, to avoid real OpenAI calls and costs during ordinary verification.

## Follow-Up Risks

- The fact checker is deterministic and numeric-focused. It does not yet verify unsupported qualitative claims.
- Some legitimate numeric text may need future allow-list tuning if the writer uses units or date formats in unexpected ways.
- Bull, Bear, and Risk roles are still not split into dedicated graph nodes.

## Feature Docs

- `docs/harness/features/asset-detail-ai-community.md`
