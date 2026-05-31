# Report Quality Heading Validator And Neutral Badge

Date: 2026-05-31

## Objective

Fix two report-quality follow-ups:

- Prevent the deterministic report format validator from passing when required fixed Markdown section headings are missing but broad words such as price or risk appear elsewhere.
- Replace recommendation-like `ReportCard` badge copy with neutral report status wording.

Source finding: `docs/harness/report-quality-verification-findings-2026-05-31.md`.

## Files Changed

- `backend/app/services/graph/nodes.py`
- `backend/tests/test_ai_report_quality_gate.py`
- `frontend/src/components/ReportCard.jsx`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/feature-index.md`

## Behavior Changes

- Fixed report sections are now checked against parsed Markdown heading lines instead of normalized text from the whole draft.
- Broad fixed-section aliases such as `가격`, `리스크`, and `결론` were removed so framework topics or body text cannot satisfy missing fixed headings.
- Added a regression test where `가격과 시장 반응` and `주요 리스크` headings are absent while framework topics still contain price/risk wording.
- The report card badge now says `AI 분석 완료` with a neutral completion icon instead of `Analyst Recommends`.

## Verification Performed

- `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\test_ai_report_quality_gate.py` passed from `backend/`.
- The focused reproduction from `report-quality-verification-findings-2026-05-31.md` now returns `format_check_pass: False` and reports missing fixed sections `가격과 시장 반응` and `주요 리스크`.
- `npm.cmd run build` passed from `frontend/`; Vite kept the existing large chunk warning.
- `npm.cmd run lint` passed from `frontend/`.
- `git diff --check` passed with only existing line-ending conversion warnings.

## Commands Not Run And Why

- No live LLM report generation was run, to avoid real provider calls and costs during ordinary verification.

## Follow-Up Risks

- The format validator still checks section and topic-label presence, not analytical depth.
- Framework topic validation still checks label presence in the draft overall; it does not yet require each topic to appear inside only the `자산군별 분석` section.

## Feature Docs

- `docs/harness/features/asset-detail-ai-community.md`
