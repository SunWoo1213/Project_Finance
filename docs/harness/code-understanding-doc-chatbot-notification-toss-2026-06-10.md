# 코드 이해 문서 보강: 챗봇·알림·Toss 미구현 명시 (2026-06-10)

## 목적
`CODE_UNDERSTANDING.md`에서 누락되었던 챗봇과 Gmail/Telegram 알림 동작을 상세히 보강하고, Toss 결제 시스템이 아직 미구현임을 코드 사실에 근거해 명시한다.

## 변경 파일
- `CODE_UNDERSTANDING.md` (수정):
  - §1 기술 스택 표: 결제를 "Toss Payments 미구현(현재 mock 즉시 활성화만 동작)"으로 수정, 챗봇·알림 행 추가.
  - §3.2 API 표: billing/notifications 엔드포인트를 실제 라우터(`billing.py`, `notifications.py`)에 맞게 갱신, `toss/billing-key`가 HTTP 501을 반환함을 표기.
  - §3.3 서비스 표: 결제 행에 미구현 주석 추가.
  - §3.8 챗봇 절 신설: 규칙/LLM 경로, 5가지 안전장치(리포트 생성 금지, grounding 한정, 수치 가드, 네비게이션 계약, 멀티턴).
  - §3.9 알림 채널 절 신설: Telegram(manual chat_id)·Gmail(OAuth refresh→send) 연결·검증·발송 흐름, 평가/재시도/다이제스트, localhost 링크 보정.
  - §5.4 구독·결제 흐름: mock 경로(동작) vs Toss 경로(미구현) 분리, 미구현 근거 5개 항목 명시.
  - §5.5 알림 흐름: Gmail API/Telegram Bot API 기준으로 정정(기존 "Gmail SMTP" 표현 교체).
  - §9 변경 이력에 본 기록 링크 추가.

## 동작 변화
- 코드 동작 변화 없음. 문서 정확도 보강만 수행.

## 작성 근거 (코드 확인)
- 챗봇: [backend/app/services/chat_service.py](../../backend/app/services/chat_service.py)(LLM→규칙 폴백, 리포트 요약·수치 가드), [backend/app/services/chat_llm.py](../../backend/app/services/chat_llm.py)(시스템 프롬프트·structured output·grounding 한정).
- 알림: [backend/app/services/notification_service.py](../../backend/app/services/notification_service.py)(`_send_telegram`, `_send_gmail_message`, `_refresh_gmail_access_token`, `evaluate_notifications`, `send_pending_notifications`, `create_scheduled_digest_notifications`, `_normalize_app_links`), [backend/app/api/notifications.py](../../backend/app/api/notifications.py)(채널 연결/검증 엔드포인트).
- Toss 미구현 근거:
  - [backend/app/api/billing.py:151-157](../../backend/app/api/billing.py#L151-L157) — `POST /api/billing/toss/billing-key`가 `HTTP 501 NOT_IMPLEMENTED` 반환.
  - [backend/app/services/payment_service.py](../../backend/app/services/payment_service.py) — `TossPaymentsProvider.create_checkout_session`는 `PaymentProviderUnavailable` raise, `normalize_event`는 tier/status/subscription_id를 None으로 둠(구독 전이 불가), `verify_webhook_signature`는 no-op.
  - 실제 동작 경로는 `MockPaymentProvider` + `activate_mock_subscription`(결제 없이 즉시 ACTIVE).

## 검증
- 문서 전용 변경이라 코드 테스트는 실행하지 않음.
- 시크릿(.env, 토큰, 비밀번호, API 키)은 본문에 포함하지 않았으며 환경 변수는 이름만 언급.

## 미실행 명령 / 사유
- `pytest`, `npm run lint/build`: 코드 변경 없음으로 생략.

## 후속 위험 / 주의
- Toss 결제가 추후 구현되면 §1·§3.2·§3.3·§5.4의 "미구현" 표기를 반드시 갱신해야 한다([CLAUDE.md](../../CLAUDE.md) 문서 동기화 규율 5번, `CODE_UNDERSTANDING.md` §8).
- 결제/구독 상세는 `docs/harness/features/subscription-billing.md`가 별도 진실 소스다. 본 요약과 어긋나면 feature 문서를 우선한다.
