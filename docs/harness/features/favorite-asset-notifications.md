# Favorite Asset Notifications

Date: 2026-06-02

## Current Behavior

로그인 사용자는 즐겨찾기 자산을 계정 기준으로 저장하고, 알림 기본 설정과 채널 연결 상태를 관리할 수 있다. 알림 평가는 기존 `market_cache`, `notification_events`, `asset_notification_snapshots`, 저장된 `AIReport`만 읽는다. 사용자 요청이나 알림 job은 새 AI 리포트 생성을 직접 트리거하지 않는다.

`ENABLE_NOTIFICATION_SCHEDULER` 기본값은 `false`이다. 운영자가 명시적으로 켜기 전까지 알림 평가/발송 scheduler는 자동 실행되지 않는다.

## Ownership Map

- Backend models: `backend/app/models.py`
- Backend schemas: `backend/app/schemas.py`
- Favorites API: `backend/app/api/favorites.py`
- Notifications API: `backend/app/api/notifications.py`
- Notification service and delivery adapters: `backend/app/services/notification_service.py`
- Favorite account sync service: `backend/app/services/favorite_service.py`
- Scheduler registration and startup schema check: `backend/app/main.py`
- Alembic migration: `backend/alembic/versions/20260602_0001_add_favorite_notification_tables.py`
- Frontend favorite sync: `frontend/src/store/favoriteStore.js`
- Frontend settings route: `frontend/src/pages/NotificationsSettings.jsx`, `frontend/src/App.jsx`

## Data Flow

1. 로그인 시 `favoriteStore.syncWithServer(token)`가 브라우저 `favoriteAssets`를 `POST /api/favorites/import-local`로 서버에 병합한다.
2. 이후 즐겨찾기 토글은 localStorage를 즉시 갱신하고, 토큰이 있으면 `POST /api/favorites` 또는 `DELETE /api/favorites/{ticker}`를 호출한다.
3. 사용자는 `/settings/notifications`에서 알림 설정, Telegram/email 채널 검증, 최근 알림 이력을 확인한다.
4. 알림 평가는 즐겨찾기별로 가격 변동, 새 뉴스 fingerprint, 저장된 최신 `AIReport.id`를 이전 snapshot과 비교한다.
5. 감지된 알림은 `notification_events`에 `in_app` 이력으로 남고, 검증된 Telegram/email 채널이 활성화되어 있으면 채널별 pending event도 생성된다.
6. Email 발송 adapter는 Gmail API만 지원한다. Gmail 설정이 없거나 provider가 `gmail`이 아니면 failed 이력으로 남긴다.
7. Email 채널 인증 코드는 API 응답으로 노출하지 않고 Gmail로 발송한다. Gmail 발송 실패 시 인증 요청은 `503`으로 실패하며 channel 상태는 재요청 가능한 pending/delivery failure 상태로 남는다.

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

Runtime variables are documented by name only: `ENABLE_NOTIFICATION_SCHEDULER`, `NOTIFICATION_EVALUATION_INTERVAL_MINUTES`, `NOTIFICATION_DELIVERY_INTERVAL_MINUTES`, `NOTIFICATION_DEFAULT_PRICE_THRESHOLD_PERCENT`, `NOTIFICATION_DEFAULT_COOLDOWN_MINUTES`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `EMAIL_PROVIDER`, `EMAIL_FROM_ADDRESS`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`.

## Change Rules

- 알림 기능은 저장된 시장 캐시, 뉴스 캐시, 저장된 AI 리포트만 읽어야 한다.
- 일반 사용자 요청, 챗봇 요청, 알림 평가/발송은 AI 리포트 생성을 직접 호출하면 안 된다.
- Telegram `chat_id`, email address, provider token은 개인정보/secret으로 취급한다.
- 실제 외부 발송 provider를 추가할 때는 실패 재시도, rate limit, unsubscribe 동작을 함께 검토한다.
- scheduler 주기나 coverage를 늘리면 API quota와 비용에 영향을 줄 수 있으므로 변경 기록에 명시한다.

## Verification

- Backend API/service tests: `python -m pytest tests/test_favorites_api.py tests/test_notifications_api.py tests/test_notification_service.py`
- Migration check: `python -m alembic upgrade head`
- Frontend checks: `npm run lint`, `npm run build`

## Change Records

- `docs/harness/favorite-asset-notification-implementation-2026-06-02.md`
- `docs/harness/gmail-only-email-notification-plan-2026-06-02.md`
- `docs/harness/gmail-only-email-notification-implementation-2026-06-02.md`
- `docs/harness/project-gap-remediation-plan-2026-06-02.md`
- `docs/harness/project-defect-remediation-plan-2026-06-02.md`

## Open Risks

- Telegram bot webhook/polling handler는 아직 별도 운영 흐름으로 남아 있다. 현재 verify endpoint는 prototype/manual 연결용이다.
- Gmail refresh token 발급 주체, 발신자 이름, Gmail quota, unsubscribe 문구, rate limit 정책은 운영 전에 확정해야 한다.
- News 알림은 캐시에 존재하는 뉴스만 평가하므로, ticker별 최신 컨텍스트 coverage가 부족하면 알림도 제한된다.

## MyPage Integration Note

As of `docs/harness/mypage-profile-implementation-2026-06-02.md`, `/mypage` provides Telegram and Google Mail consent toggles through `PUT /api/notifications/preferences`. The legacy `/settings/notifications` route renders the same MyPage screen. Turning off consent does not delete channel connection records.
