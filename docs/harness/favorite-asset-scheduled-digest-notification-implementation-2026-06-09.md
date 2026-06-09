# 즐겨찾기 자산 정시 요약 알림 구현

Date: 2026-06-09

관련 계획: `docs/harness/favorite-asset-scheduled-digest-notification-plan-2026-06-09.md`

## Objective

즐겨찾기 자산 Gmail/Telegram 알림을 변화 감지형 개별 메시지 대신 하루 3회 정시 요약 digest로 발송하도록 전환했다. 기본 시각은 `Asia/Seoul` 기준 `09:00`, `13:00`, `18:00`이다.

## Files Changed

- `backend/app/core/config.py`
- `backend/app/services/notification_service.py`
- `backend/app/main.py`
- `backend/tests/test_notification_service.py`
- `.env.example`
- `ENVIRONMENT_VARIABLE_SETUP.md`
- `docs/harness/features/favorite-asset-notifications.md`
- `docs/harness/feature-index.md`
- `docs/harness/favorite-asset-scheduled-digest-notification-plan-2026-06-09.md`
- `docs/harness/favorite-asset-scheduled-digest-notification-implementation-2026-06-09.md`

## Behavior Changes

- 새 설정을 추가했다.
  - `NOTIFICATION_DIGEST_SEND_TIMES=09:00,13:00,18:00`
  - `NOTIFICATION_TIMEZONE=Asia/Seoul`
  - `NOTIFICATION_DIGEST_MAX_ASSETS=20`
- `ENABLE_SCHEDULER=true`와 `ENABLE_NOTIFICATION_SCHEDULER=true`일 때 notification scheduler는 `NOTIFICATION_DIGEST_SEND_TIMES`의 각 시각에 cron job을 등록한다.
- 정시 job은 `create_scheduled_digest_notifications()`로 사용자별 즐겨찾기를 모아 `scheduled_digest` 이벤트를 만든다.
- Digest는 자산별 개별 이벤트가 아니라 검증되고 수신 동의된 `email`/`telegram` 채널별 1건이다.
- 같은 사용자/채널/날짜/정시 슬롯은 `digest:{user_id}:{YYYYMMDD}:{HHMM}` dedupe key로 중복 생성을 막는다.
- Digest 본문은 한국어 섹션을 먼저 쓰고 아래에 `English` 섹션을 둔다.
- 본문에는 즐겨찾기 자산명, ticker, market cache 기준 현재 가격, `FRONTEND_BASE_URL/detail/{ticker}` 링크를 포함한다.
- 가격 cache가 없으면 기존 포맷터처럼 `확인 중`을 표시한다.
- Pending event 발송과 재시도는 기존 `send_pending_notifications()` 경로를 그대로 사용한다.
- 기존 변화 감지 함수 `evaluate_notifications()`는 보존했지만 운영 scheduler에서는 더 이상 호출하지 않는다.

## Verification Performed

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_notification_service.py tests/test_notifications_api.py
```

결과:

- `17 passed`
- 경고: 기존 `datetime.utcnow()` deprecation warning이 발생했다.
- 경고: sandbox 권한상 `.pytest_cache` cache path 생성 경고가 발생했다. 테스트 결과에는 영향이 없었다.

```powershell
.\.venv\Scripts\python.exe -m compileall app
```

결과:

- passed
- `backend/app/core/config.py`, `backend/app/main.py`, `backend/app/services/notification_service.py` compile 확인.

## Commands Not Run

- Gmail/Telegram 실제 외부 발송 smoke는 실행하지 않았다. 실제 provider credential과 외부 네트워크 호출이 필요하다.
- Frontend 코드는 수정하지 않아 `npm run build`는 실행하지 않았다.

## Follow-Up Risks

- 사용자당 채널별 하루 최대 3건으로 줄였지만, 사용자 수가 커지면 Gmail/Telegram quota와 provider rate limit을 검토해야 한다.
- 정시 시각에 발송이 몰리므로 대규모 운영에서는 batching, jitter, queue worker 분리를 검토해야 한다.
- `NotificationEvent`는 정시 digest 기준 사용자당 채널별 하루 3건씩 증가한다. 테이블 보존 기간 정책이 필요할 수 있다.
- `NOTIFICATION_DIGEST_MAX_ASSETS`를 넘어서는 즐겨찾기는 본문에 모두 싣지 않고 나머지 개수만 안내한다.

## AI Report Generation Rule

이 변경은 정시 알림 이벤트 생성과 scheduler 연결만 바꾼다. 사용자-facing 요청, 챗봇 요청, 알림 job은 새 AI report 생성을 트리거하지 않는다. Digest 본문은 저장된 market cache와 상세 페이지 링크만 사용하며, report 본문을 외부 알림에 포함하지 않는다.
