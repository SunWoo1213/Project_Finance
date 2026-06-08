# Gmail/Telegram 알림 미발송 원인 진단 기록

Date: 2026-06-08

관련 기능 문서: `docs/harness/features/favorite-asset-notifications.md`
관련 구현 기록: `docs/harness/gmail-telegram-notification-delivery-remediation-implementation-2026-06-08.md`

## Objective

"메일 발송과 텔레그램 발송이 나가지 않는다"는 증상의 원인을 코드 경로 기준으로 진단한다. 이 문서는 코드 변경 없이 원인 후보와 secret 노출 없는 확인 절차를 정리한 audit 기록이다.

## 진단 결론 요약

발송 로직(`notification_service.py`) 자체는 정상이다. 메일/텔레그램이 실제로 나가려면 아래 **3개 관문**을 모두 통과해야 하며, 어느 하나라도 닫혀 있으면 발송이 멈춘다. 가능성 높은 순서는 **관문 1 → 관문 3 → 관문 2** 이다.

## 관문 1: 알림 스케줄러 활성화 여부 (1순위 의심)

- 위치: `backend/app/main.py:183`(바깥 게이트), `backend/app/main.py:234`(알림 job 등록 게이트)
- 발송 job(`run_notification_evaluation_job`, `run_notification_delivery_job`)이 등록되려면 다음 두 플래그가 **모두 true**여야 한다.

| 플래그 | 기본값 | 위치 |
|---|---|---|
| `ENABLE_SCHEDULER` | `True` | `backend/app/core/config.py:91` |
| `ENABLE_NOTIFICATION_SCHEDULER` | **`False`** | `backend/app/core/config.py:164` |

- `ENABLE_NOTIFICATION_SCHEDULER`가 기본 `False`다. `.env`에 명시적으로 `true`를 넣지 않으면 평가/발송 job 자체가 등록되지 않아 **pending 이벤트가 쌓이기만 하고 영원히 발송되지 않는다.**
- 조치: 운영에서 자동 알림을 쓰려면 `.env`에 `ENABLE_SCHEDULER=true`와 `ENABLE_NOTIFICATION_SCHEDULER=true`를 모두 설정한 뒤 백엔드를 재시작한다.

## 관문 2: 채널 검증(verified) 여부

- 위치: `backend/app/services/notification_service.py:564-577`
- 발송 직전, 해당 사용자/채널의 `NotificationChannelConnection`이 `verified=True`이고 `destination`(Telegram 숫자 `chat_id` / 이메일 주소)이 있어야 한다.
- 조건 미충족 시:
  - `event.status = "failed"`
  - `event.error_message = "Notification channel is not verified."`
- 주의: Telegram은 webhook 자동 검증이 아니라 **사용자가 숫자 `chat_id`를 직접 입력하는 수동 방식**이다(마이페이지 "수신 동의" 인라인 UI에서 connect→verify). 이메일은 코드 인증(verify→confirm)을 끝내야 한다.

## 관문 3: provider 자격증명(env) 충족 여부

- Telegram: `backend/app/services/notification_service.py:606-608`
  - `TELEGRAM_BOT_TOKEN` 누락 시 → `"Telegram bot token is not configured."`
- Gmail: `backend/app/services/notification_service.py:656-662`
  - `EMAIL_PROVIDER`가 `gmail`이 아니면 → `"EMAIL_PROVIDER must be gmail."`
  - `EMAIL_FROM_ADDRESS`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN` 중 하나라도 비면 → `"Gmail email settings are incomplete: ..."`
  - OAuth scope에 `https://www.googleapis.com/auth/gmail.send`가 포함되어야 한다.

## 재시도/실패 처리 동작

- 위치: `backend/app/services/notification_service.py:586-598`
- 발송 실패 시 `attempts`를 증가시키고, 3회 미만이면 지수 백오프(`2 ** attempts`분: 2/4/8분)로 `next_attempt_at`을 미룬다. `attempts >= 3`이면 `status="failed"`로 확정한다.
- 따라서 일시적 실패는 자동 재시도되지만, 관문 1~3이 닫혀 있으면 재시도해도 동일하게 실패한다.

## Secret 노출 없이 원인을 확인하는 방법

- 진단 함수: `backend/app/services/notification_service.py:58-86` (`get_delivery_configuration_status`)
- 노출 엔드포인트: `POST /api/notifications/test` 응답의 `delivery_status` (`backend/app/api/notifications.py:194-212`)
- 이 응답은 실제 토큰/secret 값은 숨기고 **누락된 환경 변수 이름과 활성화 상태만** 반환한다.

응답 해석 기준:

- `scheduler.enabled == false` → 관문 1 문제. `ENABLE_NOTIFICATION_SCHEDULER=true`(및 `ENABLE_SCHEDULER=true`) 설정 후 재시작.
- `email.missing_keys` 또는 `telegram.missing_keys`에 항목 존재 → 관문 3 문제. 해당 env 채우기.
- 둘 다 `configured: true`인데도 이벤트가 `failed` → 관문 2(채널 미검증) 또는 토큰 만료/HTTP 오류. 이때 sanitized 원인은 `NotificationEvent.error_message`에 저장된다.

## Verification Performed

- 코드 변경 없는 진단 기록이므로 테스트/빌드는 실행하지 않았다.
- `.env`는 secret 보호 규칙에 따라 읽지 않았다. 환경 변수는 이름 기준으로만 참조했다.

## Follow-up

- 운영자가 `delivery_status` 결과 또는 `.env`에 설정된 키 이름(값 제외)을 확인하면 어느 관문인지 확정할 수 있다.
- 필요 시 DB의 `NotificationEvent`에서 `status`/`error_message`/`attempts`를 조회하는 진단 쿼리를 별도로 작성할 수 있다.

## AI Report Generation Rule

이 진단은 알림 평가/발송 경로만 다룬다. 사용자 요청, 챗봇 요청, 알림 발송은 새 AI 리포트 생성을 트리거하지 않고 저장된 scheduled report와 market/news 캐시만 읽는 기존 규칙을 유지한다.
