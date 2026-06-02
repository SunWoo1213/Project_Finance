# 즐겨찾기 자산 변화 알림 시스템 구축 계획서

Date: 2026-06-02

## Objective

사용자가 즐겨찾기한 자산의 가격, 등락률, 주요 뉴스, 저장된 AI 리포트 갱신 등 의미 있는 변화를 감지하고, 사용자가 수신 동의한 채널인 Telegram 또는 Google Mail로 알림을 발송하는 시스템을 구축한다.

현재 즐겨찾기는 `frontend/src/store/favoriteStore.js`의 `localStorage`에만 저장되므로, 알림 기능을 위해서는 계정 기반 즐겨찾기, 채널별 수신 동의, 알림 조건, 발송 이력, 실패 재시도 상태를 백엔드 DB로 이동해야 한다.

중요 정책: 이 알림 기능은 저장된 시장 데이터, 최신 뉴스 컨텍스트, 저장된 scheduled AI report만 읽는다. 사용자 요청이나 알림 발송 자체가 새 AI 리포트 생성을 직접 트리거하지 않는다.

## Current Context

- Authentication: Google 로그인 기반이며 `users.email`을 보유한다.
- Favorites: 브라우저 `localStorage`의 `favoriteAssets` 배열로만 유지된다.
- Market data: `backend/app/services/market_service.py`가 가격, 뉴스, 최신 컨텍스트를 수집하고 `market_cache`에 저장한다.
- Scheduler: `backend/app/main.py`에서 APScheduler로 가격 5분, 뉴스 1시간, AI 리포트 6시간 주기 작업을 실행한다.
- Reports: 사용자/챗봇 요청은 저장된 scheduled report만 읽어야 하며, 새 리포트 생성을 유발하면 안 된다.
- Deployment: Vercel frontend, persistent FastAPI backend, PostgreSQL 조합을 기준으로 한다.

## Product Scope

### MVP

1. 로그인 사용자가 즐겨찾기를 계정에 저장한다.
2. 사용자는 알림 채널별 수신 동의를 설정한다.
   - Telegram: 봇과 연결된 `chat_id`가 검증된 경우에만 활성화.
   - Email: Google 로그인 이메일 또는 사용자가 검증한 이메일로 발송.
3. 기본 알림 조건을 제공한다.
   - 일일 등락률 절대값이 임계치 이상인 경우.
   - 새 주요 뉴스가 감지된 경우.
   - 새 저장 AI 리포트가 생성된 경우.
4. 백그라운드 잡이 즐겨찾기 자산의 변화를 평가하고 중복 발송을 방지한다.
5. 발송 성공/실패 이력을 저장하고 사용자가 최근 알림 내역을 볼 수 있게 한다.

### Later

- 채널별 상세 조건 설정: 가격 상/하한, 변동률 임계치, 뉴스 키워드, 리포트만 받기.
- 조용한 시간, 일간 요약, 주간 요약.
- 알림 빈도 제한과 digest 모드.
- Telegram에서 `/start`, `/status`, `/mute`, `/unsubscribe` 명령 지원.
- 이메일 템플릿 개선 및 unsubscribe 링크.
- Pro/Plus 구독 등급별 알림 개수 제한.

## Recommended Architecture

```text
Frontend
  -> Favorites API
  -> Notification Preferences API
  -> Notification History API

FastAPI
  -> notification router
  -> favorite router
  -> notification service
  -> delivery adapters
       -> Telegram Bot API
       -> Email sender, Gmail API/SMTP for prototype or transactional provider for production
  -> APScheduler notification evaluation job

PostgreSQL
  -> user_favorite_assets
  -> notification_preferences
  -> notification_channel_connections
  -> notification_rules
  -> asset_notification_snapshots
  -> notification_events
```

핵심 원칙은 "감지"와 "발송"을 분리하는 것이다. 감지 작업은 자산별 변화 이벤트를 만들고, 발송 작업은 사용자별 수신 동의와 rate limit을 적용한 뒤 채널 adapter를 호출한다.

## Data Model Plan

### `user_favorite_assets`

계정 기반 즐겨찾기 저장소.

- `id`
- `user_id`
- `asset_id`
- `ticker`
- `display_name`
- `category_key`
- `source`: `manual`, `local_import`
- `created_at`
- unique: `(user_id, ticker)`

