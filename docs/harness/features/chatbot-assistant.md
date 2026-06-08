# Chatbot Assistant Feature Notes

Date: 2026-05-31

## Current Behavior

The app has a financial navigation and explanation assistant. By default it is rule-based: it does not store server-side conversations, does not stream responses, does not call an LLM, and does not trigger AI report generation. Report answers must continue to use the latest stored `AIReport`, matching the scheduled-report-only target documented in `docs/harness/report-generation-schedule-alignment-plan-2026-06-01.md`. Subscription behavior now limits chatbot visibility and API access to active Pro users only.

### Optional LLM intent path (2026-06-04)

When `ENABLE_LLM_CHATBOT=true` and `OPENAI_API_KEY` is set, the chatbot uses an LLM (`gpt-4o-mini`) to understand natural-language / typo / sentence-style questions and to answer more actively. The path is **grounding-based**: the backend deterministically gathers asset candidates, category, a cached market snippet (no network call), and — for authenticated users — an already-fetched *stored* report summary, then passes them to the LLM. The LLM only classifies intent, writes the answer from the supplied grounding, and selects which pre-built actions to surface. Action URLs are still built by the backend, so user-controlled navigation is preserved.

The LLM path never generates reports: there is no report-generation tool, and only stored `AIReport` summaries are passed in (AGENTS.md section 14). The frontend forwards recent turns as `history` for multi-turn context; the server does not persist them. Any failure (toggle off, missing key, LLM error/timeout, empty answer) falls back to the deterministic rule-based response, so behavior is unchanged when the toggle is off.

As of 2026-06-08 the multi-turn window is **10 turns (20 messages)**: the frontend sends the last 20 user/assistant messages (`chatStore.js` `slice(-20)`) and the backend trims to `CHATBOT_HISTORY_MAX_TURNS * 2` (default 10 → 20). Because history lives only in browser session memory and is never persisted server-side, clearing the chat (trash button → `clear()`) forgets the conversation completely.

The 2026-06-01 scheduler alignment implementation keeps this chatbot behavior unchanged: report generation is limited to the backend scheduler, and the chatbot reads stored reports only.

The 2026-06-03 `ENABLE_AI_REPORT_GENERATION` implementation also leaves chatbot behavior unchanged. The variable controls backend scheduled/background generation only; chatbot report answers still summarize stored `AIReport` rows and must not trigger generation.

Users can ask for assets, market snapshots, category lists, AI report help, community help, favorites, login help, current-page help, market summaries, and latest ticker context. The backend returns a short answer plus optional action buttons. The frontend only navigates after the user clicks an action button.

Non-financial questions return a fixed scope message and no actions.

## Ownership Map

- Frontend shell integration: `frontend/src/App.jsx`
- Launcher and panel UI: `frontend/src/components/ChatbotLauncher.jsx`, `frontend/src/components/ChatbotPanel.jsx`
- Message and action rendering: `frontend/src/components/ChatMessageList.jsx`, `frontend/src/components/ChatActionCard.jsx`
- Session-only chat state: `frontend/src/store/chatStore.js`
- Current route/auth context extraction: `frontend/src/utils/chatContext.js`
- Shared API client used by chat: `frontend/src/utils/apiClient.js`
- Backend router: `backend/app/api/chat.py`
- Optional auth dependency: `backend/app/api/deps.py`
- API contracts: `backend/app/schemas.py`
- Rule-based intent and response assembly: `backend/app/services/chat_service.py`
- Optional LLM intent understanding (grounding + structured output): `backend/app/services/chat_llm.py`
- Chatbot LLM config toggles (`ENABLE_LLM_CHATBOT`, `CHATBOT_LLM_MODEL`, `CHATBOT_HISTORY_MAX_TURNS`, `CHATBOT_LLM_TIMEOUT_SECONDS`): `backend/app/core/config.py`
- Asset/category/route helpers: `backend/app/services/chat_tools.py`
- Router registration: `backend/app/main.py`
- Tests added for future verification: `backend/tests/test_chat_service.py`, `backend/tests/test_chat_api.py`

## Data Flow

1. `App.jsx` renders `ChatbotLauncher` only when subscription entitlement includes `can_use_chatbot`.
2. The launcher reads React Router location and auth state.
3. `buildChatContext` extracts `current_path`, detail/market ticker, category, and authenticated state.
4. `chatStore.sendMessage` appends a user message to session memory and posts to `POST /api/chat/message`.
5. The backend requires chatbot entitlement through `require_chatbot_access`.
6. `chat_service.handle_chat_message` classifies the request, resolves candidates through `chat_tools`, and returns `ChatResponse`.
7. Phase 2-style market explanations reuse `market_cache` or `fetch_latest_asset_context` with the existing TTL policy.
8. Phase 3-style saved report summaries query the latest stored `AIReport` only for authenticated users. They prefer stored `metadata.research_packet` base-case and risk-review snippets when available, and they do not call `POST /api/ai/generate/{ticker}`.
9. The frontend renders assistant text, candidate chips, disclaimer text, and action buttons.
10. Clicking an action calls `navigate(action.url)` and closes the panel.

