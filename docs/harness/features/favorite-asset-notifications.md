# Favorite Asset Notifications

Date: 2026-06-02

## Current Behavior

로그인 사용자는 즐겨찾기 자산을 계정 기준으로 저장하고, 알림 기본 설정과 채널 연결 상태를 관리할 수 있다. 운영 알림 scheduler는 변화 감지형 개별 메시지가 아니라 정시 digest를 생성한다. 기본 발송 시각은 `Asia/Seoul` 기준 `09:00`, `13:00`, `18:00`이며, 변화 여부와 상관없이 검증되고 수신 동의된 Gmail/Telegram 채널에 사용자당 채널별 1건을 보낸다. 알림 job은 기존 `market_cache`, `notification_events`, 저장된 `AIReport`만 읽고 새 AI 리포트 생성을 직접 트리거하지 않는다.

Gmail/Telegram 발송 본문은 한국어를 먼저 제공하고 아래에 `English` 섹션을 둔다. Email subject는 한국어 제목만 사용한다. 정시 digest는 즐겨찾기 자산명, ticker, market cache 기준 현재 가격, `FRONTEND_BASE_URL/detail/{ticker}` 링크를 묶어 보낸다. 가격 cache가 없으면 `현재 가격: 확인 중` fallback을 표시한다. Report 본문은 Gmail/Telegram에 직접 싣지 않고, 사용자는 자산 상세 페이지에서 권한/로그인 흐름을 거쳐 저장된 scheduled report를 읽는다.

News 알림은 외부 뉴스 URL을 발송 본문에 노출하지 않는다. 새 뉴스 fingerprint가 감지되면 뉴스 제목과 `FRONTEND_BASE_URL/detail/{ticker}` 상세 페이지 링크로 안내한다.

Google 최초 가입 시에는 Gmail welcome email을 한 번 시도한다. Email 또는 Telegram 채널이 처음 검증 완료되면 해당 채널로 welcome message를 한 번 시도한다. Welcome Telegram message는 제목에 인사가 들어가므로 본문에서 동일 인사를 반복하지 않는다. 중복 방지는 DB schema 변경 없이 `NotificationEvent`의 `welcome:{user_id}:{channel}` dedupe key로 처리한다.

`ENABLE_NOTIFICATION_SCHEDULER` 기본값은 `false`이다. 운영자가 명시적으로 켜기 전까지 알림 평가/발송 scheduler는 자동 실행되지 않는다.

## Ownership Map

2026-06-08 implementation note: Gmail delivery now exposes secret-safe configuration diagnostics through the notification test response. Telegram verification is the manual numeric `chat_id` flow; this backend still does not process Telegram inbound `/start <code>` webhook messages.

- Backend models: `backend/app/models.py`
- Backend schemas: `backend/app/schemas.py`
- Favorites API: `backend/app/api/favorites.py`
- Notifications API: `backend/app/api/notifications.py`
- Notification service and delivery adapters: `backend/app/services/notification_service.py`
- Favorite account sync service: `backend/app/services/favorite_service.py`
- Scheduler registration and startup schema check: `backend/app/main.py`
- Alembic migration: `backend/alembic/versions/20260602_0001_add_favorite_notification_tables.py`
- Frontend favorite sync: `frontend/src/store/favoriteStore.js`
- Frontend channel 연결·검증·해제 UI(라이브): `frontend/src/pages/MyPage.jsx`
- Frontend settings route: `frontend/src/pages/NotificationsSettings.jsx`(라우팅되지 않는 사장 코드), `frontend/src/App.jsx`

## Data Flow

