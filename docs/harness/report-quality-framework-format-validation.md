# Report Quality Framework Format Validation

Date: 2026-05-31

## Objective

Extend the deterministic report format validator so it verifies that the final report explicitly covers the selected asset-category framework topics.

## Files Changed

- `backend/app/services/graph/nodes.py`
- `backend/tests/test_ai_report_quality_gate.py`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/feature-index.md`
- `docs/harness/report-quality-improvement-plan.md`

## Behavior Changes

- `report_format_validator_node` now reads `report_facts.analysis_framework.required_sections`.
- Reports must include those framework topic labels in addition to the 10 fixed Markdown sections.
- Format feedback now separates missing fixed sections from missing asset-framework topics.
- Missing framework topics route the graph back to `writer_node` through the existing revision loop.

## Verification Performed

- `py -m compileall backend\app backend\tests` passed.
- `.\.venv\Scripts\python.exe -c "from app.services.graph.nodes import report_format_validator_node; s={'ticker':'BTC-USD','draft_report':'## 핵심 요약\n## 데이터 기준 시각과 한계\n## 가격과 시장 반응\n## Bull 시나리오\n## Bear 시나리오\n## 핵심 촉매\n## 주요 리스크\n## 자산군별 분석\n- 가격과 거래량\n## 균형 결론\n## 투자 유의사항','report_facts':{'analysis_framework':{'required_sections':['가격과 거래량','유동성 환경']}},'feedback':'','revision_count':0,'retry_count':0}; r=report_format_validator_node(s); print(r['format_check_pass'], '유동성 환경' in r['format_check_feedback'])"` returned `False True` from `backend/`.
- `git diff --check` passed with only Git line-ending conversion warnings.

## Commands Not Run And Why

- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_ai_report_quality_gate.py` could not run because the project virtualenv does not have the `pytest` module installed.
- No live LLM generation was run, to avoid real OpenAI calls and costs during ordinary verification.

## Follow-Up Risks

- The validator checks topic-label presence, not analytical depth or semantic completeness.
- UI rendering for format-check failure feedback still depends on the existing generation failure display path.

## Feature Docs

- `docs/harness/features/asset-detail-ai-community.md`
