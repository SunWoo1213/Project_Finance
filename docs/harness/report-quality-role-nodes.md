# Report Quality Role Nodes

Date: 2026-05-31

## Objective

Advance the report quality plan by separating synthesized facts into Bull, Bear, and Risk views before the writer step, without adding new LLM calls or changing the database schema.

## Files Changed

- `backend/app/services/graph/state.py`
- `backend/app/services/graph/nodes.py`
- `backend/app/services/graph/graph.py`
- `backend/app/services/ai_service.py`
- `backend/tests/test_ai_report_quality_gate.py`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/feature-index.md`
- `docs/harness/report-quality-improvement-plan.md`

## Behavior Changes

- Added `bull_agent_node`, `bear_agent_node`, and `risk_officer_node` after `synthesizer_node`.
- The new role nodes derive `bull_thesis`, `bear_thesis`, and `risk_review` from existing `structured_facts` and `report_facts`.
- The graph now routes through those role nodes before `writer_node`.
- The writer prompt receives the separated role outputs and must use them alongside `structured_facts`.
- Generation metadata now includes `role_outputs`.
- Saved `bull_summary` and `bear_summary` prefer role-node thesis outputs when available.

## Verification Performed

- `py -m compileall backend\app backend\tests` passed.
- `.\.venv\Scripts\python.exe -c "from app.services.graph.graph import app, route_fact_check; from app.services.graph.nodes import bull_agent_node, bear_agent_node, risk_officer_node; print('graph role nodes import ok')"` passed from `backend/`.
- `git diff --check` passed with only Git line-ending conversion warnings.

## Commands Not Run And Why

- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_ai_report_quality_gate.py` could not run because the project virtualenv does not have the `pytest` module installed.
- No live LLM generation was run, to avoid real OpenAI calls and costs during ordinary verification.

## Follow-Up Risks

- These are deterministic role-preparation nodes, not fully independent LLM-backed debate agents.
- Role outputs are exposed on the generation response but not persisted to `ai_reports`.
- Qualitative claim fact checking remains a future improvement.

## Feature Docs

- `docs/harness/features/asset-detail-ai-community.md`
