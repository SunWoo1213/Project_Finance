# Chatbot Feature Implementation

Date: 2026-05-31

## Objective

Implement the chatbot feature plan as a safe navigation and data-explanation assistant, while avoiding DB conversation storage, LLM fallback, and automatic AI report generation.

## Files Changed

- `backend/app/schemas.py`
- `backend/app/api/deps.py`
- `backend/app/api/chat.py`
- `backend/app/main.py`
- `backend/app/services/chat_tools.py`
- `backend/app/services/chat_service.py`
- `backend/tests/test_chat_service.py`
- `backend/tests/test_chat_api.py`
- `frontend/src/App.jsx`
- `frontend/src/components/ChatbotLauncher.jsx`
- `frontend/src/components/ChatbotPanel.jsx`
- `frontend/src/components/ChatMessageList.jsx`
- `frontend/src/components/ChatActionCard.jsx`
- `frontend/src/store/chatStore.js`
- `frontend/src/utils/apiClient.js`
- `frontend/src/utils/chatContext.js`
- `docs/harness/features/chatbot-assistant.md`
- `docs/harness/feature-index.md`
- `docs/harness/features/authentication.md`
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/frontend-routing-shell.md`

## Behavior Changes

- Added `POST /api/chat/message` as a public endpoint with optional JWT parsing.
- Added chat request/response Pydantic schemas.
- Added a deterministic chat service for intent classification, asset/category resolution, safe response assembly, and app route action creation.
- Added Korean/English aliases for common assets, market snapshots, categories, reports, comments, login, favorites, and current-page help.
- Added non-financial scope refusal with a fixed message and no actions.
- Added auth-aware report guidance:
  - Unauthenticated users receive `/login` and detail-page actions.
  - Authenticated users can receive a short summary of an already stored report.
  - The chatbot never calls report generation.
- Added cache-based market summary and latest-context explanation paths.
- Added global frontend launcher, panel, message list, action cards, empty suggestions, loading state, error retry, clear, and mobile-friendly bottom-sheet behavior.
- Added session-only Zustand chat state. No chat data is persisted to the backend.
- Added a minimal chat-specific API client using `VITE_API_BASE_URL` with the localhost backend fallback.
- Added backend test files for future verification of service routing and API response shape.

## Verification Performed

None. The user explicitly requested no verification and implementation only.

## Commands Not Run

- `pytest tests/test_chat_service.py tests/test_chat_api.py`
- `python -m compileall app`
- `npm run lint`
- `npm run build`
- Browser/dev-server smoke checks

These were intentionally skipped per request.

## Follow-Up Risks

- Run the planned backend and frontend checks before merging or deploying.
- Expand alias coverage if users ask for more local names, tickers, or category phrases.
- Add frontend component tests if the project introduces a test runner.
- Keep protected report summary logic guarded by a real authenticated user, not only the browser `authenticated` hint.
- Do not add LLM fallback, report generation triggers, or persistent chat history without a separate risk review.

## Linked Feature Documents

- `docs/harness/features/chatbot-assistant.md`
- `docs/harness/features/frontend-routing-shell.md`
- `docs/harness/features/authentication.md`
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`
