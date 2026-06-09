# 즐겨찾기 자산 리포트 링크형 메일/Telegram 알림 전환 계획

Date: 2026-06-09

## Objective

즐겨찾기한 자산의 새 저장 리포트 알림을 Gmail/Telegram으로 보낼 때 리포트 본문을 직접 전달하지 않고, 자산 상세정보 페이지 링크와 현재 가격을 함께 안내하는 형식으로 전환한다. 또한 사용자가 최초 인증 또는 알림 채널 최초 검증을 완료했을 때 `우리 서비스를 이용해주셔서 감사합니다` 성격의 가입/환영 메시지를 메일과 Telegram으로 보낼 수 있도록 설계한다.

목표 메시지:

- 제목: `즐겨찾기한 자산에 대한 보고서 발신입니다.`
- 내용: 하루 인사 문구와 함께 즐겨찾기 자산명, ticker, 현재 가격, 자산 상세정보 페이지 링크를 제공한다.
- 링크 대상: frontend 자산 상세 route인 `/detail/{ticker}`. 사용자는 해당 상세 페이지에서 저장된 scheduled AI report를 조회한다.
- 최초 인증/검증 환영 메시지: `Project Finance를 이용해주셔서 감사합니다.` 류의 짧은 가입 인사와 서비스 시작 안내를 보낸다.

이 작업은 알림 메시지 포맷과 링크 생성만 다루며, 사용자 요청이나 알림 발송이 새 AI report 생성을 트리거해서는 안 된다.

## Scope

- 대상 기능: Favorite asset notifications의 `report` 이벤트 외부 발송 메시지
- 대상 기능 추가: 최초 인증 또는 알림 채널 최초 검증 완료 시 환영 메시지 발송
- 대상 채널: Gmail, Telegram. 단, Telegram은 verified `chat_id`가 생긴 뒤에만 발송 가능하다.
- 주요 코드 후보:
  - `backend/app/services/notification_service.py`
  - `backend/app/api/auth.py`
  - `backend/app/core/config.py`
  - `backend/app/schemas.py` 또는 기존 schema 유지 여부 확인
  - `backend/tests/test_notification_service.py`
  - `backend/tests/test_notifications_api.py`
  - `.env.example`
  - `ENVIRONMENT_VARIABLE_SETUP.md`
  - `docs/harness/features/favorite-asset-notifications.md`
  - `docs/harness/features/asset-detail-ai-community.md`
  - `docs/harness/feature-index.md`
- 제외:
  - `.env` 실제 값 확인
  - Gmail/Telegram 실제 credential 출력
  - AI report scheduler cadence 변경
  - 알림 scheduler 주기 변경
  - 사용자-facing report generation endpoint 재활성화
  - frontend 상세 페이지 UI 변경

## Current Code Findings

1. `backend/app/services/notification_service.py`의 `_evaluate_report()`는 최신 `AIReport`와 `Asset`을 조회한 뒤 `event_type="report"` 이벤트를 만든다.
2. 현재 report 이벤트 제목은 `{asset.name} AI 리포트 갱신`, 본문은 `{asset.ticker}에 대한 저장된 AI 리포트가 새로 갱신되었습니다.`이다.
3. `_send_telegram()`과 `_send_email()`은 `NotificationEvent.title`과 `NotificationEvent.body`를 그대로 사용한다.
4. 가격 정보는 같은 service의 `_find_price_payload(ticker)`가 `market_cache["prices"]`에서 읽을 수 있다. 현재 가격 필드는 `currentPrice` 또는 `price`를 사용한다.
5. 상세 페이지 route는 `frontend/src/pages/AssetDetail.jsx` 기준 `/detail/:ticker`이고, 저장 리포트 조회는 `GET /api/reports/{ticker}`를 통해 이루어진다.
6. `backend/app/core/config.py`에는 frontend origin을 메시지 링크용으로 쓰는 backend 설정이 아직 없다. `VITE_API_BASE_URL`은 frontend 전용 public env이고 backend에서 읽지 않는다.
7. 알림 평가는 저장된 `AIReport`, market/news cache만 읽는다. 사용자 요청, 챗봇 요청, 알림 job은 새 AI report 생성을 직접 호출하지 않는다는 기존 규칙을 유지해야 한다.
8. Gmail은 Google 로그인 사용자 email 또는 검증된 email channel destination으로 보낼 수 있지만, Telegram은 사용자가 bot과 대화를 시작하고 `chat_id` 검증을 끝낸 뒤에만 보낼 수 있다.
9. 현재 모델에는 환영 메시지 발송 여부를 별도 column으로 기록하는 필드가 보이지 않는다. 중복 발송 방지를 위해 기존 `NotificationEvent` dedupe key를 활용할지, `User` 또는 channel connection에 별도 timestamp를 추가할지 결정해야 한다.

