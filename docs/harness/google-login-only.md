# Google-Only Login Change Record

Date: 2026-05-30

## Objective

Convert authentication so users can sign in only with Google. The app still issues its own JWT after the backend verifies the Google Identity Services ID token.

## Behavior Changes

- Local credential registration is no longer exposed from the frontend.
- The `/register` frontend route has been removed.
- The login screen renders only a Google sign-in button.
- The frontend sends the Google `credential` to `POST /api/auth/google`.
- The backend verifies the Google ID token and issues the existing app JWT.
- Existing protected API behavior can continue using the app JWT in the `Authorization: Bearer ...` header.
- The backend user model no longer maps legacy local credential columns.

## Files Changed

- `AGENTS.md`
  - Added the harness change-record rule.
- `backend/app/api/auth.py`
  - Replaced local credential register/login handlers with Google ID token login.
- `backend/app/api/deps.py`
  - Updated OAuth bearer metadata token URL to `/api/auth/google`.
- `backend/app/core/config.py`
  - Added `GOOGLE_CLIENT_ID`.
- `backend/app/core/security.py`
  - Removed local credential hashing helpers and kept JWT creation only.
- `backend/app/models.py`
  - Added `google_sub`.
  - Removed legacy local credential/provider fields from the ORM model.
- `backend/app/schemas.py`
  - Added Google login request and auth token response schemas.
  - Removed the local credential registration request schema.
- `backend/requirements.txt`
  - Added `google-auth`.
  - Removed local credential hashing dependencies.
- `frontend/src/pages/Login.jsx`
  - Replaced the old local credential form with Google Identity Services button.
- `frontend/src/App.jsx`
  - Removed the `/register` route.
- `frontend/src/pages/Register.jsx`
  - Removed the route component.
- `frontend/src/components/Header.jsx`
  - Removed the signup link.
- `frontend/src/utils/validationSchemas.js`
  - Removed old local credential form schemas.
- `frontend/src/components/ui/InputField.jsx`
  - Removed the unused legacy form input component.
- `frontend/package.json`, `frontend/package-lock.json`
  - Removed form-validation dependencies that were only used by legacy local credential forms.

## Required Environment

Backend:

```text
GOOGLE_CLIENT_ID=<Google OAuth Web Client ID>
```

Frontend:

```text
VITE_GOOGLE_CLIENT_ID=<Google OAuth Web Client ID>
```

Do not commit actual values.

## Database Follow-Up

This repository does not currently use Alembic migrations. Existing databases need the `users` table updated before Google login can run against them.

For PostgreSQL, the intended shape is:

```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS google_sub VARCHAR UNIQUE;
ALTER TABLE users DROP COLUMN IF EXISTS hashed_password;
ALTER TABLE users DROP COLUMN IF EXISTS auth_provider;
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_sub ON users (google_sub);
```

If the app is running against a fresh database, `Base.metadata.create_all` can create the new columns automatically.

## Security Notes

- The backend verifies the Google ID token audience against `GOOGLE_CLIENT_ID`.
- The backend rejects unverified Google emails.
- The stable Google user identifier is `sub`, stored as `google_sub`.
- The app does not trust a raw email or profile payload sent directly by the frontend.

## Verification Performed

- `py -m compileall backend\app`: passed.
- `npm.cmd run build`: passed after rerunning outside the sandbox because the first attempt failed with `spawn EPERM`.
- `npm.cmd run lint`: not fully passing because of pre-existing project issues:
  - `frontend/tailwind.config.js`: `require` is not defined.
  - `frontend/src/pages/AssetDetail.jsx`: existing hook dependency warning.

## Future Harness Notes

- Do not reintroduce local credential login unless the user explicitly requests it.
- If auth tests are added, mock Google token verification instead of calling Google.
- If database migrations are introduced later, convert the SQL in this document into a proper migration.
- If local login fails with a missing column error, apply the database follow-up before debugging frontend code.
