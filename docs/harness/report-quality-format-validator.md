# Report Quality Format Validator

Date: 2026-05-31

## Objective

Add a deterministic fixed-template validator so generated reports must include the 10 required Markdown sections before numeric fact checking and LLM evaluation.

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

- Added `report_format_validator_node` after `writer_node`.
- The validator checks for the fixed report sections: 핵심 요약, 데이터 기준 시각과 한계, 가격과 시장 반응, Bull 시나리오, Bear 시나리오, 핵심 촉매, 주요 리스크, 자산군별 분석, 균형 결론, 투자 유의사항.
- Drafts missing required sections receive format feedback and route back to `writer_node`.
- Repeated format failures stop at the revision limit with `is_pass=false`, so the service quality gate blocks saving.
- Generation metadata now includes `format_check_pass` and `format_check_feedback`.

## Verification Performed

- `py -m compileall backend\app backend\tests` passed.
- `.\.venv\Scripts\python.exe -c "from app.services.graph.graph import app, route_format_check; from app.services.graph.nodes import report_format_validator_node; print('format validator import ok')"` passed from `backend/`.
- `.\.venv\Scripts\python.exe -c "from app.services.graph.nodes import report_format_validator_node; from app.services.graph.graph import route_format_check; s={'ticker':'AAPL','draft_report':'## 핵심 요약','feedback':'','revision_count':0,'retry_count':0}; r=report_format_validator_node(s); print(r['format_check_pass'], route_format_check({**s, **r}))"` returned `False writer_node` from `backend/`.
- `git diff --check` passed with only Git line-ending conversion warnings.

## Commands Not Run And Why

- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_ai_report_quality_gate.py` could not run because the project virtualenv does not have the `pytest` module installed.
- No live LLM generation was run, to avoid real OpenAI calls and costs during ordinary verification.

## Follow-Up Risks

- The validator checks section presence, not section depth or analytical completeness.
- It does not yet deterministically validate that the 자산군별 분석 section includes every selected framework subtopic.
- UI rendering for format-check failure feedback still depends on the existing generation failure display path.

## Feature Docs

- `docs/harness/features/asset-detail-ai-community.md`
