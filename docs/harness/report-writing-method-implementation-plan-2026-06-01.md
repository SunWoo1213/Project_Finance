# Report Writing Method Implementation Plan

Date: 2026-06-01

## Objective

Turn the finance-quality feedback in `docs/harness/report-writing-method-feedback-2026-06-01.md` into an implementation plan for future work.

This is a planning document only. No runtime code changes were made while creating it.

The target report model is a scheduled research-desk workflow:

- Backend jobs generate stored reports on a controlled cadence.
- Users and the chatbot read the latest stored `AIReport` only.
- The writer formats a pre-built research packet instead of inventing analysis.
- Required facts are audited through a deterministic fact matrix.
- Major claims carry evidence or explicit data-limit labels.
- The frontend renders the report as an inspectable research product, not only Markdown prose.

## Source Review

- `docs/harness/report-writing-method-feedback-2026-06-01.md`
- `docs/harness/report-generation-schedule-alignment-plan-2026-06-01.md`
- `docs/harness/report-generation-schedule-alignment-implementation-2026-06-01.md`
- `docs/harness/report-quality-improvement-plan.md`
- `docs/harness/report-quality-follow-up-plan-2026-05-31.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/chatbot-assistant.md`
- `docs/harness/features/market-data.md`
- `backend/app/services/ai_service.py`
- `backend/app/services/graph/state.py`
- `backend/app/services/graph/graph.py`
- `backend/app/services/graph/nodes.py`
- `backend/app/main.py`
- `backend/app/core/config.py`
- `frontend/src/pages/AssetDetail.jsx`
- `frontend/src/components/ReportCard.jsx`

`PROJECT_STRUCTURE_ANALYSIS.md` was referenced by the repository instructions but is not present in the current checkout.

## Current Baseline

Recent schedule-alignment work already changed the generation policy in the right direction:

- `POST /api/ai/generate/{ticker}` is still registered, but normal authenticated users receive `403` instead of triggering LLM work.
- `AssetDetail.jsx` no longer calls `POST /api/ai/generate/{ticker}` after a missing stored report.
- The scheduler uses `REPORT_SCHEDULER_INTERVAL_HOURS=6`.
- The scheduler seeds a small configured target set through `REPORT_SCHEDULER_TARGET_TICKERS`.
- `REPORT_SCHEDULER_TARGET_TICKERS` defaults to `DGS10,XAU,BTC-USD,NVDA,005930.KS`.
- `REPORT_SCHEDULER_MAX_REPORTS_PER_RUN` defaults to `5`.
- `REPORT_SCHEDULER_ASSET_COOLDOWN_HOURS` defaults to `6`.
- Chatbot report answers are documented as stored-report-only.

The remaining gap is report quality architecture. The system has deterministic readiness, role nodes, format validation, numeric checking, qualitative checking, and persisted metadata, but the report is still not fully built like a professional research packet.

## Planning Principles

1. Do not widen generation triggers while improving report quality.
2. Do not run live LLM generation in ordinary tests.
3. Treat provider gaps as first-class data limitations, not text the writer can smooth over.
4. Make every required fact traceable to a collector, status, freshness rule, and UI label.
5. Keep the writer constrained to structured input.
6. Add cost-increasing LLM critic behavior only behind explicit approval and disabled defaults.
7. Keep schema changes separate and confirm migration strategy before implementation.

## Phase 0: Preserve Scheduled-Only Generation Policy

Goal: make the current scheduled-only behavior the non-negotiable foundation for all later report-quality work.

Planned work:

- Add regression tests proving `AssetDetail.jsx` does not call `POST /api/ai/generate/{ticker}` when stored reports are missing.
- Add backend tests proving normal users cannot call `POST /api/ai/generate/{ticker}`.
- Keep chatbot report requests on stored `AIReport` reads only.
- Keep the five-ticker default catalog until broader LLM/API usage is explicitly approved.

Acceptance criteria:

- User-facing page loads never trigger report generation.
- Chatbot report requests never trigger report generation.
- Missing reports render a pending, not-covered, blocked, or quality-failed state without LLM work.

Likely files:

- `backend/app/main.py`
- `backend/app/services/chat_service.py`
- `frontend/src/pages/AssetDetail.jsx`
- `frontend/src/components/ReportCard.jsx`
- `backend/tests/test_chat_service.py`
- `backend/tests/test_chat_api.py`
- New or existing report scheduler/UI tests

## Phase 1: Define A Report Coverage Contract

Goal: make report availability intentional instead of implying every visible asset has an AI report.

Planned work:

