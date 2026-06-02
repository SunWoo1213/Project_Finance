# MyPage Profile And Preferences Feature Notes

Date: 2026-06-02

## Current Behavior

`/mypage` is the authenticated account settings screen. It lets a Google-login user confirm a community nickname, manage account-synced favorite assets, and toggle Telegram or Google Mail notification consent.

Community comment creation requires `users.nickname_confirmed_at` to be set. Existing Google users keep their auto-generated nickname as a temporary display value until they confirm or save a nickname from MyPage.

The legacy `/settings/notifications` route now renders the same MyPage screen so notification settings remain reachable while the product uses one integrated account page.

## Ownership Map

- Frontend route: `frontend/src/App.jsx`
- MyPage screen: `frontend/src/pages/MyPage.jsx`
- Header entry point: `frontend/src/components/Header.jsx`
- Auth state: `frontend/src/store/authStore.js`
- Favorite state: `frontend/src/store/favoriteStore.js`
- Asset labels: `frontend/src/utils/constants.js`
- Backend profile router: `backend/app/api/profile.py`
- Nickname validation service: `backend/app/services/profile_service.py`
- Comment write gate: `backend/app/api/community.py`
- Backend models and schemas: `backend/app/models.py`, `backend/app/schemas.py`
- Migration: `backend/alembic/versions/20260602_0002_add_user_nickname_confirmed_at.py`

## Data Flow

1. Login responses include `nickname_confirmed` and `profile_complete`.
2. MyPage calls `GET /api/profile/me` to load profile state and notification preferences.
3. Nickname availability is checked with `GET /api/profile/nickname-availability?nickname=...`.
4. MyPage saves the nickname with `PATCH /api/profile/nickname`; the backend validates format, checks uniqueness, stores `nickname_confirmed_at`, and returns updated user metadata.
5. `authStore.updateUser` writes the updated nickname state to Zustand and localStorage.
6. Asset detail blocks comment submission locally when the user is authenticated but has no confirmed nickname.
7. `POST /api/community/{asset_id}/comments` enforces the same rule server-side and returns `NICKNAME_REQUIRED` when blocked.
8. MyPage reuses favorite sync APIs to add and remove favorite assets.
9. MyPage toggles `telegram_enabled` and `email_enabled` through `PUT /api/notifications/preferences`; this disables delivery consent without deleting connected channel records.

## Contracts

- Route: `/mypage`
- Legacy route alias: `/settings/notifications`
- Profile fetch: `GET /api/profile/me`
- Nickname availability: `GET /api/profile/nickname-availability`
- Nickname update: `PATCH /api/profile/nickname`
- Auth response fields: `nickname_confirmed`, `profile_complete`
- User storage field: `users.nickname_confirmed_at`
- Comment gate error code: `NICKNAME_REQUIRED`

Nickname rules:

- Trim leading and trailing whitespace.
- Collapse repeated whitespace to one space.
- Allow 2 to 20 characters.
- Allow Korean, English letters, numbers, spaces, `_`, and `-`.
- Treat the current user's own nickname as available.

## Change Rules

- Do not treat Google profile names as confirmed community nicknames.
- Keep comment read access public, and gate only comment creation on nickname confirmation.
- Do not delete Telegram or email channel connection records when a user turns off receiving consent.
- Do not store secrets or provider tokens in MyPage state or localStorage.
- If nickname rules change, update both `profile_service.py` and this feature document.

## Verification

- Backend focused tests: `python -m pytest tests/test_profile_api.py`
- Frontend checks: `npm run lint`, `npm run build`
- Manual UI check: login, open `/mypage`, check and save nickname, return to an asset detail page, post a comment, add/remove favorite assets, toggle Telegram/Google Mail consent.

## Change Records

- `docs/harness/mypage-profile-implementation-2026-06-02.md`
- `docs/harness/project-gap-remediation-plan-2026-06-02.md`

## Open Risks

- Existing databases need the new migration before running with `ENABLE_DB_SCHEMA_BOOTSTRAP=false`.
- Existing users will be asked to confirm a nickname before their next comment.
- `/settings/notifications` is currently an alias, but future product decisions may split notification channel verification back into a dedicated page.
