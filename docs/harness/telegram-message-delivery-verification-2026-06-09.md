# Telegram 메시지 발송 로직 검증 기록

Date: 2026-06-09

관련 기능 문서: `docs/harness/features/favorite-asset-notifications.md`
사용자 절차서: `TELEGRAM_MESSAGE_RECEIVE_PROCEDURE.md`

## Objective

Telegram 알림 메시지가 정상적으로 발송될 수 있는지 현재 코드 기준으로 검증하고, 이후 하네스 엔지니어링에서 같은 경로를 재검증할 수 있는 절차를 남긴다.

## Scope

- 대상 기능: 즐겨찾기 자산 알림의 Telegram 외부 발송 채널
- 대상 코드:
  - `backend/app/api/notifications.py`
  - `backend/app/services/notification_service.py`
  - `backend/app/schemas.py`
  - `backend/tests/test_notifications_api.py`
  - `backend/tests/test_notification_service.py`
  - `frontend/src/pages/MyPage.jsx`
- 제외:
  - `.env` 값 확인 또는 출력
  - 실제 Telegram bot token, chat_id, webhook secret 기록
  - Telegram inbound webhook/polling 구현

## Current Logic Conclusion

현재 구현은 Telegram webhook 자동 수신 방식이 아니라 수동 `chat_id` 검증 방식이다.

정상 발송에는 아래 조건이 모두 필요하다.

1. 백엔드 환경변수 `TELEGRAM_BOT_TOKEN`이 설정되어 있다.
2. 사용자가 앱에서 `POST /api/notifications/channels/telegram/connect`로 연결 코드를 발급받았다.
3. 사용자가 Telegram bot과 먼저 대화해 bot이 메시지를 보낼 수 있는 상태가 됐다.
4. 사용자가 숫자 `chat_id`와 연결 코드를 `POST /api/notifications/channels/telegram/verify`로 제출해 `NotificationChannelConnection.verified=True` 상태를 만들었다.
5. 사용자의 알림 preference에서 `telegram_enabled=True`이다.
6. `POST /api/notifications/test` 또는 알림 scheduler가 Telegram `pending` 이벤트를 만들고 `send_pending_notifications()`가 실행된다.

이 조건을 만족하면 `notification_service._send_telegram()`은 Telegram Bot API `sendMessage`로 `chat_id`와 메시지 본문을 JSON POST한다. HTTP 2xx 응답이면 이벤트를 `sent`로 바꾸고, 실패하면 `attempts`를 증가시킨 뒤 3회 미만은 재시도 대기, 3회 이상은 `failed`로 확정한다.

## Verified Code Paths

### 연결 contract

- `backend/app/api/notifications.py`
  - `POST /api/notifications/channels/telegram/connect`
  - 응답 메시지는 `manual chat_id` 방식을 안내한다.
  - `/start <code>` 자동 webhook 수신을 암시하지 않는다.
- `backend/app/schemas.py`
  - `TelegramVerifyRequest.chat_id`는 `^-?\d+$` 패턴만 허용한다.
  - 개인 chat은 보통 양수, 그룹/슈퍼그룹은 음수 `chat_id`일 수 있으므로 음수도 허용한다.
- `backend/app/api/notifications.py`
  - `POST /api/notifications/channels/telegram/verify`
  - 연결 코드와 `chat_id`를 `verify_channel()`에 전달해 검증된 destination으로 저장한다.

### 발송 adapter

- `backend/app/services/notification_service.py`
  - `get_delivery_configuration_status()`는 Telegram 설정 상태를 secret 값 없이 반환한다.
  - Telegram token 누락 시 `missing_keys=["TELEGRAM_BOT_TOKEN"]`와 `configured=false`가 된다.
  - `_active_channels()`는 검증된 Telegram connection과 `preference.telegram_enabled`가 모두 참일 때만 Telegram 채널을 포함한다.
  - `create_test_notification()`은 현재 활성 채널로 테스트 이벤트를 만들고 즉시 `send_pending_notifications()`를 호출한다.
  - `send_pending_notifications()`는 verified connection이 없으면 `"Notification channel is not verified."`로 실패시킨다.
  - `_send_telegram()`은 `https://api.telegram.org/bot{token}/sendMessage`에 `{"chat_id": chat_id, "text": text}`를 POST한다.

### Frontend entry

- `frontend/src/pages/MyPage.jsx`
  - "수신 동의" 섹션에서 Telegram 연결 코드를 발급한다.
  - 사용자가 직접 `chat_id`를 입력하고 확인하면 verify endpoint를 호출한다.
  - 연결된 destination은 화면에서 마스킹된다.

## Deterministic Harness Verification

실제 Telegram API를 호출하지 않는 기본 검증이다. 외부 네트워크, bot token, 실제 사용자 `chat_id`에 의존하지 않는다.

작업 전에는 repository root에서 `git status --short`를 확인한다.

```powershell
git status --short
```

백엔드 알림 API/service 테스트는 `backend/`를 작업 디렉터리로 두고 실행한다.

```powershell
cd backend
python -m pytest tests/test_notifications_api.py tests/test_notification_service.py
```

검증 기대값:

- `test_telegram_connect_contract_uses_manual_chat_id_flow`
  - connect 응답에 연결 코드가 있다.
  - 안내 문구에 `manual chat_id`가 있다.
  - 안내 문구에 `/start` 자동 검증 안내가 없다.
- `test_telegram_verify_rejects_non_numeric_chat_id`
  - 비숫자 `chat_id`는 422로 거부된다.
- `test_delivery_configuration_status_reports_missing_settings_without_values`
  - Telegram token이 없을 때 누락 key 이름만 반환하고 secret 값은 노출하지 않는다.
