# AI Report Quality Improvement Plan

Date: 2026-05-30

## Objective

Raise the current LLM-backed report pipeline from broad AI market commentary to a more reliable finance research workflow.

The target quality bar is:

- Claims and numbers have clear source, timestamp, and confidence context.
- Bull, bear, and risk views are separated before final synthesis.
- Reports that fail quality checks are not saved or served as final reports.
- LLM generation is protected from unauthenticated use and avoidable cost spikes.
- Each asset category uses a suitable analytical framework.

## Current Gaps

The current implementation has a useful foundation, but it is not yet a professional-grade research workflow.

- The documented Bull/Bear/Synthesizer architecture does not match the current graph. The actual graph is `financial_agent`, `news_agent`, `macro_agent`, `synthesizer_node`, `writer_node`, and `evaluator_node`.
- `bull_summary` is currently derived from the full report text, while `bear_summary` is a fixed string.
- The evaluator can fail, but after the revision limit the report may still be saved to the database.
- LLM input contains only minimal price data such as `price`, `change_pct`, and `symbol`.
- External research output is mostly free-form text, without strict source, URL, timestamp, or confidence metadata.
- The same LLM family performs writing and evaluation, so the quality gate is closer to self-review than independent verification.
- The scheduler runs every 6 hours, but daily generation logic can skip assets after one report for the date.
- `POST /api/ai/generate/{ticker}` is not currently protected by authentication.

## Phase 1: Safety And Quality Gate

1. Protect `POST /api/ai/generate/{ticker}` with authentication.
2. Add an authorization policy for who can trigger LLM-backed report generation.
3. Stop saving reports when `is_pass` is false after evaluation.
4. Return a clear generation failure response when the evaluator rejects the final draft.
5. Persist or expose generation metadata such as `is_pass`, `feedback`, `revision_count`, `generated_at`, `data_as_of`, and `source_status`.
6. Add mocked tests for pass/fail evaluator outcomes without making real OpenAI calls.

Primary files:

- `backend/app/main.py`
- `backend/app/services/ai_service.py`
- `backend/app/services/graph/graph.py`
- `backend/app/services/graph/nodes.py`
- `backend/tests/`

## Phase 2: Structured Report Facts

Introduce a structured facts contract before the writing step. The writer should receive a well-formed object rather than mostly free-form research strings.

Recommended shape:

```python
{
    "ticker": "...",
    "asset_category": "...",
    "price": {
        "value": "...",
        "change_pct": "...",
        "as_of": "...",
        "source": "...",
        "url": "...",
        "confidence": "high|medium|low",
    },
    "valuation": [],
    "financials": [],
    "news": [],
    "macro": [],
    "events": [],
    "risks": [],
    "data_limitations": [],
}
```

Rules:

- Every major number should include `value`, `as_of`, `source`, and `confidence`.
- URLs should be preserved when provider responses include them.
- Missing data should be represented as a data limitation, not silently filled by the LLM.
- Facts should be normalized before they reach the writer node.

Primary files:

- `backend/app/services/ai_service.py`
- `backend/app/services/external_api_service.py`
- `backend/app/services/market_service.py`
- `backend/app/services/graph/state.py`
- `backend/app/services/graph/nodes.py`

## Phase 3: Asset-Specific Data Requirements

Define required and optional facts by asset category.

US stocks:

- Price, volume, recent performance, valuation, market cap, beta.
- Revenue, earnings, margins, guidance, earnings date.
- Recent company news and management commentary.

Korean stocks:

- Price, recent performance, sector, news, and local market context.
- FX sensitivity and interest-rate sensitivity when relevant.
- Clearly mark financial statement gaps if no reliable free provider is available.

Indices:

- Index level, recent performance, sector leadership when available.
- Rates, FX, volatility, liquidity, and macro drivers.

Bonds:

- Yield level, curve context, central bank policy, CPI, real-rate context.
- Distinguish price return from yield movement.

Commodities:

- Spot or futures price, dollar, real rates, inventory or supply-demand drivers.
- Geopolitical and seasonal factors when relevant.

Crypto:

- Price, volume, ETF/regulatory news, liquidity backdrop.
- On-chain or exchange data only if a reliable source is available.

## Phase 4: LangGraph Role Redesign

Move from a broad research-and-write graph to a debate-and-verification graph.

Recommended nodes:

1. `data_collector_node`: gathers and normalizes price, news, calendar, macro, and external provider facts.
2. `bull_agent_node`: creates the positive thesis from structured facts only.
3. `bear_agent_node`: creates the negative thesis and downside scenario from structured facts only.
4. `risk_officer_node`: identifies missing risks, overconfident claims, stale data, and uncertainty.
5. `synthesizer_node`: combines bull, bear, and risk views into a balanced investment narrative.
6. `fact_checker_node`: rejects unsupported numbers or claims not present in structured facts.
7. `writer_node`: writes the final Korean Markdown report.
8. `evaluator_node`: decides whether the report is publishable.

