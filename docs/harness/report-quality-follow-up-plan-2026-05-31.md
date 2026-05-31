# Report Quality Follow-Up Plan

Date: 2026-05-31

## Objective

Record the remaining AI report-quality improvements after the current harness changes. This is a planning document for future harness engineering work. No runtime code changes were made while creating this document.

The current pipeline is already stronger than the original broad commentary flow. It now uses structured report facts, asset-specific frameworks, deterministic Bull/Bear/Risk preparation nodes, fixed Markdown format validation, numeric fact checking, and a quality gate that prevents failed reports from being saved.

This document should help future agents avoid repeating completed work and focus only on remaining gaps.

Implementation note: the items in this plan were implemented in `docs/harness/report-quality-follow-up-implementation-2026-05-31.md`. Cost-increasing options remain disabled by default: independent LLM critics are not enabled, and scheduled report generation still uses conservative DB-asset coverage.

## Source Review

Read these before implementing any item in this plan:

- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/report-quality-improvement-plan.md`
- `docs/harness/report-quality-phase-1.md`
- `docs/harness/report-quality-phase-2.md`
- `docs/harness/report-quality-fact-checker.md`
- `docs/harness/report-quality-role-nodes.md`
- `docs/harness/report-quality-asset-frameworks.md`
- `docs/harness/report-quality-format-validator.md`
- `docs/harness/report-quality-framework-format-validation.md`
- `docs/harness/report-quality-heading-validator-and-neutral-badge.md`
- Current implementation under `backend/app/services/ai_service.py`
- Current LangGraph implementation under `backend/app/services/graph/`

## Do Not Re-Open As New Gaps

These items were already implemented or verified in previous records:

- `POST /api/ai/generate/{ticker}` requires authentication.
- Evaluator, format-checker, or fact-checker failures are not saved as final reports.
- Generation responses expose quality metadata for newly generated reports.
- `bull_summary` and `bear_summary` use role outputs when available.
- `ReportCard.jsx` is used by `AssetDetail.jsx`.
- The report card badge uses neutral copy: `AI 분석 완료`.
- Fixed report sections are checked against Markdown headings, not broad body-text aliases.
- Asset-framework topic labels are checked by the deterministic format validator.
- Optional `FMP_API_KEY` and `FINNHUB_API_KEY` settings exist.
- Backend report-quality tests pass when run from `backend/` with the project venv.

## Current Baseline

The current report generation flow is:

1. Build normalized `report_facts` in `backend/app/services/ai_service.py`.
2. Run parallel financial, news, and macro research nodes.
3. Merge provider and research context into `structured_facts`.
4. Split facts into deterministic `bull_thesis`, `bear_thesis`, and `risk_review`.
5. Write the final Korean Markdown report with a fixed 10-section template.
6. Validate required Markdown headings and asset-framework topic labels.
7. Reject unsupported numeric claims before LLM evaluation.
8. Run LLM evaluation.
9. Save only passing reports to `AIReport`.

## Priority 1: Persist Report Quality And Source Metadata

### Problem

Generation metadata is created but not persisted. `AIReport` currently stores only:

- `bull_summary`
- `bear_summary`
- `final_content`
- `created_at`

The generated metadata includes richer information such as `source_status`, `missing_required_facts`, `analysis_framework`, `risk_summary`, `role_outputs`, `format_check_pass`, `fact_check_pass`, `feedback`, `revision_count`, and `data_as_of`, but this is returned only on generation responses.

### Why It Matters

Users fetching an existing report cannot see the quality status, source freshness, missing facts, or risk review that existed at generation time. Future report display work also cannot render reliable quality badges, source summaries, or data limitations from persisted reports.

### Candidate Approach

Add a migration-backed persistence strategy before changing runtime storage. Possible fields:

- `quality_status`
- `quality_feedback`
- `format_check_pass`
- `fact_check_pass`
- `revision_count`
- `data_as_of`
- `source_summary`
- `risk_summary`
- `analysis_framework`
- `metadata_json`

Prefer one JSON metadata column plus a few indexed scalar fields if the project does not yet have a formal migration workflow.

### Files Likely Involved

- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/app/main.py`
- `backend/app/services/ai_service.py`
- `frontend/src/components/ReportCard.jsx`
- `docs/harness/features/asset-detail-ai-community.md`

