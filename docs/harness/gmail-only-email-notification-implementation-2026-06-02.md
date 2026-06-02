# Gmail 단일 이메일 알림 구현

Date: 2026-06-02

## Objective

`docs/harness/gmail-only-email-notification-plan-2026-06-02.md`에 따라 관심자산 알림의 이메일 발송 경로를 Gmail API로 단일화하고, 이메일 인증 코드가 API 응답으로 노출되던 prototype 흐름을 제거했다.

## Files Changed

- `backend/app/core/config.py`
- `backend/app/services/notification_service.py`
- `backend/app/api/notifications.py`
- `backend/app/schemas.py`
- `backend/tests/test_notifications_api.py`
- `backend/tests/test_notification_service.py`
- `frontend/src/pages/NotificationsSettings.jsx`
- `.env_example`
- `ENVIRONMENT_VARIABLE_SETUP.md`
- `docs/harness/features/favorite-asset-notifications.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/features/mypage-profile.md`
- `docs/harness/feature-index.md`

## Behavior Changes

- Email delivery now supports Gmail API only.
- SMTP settings were removed from backend settings and `.env_example`.
- `_send_email` refreshes a Gmail OAuth access token with `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, and `GMAIL_REFRESH_TOKEN`, builds a MIME message, and sends it through Gmail `users.messages.send`.
- `POST /api/notifications/channels/email/verify` no longer returns the actual verification code. It creates the pending verification code in the database and sends that code through Gmail.
- If Gmail verification delivery fails, the API returns `503` without exposing the code.
- `NotificationsSettings.jsx` no longer auto-fills the email verification code from the API response.
- Pending email notification events keep the existing retry/fail flow through `attempts`, `next_attempt_at`, `status`, and `error_message`.
- User-facing notification requests and delivery do not trigger AI report generation; this change only touches notification email delivery.

## Verification Performed

```powershell
cd backend
python -m pytest tests/test_notifications_api.py tests/test_notification_service.py
```

Result: passed, 6 tests.

```powershell
cd frontend
npm run lint
npm run build
```

Result: `npm.ps1` was blocked by the local PowerShell execution policy, so the same scripts were rerun with `npm.cmd`. `npm.cmd run lint` passed. `npm.cmd run build` passed with the existing Vite large chunk warning.

## Commands Not Run And Why

- Manual Gmail smoke was not run because real Gmail OAuth credentials are secrets and were not inspected.
- `.env` was not read.

## Follow-Up Risks

- Gmail refresh token 발급 주체, Workspace/개인 계정 정책, 발신자 이름, quota, unsubscribe 문구, rate limit 정책은 운영 전에 확정해야 한다.
- 실제 Gmail credential 설정 후 이메일 채널 인증과 `POST /api/notifications/test`를 수동 smoke로 확인해야 한다.
- Telegram webhook/polling 운영 흐름은 이 변경 범위 밖이다.

## Linked Feature Docs

- `docs/harness/features/favorite-asset-notifications.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/features/mypage-profile.md`