## Target Behavior

새 저장 리포트가 감지되면 각 사용자/채널별 report notification event는 다음 메시지를 가진다.

```text
제목: 즐겨찾기한 자산에 대한 보고서 발신입니다.

내용:
오늘 하루도 좋은 흐름으로 보내시길 바랍니다.

즐겨찾기하신 {asset.name}({asset.ticker}) 리포트가 준비되었습니다.
현재 가격: {formatted_current_price}
자산 리포트 링크: {frontend_base_url}/detail/{url_encoded_ticker}
```

가격을 cache에서 찾을 수 없으면 이벤트 생성을 막지 않고 `현재 가격: 확인 중` 또는 `현재 가격: 최신 가격을 불러오는 중입니다.`처럼 명확한 fallback을 사용한다.

상세 페이지 링크는 리포트 본문을 직접 포함하지 않고, 사용자가 앱의 권한/로그인 흐름을 거쳐 저장 리포트를 읽도록 안내한다. Plus/Pro 권한이 없는 사용자는 현재 상세 페이지의 paywall 또는 접근 제한 UI를 보게 된다.

최초 인증/검증 환영 메시지는 다음처럼 짧고 가입 멘트성으로 보낸다.

```text
제목: Project Finance를 이용해주셔서 감사합니다.

내용:
Project Finance를 이용해주셔서 감사합니다.
관심 자산을 즐겨찾기하면 주요 리포트와 알림을 이 채널로 받아보실 수 있습니다.
오늘도 좋은 하루 보내세요.
```

Google 로그인 최초 가입 시점에는 email만 즉시 발송 가능하다. Telegram 환영 메시지는 Telegram channel verification이 처음 `verified=true`가 되는 시점에 발송한다. 이미 검증된 channel을 재검증하거나 재연결하는 경우에는 중복 환영 메시지를 보내지 않는 것을 기본 목표로 한다.

## Design Decisions Needed

1. Frontend base URL 설정명
   - 권장: backend-only non-secret 설정 `FRONTEND_BASE_URL`.
   - 기본값 후보: `http://localhost:5173`.
   - 운영에서는 Vercel frontend origin을 넣는다.
   - secret이 아니지만 배포 URL이므로 `.env.example`과 환경변수 문서에 변수명만 명확히 남긴다.

2. 메시지 포맷 적용 위치
   - 권장: `_evaluate_report()`에서 report event의 `title`, `body`, `payload_json`을 링크형으로 생성한다.
   - 장점: Gmail/Telegram뿐 아니라 in-app history도 같은 문맥을 보게 된다.
   - 대안: `_send_email()`/`_send_telegram()`에서 `event_type=="report"`일 때만 외부 발송 body를 재구성한다. In-app 문구를 유지하고 싶다면 이 방식을 선택한다.
   - 현재 사용자 요청은 메일/Telegram 발송 형식 변경이므로, 구현 시 제품 의도에 따라 둘 중 하나를 확정한다.

3. 가격 포맷
   - backend에 frontend `formatPrice()`를 직접 공유할 수 없으므로 `notification_service.py`에 작은 private helper를 둔다.
   - `favorite.category_key`와 ticker를 기준으로 주식/채권/원자재/코인/환율 포맷을 보수적으로 맞춘다.
   - 정확한 통화 단위보다 “값을 잘못 말하지 않는 것”이 우선이다. 알 수 없는 자산군은 숫자와 원본 ticker를 그대로 표시한다.

