# Authentication Feature Notes

Date: 2026-05-30

## Current Behavior

Authentication is currently Google-only. The frontend renders Google Identity Services on the login page, sends the Google credential to the backend, and stores the app-issued JWT for authenticated API calls.

Local email/password registration and login are not part of the current UI flow. Older project specs may still describe local credentials, but the current code and change record supersede that behavior.

## Ownership Map

- Frontend route: `frontend/src/App.jsx`
- Login screen: `frontend/src/pages/Login.jsx`
- Header auth links/state display: `frontend/src/components/Header.jsx`
- Client auth state: `frontend/src/store/authStore.js`
- Backend auth router: `backend/app/api/auth.py`
- Current-user dependency: `backend/app/api/deps.py`
- Optional current-user dependency for public routes and subscription entitlement dependencies: `backend/app/api/deps.py`
- JWT helper: `backend/app/core/security.py`
- Config variable names: `backend/app/core/config.py`
- User storage shape: `backend/app/models.py`
- Auth request/response schemas: `backend/app/schemas.py`

## Data Flow

1. User opens `/login`.
2. Google Identity Services returns a credential to the browser.
3. `Login.jsx` posts the credential to `POST /api/auth/google`.
4. The backend validates the token audience against the configured Google client ID.
5. The backend creates or updates the user record and returns the app JWT plus user metadata, including the numeric user id needed for owner-only community controls.
6. `authStore.js` keeps token and user data in Zustand and localStorage.
7. Protected API calls send `Authorization: Bearer <token>`.
8. JWTs with missing or non-numeric `sub` claims are rejected with HTTP 401 before any user lookup.
9. The chatbot endpoint now requires authenticated Pro entitlement. Missing or invalid chat tokens return 401, and authenticated users without Pro return 403.

## Contracts

- Frontend environment variable name: `VITE_GOOGLE_CLIENT_ID`
- Backend environment variable name: `GOOGLE_CLIENT_ID`
- Login endpoint: `POST /api/auth/google`
- Login response user metadata: `id`, `email`, `nickname`
- Protected report endpoint: `GET /api/reports/{ticker}`
- Tier entitlement behavior: report access requires active Plus or Pro, and chatbot access requires active Pro.
- Protected community write endpoints:
  - `POST /api/community/{asset_id}/comments`
  - `PUT /api/community/{asset_id}/comments/{comment_id}`
  - `DELETE /api/community/{asset_id}/comments/{comment_id}`
  - `POST /api/community/comments/{comment_id}/like`
  - `POST /api/community/comments/{comment_id}/report`
- Protected chatbot endpoint: `POST /api/chat/message`. It requires a valid JWT and active Pro entitlement.

Document variable names only. Do not write actual client IDs, JWT secrets, tokens, or `.env` contents into docs.

## Change Rules

- Do not reintroduce local credential screens or password hashing unless the user explicitly requests that product change.
- Auth changes should inspect frontend state, backend token creation, current-user dependency, and DB user fields together.
- Database shape changes are risky because this repository does not currently have Alembic migrations.
- Tests should mock Google verification rather than calling Google.

## Verification

- Backend syntax/import check: `py -m compileall backend\app`
- Frontend build check from `frontend/`: `npm run build`
- If auth UI changes: run or visually inspect the login route.
- If protected endpoints change: test token-required and no-token paths.

## Change Records

- `docs/harness/harness-feature-documentation.md`
- `docs/harness/google-login-only.md`
- `docs/harness/community-comment-reporting.md`
- `docs/harness/feature-implementation-fixes-2026-05-31.md`
- `docs/harness/feature-implementation-fixes-verification-2026-05-31.md`
- `docs/harness/chatbot-feature-implementation-2026-05-31.md`
- `docs/harness/subscription-tier-payment-plan-2026-06-01.md`
- `docs/harness/subscription-tier-payment-implementation-2026-06-01.md`

## Open Risks

- Existing databases may still need manual schema alignment for `users.google_sub`.
- Auth tests are not yet documented as present.
- Frontend API base URLs are still hardcoded in some pages.
