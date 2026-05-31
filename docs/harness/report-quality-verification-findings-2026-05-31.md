# Report Quality Verification Findings

Date: 2026-05-31

## Objective

Verify the current report-quality, asset-framework, role-node, authentication, market-history, and frontend display changes without modifying source code. This document records issues that should be fixed later.

## Scope Reviewed

- `backend/app/services/ai_service.py`
- `backend/app/services/graph/nodes.py`
- `backend/app/services/graph/graph.py`
- `backend/app/services/graph/state.py`
- `backend/app/main.py`
- `backend/app/api/deps.py`
- `backend/app/services/external_api_service.py`
- `frontend/src/pages/AssetDetail.jsx`
- `frontend/src/pages/CategoryView.jsx`
- `frontend/src/components/ReportCard.jsx`
- `frontend/src/utils/assetCategories.js`
- Related tests under `backend/tests/`
- Related report-quality and feature documentation under `docs/harness/`

## Verification Performed

- `py -m compileall backend\app backend\tests` passed.
- Initial root-level pytest command failed because `app` was not importable from the repository root.
- `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\test_ai_report_quality_gate.py tests\test_auth_deps.py tests\test_macro_service.py tests\test_market_history_route.py` passed from `backend/` with 24 tests.
- `npm.cmd run lint` passed from `frontend/`.
- `npm.cmd run build` passed from `frontend/`; Vite kept the existing large chunk warning.
- `git diff --check` passed with only line-ending conversion warnings.
- A focused smoke check reproduced a report-format validator false positive.

## Findings To Fix

### 1. Format validator can pass reports that omit required section headings

Severity: High

The report-format validator is documented as requiring the fixed 10 Markdown sections, but `_missing_report_sections` in `backend/app/services/graph/nodes.py` checks normalized substrings across the entire draft. Because aliases such as `가격` and `리스크` are very broad, framework-topic text can satisfy fixed-section requirements even when the actual fixed Markdown headings are missing.

Reproduced behavior:

```powershell
cd backend
.\.venv\Scripts\python.exe -c "from app.services.graph.nodes import report_format_validator_node; draft='''## 핵심 요약\n## 데이터 기준 시각과 한계\n## Bull 시나리오\n## Bear 시나리오\n## 핵심 촉매\n## 자산군별 분석\n- 가격과 거래량\n- 리스크온/오프 심리\n## 균형 결론\n## 투자 유의사항'''; r=report_format_validator_node({'ticker':'BTC-USD','draft_report':draft,'report_facts':{'analysis_framework':{'required_sections':['가격과 거래량','리스크온/오프 심리']}},'feedback':'','revision_count':0,'retry_count':0}); print(r)"
```

Actual result:

```text
{'format_check_pass': True, 'format_check_feedback': ''}
```

Expected result: `format_check_pass` should be `False` because the fixed headings `가격과 시장 반응` and `주요 리스크` are absent.

Recommended fix: parse Markdown headings or line-level section labels and require each fixed section heading explicitly. Keep framework-topic checks separate from fixed-section heading checks. Add a regression test where framework topics include broad words like `가격` and `리스크`, but the fixed headings are missing.

### 2. Asset detail now shows recommendation-like copy despite report prompt policy

Severity: Medium

`AssetDetail.jsx` now renders `ReportCard`, and `ReportCard.jsx` displays the badge text `Analyst Recommends`. The writer prompt in `backend/app/services/graph/nodes.py` explicitly tells the LLM to avoid direct buy/sell recommendations. The badge is UI copy, not generated content, but it can still imply an investment recommendation and conflicts with the report-quality safety posture.

Recommended fix: replace the badge with neutral wording such as `AI 분석 완료`, `품질 검증 완료`, or `리포트 생성 완료`. This is a UI-only change and should not affect backend report generation.

## Notes

- The core role-node and quality-gate tests currently pass.
- No source code was modified during this verification.
- No live LLM generation or paid/provider network smoke test was run.