4. 환영 메시지 발송 트리거
   - 권장: 두 트리거를 분리한다.
   - Google 최초 가입: `backend/app/api/auth.py`에서 새 `User`가 생성된 경우 Gmail welcome 발송을 시도한다.
   - 채널 최초 검증: `backend/app/api/notifications.py`의 email/telegram confirm 또는 `notification_service.verify_channel()` 흐름에서 해당 channel이 처음 verified가 된 경우 welcome 발송을 시도한다.
   - Telegram은 Google 가입 시점에는 destination이 없으므로 가입 직후에는 발송하지 않는다.

5. 환영 메시지 중복 방지
   - 작은 변경을 우선한다면 `NotificationEvent`에 `event_type="welcome"`과 channel별 dedupe key `welcome:{user_id}:{channel}`을 남긴다.
   - 더 명확한 장기 설계가 필요하면 `User` 또는 `NotificationChannelConnection`에 `welcome_sent_at`류 column을 추가한다. 이 경우 Alembic migration이 필요하므로 구현 전 DB schema 변경 승인 범위로 다룬다.
   - 권장 초안은 schema 변경 없이 `NotificationEvent` dedupe key로 중복 발송을 막는 방식이다.

## Implementation Plan

### Phase 1. 링크와 가격 helper 추가

- `backend/app/core/config.py`
  - `FRONTEND_BASE_URL: str = "http://localhost:5173"` 추가를 검토한다.
  - validator 또는 helper에서 trailing slash를 제거해 링크 중복 slash를 방지한다.
- `backend/app/services/notification_service.py`
  - `_build_asset_detail_url(ticker)` helper 추가.
  - `_format_notification_price(ticker, favorite, payload)` helper 추가.
  - `urllib.parse.quote()`를 사용해 `/detail/{ticker}` 경로 segment를 안전하게 인코딩한다.

### Phase 2. report 이벤트 메시지 재구성

- `_evaluate_report()`에서 `title`을 고정 문자열 `즐겨찾기한 자산에 대한 보고서 발신입니다.`로 변경한다.
- `body`에 하루 인사, 자산명/ticker, 현재 가격, 상세 페이지 링크를 포함한다.
- `payload_json`에는 향후 디버깅과 UI 재구성을 위해 아래 값을 저장한다.
  - `report_id`
  - `created_at`
  - `detail_url`
  - `current_price`
  - `current_price_text`
  - `price_source`
- `AIReport.final_content`는 외부 알림 body에 포함하지 않는다.

### Phase 3. 외부 발송 채널 확인

- `_send_telegram()`이 `event.title + event.body`만 발송하므로 별도 수정이 필요 없는지 확인한다.
- `_send_email()`도 동일하게 `event.title`, `event.body`를 Gmail subject/body로 넘긴다. 제목 고정이 반영되는지 테스트한다.
- Telegram 메시지 길이는 짧은 링크형 문구라 Telegram limit 위험은 낮다.

### Phase 4. 최초 인증/채널 검증 환영 메시지 추가

- `backend/app/services/notification_service.py`
  - `create_welcome_notification_events()` 또는 `send_welcome_message_for_channel()` helper를 추가한다.
  - 제목은 `Project Finance를 이용해주셔서 감사합니다.`로 통일한다.
  - body는 가입 감사, 즐겨찾기/리포트 알림 안내, 짧은 하루 인사로 구성한다.
  - `NotificationEvent`를 사용할 경우 `event_type="welcome"`, `ticker="WELCOME"` 또는 `ticker="SYSTEM"`, `dedupe_key="welcome:{user_id}:{channel}"`를 사용한다.
  - verified destination이 있는 channel만 외부 발송 대상으로 만든다.