## Contracts

- Chat endpoint: `POST /api/chat/message`
- Tier behavior: active Pro required. Free and Plus users should not see the launcher, and backend rejects direct API calls.
- Endpoint auth policy: protected. Missing or invalid JWT returns 401; valid non-Pro users return 403.
- Request fields:
  - `message`: required, 1-500 characters
  - `current_path`: current frontend path
  - `context.ticker`: optional decoded ticker from route context
  - `context.category`: optional category route key
  - `context.authenticated`: browser auth state hint
  - `conversation_id` and `client_message_id`: client session identifiers only
  - `history`: optional recent turns (`role`/`content`) for LLM multi-turn context; server does not persist them
- Response fields:
  - `answer`, `intent`, `confidence`
  - `actions[]` with `type`, `label`, `url`, `reason`, `confidence`, `requires_auth`
  - `cards[]` for asset or context candidates
  - `requires_auth`, `safe_completion`, `disclaimer`
- Supported action types in Phase 1: `navigate`, `login`, and candidate-like navigate actions.
- Chat intents include asset detail navigation, market snapshot navigation, category navigation, report help, community help, auth help, favorite help, market summary, current page help, non-financial, and unknown.

## Change Rules

- Do not make chatbot messages trigger report generation or other cost-bearing LLM workflows without explicit product approval.
- Chatbot report answers must fetch and summarize the stored scheduled report. They must not generate a new report per user request. This applies to the LLM path too: never add a report-generation tool/action; only pass already-fetched stored report summaries as grounding.
- Keep the LLM path gated by `ENABLE_LLM_CHATBOT` (default off) with a deterministic rule-based fallback on any failure, so the chatbot keeps working without an LLM/API key.
- Any future audit, plan, or implementation that touches chatbot report behavior must create/update a `docs/harness/` record and link it from this feature doc.
- Do not add server-side conversation storage without privacy, retention, and deletion design.
- Keep protected data access entitlement-aware. Saved report summaries require an entitled user and must use stored report rows.
- Keep the assistant scoped to financial data, market information, reports, and Project Finance app navigation.
- Prefer deterministic rules and existing cache/service functions before adding external providers.
- Preserve user-controlled navigation. The backend should return actions, not directly move the browser.
- If ticker/category mappings change, keep `chat_tools.py`, frontend constants, market service groups, and feature docs aligned.

## Verification

Planned checks for future agents:

- Backend unit/API checks from `backend/`: `pytest tests/test_chat_service.py tests/test_chat_api.py`
- Backend import check: `python -m compileall app`
- Frontend build from `frontend/`: `npm run build`
- Frontend lint from `frontend/`: `npm run lint`
- Manual smoke: open `/`, send "삼성전자 보여줘", click the action, confirm `/detail/005930.KS`

For the 2026-05-31 implementation request, verification commands were intentionally not run because the user explicitly requested implementation and documentation only.

## Change Records

- `docs/harness/chatbot-feature-plan-2026-05-31.md`
- `docs/harness/chatbot-feature-implementation-2026-05-31.md`
- `docs/harness/chatbot-implementation-verification-2026-06-01.md`
- `docs/harness/report-generation-schedule-alignment-plan-2026-06-01.md`
- `docs/harness/report-generation-schedule-alignment-implementation-2026-06-01.md`
- `docs/harness/report-writing-method-implementation-plan-2026-06-01.md`
- `docs/harness/report-writing-method-implementation-2026-06-01.md`
- `docs/harness/subscription-tier-payment-plan-2026-06-01.md`
- `docs/harness/subscription-tier-payment-implementation-2026-06-01.md`
- `docs/harness/subscription-tier-payment-provider-db-implementation-plan-2026-06-01.md`
- `docs/harness/subscription-tier-payment-provider-db-implementation-2026-06-01.md`
- `docs/harness/project-gap-remediation-plan-2026-06-02.md`
- `docs/harness/project-defect-remediation-plan-2026-06-02.md`
- `docs/harness/report-generation-env-switch-plan-2026-06-03.md`
- `docs/harness/report-generation-env-switch-implementation-2026-06-03.md`
- `docs/harness/chatbot-llm-intent-upgrade-plan-2026-06-04.md`
- `docs/harness/chatbot-llm-intent-upgrade-implementation-2026-06-04.md`
- `docs/harness/chatbot-multiturn-10turns-implementation-2026-06-08.md`

## Open Risks

- The rule-based Korean/English alias dictionary is intentionally small and may need expansion as supported assets grow.
- Market summary can only explain what the current cache or latest-context service can provide.
- Invalid JWTs now fail the chat endpoint with 401 because chatbot access is Pro-only.
- Frontend chat does not yet have automated component tests.
- The chatbot is aligned with the stored-report rule, but report summaries are only available after the scheduler has produced a stored report for a configured target ticker.
- The LLM path (when enabled) incurs OpenAI cost per message. It is off by default, Pro-only, uses `gpt-4o-mini`, and limits history turns; consider a rate limit before high-traffic rollout. The cached market snippet is used without a network call, so empty cache means the LLM answers that it does not know rather than fabricating numbers.