### Risk

This is a schema change. Ask for confirmation before implementing because existing databases may need migration or table recreation.

### Verification

- `py -m compileall backend\app backend\tests`
- Focused backend tests for report creation and report retrieval.
- Frontend build if persisted metadata is rendered.
- Do not run live LLM generation by default.

## Priority 2: Grade Or Block Reports With Missing Required Facts

### Problem

`missing_required_facts` is recorded as a limitation, but generation continues. A report can still pass if it acknowledges missing data, even when important category-specific facts are absent.

### Why It Matters

A professional finance report should distinguish between:

- publishable full report
- limited report with visible data gaps
- blocked report because required facts are too sparse

For example, a crypto report without liquidity data or a stock report without company news should not look equivalent to a fully sourced report.

### Candidate Approach

Introduce a deterministic report readiness grade before or immediately after `report_facts` construction:

- `ready`: required facts present enough for a normal report.
- `limited`: report may be generated, but must surface limitations prominently.
- `blocked`: do not call the LLM; return a clear unavailable/insufficient-data response.

Keep the threshold asset-category specific. For example:

- price missing should usually block.
- news missing may produce `limited`.
- market cap missing for US stocks may produce `limited`, not always `blocked`.
- bond policy/inflation context missing may produce `limited` unless the report would otherwise make policy claims.

### Files Likely Involved

- `backend/app/services/ai_service.py`
- `backend/app/services/graph/state.py`
- `backend/app/services/graph/nodes.py`
- `backend/app/main.py`
- `frontend/src/pages/AssetDetail.jsx`
- `frontend/src/components/ReportCard.jsx`
- `backend/tests/test_ai_report_quality_gate.py`

### Risk

Blocking generation changes user-visible behavior and may reduce report availability for Korean stocks, bonds, commodities, and macro tickers where free provider coverage is sparse.

### Verification

- Mocked tests for `ready`, `limited`, and `blocked` paths.
- Ensure blocked reports do not call graph or LLM code.
- Ensure frontend explains insufficient data without treating it as an app error.

## Priority 3: Add Qualitative Claim Fact Checking

### Problem

The current fact checker rejects unsupported numeric claims only. It does not reliably catch unsupported qualitative claims such as:

- "규제 완화 기대가 커지고 있다"
- "기관 수급이 강화되고 있다"
- "실적 개선세가 확인된다"
- "중앙은행 정책이 완화적으로 전환됐다"

### Why It Matters

Financial reports often mislead through unsupported qualitative claims rather than only fabricated numbers. A professional-grade workflow needs claim-to-evidence discipline.

### Candidate Approach

Start with a deterministic or semi-deterministic claim audit before adding another LLM call:

1. Extract key qualitative claims from the draft by sentence.
2. Compare each claim against `structured_facts`, provider facts, news titles/summaries, and data limitations.
3. Flag high-risk unsupported words such as confirmed policy shifts, earnings improvement, guidance changes, ETF/regulatory events, institutional flow, inventory shortage, or on-chain trends unless evidence exists.
4. Route flagged claims back to `writer_node` with specific feedback.

If deterministic checks are too brittle, add an optional LLM-backed qualitative checker only after explicit cost approval.

### Files Likely Involved

- `backend/app/services/graph/nodes.py`
- `backend/app/services/graph/graph.py`
- `backend/app/services/graph/state.py`
- `backend/tests/test_ai_report_quality_gate.py`

### Risk

Over-strict qualitative checking can reject useful interpretation. Start narrow with high-risk claim categories and good tests.

### Verification

- Node-level tests where unsupported qualitative claims fail.
- Node-level tests where the same claims pass when supporting news/provider facts are present.
- No live LLM calls in ordinary tests unless the chosen implementation explicitly requires an approved LLM-backed checker.

## Priority 4: Validate Analytical Depth Inside Asset Framework Sections

### Problem

The format validator checks fixed Markdown headings and asset-framework topic-label presence. It does not prove that each framework topic is analyzed with enough substance, and framework topic checks are not currently constrained to the `자산군별 분석` section only.

### Why It Matters

A report can pass by merely mentioning framework labels without meaningful analysis. For a finance report, topic coverage should include evidence, interpretation, and data limitation when applicable.

### Candidate Approach