- `backend/app/api/auth.py`
  - 새 사용자 생성 여부를 감지할 수 있는 현재 auth flow를 확인한다.
  - Google 최초 가입 시 Gmail 설정이 완료되어 있으면 account email로 welcome 발송을 시도한다.
  - 발송 실패가 로그인 성공을 막지 않도록 실패는 sanitized log/event로만 남기는 방식을 우선한다.
- `backend/app/api/notifications.py` 또는 `verify_channel()`
  - email/Telegram channel이 처음 verified가 된 시점에 해당 channel welcome을 발송한다.
  - 이미 welcome event dedupe key가 있으면 재발송하지 않는다.

### Phase 5. 테스트 추가/수정

- `backend/tests/test_notification_service.py`
  - 저장된 `AIReport`가 새로 감지될 때 report event title이 고정 문자열인지 검증한다.
  - body에 `/detail/NVDA` 또는 URL 인코딩된 ticker가 포함되는지 검증한다.
  - market cache에 현재 가격이 있으면 body/payload에 가격이 포함되는지 검증한다.
  - market cache에 가격이 없으면 fallback 문구로 이벤트가 생성되는지 검증한다.
  - `AIReport.final_content`가 event body에 포함되지 않는지 검증한다.
  - welcome event가 channel별로 한 번만 생성되는지 검증한다.
  - Telegram destination이 없으면 Telegram welcome이 생성/발송되지 않는지 검증한다.
- `backend/tests/test_notifications_api.py`
  - 기존 test notification 경로는 유지한다.
  - 필요 시 report 이벤트 외부 발송 mock 테스트를 추가한다.
  - email confirm 또는 Telegram verify 후 welcome 발송 helper가 호출되는지 mock으로 검증한다.
- `backend/tests/test_auth_api.py` 또는 auth 관련 기존 테스트
  - 새 Google 사용자 생성 시 Gmail welcome 발송이 시도되는지 mock으로 검증한다.
  - 기존 사용자 로그인 시 welcome이 중복 발송되지 않는지 검증한다.
  - welcome 발송 실패가 로그인 응답을 실패시키지 않는지 검증한다.

### Phase 6. 문서 갱신

- `docs/harness/features/favorite-asset-notifications.md`
  - report 알림이 리포트 원문이 아니라 상세 페이지 링크와 현재 가격을 보낸다는 점을 반영한다.
  - 최초 channel verification 시 welcome 메시지를 보낸다는 점과 중복 방지 기준을 반영한다.
  - 알림 job이 새 report를 생성하지 않는다는 규칙을 다시 명시한다.
- `docs/harness/features/authentication.md`
  - Google 최초 가입 welcome email을 구현할 경우 해당 auth side effect를 기록한다.
- `docs/harness/features/asset-detail-ai-community.md`
  - 외부 알림 링크가 `/detail/:ticker`로 들어오며 저장 리포트만 읽는다는 점을 연결한다.
- `docs/harness/feature-index.md`
  - 이 계획서와 향후 구현 기록을 Favorite asset notifications, Authentication, Asset detail change records에 연결한다.
- `.env.example`, `ENVIRONMENT_VARIABLE_SETUP.md`
  - `FRONTEND_BASE_URL`을 추가할 경우 문서화한다.

## Verification Plan

구현 후 최소 검증:

```powershell
cd backend
python -m pytest tests/test_notification_service.py tests/test_notifications_api.py
```

설정 추가가 있으면 import/설정 로드 smoke:

```powershell
cd backend
python -m compileall app
```

frontend 코드를 건드리지 않는다면 `npm run build`는 필수는 아니다. 단, 링크 route 확인이나 frontend 문구/UI를 함께 수정하면 다음을 실행한다.

```powershell
cd frontend
npm run build
```

실제 provider smoke는 별도 승인 및 credential 설정 후에만 진행한다. 이때도 token, refresh token, chat_id 전체값은 출력하지 않는다.

## Commands Run For This Plan

