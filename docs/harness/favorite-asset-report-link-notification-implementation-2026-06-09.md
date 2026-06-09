# 즐겨찾기 자산 리포트 링크형 메일/Telegram 알림 전환 구현

Date: 2026-06-09

## Objective

즐겨찾기 자산의 새 저장 리포트 알림을 Gmail/Telegram으로 보낼 때 리포트 본문 대신 자산 상세정보 페이지 링크와 현재 가격을 안내하도록 전환했다. 또한 Google 최초 가입과 알림 채널 최초 검증 완료 시 짧은 welcome message를 채널별로 한 번만 발송하도록 구현했다.

이 구현은 알림 메시지 포맷과 welcome 발송만 다룬다. 사용자 요청, 챗봇 요청, 알림 평가, 외부 발송은 새 AI report 생성을 트리거하지 않고 저장된 `AIReport`와 `market_cache`만 읽는다.

## Files Changed

- `backend/app/core/config.py`
  - backend-only non-secret 설정 `FRONTEND_BASE_URL`을 추가했다.
  - trailing slash를 제거하는 validator를 추가해 `/detail/{ticker}` 링크가 중복 slash를 만들지 않게 했다.
- `backend/app/services/notification_service.py`
  - report 알림 제목을 `즐겨찾기한 자산에 대한 보고서 발신입니다.`로 고정했다.
  - report 알림 body에 하루 인사, 자산명/ticker, 현재 가격, `FRONTEND_BASE_URL/detail/{ticker}` 링크를 포함했다.
  - `AIReport.final_content`는 외부 알림 body에 포함하지 않는다.
  - 가격 cache가 없으면 `현재 가격: 확인 중` fallback으로 이벤트를 계속 생성한다.
  - welcome message helper `send_welcome_notification_for_channel()`을 추가했다.
  - welcome 중복 방지는 `NotificationEvent` dedupe key `welcome:{user_id}:{channel}`로 처리한다.
- `backend/app/api/auth.py`
  - Google login에서 새 `User`가 생성된 경우 account email로 welcome email 발송을 시도한다.
  - welcome 발송 실패가 로그인 성공을 막지 않도록 예외를 삼키고 sanitized warning만 남긴다.
- `backend/app/api/notifications.py`
  - email/Telegram 채널 검증 완료 후 해당 채널 welcome message 발송을 시도한다.
  - welcome 발송 실패가 채널 검증 성공 응답을 막지 않도록 보호했다.
- `backend/tests/test_notification_service.py`
  - report 알림의 상세 링크, 가격 텍스트, payload, 본문 미포함 규칙 테스트를 추가했다.
  - 가격 cache fallback 테스트를 추가했다.
  - welcome event의 채널별 1회 dedupe와 destination 없는 Telegram skip 테스트를 추가했다.
- `backend/tests/test_notifications_api.py`
  - email confirm 테스트가 welcome 발송 hook을 mock하도록 갱신했다.
- `.env.example`
  - `FRONTEND_BASE_URL` 예시와 설명을 추가했다.
- `ENVIRONMENT_VARIABLE_SETUP.md`
  - `FRONTEND_BASE_URL`의 저장 위치, 용도, `VITE_API_BASE_URL`과의 차이를 문서화했다.
- `docs/harness/features/favorite-asset-notifications.md`
  - report 알림이 리포트 본문 대신 상세 링크와 현재 가격을 보낸다는 점을 반영했다.
  - Google 최초 가입 및 채널 최초 검증 welcome message와 dedupe 기준을 반영했다.
- `docs/harness/features/authentication.md`
  - Google 최초 가입 welcome email side effect를 기록했다.
- `docs/harness/features/asset-detail-ai-community.md`
  - 외부 report 알림 링크가 `/detail/:ticker`로 들어오며 저장 리포트 권한 흐름을 따른다는 점을 기록했다.
- `docs/harness/feature-index.md`
  - 계획서와 구현 기록을 Favorite asset notifications, Authentication, Asset detail change records에 연결했다.

## Behavior Changes

- 새 저장 report가 감지되면 report notification event는 아래 형식의 외부 발송 본문을 가진다.

```text
오늘 하루도 좋은 흐름으로 보내시길 바랍니다.

즐겨찾기하신 {asset.name}({asset.ticker}) 리포트가 준비되었습니다.
현재 가격: {current_price_text}
자산 리포트 링크: {FRONTEND_BASE_URL}/detail/{ticker}
```

- `payload_json`에는 `report_id`, `created_at`, `detail_url`, `current_price`, `current_price_text`, `price_source`를 저장한다.
- `FRONTEND_BASE_URL` 기본값은 `http://localhost:5173`이다.
- Google 최초 가입 시 Gmail welcome email을 한 번 시도한다.
- Email/Telegram 채널 검증 완료 시 해당 채널 welcome message를 한 번 시도한다.
- welcome 발송 실패는 로그인 또는 채널 검증 성공 자체를 실패시키지 않는다.

## Verification Performed

사용자 요청에 따라 검증 명령은 실행하지 않았다.

## Commands Not Run

- `python -m pytest tests/test_notification_service.py tests/test_notifications_api.py`: 사용자가 검증을 하지 말라고 요청했다.
- `python -m compileall app`: 사용자가 검증을 하지 말라고 요청했다.
- `npm run build`: frontend 코드를 수정하지 않았고, 사용자가 검증을 하지 말라고 요청했다.
- Gmail/Telegram 실제 발송: 실제 provider credential과 외부 네트워크 호출이 필요하며, 이번 요청은 검증 금지 조건이었다.

## Follow-Up Risks

- `FRONTEND_BASE_URL`이 운영 frontend origin과 다르면 메일/Telegram 링크가 잘못된 주소로 향한다.
- welcome 중복 방지를 `NotificationEvent` dedupe key에 의존하므로, 향후 이벤트 테이블 정리 정책이 생기면 별도 `welcome_sent_at` column을 검토해야 한다.
- Google 최초 가입 welcome email은 알림 email channel verification과 별개로 account email에 직접 발송을 시도한다. 운영 정책상 가입 직후 email 발송을 제한해야 한다면 별도 opt-in 정책을 추가해야 한다.
- 가격은 `market_cache` 기준이므로 cache가 비어 있거나 stale이면 fallback 또는 오래된 값이 표시될 수 있다.

## Linked Feature Docs

- `docs/harness/features/favorite-asset-notifications.md`
- `docs/harness/features/authentication.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/deployment-runtime.md`

## AI Report Generation Rule

이 구현은 report notification의 메시지 형식과 welcome message만 바꾼다. 사용자-facing 요청, 챗봇 요청, 알림 평가, Gmail/Telegram 발송은 새 AI report 생성을 트리거하지 않고 저장된 scheduled report와 market cache만 읽어야 한다.