### `notification_preferences`

사용자의 알림 기본 설정.

- `user_id`
- `telegram_enabled`
- `email_enabled`
- `price_change_enabled`
- `news_enabled`
- `report_enabled`
- `daily_digest_enabled`
- `quiet_hours_start`
- `quiet_hours_end`
- `timezone`, 기본 `Asia/Seoul`
- `updated_at`

### `notification_channel_connections`

채널별 연결 상태. 민감한 토큰은 저장하지 않는다. Telegram bot token은 환경변수에만 둔다.

- `id`
- `user_id`
- `channel`: `telegram`, `email`
- `destination`: Telegram `chat_id` 또는 이메일 주소
- `verified`
- `verification_status`
- `verified_at`
- `created_at`
- `updated_at`

### `notification_rules`

즐겨찾기 또는 사용자 단위 알림 조건.

- `id`
- `user_id`
- `ticker`, nullable이면 사용자 기본 규칙
- `event_type`: `price_change`, `news`, `report`
- `threshold_json`
- `enabled`
- `created_at`
- `updated_at`

예시 `threshold_json`:

```json
{
  "abs_change_percent_gte": 3,
  "cooldown_minutes": 180
}
```

### `asset_notification_snapshots`

자산별 마지막 평가 기준점.

- `ticker`
- `last_price`
- `last_change_percent`
- `last_news_fingerprints`
- `last_report_id`
- `evaluated_at`

### `notification_events`

감지 및 발송 이력.

- `id`
- `user_id`
- `ticker`
- `event_type`
- `severity`
- `title`
- `body`
- `payload_json`
- `dedupe_key`
- `status`: `pending`, `sent`, `failed`, `suppressed`
- `channel`: nullable 또는 `telegram`/`email`
- `error_message`
- `created_at`
- `sent_at`
- unique: `(user_id, dedupe_key, channel)`

## API Plan

### Favorites

- `GET /api/favorites`
- `POST /api/favorites`
- `DELETE /api/favorites/{ticker}`
- `POST /api/favorites/import-local`

`import-local`은 기존 `localStorage` 즐겨찾기를 로그인 후 서버에 동기화하기 위한 전환용 endpoint다.

### Notification Preferences

- `GET /api/notifications/preferences`
- `PUT /api/notifications/preferences`
- `GET /api/notifications/history`

### Channel Connections

- `POST /api/notifications/channels/telegram/connect`
- `POST /api/notifications/channels/telegram/verify`
- `DELETE /api/notifications/channels/telegram`
- `POST /api/notifications/channels/email/verify`
- `POST /api/notifications/channels/email/confirm`
- `DELETE /api/notifications/channels/email`
- `POST /api/notifications/test`

Telegram 연결 방식은 초대 코드 기반을 권장한다.

1. 앱에서 1회용 연결 코드를 생성한다.
2. 사용자가 Telegram bot에 `/start <code>`를 보낸다.
3. webhook 또는 polling handler가 `chat_id`와 코드를 매칭한다.
4. 연결이 검증되면 `telegram_enabled`를 켤 수 있다.

Email은 Google 로그인 이메일을 기본 대상으로 사용하되, 실제 발송 전 이메일 수신 동의와 확인 링크를 거친다.

## Change Detection Plan

### Price Change

기존 `market_cache["prices"]`를 우선 사용한다. 알림 평가 작업은 외부 provider를 직접 호출하지 않고, 캐시가 갱신된 뒤 현재 값과 이전 snapshot을 비교한다.

MVP 조건:

- `abs(changePercent) >= user threshold`
- 동일 ticker/event/channel은 기본 3시간 cooldown
- 장 마감 후에도 중복 발송되지 않도록 `dedupe_key`에 날짜와 조건 구간을 포함

### News

기존 `market_cache["news"]` 또는 `fetch_latest_asset_context` 결과를 사용하되, 알림 잡이 ticker별 최신 컨텍스트를 강제로 자주 갱신하지 않는다. 뉴스 식별자는 `title + source + link` 해시로 만든다.

MVP 조건:

- 즐겨찾기 ticker에 새 뉴스 fingerprint가 생긴 경우
- 같은 뉴스는 한 번만 발송
- 뉴스 제목만 보내고 링크는 원문 링크를 포함

### Stored AI Report

`AIReport`의 최신 `id` 또는 `created_at`을 snapshot과 비교한다.

MVP 조건:

- 즐겨찾기 ticker에 새 저장 리포트가 생긴 경우
- 사용자의 report access entitlement를 확인한 뒤 링크 안내
- 알림은 리포트 생성을 트리거하지 않고, 이미 저장된 리포트만 기준으로 한다.

## Scheduler Plan

`backend/app/main.py`의 scheduler에 알림 평가 job을 추가하되, service 구현은 `backend/app/services/notification_service.py`에 둔다.

권장 주기:

- price/news/report 변화 평가: 10분
- pending event 발송: 1분 또는 같은 job 내부 처리
- 실패 재시도: exponential backoff, 최대 3회

권장 환경변수:

- `ENABLE_NOTIFICATION_SCHEDULER`
- `NOTIFICATION_EVALUATION_INTERVAL_MINUTES`
- `NOTIFICATION_DELIVERY_INTERVAL_MINUTES`
- `NOTIFICATION_DEFAULT_PRICE_THRESHOLD_PERCENT`
- `NOTIFICATION_DEFAULT_COOLDOWN_MINUTES`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET`
- `EMAIL_PROVIDER`
- `EMAIL_FROM_ADDRESS`
- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_REFRESH_TOKEN`

시크릿 값은 `.env` 또는 호스팅 secret에만 저장하고 문서, 로그, frontend env에 노출하지 않는다.

## Frontend Plan

### Favorites Migration

- 로그인 전: 기존 `localStorage` 즐겨찾기를 유지한다.
- 로그인 후: 서버 즐겨찾기와 병합한다.
- 병합 원칙: ticker 기준 중복 제거, 서버 상태 우선, 누락분 업로드.
- UI는 기존 별 버튼을 유지하되 authenticated 상태에서는 API mutation을 수행한다.

### Notification Settings UI

추가 위치 후보:

- Header 사용자 메뉴 안의 `알림 설정`
- `/settings/notifications` 신규 route
- 즐겨찾기 패널 하단의 간단한 CTA

필수 UI:

- Telegram 연결 상태, 연결 코드 발급, 테스트 발송.
- Email 수신 동의, 확인 상태, 테스트 발송.
- 가격 변동률 threshold.
- 뉴스/리포트 알림 toggle.
- 최근 알림 이력.

## Delivery Adapter Plan

### Telegram

- Bot token은 backend 환경변수로만 보관.
- webhook endpoint는 secret path 또는 header secret으로 검증.
- 메시지는 짧게 구성한다.
  - 자산명/ticker
  - 변화 요약
  - 현재 가격 또는 등락률
  - 관련 앱 링크
- Telegram 실패 원인별 처리:
  - bot blocked: 채널 비활성화.
  - chat not found: 연결 상태 invalid.
  - rate limit: 재시도 예약.

### Google Mail / Email

MVP에서는 "사용자의 Gmail 계정으로 보내기"가 아니라 "앱이 사용자 동의 이메일 주소로 발송"하는 구조를 권장한다. Google 로그인 이메일을 기본값으로 사용할 수 있지만, 별도 수신 동의와 확인 절차를 둔다.

구현 선택지:

1. Prototype: Gmail SMTP 또는 Gmail API를 앱 발신 계정으로 사용.
2. Production 권장: SendGrid, Mailgun, Amazon SES 같은 transactional email provider 사용.

Gmail API를 production 발송 채널로 사용할 경우 OAuth 동의 화면, 발송 quota, refresh token 보관, restricted scope 검토가 필요하므로 별도 승인 작업으로 분리한다.

## Security And Compliance

- Telegram `chat_id`와 이메일 주소는 개인정보로 취급한다.
- 수신 동의, 확인, 해지 이력을 DB에 남긴다.
- 모든 발송 메시지에 앱 링크와 수신 해지 경로를 포함한다.
- 이메일은 unsubscribe 링크를 제공한다.
- Telegram은 `/unsubscribe` 또는 앱 설정에서 해지 가능해야 한다.
- provider token, refresh token, webhook secret은 로그에 남기지 않는다.
- 알림 API는 모두 `get_current_user` 인증을 요구한다.
- 발송 이력의 `payload_json`에는 민감한 사용자 정보나 raw provider 응답을 저장하지 않는다.