- `git status --short`
- `Get-ChildItem -Force`
- `Get-ChildItem docs/harness -Force`
- `Get-Content ARCHITECTURE.md`
- `Get-Content PROJECT_STRUCTURE_ANALYSIS.md`
- `Get-Content DEVELOPMENT_DIRECTION.md`
- `Get-Content docs/harness/feature-documentation-guide.md`
- `Select-String docs/harness/feature-index.md`
- `Get-Content docs/harness/features/favorite-asset-notifications.md`
- `Get-Content docs/harness/features/asset-detail-ai-community.md`
- `Get-Content docs/harness/gmail-telegram-notification-delivery-remediation-plan-2026-06-08.md`
- `rg`로 알림, 가격, 리포트, 상세 route 관련 코드 검색
- `Get-Content backend/app/services/notification_service.py`
- `Get-Content backend/app/api/notifications.py`
- `Get-Content backend/app/schemas.py`
- `Get-Content backend/app/models.py`
- `Get-Content backend/app/core/config.py`
- `Get-Content backend/tests/test_notification_service.py`
- `Get-Content backend/tests/test_notifications_api.py`
- `Get-Content frontend/src/pages/AssetDetail.jsx`
- `Get-Content frontend/src/utils/apiClient.js`
- `Get-Content frontend/src/utils/formatters.js`
- `Get-Content frontend/src/utils/assetCategories.js`

## Commands Not Run

- `python -m pytest ...`: 이번 요청은 계획서 작성만이며 구현 변경을 하지 않았다.
- `npm run build`: frontend 코드를 수정하지 않았다.
- Gmail/Telegram 실제 발송: 실제 provider credential과 외부 네트워크 호출이 필요하고, 이번 요청 범위는 하네스 엔지니어링 계획서 작성이다.
- `.env` 확인: secret 보호 규칙에 따라 읽지 않았다.

## Risks And Follow-Ups

- `FRONTEND_BASE_URL`을 잘못 설정하면 메일/Telegram 링크가 잘못된 배포 주소로 향한다.
- 현재 가격은 `market_cache` 기준이므로 cache가 비어 있거나 stale이면 fallback 또는 오래된 값이 노출될 수 있다. 메시지에 “현재 가격”을 표시하되, 가격 기준 시각이 필요하면 payload에 cache timestamp를 추가하는 후속 개선을 검토한다.
- 상세 페이지의 리포트 조회는 권한이 필요하므로, 링크를 받은 사용자가 Free tier이면 리포트 본문 대신 paywall을 볼 수 있다.
- Google 최초 가입 시점에는 Telegram `chat_id`가 없으므로 Telegram welcome은 channel verification 이후에만 가능하다.
- welcome 발송을 로그인/인증 흐름에 동기적으로 묶으면 외부 provider 장애가 사용자 로그인 경험을 망칠 수 있다. 구현 시 발송 실패가 인증 성공을 막지 않도록 처리해야 한다.
- welcome 중복 방지를 `NotificationEvent` dedupe key로 처리하면 schema 변경은 피할 수 있지만, 이벤트 테이블 정리 정책이 생길 때 중복 방지 근거가 사라질 수 있다. 장기적으로는 명시적인 `welcome_sent_at` column을 검토할 수 있다.
- report notification은 저장된 `AIReport` 변경을 감지할 뿐 새 report를 만들지 않는다. 이 규칙을 깨는 구현은 비용과 운영 리스크가 있으므로 금지한다.
- 기존 작업트리에 `docs/harness/feature-index.md`, `docs/harness/features/favorite-asset-notifications.md`, `TELEGRAM_MESSAGE_RECEIVE_PROCEDURE.md`, `docs/harness/telegram-message-delivery-verification-2026-06-09.md` 변경이 이미 있었다. 구현 단계에서는 이 사용자/기존 변경과 충돌하지 않도록 diff를 먼저 확인해야 한다.

## AI Report Generation Rule

이 계획은 report notification의 외부 메시지 형식만 바꾼다. 사용자-facing 요청, 챗봇 요청, 알림 평가, Gmail/Telegram 발송은 새 AI report 생성을 트리거하지 않고 저장된 scheduled report와 market cache만 읽어야 한다.
