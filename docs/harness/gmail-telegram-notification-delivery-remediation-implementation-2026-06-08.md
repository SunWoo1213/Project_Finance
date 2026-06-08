# Gmail/Telegram 알림 발송 보강 구현 기록

Date: 2026-06-08

관련 계획: `docs/harness/gmail-telegram-notification-delivery-remediation-plan-2026-06-08.md`

## Objective

Gmail API와 Telegram 외부 알림 발송 경로가 실패할 때 원인을 더 쉽게 진단하고, Telegram 연결 contract를 현재 구현인 수동 `chat_id` 방식과 일치시키며, 깨진 알림 테스트를 복구한다.

## Files Changed

- `backend/app/services/notification_service.py`
- `backend/app/api/notifications.py`
- `backend/app/schemas.py`
- `backend/tests/test_notification_service.py`
- `backend/tests/test_notifications_api.py`
- `frontend/src/pages/MyPage.jsx`
- `docs/harness/features/favorite-asset-notifications.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/feature-index.md`
- `docs/harness/gmail-telegram-notification-delivery-remediation-implementation-2026-06-08.md`

## Behavior Changes

- `notification_service.get_delivery_configuration_status()`를 추가해 secret 값 없이 delivery 설정 상태를 확인할 수 있게 했다.
  - `scheduler.enabled`
  - `email.provider`, `email.configured`, `email.missing_keys`
  - `telegram.configured`, `telegram.missing_keys`, `telegram.verification_mode`
- `POST /api/notifications/test` 응답에 `delivery_status`를 포함한다. 실제 token/client secret 값은 반환하지 않고 누락된 환경 변수 이름만 반환한다.
- Gmail 발송 실패 메시지를 더 명확히 분류했다.
  - `EMAIL_PROVIDER must be gmail.`
  - `Gmail email settings are incomplete: ...`
  - Gmail OAuth/API HTTP 오류는 provider, HTTP status, sanitized 원인 문자열로 요약한다.
- Telegram Bot API `HTTPError`도 sanitized provider 오류로 저장한다.
- Telegram 연결 API의 안내 문구를 `/start <code>` 자동 webhook 방식에서 수동 `chat_id` 입력 방식으로 정정했다.
- `TelegramVerifyRequest.chat_id`는 숫자 문자열만 허용하도록 제한했다. 음수 chat id도 허용한다.
- `backend/tests/test_notifications_api.py`의 깨진 문자열을 복구하고 API 테스트 파일을 정리했다.
- Telegram 수동 contract, 비숫자 `chat_id` 거부, delivery configuration status, Telegram token 누락 시 retry limit 이후 failed 처리 테스트를 추가했다.
- MyPage Telegram 연결 요청 후 backend가 반환한 수동 `chat_id` 안내 메시지를 최종 상태 메시지로 표시하도록 보강했다.

## Verification Performed

```powershell
cd backend
python -m pytest tests/test_notifications_api.py tests/test_notification_service.py
```

결과:

- `10 passed`
- 경고: SQLAlchemy/Python `datetime.utcnow()` deprecation warning이 발생했다. 이번 변경 범위 밖이며 기존 시간 처리 방식에서 나온다.

```powershell
cd frontend
npm.cmd run lint
npm.cmd run build
```

결과:

- `npm.cmd run lint`: passed
- `npm.cmd run build`: passed
- Vite chunk size warning이 발생했다. 이번 변경 범위 밖의 번들 크기 경고다.

## Commands Not Run

- Gmail/Telegram 실제 발송 smoke는 실행하지 않았다. 실제 provider credential과 외부 네트워크 호출이 필요하다.
- `.env`는 secret 보호 규칙에 따라 읽지 않았다.
- Alembic migration은 schema 변경이 없어 실행하지 않았다.

## Follow-up Risks

- 운영에서 자동 알림을 쓰려면 `ENABLE_SCHEDULER=true`와 `ENABLE_NOTIFICATION_SCHEDULER=true`가 모두 필요하다.
- Gmail은 `EMAIL_PROVIDER=gmail`, `EMAIL_FROM_ADDRESS`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`이 모두 필요하며 OAuth scope에 `https://www.googleapis.com/auth/gmail.send`가 있어야 한다.
- Telegram은 이번 구현에서 webhook 자동 검증을 만들지 않았다. 현재 방식은 사용자가 bot과 대화를 시작한 뒤 숫자 `chat_id`를 알아내서 직접 입력하는 수동 방식이다.
- `frontend/src/pages/MyPage.jsx`는 기존 파일에 깨진 표시 문자열이 많다. 이번 변경은 Telegram 상태 메시지 경로만 좁게 보강했다.

## AI Report Generation Rule

이번 변경은 알림 평가/발송 경로와 테스트만 수정했다. 사용자 요청, 챗봇 요청, 알림 발송은 새 AI report 생성을 트리거하지 않고 저장된 scheduled report와 market/news cache만 읽는 기존 규칙을 유지한다.
