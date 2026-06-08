# Gmail OAuth refresh token 발급 절차 문서화 기록

Date: 2026-06-08

관련 기능 문서: `docs/harness/features/favorite-asset-notifications.md`

## Objective

운영 환경에서 `/api/notifications/channels/email/verify`가 `503`을 반환할 때 필요한 `EMAIL_FROM_ADDRESS`, `GMAIL_REFRESH_TOKEN` 발급 절차를 루트 문서로 정리했다. 실제 secret 값은 다루지 않고, Google Cloud OAuth 설정과 Render 환경변수 입력 절차만 문서화했다.

## Files Changed

- `GMAIL_OAUTH_REFRESH_TOKEN_SETUP.md`
- `docs/harness/features/favorite-asset-notifications.md`
- `docs/harness/feature-index.md`
- `docs/harness/gmail-oauth-refresh-token-setup-documentation-2026-06-08.md`

## Behavior Changes

- 코드 동작 변경 없음.
- 루트에 Gmail API 발송용 OAuth refresh token 발급 절차 문서를 추가했다.
- 문서는 `EMAIL_FROM_ADDRESS`가 발신 Gmail 주소이고, `GMAIL_REFRESH_TOKEN`은 `gmail.send` scope와 offline access 동의로 발급받는 secret임을 명시한다.
- Render 환경변수 설정과 `/api/notifications/channels/email/verify` `503` 응답 해석 기준을 정리했다.

## Verification Performed

- 문서 작성 작업이므로 pytest, lint, build는 실행하지 않았다.
- `.env` 파일은 읽지 않았고, 실제 secret 값은 확인하거나 기록하지 않았다.

## Follow-up Risks

- Google OAuth consent screen이 `External + Testing` 상태이면 refresh token 수명이 제한될 수 있다. 운영 장기 사용 전 Google OAuth 게시 상태와 민감 scope 검토 요구사항을 확인해야 한다.
- OAuth Playground redirect URI는 token 발급 후 운영 client의 authorized redirect URI 정책에 맞게 유지 여부를 판단해야 한다.
