# Gmail/Telegram 알림 발송 장애 원인 분석 및 해결 계획

Date: 2026-06-08

## Objective

백엔드의 Google Mail(Gmail API) 및 Telegram 알림 발송 경로가 실제 운영/로컬 검증에서 제대로 작동하지 않는 원인을 코드 기준으로 분석하고, 안전하게 해결하기 위한 단계별 계획을 정의한다.

## Scope

- 대상 기능: 즐겨찾기 자산 알림의 `email`, `telegram` 외부 발송 채널
- 주요 코드:
  - `backend/app/services/notification_service.py`
  - `backend/app/api/notifications.py`
  - `backend/app/main.py`
  - `backend/app/core/config.py`
  - `backend/tests/test_notification_service.py`
  - `backend/tests/test_notifications_api.py`
  - `frontend/src/pages/MyPage.jsx`
- 제외:
  - `.env` 실제 값 확인
  - Gmail/Telegram 실계정 credential 출력
  - AI report scheduler cadence 변경
  - 일반 사용자 요청에서 AI report를 새로 생성하는 흐름

## Current Findings

1. Gmail 발송 adapter는 이미 구현되어 있다.
   - `notification_service._send_gmail_message()`가 OAuth refresh token으로 access token을 발급받고 Gmail `users.messages.send` API를 호출한다.
   - `send_email_verification_code()`는 이메일 인증 코드를 API 응답에 노출하지 않고 Gmail로 발송하도록 되어 있다.
   - 실패 시 `DeliveryResult(success=False, error_message=...)`로 반환하고, 인증 요청 API는 `503`을 반환한다.

2. Gmail 발송은 설정값 중 하나라도 빠지면 항상 실패한다.
   - 필수 설정명: `EMAIL_PROVIDER`, `EMAIL_FROM_ADDRESS`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`
   - `EMAIL_PROVIDER`는 `gmail`만 허용된다.
   - `.env`를 확인하지 않았으므로 실제 누락 여부는 단정하지 않지만, 현재 코드상 가장 흔한 실패 메시지는 `Gmail email settings are incomplete.` 또는 Gmail OAuth/API HTTP 오류다.

3. Telegram 발송 adapter는 단순 `sendMessage` 호출만 있다.
   - `notification_service._send_telegram()`은 `TELEGRAM_BOT_TOKEN`과 저장된 `chat_id`로 Telegram Bot API `sendMessage`를 호출한다.
   - Telegram bot webhook/polling으로 `/start <code>`를 받아 자동 검증하는 백엔드 엔드포인트는 없다.
   - 현재 UI는 사용자가 `chat_id`를 직접 알아내서 입력해야 하므로, 사용자가 bot에게 코드를 보냈더라도 백엔드가 그 메시지를 자동 수신하지 못한다.

4. 백그라운드 알림 스케줄러는 기본값이 꺼져 있다.
   - `ENABLE_NOTIFICATION_SCHEDULER=false`가 기본값이다.
   - 이 값이 꺼져 있으면 가격/뉴스/리포트 변화 감지와 pending 외부 발송 job이 자동 실행되지 않는다.
   - `POST /api/notifications/test`는 수동 테스트 발송을 즉시 시도하지만, 운영 알림은 scheduler가 켜져야 자동 발송된다.

5. 채널 발송은 두 조건을 모두 만족해야 한다.
   - `notification_channel_connections.verified == true`
   - 사용자 preference의 `telegram_enabled` 또는 `email_enabled`가 `true`
   - 채널 연결만 되어 있고 수신 동의 toggle이 꺼져 있으면 외부 발송 이벤트가 생성되지 않는다.

6. 테스트 파일 자체에 문법/문자열 손상 의심 지점이 있다.
   - `backend/tests/test_notifications_api.py`에서 테스트 알림 요청 JSON의 `message` 문자열이 깨진 상태로 보인다.
   - 이 상태라면 관련 pytest가 수집 단계에서 실패할 수 있어, 발송 로직 회귀 테스트가 신뢰 가능한 안전망이 되지 못한다.

7. 사용자-facing 문구와 현재 Telegram 동작이 어긋난다.
   - `connect_telegram()` 응답은 bot에게 `/start <code>`를 전달하라는 식의 메시지를 반환한다.
   - 그러나 실제 백엔드는 Telegram inbound update를 처리하지 않고, `verify_telegram()`은 별도의 `chat_id`와 `code`를 API로 직접 받아 검증한다.
   - 결과적으로 사용자는 안내대로 bot에 코드를 보내도 연결이 완료되지 않는다고 느낄 수 있다.

## Likely Root Causes

### Gmail

- 운영 환경의 Gmail OAuth 설정 누락 또는 불일치
  - `GMAIL_REFRESH_TOKEN`이 없거나 만료/폐기됨
  - OAuth scope에 `https://www.googleapis.com/auth/gmail.send`가 없음
  - `EMAIL_FROM_ADDRESS`가 Gmail API 인증 주체와 맞지 않음
  - `EMAIL_PROVIDER`가 비어 있거나 `gmail` 외 값으로 설정됨

