# Gmail 단일 이메일 알림 전환 계획

Date: 2026-06-02

## Objective

관심자산 알림의 이메일 발송 경로를 Gmail로 단일화한다. 사용자는 Gmail을 통해서만 이메일을 보낼 예정이므로 SMTP, Resend, SendGrid 같은 별도 메일 provider를 운영 전제로 두지 않는다.

## Current Findings

- 현재 이메일 채널 모델과 API는 존재한다.
  - `POST /api/notifications/channels/email/verify`
  - `POST /api/notifications/channels/email/confirm`
  - `DELETE /api/notifications/channels/email`
  - `POST /api/notifications/test`
- `backend/app/services/notification_service.py`의 실제 이메일 발송 함수 `_send_email`은 `settings.EMAIL_PROVIDER == "smtp"`일 때만 동작한다.
- `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`은 `backend/app/core/config.py`, `.env_example`, `ENVIRONMENT_VARIABLE_SETUP.md`에 변수명으로 존재하지만, Gmail API 발송 구현은 아직 없다.
- 현재 이메일 인증 코드는 운영 이메일로 전송되지 않고, prototype 편의를 위해 API 응답의 `verification_code`로 반환된다.
- `docs/harness/features/mypage-profile.md`는 사용자 설정을 `Google Mail notification consent`로 설명하지만, 실제 발송 구현은 아직 Google Mail/Gmail API가 아니다.

## Target Behavior

1. 이메일 알림 provider는 Gmail API 하나만 지원한다.
2. `EMAIL_PROVIDER`를 유지한다면 허용값은 `gmail`만 둔다. 더 단순하게는 `EMAIL_PROVIDER`를 제거하고 Gmail 설정 존재 여부로 발송 가능성을 판단한다.
3. SMTP 관련 환경변수와 문서는 운영 필수값에서 제외한다.
4. 이메일 인증 코드는 `/api/notifications/channels/email/verify` 응답으로 노출하지 않고 Gmail로 전송한다.
5. 알림 이벤트 발송은 pending email event를 Gmail API로 전송하고, 실패 시 기존 `attempts`, `next_attempt_at`, `status`, `error_message` 재시도 흐름을 유지한다.
6. 사용자-facing 요청, 알림 평가, 알림 발송은 AI 리포트 생성을 직접 트리거하지 않는다. 이 변경은 이메일 delivery adapter만 다룬다.

## Implementation Plan

### Phase 1. 설정 경계 정리