1. 로그인 시 `favoriteStore.syncWithServer(token)`가 브라우저 `favoriteAssets`를 `POST /api/favorites/import-local`로 서버에 병합한다.
2. 이후 즐겨찾기 토글은 localStorage를 즉시 갱신하고, 토큰이 있으면 `POST /api/favorites` 또는 `DELETE /api/favorites/{ticker}`를 호출한다.
3. 사용자는 `/settings/notifications`에서 알림 설정, Telegram/email 채널 검증, 최근 알림 이력을 확인한다.
4. 정시 digest scheduler는 `NOTIFICATION_DIGEST_SEND_TIMES`의 각 시각에 사용자별 즐겨찾기를 모아 `scheduled_digest` 이벤트를 만든다.
5. Digest 이벤트는 자산별 개별 메시지가 아니라 검증되고 수신 동의된 Telegram/email 채널별 1건이다.
6. 같은 사용자/채널/날짜/정시 슬롯은 `digest:{user_id}:{YYYYMMDD}:{HHMM}` dedupe key로 한 번만 생성한다.
7. Digest 본문은 cache item의 외부 뉴스 URL이나 report 본문을 싣지 않고 자산 상세 페이지로 안내한다.
8. Telegram 발송 adapter는 저장된 숫자 `chat_id`로 Telegram Bot API `sendMessage`를 호출한다. 현재 연결 방식은 webhook 자동 수신이 아니라 수동 `chat_id` 입력이다.
9. Email 발송 adapter는 Gmail API만 지원한다. Gmail 설정이 없거나 provider가 `gmail`이 아니면 failed 이력으로 남긴다.
10. Email 채널 인증 코드는 API 응답으로 노출하지 않고 Gmail로 발송한다. Gmail 발송 실패 시 인증 요청은 `503`으로 실패하며 channel 상태는 재요청 가능한 pending/delivery failure 상태로 남는다.
11. Welcome message는 Google 최초 가입의 email 채널 또는 각 알림 채널의 최초 검증 완료 시점에 즉시 발송을 시도하며, 실패가 가입/채널 검증 성공 응답을 막지 않는다.

## Contracts

- Favorites:
  - `GET /api/favorites`
  - `POST /api/favorites`
  - `DELETE /api/favorites/{ticker}`
  - `POST /api/favorites/import-local`
- Notifications:
  - `GET /api/notifications/preferences`
  - `PUT /api/notifications/preferences`
  - `GET /api/notifications/channels`
  - `POST /api/notifications/channels/telegram/connect`
  - `POST /api/notifications/channels/telegram/verify`
  - `DELETE /api/notifications/channels/telegram`
  - `POST /api/notifications/channels/email/verify`
  - `POST /api/notifications/channels/email/confirm`
  - `DELETE /api/notifications/channels/email`
  - `GET /api/notifications/history`
  - `POST /api/notifications/test`

Runtime variables are documented by name only: `ENABLE_NOTIFICATION_SCHEDULER`, `NOTIFICATION_DIGEST_SEND_TIMES`, `NOTIFICATION_TIMEZONE`, `NOTIFICATION_DIGEST_MAX_ASSETS`, `NOTIFICATION_EVALUATION_INTERVAL_MINUTES`, `NOTIFICATION_DELIVERY_INTERVAL_MINUTES`, `NOTIFICATION_DEFAULT_PRICE_THRESHOLD_PERCENT`, `NOTIFICATION_DEFAULT_COOLDOWN_MINUTES`, `FRONTEND_BASE_URL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `EMAIL_PROVIDER`, `EMAIL_FROM_ADDRESS`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`.

## Change Rules

- 알림 기능은 저장된 시장 캐시, 뉴스 캐시, 저장된 AI 리포트만 읽어야 한다.
- 일반 사용자 요청, 챗봇 요청, 알림 평가/발송은 AI 리포트 생성을 직접 호출하면 안 된다.
- 운영 scheduler는 기본적으로 정시 digest를 발송한다. 변화 감지형 개별 알림을 다시 scheduler에 연결하면 발송량, provider quota, 사용자 피로도를 별도 검토해야 한다.
- Report 알림 body에 `AIReport.final_content`를 포함하지 않는다. 상세 페이지 링크로 저장 리포트 조회 흐름을 안내한다.
- News 알림 body에는 외부 뉴스 링크를 포함하지 않고 자산 상세 페이지 링크를 포함한다.
- Email/Telegram 발송용 본문은 한국어를 먼저 쓰고 영어를 아래에 둔다. Email subject는 한국어만 유지한다.
- Telegram `chat_id`, email address, provider token은 개인정보/secret으로 취급한다.
- 실제 외부 발송 provider를 추가할 때는 실패 재시도, rate limit, unsubscribe 동작을 함께 검토한다.
- scheduler 주기나 coverage를 늘리면 API quota와 비용에 영향을 줄 수 있으므로 변경 기록에 명시한다.