- 발송 실패를 UI/운영자가 진단하기 어렵다.
  - 현재 API는 `503` detail에 provider 오류를 일부 담지만, 설정 누락인지 OAuth 실패인지 quota/permission 실패인지 운영자가 빠르게 구분할 별도 진단 엔드포인트나 structured status가 없다.

### Telegram

- 채널 연결 UX와 백엔드 구현이 서로 다르다.
  - 문구는 bot inbound 검증을 암시하지만, 실제 구현은 수동 `chat_id` 입력 방식이다.
  - Telegram `chat_id`를 모르는 일반 사용자는 연결을 완료하기 어렵다.

- `TELEGRAM_BOT_TOKEN`이 없거나 bot이 사용자에게 먼저 메시지를 보낼 수 없는 상태일 수 있다.
  - 사용자가 bot과 대화를 시작하지 않았거나, 잘못된 `chat_id`를 입력한 경우 `sendMessage`가 실패한다.

### Shared

- `ENABLE_NOTIFICATION_SCHEDULER=false`이면 실제 알림 자동 발송이 일어나지 않는다.
- 알림 이벤트가 생성되어도 외부 채널 연결/동의 조건이 맞지 않으면 `email`/`telegram` pending 이벤트가 생성되지 않는다.
- 현재 테스트가 손상되어 있으면 수정 전후의 발송 경로를 안정적으로 검증할 수 없다.

## Remediation Plan

### Phase 1. 재현 가능한 진단 경로 정리

- `.env` 값을 출력하지 않고 설정 존재 여부만 점검하는 내부 헬퍼를 추가한다.
  - 예: `notification_service.get_delivery_configuration_status()`
  - 반환값은 `configured: bool`, `missing_keys: list[str]`, `provider: str`, `scheduler_enabled: bool` 정도만 포함한다.
  - secret 값 자체는 절대 반환하지 않는다.
- `POST /api/notifications/test` 결과가 `created/sent/failed` 숫자만이 아니라 실패 채널과 sanitized error summary를 확인할 수 있도록 응답 확장을 검토한다.
- 운영자 확인용으로는 `/api/notifications/channels`와 `/api/notifications/history`를 먼저 사용하고, 별도 admin endpoint가 필요하면 인증/권한 범위를 따로 설계한다.

### Phase 2. Gmail 설정 및 오류 처리 보강

- `notification_service._send_gmail_message()`에서 설정 누락 오류를 명확히 분류한다.
  - provider mismatch
  - missing Gmail config
  - OAuth token refresh failure
  - Gmail send failure