- `backend/app/core/config.py`
  - Gmail API 발송에 필요한 변수만 남긴다.
  - 후보 변수: `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, `EMAIL_FROM_ADDRESS`.
  - `EMAIL_SMTP_HOST`, `EMAIL_SMTP_PORT`, `EMAIL_SMTP_USERNAME`, `EMAIL_SMTP_PASSWORD`, `EMAIL_SMTP_USE_TLS`는 제거하거나 deprecated 문서 상태로 낮춘다.
- `.env_example`
  - Favorite asset notifications 섹션에서 SMTP 설명과 placeholder를 제거한다.
  - `EMAIL_PROVIDER=gmail` 또는 provider 변수 제거 중 하나를 선택해 일관되게 적는다.
- `ENVIRONMENT_VARIABLE_SETUP.md`
  - `SMTP email` 절을 제거하거나 "지원하지 않음"으로 명시한다.
  - Gmail API 발급 절차를 실제 구현 기준 절차로 승격한다.

### Phase 2. Gmail 발송 adapter 구현

- `backend/app/services/notification_service.py`
  - `_send_email`을 Gmail API 기반 구현으로 교체한다.
  - OAuth refresh token으로 access token을 갱신한다.
  - MIME 메시지를 만들고 Gmail `users.messages.send` endpoint로 전송한다.
  - 외부 provider 오류는 `DeliveryResult(success=False, error_message=...)`로 반환해 기존 재시도 로직과 연결한다.
- 구현 방식 후보
  - 표준 라이브러리 `urllib.request`로 OAuth token refresh와 Gmail send를 직접 호출한다.
  - 또는 `google-auth`/`google-api-python-client` 의존성을 추가한다. 의존성 추가 시 `backend/requirements.txt`와 테스트 격리가 필요하다.
- 권장
  - 현재 서비스가 Telegram 전송도 표준 라이브러리로 처리하므로, 첫 구현은 표준 라이브러리로 좁게 추가한다. 필요해지면 Google SDK로 전환한다.

### Phase 3. 이메일 인증 코드 운영화

- `backend/app/api/notifications.py`
  - `request_email_verification` 응답에서 실제 `verification_code`를 반환하지 않는다.
  - 메시지는 "Gmail로 확인 코드를 보냈습니다."처럼 변경한다.
- `backend/app/services/notification_service.py`
  - `create_channel_verification` 이후 확인 코드를 Gmail로 발송하는 함수 또는 service 경로를 추가한다.
  - 인증 코드 발송 실패 시 channel connection을 pending으로 남길지, 실패 상태로 표시할지 정책을 정한다.
- `frontend/src/pages/NotificationsSettings.jsx`
  - 응답에서 `verification_code`를 자동으로 입력하는 prototype UI를 제거한다.
  - 사용자가 Gmail에서 받은 코드를 직접 입력하도록 한다.
- `frontend/src/pages/MyPage.jsx`
  - 현재 MyPage는 수신 동의 toggle 중심이므로, 채널 인증 UI가 필요하면 기존 route/컴포넌트 재사용 여부를 제품 결정으로 남긴다.

### Phase 4. 테스트와 회귀 보호

- `backend/tests/test_notifications_api.py`
  - 이메일 verify 응답이 code를 노출하지 않는지 확인한다.
  - Gmail 발송 함수를 mock/stub 처리해 실제 Gmail 호출 없이 검증한다.
- `backend/tests/test_notification_service.py`
  - pending email event가 Gmail adapter 성공 시 `sent`, 실패 시 retry/fail 상태로 바뀌는지 테스트한다.
- 외부 Gmail API 호출은 일반 테스트에서 금지한다.
- 알림 scheduler cadence나 AI report generation 설정은 변경하지 않는다.

### Phase 5. 문서 연결

- `docs/harness/features/favorite-asset-notifications.md`
  - Current Behavior에 Gmail 단일 provider 전환 결과를 반영한다.
  - Open Risks에서 prototype email code 노출 위험을 제거하거나 해결 상태로 바꾼다.
- `docs/harness/features/deployment-runtime.md`
  - notification email 환경변수 목록을 Gmail 전용으로 줄인다.
- `docs/harness/features/mypage-profile.md`
  - `Google Mail notification consent` 문구가 실제 Gmail API 발송과 일치하는지 확인한다.
- `docs/harness/feature-index.md`
  - 이 계획서와 구현 기록을 Favorite asset notifications 변경 기록에 연결한다.

## Files Expected To Change

- `backend/app/core/config.py`
- `backend/app/services/notification_service.py`
- `backend/app/api/notifications.py`
- `backend/tests/test_notifications_api.py`
- `backend/tests/test_notification_service.py`
- `.env_example`
- `ENVIRONMENT_VARIABLE_SETUP.md`
- `frontend/src/pages/NotificationsSettings.jsx`
- 필요 시 `frontend/src/pages/MyPage.jsx`
- `docs/harness/features/favorite-asset-notifications.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/features/mypage-profile.md`
- `docs/harness/feature-index.md`

## Verification Plan

Backend focused tests:

```powershell
cd backend
python -m pytest tests/test_notifications_api.py tests/test_notification_service.py
```

Frontend checks:

```powershell
cd frontend
npm run lint
npm run build
```

Manual smoke after real Gmail credentials are configured:

1. `ENABLE_NOTIFICATION_SCHEDULER=false`로 backend를 시작한다.
2. 로그인 후 이메일 채널 인증 요청을 보낸다.
3. Gmail 받은편지함에서 확인 코드를 받는다.
4. `/api/notifications/channels/email/confirm` 또는 UI에서 코드를 확인한다.
5. `POST /api/notifications/test`로 테스트 알림을 보내고 history에 `email` 이벤트가 `sent`로 남는지 확인한다.

## Commands Not Run

- 이 문서는 계획서 작성만 수행하므로 backend/frontend 테스트와 build는 실행하지 않았다.
- `.env`는 읽지 않았다. Gmail client secret, refresh token, SMTP password 같은 secret 값은 확인하거나 출력하지 않았다.

## Risks And Decisions Needed

- Gmail API OAuth scope는 발송 전용 최소 scope를 사용해야 한다. 권장 후보는 `https://www.googleapis.com/auth/gmail.send`이다.
- Gmail refresh token 발급 주체가 개인 계정인지 Workspace 계정인지 결정해야 한다.
- Gmail quota, 발신자 이름, reply-to, unsubscribe 문구, rate limit 정책이 운영 전에 필요하다.
- 확인 코드 메일과 실제 알림 메일의 제목/본문 템플릿을 정해야 한다.
- SMTP 변수를 즉시 제거하면 기존 로컬 설정이 깨질 수 있다. 제거 대신 deprecated 기간을 둘지 결정해야 한다.

## Linked Feature Docs

- `docs/harness/features/favorite-asset-notifications.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/features/mypage-profile.md`