## Implementation Phases

### Phase 1. Foundation

- DB 모델과 Alembic migration 추가.
- `backend/app/api/favorites.py` 추가.
- `backend/app/api/notifications.py` 추가.
- `backend/app/services/notification_service.py` 추가.
- 기존 frontend localStorage 즐겨찾기와 서버 즐겨찾기 병합.
- 기본 알림 설정 화면 추가.

### Phase 2. Detection

- price/news/report 변화 evaluator 구현.
- snapshot과 `notification_events` dedupe 구현.
- scheduler에 notification evaluation job 추가.
- report notification이 새 report 생성을 트리거하지 않는지 테스트로 고정.

### Phase 3. Delivery

- Telegram adapter 구현.
- Email adapter 구현.
- 테스트 발송 endpoint 추가.
- 실패 재시도와 채널 비활성화 정책 구현.

### Phase 4. Hardening

- rate limit, quiet hours, digest 모드.
- 구독 등급별 알림 개수 제한 정책 확정.
- 운영 로그와 지표 추가.
- webhook 보안 검증과 배포 runbook 작성.

## Testing Plan

Backend:

- favorite CRUD and import tests.
- preference update tests.
- Telegram 연결 코드 검증 tests.
- price/news/report event dedupe tests.
- delivery adapter mocked success/failure tests.
- scheduler job tests with mocked `market_cache`.
- entitlement test: stored report 알림은 가능하지만 generation은 호출되지 않음.

Frontend:

- favorite toggle 로그인 전/후 동작.
- localStorage to server import flow.
- notification settings form validation.
- channel connect/disconnect 상태 표시.
- build and lint.

Manual:

- Telegram bot `/start <code>` 연결.
- test notification 발송.
- email verification 링크 확인.
- 알림 해지 후 발송 억제 확인.

## Verification Commands

구현 후 권장 검증:

```powershell
cd backend
python -m alembic upgrade head
pytest tests/test_favorites_api.py tests/test_notifications_api.py tests/test_notification_service.py
```

```powershell
cd frontend
npm run lint
npm run build
```

## Documentation Updates Required During Implementation

- `docs/harness/features/favorites.md`: 계정 기반 즐겨찾기와 localStorage migration 반영.
- `docs/harness/features/market-data.md`: 알림 evaluator가 cache 기반으로 동작한다는 점 반영.
- `docs/harness/features/authentication.md`: Google 이메일을 알림 수신 기본 주소로 사용할 수 있다는 점 반영.
- `docs/harness/features/deployment-runtime.md`: Telegram/Gmail/email 환경변수와 scheduler 운영 정책 반영.
- `docs/harness/feature-index.md`: 새 알림 feature 문서가 생기면 feature map에 추가.

## Open Decisions

- Gmail을 반드시 Gmail API로 구현할지, 앱 발신 이메일 provider로 구현할지 결정해야 한다.
- 알림 기능을 무료 사용자에게도 제공할지, Plus/Pro 전용 또는 건수 제한형으로 제공할지 결정해야 한다.
- 가격 변동 기준을 일일 등락률로 볼지, 이전 알림 이후 변화율로 볼지 결정해야 한다.
- 뉴스 알림 범위를 모든 즐겨찾기 자산으로 할지, provider coverage가 안정적인 자산군부터 열지 결정해야 한다.
- Telegram webhook을 사용할지 polling을 사용할지 배포 환경에 맞춰 결정해야 한다.

## Follow-up Risks

- 현재 즐겨찾기는 backend와 연결되어 있지 않으므로 DB migration이 필수다.
- Telegram/Gmail 발송은 외부 API quota와 실패 처리가 필요하다.
- 알림 scheduler를 너무 자주 돌리면 provider rate limit과 운영 비용이 증가할 수 있다.
- Gmail API로 직접 발송하면 OAuth scope 검토와 refresh token 보관 위험이 커진다.
- 뉴스 provider의 응답 형식과 coverage는 외부 변경에 취약하다.