The final output should not depend on the writer inventing structure. The graph should enforce the structure.

## Phase 5: Fixed Report Format

Use a stable report template to reduce LLM drift.

Recommended sections:

1. Core summary
2. Data timestamp and limitations
3. Price and market reaction
4. Bull scenario
5. Bear scenario
6. Key catalysts
7. Main risks
8. Asset-category analysis
9. Balanced conclusion
10. Investment disclaimer

Guidelines:

- Avoid direct buy/sell recommendations unless the product intentionally supports regulated investment advice.
- Prefer observation points, scenario conditions, and risk balance.
- Separate confirmed facts from interpretation.
- Make data limitations visible near the top of the report.

## Phase 6: Database And API Contract Improvements

The current `AIReport` shape can serve a first version, but professional reports need richer metadata.

Candidate fields:

- `bull_summary`
- `bear_summary`
- `risk_summary`
- `source_summary`
- `quality_status`
- `quality_feedback`
- `data_as_of`
- `model_name`
- `revision_count`
- `final_content`

Schema changes require confirmation because they can need migrations or database updates.

Primary files:

- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/app/main.py`
- `frontend/src/pages/AssetDetail.jsx`
- `frontend/src/components/ReportCard.jsx`

## Phase 7: Scheduling And Cost Controls

Clarify whether reports are daily or intraday.

Daily model:

- Generate once per asset per date.
- Report framing should focus on daily market context and recent changes.

Intraday model:

- Generate every 6 hours only when meaningful context changed.
- Report framing can compare against the previous report's delta.

Required controls:

- Per-asset cooldown.
- Maximum generation attempts.
- Admin or authenticated-only generation.
- Cached report first, LLM call second.
- Clear failure state when external providers or LLM calls fail.

## Recommended Implementation Order

1. Protect the generation endpoint.
2. Block failed evaluator results from being saved.
3. Split real `bull_summary`, `bear_summary`, and `risk_summary`.
4. Add structured `ReportFacts`.
5. Add Bull, Bear, Risk, and Fact Checker nodes.
6. Introduce asset-category templates.
7. Expand database fields after confirming migration strategy.
8. Update frontend report rendering for richer sections and metadata.

## Implementation Progress

### 2026-05-30 Phase 1 Safety Gate

Implemented in `docs/harness/report-quality-phase-1.md`.

Completed:

- Protected `POST /api/ai/generate/{ticker}` with authentication.
- Added an explicit first authorization policy: authenticated app users may trigger manual generation until roles/admin fields exist.
- Updated the asset detail generation call to send the authenticated bearer token.
- Blocked failed evaluator results from being saved by raising a quality failure before DB writes.
- Added HTTP 422 failure responses for evaluator-rejected drafts.
- Exposed generation metadata on successful generation responses.
- Replaced placeholder summary behavior with structured bull and bear summaries.
- Added mocked tests for evaluator pass/fail paths.

Partially completed:

- Structured report facts are now built before the graph and passed into the synthesizer, but the full Bull/Bear/Risk/Fact Checker graph redesign remains future work.
- Risk summary is exposed in generation metadata, but not persisted because database field additions need migration confirmation.

Deferred:

- Database schema expansion for quality fields.
- Admin-only generation policy, unless user roles or permissions are added.
- Independent evaluator model/provider separation.
- Frontend rendering for persisted rich metadata.

### 2026-05-30 Phase 2 Structured Facts

Implemented in `docs/harness/report-quality-phase-2.md`.

Completed:

- Added asset-category fact requirements for US stocks, Korean stocks, indices, US/Korean bonds, commodities, and crypto.
- Expanded `ReportFacts` with requirements, market metadata, missing required facts, source timestamps, confidence labels, and asset-specific data limitations.
- Added structured provider payloads for FMP, Finnhub, and CoinGecko while preserving existing string helper compatibility.
- Passed provider facts into graph state as `financial_facts`, `news_facts`, and `macro_facts`.
- Updated synthesizer prompts to consume normalized report facts and provider facts before writing.
- Added mocked/no-network tests for missing required facts and provider missing/unsupported states.

Partially completed:

- Asset requirements identify gaps, but they do not yet hard-fail generation before the LLM step.
- Provider facts are available to the graph but not persisted to the database.

Deferred:

- Strong enforcement via a dedicated `data_collector_node` or `fact_checker_node`.
- UI rendering of missing required facts and provider source metadata.
- Database fields for source and quality metadata.

### 2026-05-30 Fact Checker Node

Implemented in `docs/harness/report-quality-fact-checker.md`.

Completed:

- Added a deterministic `fact_checker_node` between `writer_node` and `evaluator_node`.
- Added graph routing so unsupported numeric claims return to `writer_node` with feedback before evaluator review.
- Added revision-limit handling so repeated fact checker failure ends as `is_pass=false` and is blocked by the service quality gate.
- Exposed `fact_check_pass` and `fact_check_feedback` in generation metadata.
- Added node-level tests for supported numbers, unsupported numbers, and revision-limit routing.

Partially completed:

- The fact checker validates numeric support only. It does not yet validate unsupported qualitative claims.

Deferred:

- Dedicated Bull, Bear, and Risk agent nodes.
- LLM or retrieval-backed qualitative fact checking.

### 2026-05-31 Phase 4 Role Preparation Nodes

Implemented in `docs/harness/report-quality-role-nodes.md`.

Completed:

- Added cost-neutral `bull_agent_node`, `bear_agent_node`, and `risk_officer_node` after `synthesizer_node`.
- Routed the graph so structured facts are separated into positive scenario, negative scenario, and risk/uncertainty views before writing.
- Updated the writer prompt to consume `bull_thesis`, `bear_thesis`, and `risk_review` alongside `structured_facts`.
- Exposed role outputs in generation metadata and used thesis outputs for saved bull/bear summaries when available.
- Added mocked node tests for separated role outputs without real LLM or provider calls.

Partially completed:

- The role nodes are deterministic preparation nodes, not additional LLM-backed debate agents, so this improves structure without increasing generation token cost.

Deferred:

- Fully independent LLM-backed Bull, Bear, and Risk agents.
- Qualitative claim fact checking.
- Database persistence for role outputs and risk review fields.

### 2026-05-31 Asset-Specific Analysis Frameworks

Implemented in `docs/harness/report-quality-asset-frameworks.md`.

Completed:

- Added deterministic asset-category analysis frameworks for US stocks, Korean stocks, indices, US/Korean bonds, commodities, and crypto.
- Attached the selected framework to `report_facts.analysis_framework` before graph execution.
- Preserved the framework in structured facts and passed it directly to the writer prompt.
- Exposed the selected framework in generation metadata for newly generated reports.
- Added mocked tests for Korean stock and crypto framework selection without provider or LLM calls.

Partially completed:

- The writer is instructed to follow the framework in the fixed "자산군별 분석" section, but there is not yet a deterministic post-write section validator.

Deferred:

- Hard rejection when category-specific required facts are missing.
- UI rendering of the selected framework and data limitations.

### 2026-05-31 Fixed Format Validator

Implemented in `docs/harness/report-quality-format-validator.md`.

Completed:

- Added a deterministic `report_format_validator_node` after `writer_node` and before numeric fact checking.
- Added graph routing so drafts missing required fixed-template sections are sent back to `writer_node` with feedback.
- Added revision-limit handling so repeated format failure ends as `is_pass=false` and is blocked by the service quality gate.
- Exposed `format_check_pass` and `format_check_feedback` in generation metadata.
- Added node-level tests for complete template pass, missing-section retry, and revision-limit end routing.

Partially completed:

- The validator checks presence of the 10 fixed report sections, but it does not yet validate the quality or completeness of each section.

Deferred:

- Deterministic validation that the "자산군별 분석" section covers every selected `analysis_framework.required_sections` item.
- UI rendering of format-check feedback on generation failure.

### 2026-05-31 Asset Framework Format Validation

Implemented in `docs/harness/report-quality-framework-format-validation.md`.

Completed:

- Extended `report_format_validator_node` to check selected `analysis_framework.required_sections` topics.
- Drafts that contain all 10 fixed sections but omit required asset-framework topics now route back to `writer_node`.
- Added format feedback that distinguishes missing fixed sections from missing asset-framework topics.
- Added node-level tests for framework-topic pass and fail cases.

Partially completed:

- The validator checks that framework topic labels appear in the final report. It does not judge analytical depth inside each topic.

Deferred:

- UI rendering of format-check feedback on generation failure.
- More semantic validation of framework topic coverage.

## Verification Plan

Use narrow verification first.

- Backend syntax check: `py -m compileall backend\app`
- Mocked graph tests for evaluator pass/fail behavior.
- Mocked service tests for `generate_report_for_ticker`.
- Frontend build after response shape changes: `npm run build` from `frontend/`.

Avoid real LLM calls in ordinary tests. Run live LLM generation only as a deliberate manual smoke test with known cost and provider limits.

## Follow-Up Risks

- Free data providers may be sparse for Korean assets, bonds, commodities, and macro tickers.
- Stronger source requirements may expose provider gaps that the UI must explain.
- Database schema changes need a migration plan.
- Higher-quality multi-agent workflows can increase token usage unless guarded by caching and cooldowns.
- Legal/compliance language should be reviewed before presenting outputs as investment advice.

## Related Feature Docs

- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/market-data.md`
- `docs/harness/latest-context-report-quality.md`