## Verification

- Backend API/service tests: `python -m pytest tests/test_favorites_api.py tests/test_notifications_api.py tests/test_notification_service.py`
- Migration check: `python -m alembic upgrade head`
- Frontend checks: `npm run lint`, `npm run build`
- Telegram 발송 하네스 검증 절차: `docs/harness/telegram-message-delivery-verification-2026-06-09.md`

## Change Records

- `docs/harness/favorite-asset-notification-implementation-2026-06-02.md`
- `docs/harness/gmail-only-email-notification-plan-2026-06-02.md`
- `docs/harness/gmail-only-email-notification-implementation-2026-06-02.md`
- `docs/harness/project-gap-remediation-plan-2026-06-02.md`
- `docs/harness/project-defect-remediation-plan-2026-06-02.md`
- `docs/harness/notification-channel-inline-setup-plan-2026-06-04.md`
- `docs/harness/notification-channel-inline-setup-implementation-2026-06-04.md`
- `docs/harness/gmail-telegram-notification-delivery-remediation-plan-2026-06-08.md`
- `docs/harness/gmail-telegram-notification-delivery-remediation-implementation-2026-06-08.md`
- `docs/harness/notification-delivery-not-sending-diagnosis-2026-06-08.md`
- `docs/harness/gmail-oauth-refresh-token-setup-documentation-2026-06-08.md`
- `docs/harness/telegram-message-delivery-verification-2026-06-09.md`
- `docs/harness/favorite-asset-report-link-notification-plan-2026-06-09.md`
- `docs/harness/favorite-asset-report-link-notification-implementation-2026-06-09.md`
- `docs/harness/notification-bilingual-detail-link-message-implementation-2026-06-09.md`
- `docs/harness/favorite-asset-scheduled-digest-notification-plan-2026-06-09.md`
- `docs/harness/favorite-asset-scheduled-digest-notification-implementation-2026-06-09.md`

## Open Risks

- Telegram bot webhook/polling handler는 아직 별도 운영 흐름으로 남아 있다. 현재 verify endpoint는 prototype/manual 연결용이다.
- Gmail refresh token 발급 주체, 발신자 이름, Gmail quota, unsubscribe 문구, rate limit 정책은 운영 전에 확정해야 한다.
- News 알림은 캐시에 존재하는 뉴스만 평가하므로, ticker별 최신 컨텍스트 coverage가 부족하면 알림도 제한된다.

## MyPage Integration Note

As of `docs/harness/mypage-profile-implementation-2026-06-02.md`, `/mypage` provides Telegram and Google Mail consent toggles through `PUT /api/notifications/preferences`. The legacy `/settings/notifications` route renders the same MyPage screen. Turning off consent does not delete channel connection records.

As of `docs/harness/notification-channel-inline-setup-implementation-2026-06-04.md`, `/mypage`의 "수신 동의" 섹션은 각 토글 아래에 채널 연결·검증·해제 인라인 UI를 함께 제공한다. Telegram은 `channels/telegram/connect`→`verify`(숫자 chat_id 입력), Email은 `channels/email/verify`→`confirm`(Gmail 코드)으로 검증하고, 각각 DELETE로 해제한다. 연결된 destination은 화면에서 마스킹 표시된다. `frontend/src/pages/NotificationsSettings.jsx`는 동일 기능을 가지지만 라우팅되지 않는 사장 코드이며, 삭제는 별도 승인 대상이다.