Enhance validation for the `자산군별 분석` section:

- Parse Markdown sections into heading-bound blocks.
- Locate the `자산군별 분석` block.
- Require each `analysis_framework.required_sections` topic to appear inside that block.
- For each topic, require at least one evidence or limitation sentence.
- Keep the first version deterministic and conservative.

### Files Likely Involved

- `backend/app/services/graph/nodes.py`
- `backend/tests/test_ai_report_quality_gate.py`

### Risk

This may increase rewrite loops if the writer prompt is not updated with exact formatting instructions. Update the prompt and validator together.

### Verification

- Regression test where topic labels appear outside `자산군별 분석` and should fail.
- Test where every topic appears inside the section and passes.
- Test where a topic label appears but has no meaningful body text and fails if depth rules are enabled.

## Priority 5: Decide Whether To Add Independent Bull/Bear/Risk LLM Critics

### Problem

Current Bull, Bear, and Risk nodes are deterministic preparation nodes. They improve structure without adding cost, but they are not independent analyst agents.

### Why It Matters

Professional research benefits from adversarial review: a bull case, a bear case, and a risk officer should challenge each other rather than only reorganize the same synthesized facts.

### Candidate Approach

Only after explicit cost approval, consider:

- `bull_critic_node`: creates the strongest evidence-backed positive case.
- `bear_critic_node`: creates the strongest evidence-backed negative case.
- `risk_officer_llm_node`: identifies stale data, unsupported claims, missing catalysts, and overconfidence.
- `synthesizer_node`: reconciles disagreements and preserves uncertainty.

Each critic must be constrained to structured facts and must not perform broad open-ended browsing unless separately approved.

### Files Likely Involved

- `backend/app/services/graph/nodes.py`
- `backend/app/services/graph/graph.py`
- `backend/app/services/graph/state.py`
- `backend/app/services/ai_service.py`
- `backend/tests/test_ai_report_quality_gate.py`

### Risk

This increases token cost and latency. Do not implement as part of a low-risk cleanup.

### Verification

- Mock LLM tests for routing and retry behavior.
- Manual live smoke test only with explicit user approval.
- Track token/cost impact in the change record.

## Priority 6: Clarify Scheduled Report Coverage

### Problem

Scheduled generation currently iterates DB `Asset` rows. It does not seed every default market-cache ticker into the database first.

### Why It Matters

This can be correct for a conservative product policy, but it should be explicit:

- Conservative mode: only assets users have touched or reports/comments have created are refreshed.
- Full coverage mode: every default ticker in the market cache receives scheduled reports.

### Candidate Approach

Keep conservative mode unless the user explicitly approves broader LLM/API usage.

If full coverage is approved, add a DB asset sync step and cost controls:

- per-asset cooldown
- max reports per scheduler run
- provider freshness checks before generation
- skip if no meaningful context changed
- admin/runtime flag for enabling broad scheduled generation

### Files Likely Involved

- `backend/app/services/ai_service.py`
- `backend/app/services/market_service.py`
- `backend/app/main.py`
- `backend/app/core/config.py`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/market-data.md`

### Risk

Broadening scheduled report generation can materially increase LLM and external provider usage.

### Verification

- Mocked scheduler tests only.
- No live broad generation in ordinary verification.

## Recommended Implementation Order

1. Persist report quality/source metadata after confirming migration strategy.
2. Add readiness grading for missing required facts.
3. Strengthen framework-section depth validation.
4. Add qualitative claim checking for narrow high-risk claim categories.
5. Decide whether independent LLM critics are worth the token cost.
6. Decide scheduled generation coverage policy.

## Documentation Updates Required When Implementing

For any implementation based on this plan:

- Update `docs/harness/features/asset-detail-ai-community.md`.
- Update `docs/harness/feature-index.md`.
- Add a focused change record under `docs/harness/`.
- If scheduler coverage changes, update `docs/harness/features/market-data.md`.
- If DB fields change, document migration assumptions and manual follow-up.

## Verification Performed For This Planning Step

- Reviewed `git status --short`.
- Read `docs/harness/feature-index.md`.
- Read `docs/harness/features/asset-detail-ai-community.md`.
- Read `docs/harness/report-quality-improvement-plan.md`.

No runtime tests were run for this planning-only document.