- OAuth refresh 실패 시 HTTP body에서 민감값 없이 `invalid_grant`, `invalid_client`, `insufficient_scope` 같은 원인 코드를 보존한다.
- `EMAIL_PROVIDER`는 코드 기본값이 `gmail`이므로 문서/예시는 `EMAIL_PROVIDER=gmail`로 통일한다.
- Gmail 인증 코드 발송 실패 후 DB connection 상태가 `delivery_failed`로 남는 현재 동작을 유지하되, 재시도 요청 시 `pending`으로 정상 갱신되는지 테스트한다.

### Phase 3. Telegram 연결 방식을 하나로 결정

권장안 A: 현재 구현을 정직한 수동 `chat_id` 방식으로 정리한다.

- API 응답과 UI 문구에서 `/start <code>` 자동 검증 안내를 제거한다.
- 사용자가 Telegram bot과 대화를 시작한 뒤 `getUpdates` 또는 별도 안내로 `chat_id`를 확인해 입력하는 방식임을 명확히 한다.
- `verify_telegram()`에서 `chat_id` 형식 검증과 테스트 메시지 전송 옵션을 추가한다.

권장안 B: 실제 Telegram inbound 검증을 구현한다.

- `POST /api/notifications/telegram/webhook` 엔드포인트를 추가한다.
- `TELEGRAM_WEBHOOK_SECRET` 또는 secret path/header로 webhook 요청을 검증한다.
- `/start <code>` 메시지를 받으면 pending connection의 `verification_code`를 찾아 `chat_id`를 저장하고 verified 처리한다.
- 운영 배포 URL에서 Telegram `setWebhook` 절차와 secret rotation 절차를 문서화한다.

우선순위는 A다. 현재 구조에 가장 작고 안전하게 맞으며, 별도 public webhook 운영 리스크가 없다. 다만 사용자 경험은 B가 더 낫다.

### Phase 4. Scheduler/이벤트 생성 조건 검증

- `ENABLE_NOTIFICATION_SCHEDULER=true`일 때 `main.py`가 `notification_evaluation`, `notification_delivery` job을 등록하는지 테스트 또는 startup smoke로 확인한다.
- `ENABLE_SCHEDULER=false`이면 알림 scheduler도 등록되지 않는 의존 관계를 문서화한다.
- 외부 발송 이벤트 생성 조건을 테스트에 명시한다.
  - channel verified
  - preference enabled
  - favorite exists
  - market cache/report/news 변화 조건 충족
- 운영에서 자동 알림을 쓰려면 `ENABLE_SCHEDULER=true`와 `ENABLE_NOTIFICATION_SCHEDULER=true`가 모두 필요하다고 문서화한다.

### Phase 5. 테스트 복구 및 확장

- `backend/tests/test_notifications_api.py`의 손상된 문자열/문법을 복구한다.
- 기존 mock 기반 테스트를 유지해 실제 Gmail/Telegram 네트워크 호출 없이 검증한다.
- 추가 테스트:
  - Gmail 설정 누락 시 email verify가 `503`이고 verification code를 노출하지 않음
  - Gmail OAuth 실패 메시지가 sanitized error로 저장됨
  - Telegram token 누락 시 pending event가 retry 후 failed 처리됨
  - Telegram 수동 검증 문구/contract가 현재 구현과 일치함
  - `ENABLE_NOTIFICATION_SCHEDULER` 기본 off 상태를 명시적으로 검증하거나 문서화

### Phase 6. 문서 갱신

- `docs/harness/features/favorite-asset-notifications.md`
  - Gmail API adapter가 존재하지만 credential/scope가 필수라는 점을 반영한다.
  - Telegram은 현재 수동 `chat_id` 방식인지, webhook 방식으로 바꾸는지 결정 결과를 반영한다.
  - `ENABLE_SCHEDULER`와 `ENABLE_NOTIFICATION_SCHEDULER` 관계를 명시한다.
- `docs/harness/features/deployment-runtime.md`
  - 운영 환경 변수 이름만 문서화하고 secret 값은 쓰지 않는다.
