# Chatbot Assistant Feature Notes

Date: 2026-05-31

## Current Behavior

The app now has a global chatbot launcher in the bottom-right corner of every frontend route. The first implementation is a rule-based financial navigation and explanation assistant. It does not store server-side conversations, does not stream responses, does not call an LLM, and does not trigger AI report generation.

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
- Asset/category/route helpers: `backend/app/services/chat_tools.py`
- Router registration: `backend/app/main.py`
- Tests added for future verification: `backend/tests/test_chat_service.py`, `backend/tests/test_chat_api.py`

## Data Flow

1. `ChatbotLauncher` is mounted once inside the app shell.
2. The launcher reads React Router location and auth state.
3. `buildChatContext` extracts `current_path`, detail/market ticker, category, and authenticated state.
4. `chatStore.sendMessage` appends a user message to session memory and posts to `POST /api/chat/message`.
5. The backend parses optional JWT state through `get_optional_current_user`.
6. `chat_service.handle_chat_message` classifies the request, resolves candidates through `chat_tools`, and returns `ChatResponse`.
7. Phase 2-style market explanations reuse `market_cache` or `fetch_latest_asset_context` with the existing TTL policy.
8. Phase 3-style saved report summaries query the latest stored `AIReport` only for authenticated users. They do not call `POST /api/ai/generate/{ticker}`.
9. The frontend renders assistant text, candidate chips, disclaimer text, and action buttons.
10. Clicking an action calls `navigate(action.url)` and closes the panel.

## Contracts

- Chat endpoint: `POST /api/chat/message`
- Endpoint auth policy: public. A valid JWT can enrich auth-aware responses; missing or invalid JWT is treated as unauthenticated for chat.
- Request fields:
  - `message`: required, 1-500 characters
  - `current_path`: current frontend path
  - `context.ticker`: optional decoded ticker from route context
  - `context.category`: optional category route key
  - `context.authenticated`: browser auth state hint
  - `conversation_id` and `client_message_id`: client session identifiers only
- Response fields:
  - `answer`, `intent`, `confidence`
  - `actions[]` with `type`, `label`, `url`, `reason`, `confidence`, `requires_auth`
  - `cards[]` for asset or context candidates
  - `requires_auth`, `safe_completion`, `disclaimer`
- Supported action types in Phase 1: `navigate`, `login`, and candidate-like navigate actions.
- Chat intents include asset detail navigation, market snapshot navigation, category navigation, report help, community help, auth help, favorite help, market summary, current page help, non-financial, and unknown.

## Change Rules

- Do not make chatbot messages trigger report generation or other cost-bearing LLM workflows without explicit product approval.
- Do not add server-side conversation storage without privacy, retention, and deletion design.
- Keep protected data access auth-aware. Public users may receive guidance, but saved report summaries require a valid user.
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

## Open Risks

- The rule-based Korean/English alias dictionary is intentionally small and may need expansion as supported assets grow.
- Market summary can only explain what the current cache or latest-context service can provide.
- Invalid JWTs are ignored for chat guidance, which improves UX but means protected-data branches must continue checking `current_user`.
- Frontend chat does not yet have automated component tests.
- The existing `AssetDetail.jsx` may auto-generate reports when authenticated users open detail pages; the chatbot itself does not trigger that endpoint.
