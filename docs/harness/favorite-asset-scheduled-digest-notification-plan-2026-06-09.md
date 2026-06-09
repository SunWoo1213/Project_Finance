# 즐겨찾기 자산 정시 요약 알림 계획

Date: 2026-06-09

## Objective

즐겨찾기 자산의 Gmail/Telegram 알림을 변화 감지형 개별 메시지에서 하루 3회 정시 요약 digest로 전환한다. 기본 발송 시각은 `Asia/Seoul` 기준 `09:00`, `13:00`, `18:00`이며, 변화 여부와 상관없이 검증되고 수신 동의된 채널별로 사용자당 1건의 요약 메시지를 만든다.

## Planned Behavior

- `ENABLE_SCHEDULER=true`와 `ENABLE_NOTIFICATION_SCHEDULER=true`일 때만 정시 digest scheduler를 등록한다.
- 기본 발송 시간은 `NOTIFICATION_DIGEST_SEND_TIMES=09:00,13:00,18:00`로 둔다.
- 기본 시간대는 `NOTIFICATION_TIMEZONE=Asia/Seoul`로 둔다.
- 각 정시 job은 사용자별 즐겨찾기 목록을 읽고, 활성화된 `email`/`telegram` 채널에만 digest `NotificationEvent`를 생성한다.
- digest는 자산별 개별 이벤트가 아니라 채널별 1건이다.
- 같은 사용자/채널/날짜/정시 슬롯은 `dedupe_key`로 한 번만 생성한다.
- 발송 본문은 한국어를 먼저 쓰고 아래에 `English` 섹션을 둔다.
- 본문에는 즐겨찾기 자산명, ticker, market cache 기준 현재 가격, 자산 상세 페이지 링크를 포함한다.
- 즐겨찾기가 많을 때 Telegram 길이와 사용자 피로도를 줄이기 위해 기본 표시 개수를 제한하고, 나머지 개수를 안내한다.
- 기존 `send_pending_notifications()` 재시도 흐름은 유지한다.

## Files To Change

- `backend/app/core/config.py`
- `backend/app/services/notification_service.py`
- `backend/app/main.py`
- `backend/tests/test_notification_service.py`
- `.env.example`
- `ENVIRONMENT_VARIABLE_SETUP.md`
- `docs/harness/features/favorite-asset-notifications.md`
- `docs/harness/feature-index.md`
- 구현 기록 문서

## Risk Notes

- 변화 여부와 상관없이 발송하므로 발송량은 기존보다 늘 수 있다.
- digest 설계로 자산별 개별 메시지 폭증은 피하지만, 사용자 수와 채널 수가 늘면 Gmail/Telegram quota와 provider rate limit을 확인해야 한다.
- 정시 job이 같은 시각에 몰리므로 운영 규모가 커지면 user batching, jitter, queue worker 분리를 검토해야 한다.
- `notification_events`는 사용자당 채널별 하루 최대 3건씩 증가한다.

## Verification Plan

- Backend focused tests:
  - `python -m pytest tests/test_notification_service.py tests/test_notifications_api.py`
- Config/import smoke:
  - `python -m compileall app`
- 실제 Gmail/Telegram 외부 발송 smoke는 credential과 외부 네트워크가 필요하므로 이번 구현 검증에서는 실행하지 않는다.

## AI Report Generation Rule

이 변경은 정시 알림 생성과 발송 스케줄만 바꾼다. 사용자 요청, 챗봇 요청, 알림 job은 새 AI 리포트를 생성하지 않는다. digest 본문은 저장된 market cache와 상세 페이지 링크만 사용하며, 저장된 리포트 본문도 외부 알림에 포함하지 않는다.