- Promote the current scheduled target dictionary into a clearer `REPORT_COVERAGE_CATALOG` concept, either in code first or later as a DB-backed table.
- Store or expose:
  - ticker
  - display name
  - asset category
  - coverage tier
  - cadence
  - enabled flag
  - user-facing unavailable reason
- Define tier behavior:
  - Tier 1: always scheduled on the 6-hour cadence, subject to cooldown and cap.
  - Tier 2: scheduled less often or during low-cost windows after approval.
  - Tier 3: market data and news only, no AI report promise.
- Add a read contract so the frontend can distinguish `covered_pending`, `not_covered`, `blocked_insufficient_data`, and `quality_failed`.

Acceptance criteria:

- Every scheduled target has an `Asset` row before generation starts.
- The frontend does not promise AI reports for uncovered assets.
- Expanding coverage requires explicit product and cost approval.

Likely files:

- `backend/app/services/ai_service.py`
- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/app/schemas.py`
- `frontend/src/pages/AssetDetail.jsx`
- `frontend/src/components/ReportCard.jsx`
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`

## Phase 2: Replace Missing-List Readiness With A Fact Matrix

Goal: make data readiness auditable by asset class.

Planned work:

- Convert `ASSET_FACT_REQUIREMENTS` entries into fact definitions with:
  - `fact_key`
  - display label
  - asset categories
  - collector source
  - required or optional status
  - stale-after threshold
  - blocking severity
  - UI note
- Build `fact_matrix` during `_build_report_facts`.
- Give every expected fact one of four statuses:
  - `present`
  - `missing_optional_provider`
  - `missing_required`
  - `not_applicable`
- Compute readiness from the matrix instead of selected hardcoded checks.
- Ensure blocked readiness returns before graph or LLM invocation.

Acceptance criteria:

- Every required fact listed for an asset category has a deterministic status.
- `blocked` reports do not invoke LangGraph or the LLM.
- `limited` reports include limitations near the top of metadata and final report text.
- Tests cover at least one stock, one bond, one commodity, and one crypto readiness matrix.

Likely files:

- `backend/app/services/ai_service.py`
- `backend/app/services/external_api_service.py`
- `backend/app/services/market_service.py`
- `backend/app/services/graph/state.py`
- `backend/tests/test_ai_report_quality_gate.py`
- New fact-matrix tests if the existing test file becomes too broad

## Phase 3: Build A Research Packet Before Writing

Goal: make the writer a formatting step rather than the analytical source of truth.

Planned work:

- Extend graph state with a `research_packet` object.
- Build the packet before `writer_node` from structured facts and role outputs.
- Include:
  - `base_case`
  - `bull_case`
  - `bear_case`
  - `risk_review`
  - `catalysts`
  - `watchlist`
  - `source_table`
  - `data_limitations`
  - `prior_report_delta`
- Require each packet entry to include evidence IDs or a limitation reason.
- Change `writer_node` prompt so it can only format packet contents.
- Preserve existing `bull_summary`, `bear_summary`, and `risk_summary` by deriving them from packet fields.

Acceptance criteria:

- The final Markdown can be regenerated from the packet without re-running analytical nodes.
- Bull, bear, base, risk, catalyst, and watchlist content is present before the writer runs.
- Unsupported scenarios say insufficient evidence instead of becoming vague prose.

Likely files:

- `backend/app/services/graph/state.py`
- `backend/app/services/graph/nodes.py`
- `backend/app/services/graph/graph.py`
- `backend/app/services/ai_service.py`
- `backend/tests/test_ai_report_quality_gate.py`

## Phase 4: Add Claim-Level Evidence Discipline

Goal: prevent unsupported professional-sounding claims.

Planned work:

- Add evidence IDs to structured facts and packet entries.
- Require high-risk claims to reference supporting evidence IDs.
- Extend qualitative checking to inspect:
  - regulation and ETF claims
  - institutional flow claims
  - earnings, guidance, margin, and valuation claims
  - policy, CPI, rate, and FX claims
  - inventory, supply-demand, on-chain, and liquidity claims
- Add a compact source table or evidence notes section to persisted metadata and final Markdown.
- Keep optional LLM critic mode disabled unless cost is approved.

Acceptance criteria:

- Unsupported high-risk qualitative claims fail validation.
- Numeric claims continue to fail if not found in structured facts or provider facts.
- Reports can explain missing evidence without turning it into a conclusion.

Likely files:

- `backend/app/services/graph/nodes.py`
- `backend/app/services/graph/state.py`
- `backend/app/services/ai_service.py`
- `backend/tests/test_ai_report_quality_gate.py`

## Phase 5: Persist And Serve The Research Packet

Goal: make the structured research output available to the frontend and chatbot after generation.

Planned work:

- Decide whether to store the packet in existing `metadata_json` or add first-class columns.
- Prefer using `metadata_json` for the first iteration if no query/index requirement exists.
- Add response fields for:
  - readiness and fact matrix summary
  - source table
  - base, bull, bear, and risk blocks
  - catalysts and watchlist
  - quality status and validation feedback
- Keep backward compatibility for `bull_summary`, `bear_summary`, and `final_content`.

Acceptance criteria:

- `GET /api/reports/{ticker}` returns enough metadata for a structured report card.
- Chatbot can summarize the stored packet without calling generation.
- Existing reports without packet metadata still render through Markdown fallback.

Likely files:

- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/app/main.py`
- `backend/app/services/ai_service.py`
- `backend/app/services/chat_service.py`
- `frontend/src/components/ReportCard.jsx`

Risk:

- Adding columns or changing stored report shape may require migration planning. Confirm before implementing schema changes.

## Phase 6: Upgrade The Report UI To A Research Card

Goal: show confidence, coverage, and limitations before polished Markdown.

Planned work:

- Render distinct unavailable states:
  - `not_covered`
  - `scheduled_pending`
  - `blocked_insufficient_data`
  - `quality_failed`
- Show top-level metadata:
  - report status
  - data as-of time
  - readiness
  - source coverage
  - missing required facts
- Render packet blocks:
  - base case
  - bull case
  - bear case
  - risk review
  - catalysts
  - watchlist
- Keep full Markdown as a lower-priority detailed narrative.
- Avoid direct buy/sell advice and keep disclaimer language visible.

Acceptance criteria:

- Users can tell why a report is unavailable.
- Users can inspect evidence coverage without reading the full Markdown.
- The UI does not imply unsupported investment advice.

Likely files:

- `frontend/src/components/ReportCard.jsx`
- `frontend/src/pages/AssetDetail.jsx`
- `frontend/src/utils/formatters.js` if shared formatting becomes necessary

## Phase 7: Verification And Documentation

Goal: make the implementation safe to ship and easy for future harness agents to continue.

Planned verification:

- Backend syntax check: `py -m compileall backend\app backend\tests`
- Backend tests:
  - normal users cannot manually generate reports
  - user-facing report fetch does not invoke generation
  - chatbot report answers read stored reports only
  - blocked readiness does not invoke graph or LLM
  - fact matrix statuses are computed by asset class
  - research packet construction is deterministic from structured facts
  - unsupported evidence-sensitive claims fail validation
- Frontend checks:
  - `npm.cmd run lint`
  - `npm.cmd run build`
  - manually inspect stored, pending, not-covered, blocked, and failed report states when feasible

Documentation required for implementation:

- Update `docs/harness/features/asset-detail-ai-community.md`.
- Update `docs/harness/features/chatbot-assistant.md` if chatbot report responses change.
- Update `docs/harness/features/market-data.md` if scheduler coverage or catalog behavior changes.
- Update `docs/harness/feature-index.md`.
- Add a focused implementation record under `docs/harness/`.
- State explicitly whether user-facing requests can trigger report generation. The target answer remains no.

## Recommended Implementation Order

1. Add regression coverage around scheduled-only behavior.
2. Define the report coverage contract and unavailable states.
3. Build the fact matrix and readiness calculation.
4. Build the research packet before `writer_node`.
5. Add evidence IDs and claim-level validation.
6. Persist and serve packet metadata.
7. Upgrade `ReportCard.jsx` to render the packet and clearer unavailable states.
8. Add broad verification only after the behavior is stable in focused tests.

## Commands Run For This Planning Step

- `git status --short`
- `rg --files -g DEVELOPMENT_DIRECTION.md -g ARCHITECTURE.md -g PROJECT_STRUCTURE_ANALYSIS.md`
- `Get-Content` for the feedback document, feature docs, related plans, and relevant code files
- `rg` searches for report-generation, writer, fact requirement, and report-card references

No lint, build, backend tests, frontend tests, or live LLM calls were run because this task requested a plan only.

## Follow-Up Risks

- Broader report coverage can materially increase LLM/API cost.
- Stronger fact requirements may reduce report availability until provider coverage improves.
- Packet persistence may require database migration strategy.
- Evidence-level validation can be over-strict if introduced too broadly; start with high-risk claim categories.
- Existing Korean text in some source and docs appears mojibake-encoded in this checkout, so text-facing edits should be handled carefully.

## User-Facing Generation Rule

User-facing requests must not trigger report generation. Users and the chatbot should read stored scheduled reports only. If no stored report exists, the product should return a clear pending, not-covered, insufficient-data, or quality-failed state without invoking LLM-backed generation.
