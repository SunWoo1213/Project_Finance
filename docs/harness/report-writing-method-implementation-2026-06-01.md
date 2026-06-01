# Report Writing Method Implementation

Date: 2026-06-01

## Objective

Start implementing `docs/harness/report-writing-method-implementation-plan-2026-06-01.md` without changing the scheduled-only report generation policy.

This implementation slice focuses on deterministic report structure:

- Build a fact matrix before readiness grading.
- Store fact matrix metadata with generated report metadata.
- Build a research packet before the writer node.
- Persist and serve the research packet through existing `metadata_json`.
- Render packet blocks in `ReportCard.jsx`.
- Let chatbot report summaries prefer stored packet content when available.

## Files Changed

- `backend/app/services/ai_service.py`
- `backend/app/services/graph/state.py`
- `backend/app/services/graph/nodes.py`
- `backend/app/services/graph/graph.py`
- `backend/app/services/chat_service.py`
- `frontend/src/components/ReportCard.jsx`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/chatbot-assistant.md`
- `docs/harness/feature-index.md`

## Behavior Changes

- `_build_report_facts` now creates `fact_matrix` entries for required and optional asset facts.
- Report readiness now derives missing required facts from the fact matrix and exposes `fact_matrix_summary`.
- Blocked readiness metadata includes a minimal research packet explaining why generation stopped.
- The LangGraph pipeline now runs `research_packet_node` after Bull, Bear, and Risk nodes and before `writer_node`.
- `writer_node` receives `research_packet` and is instructed to stay within packet entries, evidence IDs, source table, and limitations.
- Successful report metadata includes:
  - `fact_matrix`
  - `fact_matrix_summary`
  - `research_packet`
  - `source_table`
- `ReportCard.jsx` renders packet sections for base case, risk review, bull case, bear case, catalysts, and watchlist when stored metadata contains them.
- Chatbot report summaries still read only stored `AIReport` rows, but now prefer packet base-case and risk-review snippets when metadata is available.

## User-Facing Generation Rule

User-facing requests still do not trigger report generation.

Users and the chatbot continue to read stored scheduled reports only. Missing reports must remain pending, not-covered, blocked, or quality-failed states without invoking LLM-backed generation.

## Verification

No verification commands were run because the user explicitly requested implementation without verification.

Not run:

- Backend compile checks
- Backend tests
- Frontend lint
- Frontend build
- Browser/manual UI inspection

## Follow-Up Risks

- The fact matrix is intentionally conservative and may mark more required facts as missing than the older selected checks.
- The research packet is deterministic from available structured facts and role outputs, but prior-report delta is still a placeholder until a deterministic delta extractor is added.
- Packet evidence IDs are compact references to source-table rows, not full claim-level citations yet.
- Existing reports without `metadata_json.research_packet` still render through the previous Markdown fallback.