- `test_send_pending_telegram_event_marks_failed_after_retry_limit`
  - Telegram token이 없으면 pending Telegram 이벤트가 3번째 시도에서 `failed`가 된다.

문서 변경만 검증하는 경우 frontend build는 필수는 아니다. UI 문구나 `MyPage.jsx`를 수정한 경우 아래를 추가한다.

```powershell
cd frontend
npm run lint
npm run build
```

## Optional Real Provider Smoke

실제 Telegram 수신까지 확인하려면 운영자 또는 로컬 개발자가 secret 값을 가진 환경에서만 수행한다. 하네스 응답이나 문서에 token, refresh token, chat_id 원문을 기록하지 않는다.

1. 백엔드 env에 `TELEGRAM_BOT_TOKEN`을 설정하고 백엔드를 재시작한다.
2. 사용자가 `TELEGRAM_MESSAGE_RECEIVE_PROCEDURE.md`에 따라 bot과 대화하고 숫자 `chat_id`를 확인한다.
3. 앱 `/mypage`에서 Telegram 코드를 발급하고 `chat_id`와 함께 확인한다.
4. Telegram 수신 토글을 켠다.
5. 인증된 사용자 세션으로 `POST /api/notifications/test`를 호출한다.

테스트 호출 전제:

- 호출 사용자는 Telegram 채널을 연결한 동일 계정이다.
- `Authorization: Bearer <access_token>` 헤더가 필요하다.
- `<access_token>`은 Google ID token이 아니라 frontend 로그인 후 `localStorage.token`에 저장되는 Project Finance 앱 JWT이다.
- token, `chat_id`, bot token 원문은 하네스 응답과 문서에 기록하지 않는다.

예시 payload:

```json
{
  "ticker": "TEST",
  "message": "Telegram 알림 수신 smoke test"
}
```

응답 해석:

- `delivery_status.telegram.configured=true`: 백엔드가 `TELEGRAM_BOT_TOKEN`을 읽고 있다.
- `delivery_status.telegram.missing_keys=[]`: Telegram 발송 env 누락이 없다.
- `created_events=0`: 활성 외부 채널이 없거나 같은 dedupe window에서 이미 테스트 이벤트가 생성됐을 가능성이 있으므로 `/mypage` 연결/토글 상태를 재확인한다.
- `sent_events>=1`: 이번 호출에서 외부 채널 발송이 성공했다.
- `failed_events>=1`: `/api/notifications/history`에서 Telegram 이벤트의 `error_message`를 확인한다.

성공 기준:

- 응답의 `delivery_status.telegram.configured`가 `true`이다.
- `sent_events`가 1 이상이거나, `/api/notifications/history`에서 Telegram 이벤트가 `sent`이다.
- Telegram 앱에서 테스트 메시지를 받는다.
- 최종 성공 기준은 push banner가 아니라 bot 대화방에 메시지가 실제로 도착했는지 여부다.

실패 시 우선순위:

1. HTTP `401 Unauthorized`이면 Telegram 발송 전 인증 실패다. 로그인 후 frontend `localStorage.token`의 앱 JWT를 다시 가져와 같은 backend URL에 보낸다.
2. `delivery_status.telegram.missing_keys`에 `TELEGRAM_BOT_TOKEN`이 있는지 확인한다.
3. 채널 connection이 `verified=True`이고 destination이 있는지 확인한다.
4. `telegram_enabled=True`인지 확인한다.
5. `/api/notifications/history` 또는 DB의 `NotificationEvent.error_message`에서 sanitized provider 오류를 확인한다.

## Remaining Risks

- Telegram inbound webhook/polling handler는 없다. 사용자가 bot에게 `/start <code>`를 보내는 것만으로는 앱 연결이 완료되지 않는다.
- `chat_id`는 개인정보로 취급해야 한다. 원문은 로그, 이슈, 하네스 응답, 문서에 남기지 않는다.
- `TELEGRAM_WEBHOOK_SECRET`은 현재 발송 경로에서 사용되지 않는다. webhook 방식으로 전환할 때만 별도 설계와 검증이 필요하다.
- 자동 알림 발송 scheduler는 `ENABLE_SCHEDULER=true`와 `ENABLE_NOTIFICATION_SCHEDULER=true`가 모두 필요하다. 수동 테스트 endpoint는 scheduler가 꺼져 있어도 즉시 발송 경로를 시도할 수 있다.

## Verification Performed

- `.env`는 secret 보호 규칙에 따라 읽지 않았다.
- 코드 정적 검토:
  - `backend/app/api/notifications.py`
  - `backend/app/services/notification_service.py`
  - `backend/app/schemas.py`
  - `backend/tests/test_notifications_api.py`
  - `backend/tests/test_notification_service.py`
  - `frontend/src/pages/MyPage.jsx`
- `python -m pytest tests/test_notifications_api.py tests/test_notification_service.py`
  - 결과: 실패. Windows App Execution Alias 환경에서 `Python was not found`가 반환되어 repository 가상환경 인터프리터로 재실행했다.
- `.\\.venv\\Scripts\\python.exe -m pytest tests/test_notifications_api.py tests/test_notification_service.py`
  - 작업 디렉터리: `backend/`
  - 결과: 10 passed, 60 warnings.
  - warning: 기존 `datetime.utcnow()` deprecation warning 및 `.pytest_cache` write 권한 warning. 테스트 assertion에는 영향 없음.

## AI Report Generation Rule

이 검증은 알림 발송 경로만 다룬다. 사용자 요청, 챗봇 요청, Telegram 테스트 발송은 새 AI 리포트 생성을 트리거하지 않는다. 알림 평가는 저장된 시장/news cache와 저장된 scheduled report만 읽어야 한다.