- `ENVIRONMENT_VARIABLE_SETUP.md` 및 `.env.example`
  - Gmail/Telegram 설정 절차를 실제 구현과 맞춘다.
  - Telegram webhook을 구현하지 않는다면 webhook secret 설명을 optional/future로 낮춘다.
- `docs/harness/feature-index.md`
  - 이 계획서와 향후 구현 기록을 Favorite asset notifications change records에 연결한다.

## Expected Files To Change During Implementation

- `backend/app/services/notification_service.py`
- `backend/app/api/notifications.py`
- `backend/app/main.py` 또는 scheduler 관련 테스트
- `backend/app/schemas.py`
- `backend/tests/test_notification_service.py`
- `backend/tests/test_notifications_api.py`
- `frontend/src/pages/MyPage.jsx`
- `.env.example`
- `ENVIRONMENT_VARIABLE_SETUP.md`
- `docs/harness/features/favorite-asset-notifications.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/feature-index.md`
- 새 구현 기록: `docs/harness/gmail-telegram-notification-delivery-remediation-implementation-2026-06-08.md`

## Verification Plan

Backend focused tests:

```powershell
cd backend
python -m pytest tests/test_notifications_api.py tests/test_notification_service.py
```

Scheduler/schema smoke when DB is available:

```powershell
cd backend
python -m alembic upgrade head
```

Frontend checks if MyPage copy or flow changes:

```powershell
cd frontend
npm run lint
npm run build
```

Manual smoke with real provider settings configured:

1. Secret 값을 출력하지 않고 Gmail/Telegram required config presence만 확인한다.
2. `ENABLE_SCHEDULER=true`, `ENABLE_NOTIFICATION_SCHEDULER=true`로 backend를 시작한다.
3. `/mypage`에서 email 채널 인증 코드를 요청하고 Gmail 수신함에서 코드를 확인한다.
4. `/mypage`에서 Telegram 채널을 현재 선택한 방식에 따라 연결한다.
5. `POST /api/notifications/test`를 호출해 `email`과 `telegram` 이벤트가 `sent`가 되는지 `/api/notifications/history`에서 확인한다.
6. 실패 시 `error_message`가 secret 없이 원인 분류를 보여주는지 확인한다.

## Commands Run For This Analysis

- `git status --short`
- `rg --files`로 관련 문서 목록 확인
- `Get-Content`로 관련 문서 및 알림 백엔드/프론트엔드 파일 확인

## Commands Not Run

- `python -m pytest ...`: 이번 요청은 분석 및 계획서 작성이며, 현재 테스트 파일에 손상 의심 지점이 있어 먼저 계획에 복구 항목으로 남겼다.
- Gmail/Telegram 실제 발송 smoke: 실제 provider credential과 외부 네트워크 호출이 필요하므로 실행하지 않았다.
- `.env` 확인: secret 보호 규칙에 따라 읽지 않았다.

## Risks And Decisions Needed

- Telegram은 수동 `chat_id` 방식으로 정리할지, webhook 기반 자동 검증으로 확장할지 제품 결정을 해야 한다.
- Gmail refresh token 발급 주체, scope, 발신 주소 정책은 운영 계정 기준으로 확정해야 한다.
- `ENABLE_NOTIFICATION_SCHEDULER`를 운영에서 켜면 market/news/report 상태 변화에 따라 외부 API 호출 및 발송 빈도가 증가한다. 비용성 AI report 생성은 건드리지 않지만, 외부 알림 발송 정책과 rate limit은 별도 확인이 필요하다.
- 실패 원인 메시지는 운영자가 진단할 만큼 충분해야 하지만, OAuth client secret, refresh token, bot token, email/chat_id 전체값은 절대 노출하지 않아야 한다.

## AI Report Generation Rule

이 계획은 알림 평가/발송 경로만 다룬다. 사용자-facing 요청, 챗봇 요청, 알림 발송은 새 AI report 생성을 트리거하지 않고 저장된 scheduled report와 market/news cache만 읽어야 한다.
