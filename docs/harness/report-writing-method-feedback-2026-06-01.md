# Report Writing Method Feedback

Date: 2026-06-01

## Objective

Review the currently implemented AI report writing method from a finance report quality perspective and define how future implementation should evolve.

This document is a feedback and implementation guide only. No runtime code changes were made while creating it.

## Files Reviewed

- `backend/app/services/ai_service.py`
- `backend/app/services/graph/nodes.py`
- `backend/app/services/graph/graph.py`
- `backend/app/main.py`
- `backend/app/core/config.py`
- `backend/app/services/external_api_service.py`
- `frontend/src/pages/AssetDetail.jsx`
- `frontend/src/components/ReportCard.jsx`
- `backend/tests/test_ai_report_quality_gate.py`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/report-quality-improvement-plan.md`
- `docs/harness/report-quality-follow-up-plan-2026-05-31.md`
- `docs/harness/report-quality-follow-up-implementation-2026-05-31.md`
- `docs/harness/report-generation-schedule-alignment-plan-2026-06-01.md`

## Current Implementation Summary

The current report pipeline is no longer a simple "ask the LLM to write market commentary" flow. It already has several professional-grade foundations:

1. `generate_report_for_ticker` builds normalized `report_facts` before invoking LangGraph.
2. `report_facts` includes price, source status, news, events, missing facts, readiness, and asset-category framework metadata.
3. The graph collects financial, news, and macro context, synthesizes structured facts, derives bull/bear/risk views, writes the final Markdown report, and runs format, numeric, qualitative, and evaluator checks.
4. Failed readiness or quality checks block persistence, so failed drafts are not saved as final reports.
5. Report metadata is persisted and returned to the frontend, allowing the UI to show data freshness, validation state, missing facts, and risk summary.
6. Scheduler settings now express a 6-hour report interval and a target ticker list.

This is a strong engineering direction. The key remaining issue is that the pipeline is structurally safe but not yet fully equivalent to a professional finance research desk workflow.

## Expert Feedback

### 1. The report is still too writer-centric

The graph has bull, bear, and risk nodes, but those nodes currently reorganize `structured_facts` deterministically. The final investment narrative still depends heavily on one `writer_node`.

For professional reporting, the writer should not be the place where analysis is invented. The writer should only format a pre-built research packet. The actual analytical stance should be created before the writer step.

Target behavior:

- `bull_case`, `bear_case`, `base_case`, `risk_review`, and `watchlist` should be explicit structured objects.
- The writer should be forbidden from creating new claims, scenarios, catalysts, or numbers.
- If a scenario cannot be supported by available facts, the scenario should say "insufficient evidence" rather than become a vague paragraph.

### 2. The fact requirements are broader than the enforced checks

`ASSET_FACT_REQUIREMENTS` defines professional-looking required fields, but `_build_report_facts` only checks a subset of them. For example, `recent_performance`, `valuation_or_beta`, `macro_drivers`, curve context, real rates, supply-demand drivers, and liquidity backdrop are listed as required for some asset classes but are not all deterministically collected or enforced.

This means a report can be labeled `limited` rather than blocked even when the missing fields are central to that asset class.

Target behavior:

- Each required fact should map to a concrete collector and a concrete validation rule.
- A required fact should have one of these statuses: `present`, `missing_optional_provider`, `missing_required`, or `not_applicable`.
- Readiness should be computed from this fact matrix, not from a few selected fields.

### 3. Source traceability exists in metadata but is not visible enough in the final report

The pipeline preserves source status, timestamps, provider facts, and confidence fields in metadata. However, the final Markdown report can still read like unsupported prose because the body does not require source labels or evidence references per major claim.

Professional finance reports need claim-level traceability, especially for:

- price and performance numbers
- earnings, valuation, margin, or beta claims
- policy, CPI, rate, and FX claims
- ETF, regulation, flow, inventory, and on-chain claims
- news-driven catalysts

Target behavior:

- Every section should distinguish `confirmed facts`, `interpretation`, and `data limitations`.
- Important facts should carry short source labels such as `market_cache`, `FMP profile`, `Finnhub company-news`, `CoinGecko`, `latest_context`, or `internal limitation`.
- The final report should include a compact source table or evidence notes section.

### 4. The current fixed template is good, but the report needs a sharper investment structure

The 10-section template reduces LLM drift, which is good. But the current structure is closer to a general commentary report than a decision-useful investment note.

Recommended report structure:

1. 핵심 요약
2. 데이터 기준 시각과 신뢰도
3. 이전 리포트 대비 변화
4. 가격과 시장 반응
5. Base case
6. Bull case
7. Bear case
8. 주요 촉매와 체크포인트
9. 핵심 리스크와 반증 조건
10. 자산군별 전문 분석
11. 균형 결론
12. 투자 유의사항

The current 10-section format can remain for compatibility, but the internal structured facts should support these concepts explicitly. The UI can later render the same data as cards instead of relying only on Markdown.

### 5. The scheduler and user-facing generation path must be aligned before report quality can be trusted

The planning document already identifies the product rule: users and the chatbot should read stored scheduled reports only. The current `AssetDetail.jsx` still calls `POST /api/ai/generate/{ticker}` after a 404.

From a finance-reporting perspective, user-triggered generation is risky because it creates inconsistent report timing, variable source freshness, and unpredictable LLM/API cost. A scheduled research desk model is better:

- market data refreshes on its own cadence
- reports are generated on a controlled cadence
- users see the latest published report
- missing reports show "scheduled report not ready"
- manual generation is admin-only or disabled in production

### 6. Report coverage is too narrow for the visible product surface

`REPORT_SCHEDULER_TARGET_TICKERS` defaults to five tickers: `DGS10`, `XAU`, `BTC-USD`, `NVDA`, and `005930.KS`. This is useful for cost control, but users can browse many more assets.

If most visible assets do not have stored reports, the product will feel broken even if the report pipeline is technically correct.

Target behavior:

- Define a production report catalog separate from the market-price catalog.
- Tier assets by priority:
  - Tier 1: always pre-generated flagship assets.
  - Tier 2: generated during low-cost windows or once daily.
  - Tier 3: no report, only market data and news.
- The frontend should know whether a ticker is report-covered and should not promise AI reports for uncovered assets.

### 7. The frontend report card should present a research product, not only Markdown

`ReportCard.jsx` correctly renders stored metadata, bull/bear summaries, and Markdown. The next step is to make the report inspectable:

- show data timestamp and freshness badge at the top
- show source coverage and missing facts before the conclusion
- render base/bull/bear/risk blocks as separate cards
- show catalysts and monitoring checklist
- render "not covered" and "scheduled report pending" states differently from "blocked due to insufficient data"

This reduces user overtrust in a polished Markdown paragraph and makes data limitations visible.

## Recommended Implementation Design

### Phase 1: Make generation policy research-desk style

Goal: scheduled stored reports only for normal users.

Implementation:

- Remove the frontend 404 fallback that calls `POST /api/ai/generate/{ticker}`.
- Change the missing-report state to "scheduled report not ready" or "not covered".
- Keep `GET /api/reports/{ticker}` as the only user-facing report read path.
- Disable, remove, or admin-gate `POST /api/ai/generate/{ticker}`.
- Keep chatbot behavior read-only against stored reports.

Acceptance criteria:

- Opening an authenticated asset detail page never calls the generation endpoint.
- Chatbot report requests never call generation.
- A missing report does not trigger LLM work.

### Phase 2: Create a report coverage catalog

Goal: make report availability intentional.

Implementation:

- Introduce a `REPORT_COVERAGE_CATALOG` or DB-backed report coverage table.
- Store ticker, display name, asset category, coverage tier, generation cadence, and enabled flag.
- Seed scheduled report assets from this catalog instead of relying only on existing DB `Asset` rows.
- Keep cost controls: max reports per run, cooldown, provider timeout, and failure isolation.

Acceptance criteria:

- Every scheduled report target has an `Asset` row before generation starts.
- Frontend can distinguish `covered`, `pending`, `blocked`, and `not_covered`.
- Broadening coverage requires explicit product/cost approval.

### Phase 3: Replace loose required facts with a fact matrix

Goal: make data readiness auditable.

Implementation:

- Convert `ASSET_FACT_REQUIREMENTS` into concrete fact definitions.
- For each fact, define:
  - collector source
  - required/optional status
  - stale-after threshold
  - blocking severity
  - display label
- Build `fact_matrix` during `_build_report_facts`.
- Compute readiness from `fact_matrix`.

Example shape:

```python
{
    "fact_key": "valuation_or_beta",
    "label": "밸류에이션 또는 베타",
    "status": "missing_required",
    "source": "FMP profile",
    "severity": "limited",
    "as_of": None,
    "display_note": "FMP 키가 없거나 provider 응답이 비어 있어 확인하지 못했습니다.",
}
```

Acceptance criteria:

- Every listed required fact has a deterministic status.
- Blocked reports never invoke the LLM.
- Limited reports must include the limitation near the top of the report and in metadata.

### Phase 4: Build the research packet before writing

Goal: make writing a formatting step, not an analysis step.

Implementation:

- Add or refactor graph state to include:
  - `base_case`
  - `bull_case`
  - `bear_case`
  - `risk_review`
  - `catalysts`
  - `watchlist`
  - `source_table`
  - `data_limitations`
- These objects should be produced before `writer_node`.
- The writer prompt should state that it can only format these objects.

Acceptance criteria:

- The final Markdown can be regenerated from the structured packet.
- Bull/bear summaries come from `bull_case` and `bear_case`, not from free-form final text.
- Risk summary comes from `risk_review`.

### Phase 5: Add claim-level evidence discipline

Goal: prevent unsupported professional-sounding claims.

Implementation:

- Extend the deterministic checker beyond broad qualitative trigger words.
- Require high-risk claims to include source-backed evidence IDs.
- Add a source table to `structured_facts`.
- Make the writer include evidence labels for major claims.
- Keep optional LLM critic disabled unless cost is approved.

Acceptance criteria:

- Unsupported claims about regulation, ETF flows, institutional flows, earnings, guidance, policy shifts, inventories, on-chain flows, or supply-demand fail validation.
- Numeric claims continue to fail if not found in structured facts or provider facts.
- The report can explain missing data without converting it into a conclusion.

### Phase 6: Improve report UI from Markdown viewer to research card

Goal: make confidence and limitations visible.

Implementation:

- Update `ReportCard.jsx` to show:
  - report status
  - data as-of time
  - source coverage
  - missing required facts
  - base/bull/bear/risk blocks
  - catalysts/watchlist
  - final Markdown or conclusion
- Use separate empty states:
  - `not_covered`
  - `scheduled_pending`
  - `blocked_insufficient_data`
  - `quality_failed`

Acceptance criteria:

- Users can tell whether a report is unavailable due to coverage, scheduling, data insufficiency, or quality rejection.
- The UI does not imply direct buy/sell advice.
- The report's limitations are visible without expanding the full Markdown body.

## Suggested Implementation Order

1. Remove user-triggered report generation from `AssetDetail.jsx`.
2. Admin-gate or disable `POST /api/ai/generate/{ticker}` for normal users.
3. Add report coverage status to the backend and frontend.
4. Build the fact matrix and readiness grading from concrete required facts.
5. Refactor graph state into a pre-written research packet.
6. Add source/evidence IDs and improve claim validation.
7. Upgrade `ReportCard.jsx` to render the research packet.
8. Add focused tests for scheduler-only generation, fact matrix readiness, report packet construction, and UI states.

## Verification Plan

- Backend syntax check: `py -m compileall backend\app backend\tests`
- Backend tests:
  - report generation does not save failed reports
  - blocked readiness does not invoke graph/LLM
  - fact matrix statuses are computed correctly by asset class
  - user-facing report paths do not call generation
  - chatbot report path reads stored reports only
- Frontend checks:
  - `npm.cmd run lint`
  - `npm.cmd run build`
  - inspect asset detail behavior for stored, missing, blocked, and not-covered report states
- Do not run live LLM generation in ordinary verification.

## Follow-Up Risks

- Expanding scheduled coverage can increase LLM/API cost and should be explicitly approved.
- Stronger readiness rules may reduce report availability until providers are improved.
- Adding evidence IDs or a report packet may require schema or metadata migration.
- Admin-only generation needs a user role or permission model if the product wants manual operations.
- A fully independent bull/bear/risk LLM critic system would increase latency and token cost; keep it optional.

## Relationship To Existing Plans

- This document complements `docs/harness/report-generation-schedule-alignment-plan-2026-06-01.md`.
- The schedule plan defines when and how reports should be generated.
- This document defines what a generated report should contain and how the implementation should enforce professional research quality.

## User-Facing Generation Rule

User-facing requests should not trigger report generation. Users and the chatbot should read stored scheduled reports only. If no stored report exists, the product should return a clear pending, not-covered, or insufficient-data state without invoking LLM-backed generation.
