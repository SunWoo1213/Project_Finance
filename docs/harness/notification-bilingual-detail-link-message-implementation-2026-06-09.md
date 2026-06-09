# Notification Bilingual Detail Link Message Implementation

Date: 2026-06-09

## Objective

Email과 Telegram으로 발송되는 알림 본문을 한국어 우선, 영어 하단 형식으로 정리한다. Telegram 최초 welcome message에서 제목과 본문이 같은 인사로 중복되는 문제를 제거하고, 뉴스 알림은 외부 뉴스 링크 대신 서비스의 자산 상세 페이지로 안내한다.

## Files Changed

- `backend/app/services/notification_service.py`
- `backend/tests/test_notification_service.py`
- `docs/harness/features/favorite-asset-notifications.md`
- `docs/harness/feature-index.md`

## Behavior Changes

- Welcome notification body에서 `Project Finance를 이용해주셔서 감사합니다.` 중복 문구를 제거했다. Telegram은 여전히 제목을 먼저 붙여 보내지만, 본문은 채널 안내로 바로 시작한다.
- Report, price change, news, 기본 test notification, email verification code 본문은 한국어 블록을 먼저 제공하고 `English` 섹션을 아래에 제공한다.
- Email subject는 기존 한국어 제목을 유지한다. 이메일 인증 제목도 `Project Finance 이메일 확인 코드`로 유지한다.
- News notification body는 원본 뉴스 `link`를 노출하지 않고 `FRONTEND_BASE_URL/detail/{ticker}` 상세 페이지 링크를 노출한다.
- News notification payload에는 원본 news item과 함께 `detail_url`을 저장한다. 원본 링크는 dedupe fingerprint와 payload 보존 용도이며 사용자 발송 본문에는 포함하지 않는다.
- 사용자 요청, 챗봇 요청, 알림 평가/발송은 새 AI 리포트 생성을 트리거하지 않는다. 이번 변경은 메시지 템플릿과 링크 정책만 수정한다.

## Verification Performed

- `.\.venv\Scripts\python.exe -m pytest tests\test_notification_service.py tests\test_notifications_api.py` from `backend/`: passed, 16 tests.
- Pytest emitted existing warnings for `datetime.utcnow()` deprecation and `.pytest_cache` write permission; no test failed.

## Follow-up Risks

- 사용자 입력으로 생성되는 test notification custom message는 자동 번역하지 않는다. 기본 테스트 메시지만 한/영 형식을 보장한다.
- In-app notification history도 같은 `NotificationEvent.body`를 표시하므로 외부 채널과 동일한 한/영 본문을 보게 된다.
- News 상세 페이지가 최신 뉴스 섹션을 충분히 노출하지 못하면 사용자가 본문 제목과 상세 페이지 내용을 매칭하기 어려울 수 있다.
