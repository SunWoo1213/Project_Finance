# 정기요약 알림 링크 localhost → 실제 주소 전환 구현 기록

Date: 2026-06-10

관련 계획서: `docs/harness/scheduled-digest-localhost-link-fix-plan-2026-06-10.md`
관련 기능 문서: `docs/harness/features/favorite-asset-notifications.md`

## Objective

정기요약(scheduled digest)을 포함한 모든 Gmail/Telegram 알림의 자산 상세 페이지 링크가 `http://localhost:5173` 로컬 개발 주소로 발송되는 문제를 해결한다. 운영 환경에서는 이용자가 실제 접속 가능한 프론트엔드 공개 origin을 링크로 받도록 하고, 발송 직전 보정 계층과 운영 환경 가드를 추가했다. 메일·Telegram 두 채널 모두 동일하게 적용한다.

## 근본 원인 (코드 기준 확인)

- 모든 알림 본문 링크는 단일 helper `_build_asset_detail_url(ticker)` → `{settings.FRONTEND_BASE_URL}/detail/{ticker}`를 사용한다.
- `FRONTEND_BASE_URL` 기본값은 `http://localhost:5173`이며, 운영 backend에 환경변수가 실제 frontend origin으로 설정되지 않으면 localhost가 그대로 링크에 들어간다. 즉 1차 원인은 배포 설정 누락이고, 2차 원인은 운영에서 localhost를 막는 방어 계층 부재였다.
- 기존 `docs/harness/notification-public-link-remediation-*-2026-06-10.md` 문서는 `FRONTEND_PUBLIC_BASE_URL`과 `_normalize_message_links` 등을 추가했다고 기록하지만 **실제 코드에는 존재하지 않았다.** 이번 구현은 이미 배선되어 있는 `FRONTEND_BASE_URL`을 기준으로 진행했다.

## Files Changed

- `backend/app/services/notification_service.py`
- `backend/tests/test_notification_service.py`
- `docs/harness/features/favorite-asset-notifications.md`
- `docs/harness/feature-index.md`
- `docs/harness/scheduled-digest-localhost-link-fix-implementation-2026-06-10.md`

## Behavior Changes

- `notification_service.py`에 `import logging`과 module logger를 추가했다.
- 상수 `LOCALHOST_APP_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")`를 추가했다.
- helper `_is_localhost_base_url(base_url)`를 추가했다.
- `_build_asset_detail_url(ticker)`에 운영 환경 가드를 추가했다. `ENVIRONMENT != "development"`인데 `FRONTEND_BASE_URL`이 localhost면 `logger.warning`으로 1회 경고한다. URL 생성 동작 자체(`{base_url}/detail/{ticker}`)는 그대로다.
- helper `_normalize_app_links(body)`를 추가했다.
  - `FRONTEND_BASE_URL`이 localhost가 **아닐 때만** 본문의 `http://localhost:5173`·`http://127.0.0.1:5173` 앱 내부 origin을 `FRONTEND_BASE_URL`로 치환한다.
  - 개발 환경(`FRONTEND_BASE_URL`이 localhost)에서는 그대로 둔다.
  - 외부 뉴스/일반 링크는 건드리지 않는다(앱 내부 origin만 대상).
- 발송 직전 보정 적용:
  - `_send_telegram()`: `text = f"{event.title}\n\n{_normalize_app_links(event.body)}"`.
  - `_send_email()`: `_send_gmail_message(destination, event.title, _normalize_app_links(event.body))`.
  - DB의 `NotificationEvent.body`는 변경하지 않고 발송 메시지에만 보정을 적용한다.

이로써 (1) 운영 backend에 `FRONTEND_BASE_URL`이 올바르게 설정되면 신규 정기요약 링크는 처음부터 실제 주소가 되고, (2) 이미 저장된 pending 이벤트 본문에 localhost가 남아 있어도 발송 직전 실제 origin으로 보정된다.

## Verification Performed

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_notification_service.py tests/test_notifications_api.py -q
```

결과: `21 passed` (기존 17 + 신규 4).

신규 테스트:

- `test_normalize_app_links_rewrites_localhost_app_links`: `FRONTEND_BASE_URL=https://finance.example.com`일 때 본문의 `localhost:5173`·`127.0.0.1:5173` 상세 링크가 실제 origin으로 치환된다.
- `test_normalize_app_links_keeps_external_news_links`: 외부 뉴스 링크는 치환하지 않는다.
- `test_normalize_app_links_noop_in_localhost_environment`: `FRONTEND_BASE_URL`이 localhost면 그대로 둔다.
- `test_build_asset_detail_url_warns_on_localhost_in_production`: 비개발 환경에서 localhost base면 경고 로그를 남기고 URL은 그대로 생성한다.

경고: 기존 `datetime.utcnow()` deprecation warning이 발생했다. 이번 변경과 무관한 기존 시간 처리 방식 경고다.

## Commands Not Run

- Frontend 코드는 변경하지 않아 `npm run lint`/`npm run build`는 실행하지 않았다.
- Alembic migration은 schema 변경이 없어 실행 대상이 아니다.
- 실제 Gmail/Telegram 외부 발송 smoke는 provider credential과 외부 네트워크가 필요하므로 자동 검증 범위에서 제외했다.

## Deployment Notes (필수)

- 운영 backend 호스트(Render) 환경변수에 `FRONTEND_BASE_URL=https://<vercel-frontend-origin>`을 설정하고 재배포해야 신규 정기요약 링크가 실제 주소로 나간다. 코드 보정은 이미 발송된 과거 메시지를 고치지 못한다.
- `FRONTEND_BASE_URL`은 backend가 사용자에게 보여줄 **프론트엔드 origin**, `VITE_API_BASE_URL`은 frontend가 호출할 **backend origin**이다. 두 값을 혼동하지 않는다.
- `FRONTEND_BASE_URL`은 secret은 아니나 환경별 운영 정보이므로 문서/로그에 실제 값을 반복 노출하지 않는다.

## Follow-up Risks

- 운영 환경에서 `FRONTEND_BASE_URL`이 설정되지 않으면 링크는 여전히 localhost로 생성된다(경고 로그만 남는다). 발송 직전 보정도 `FRONTEND_BASE_URL`이 localhost이면 동작하지 않는다. 따라서 배포 환경변수 설정이 반드시 선행되어야 한다.
- 기존 불일치 문서 `docs/harness/notification-public-link-remediation-plan-2026-06-10.md` / `...-implementation-2026-06-10.md`는 코드에 없는 `FRONTEND_PUBLIC_BASE_URL`을 전제하므로 이 구현 기록이 실제 동작의 기준이다.

## AI Report Generation Rule

이번 변경은 알림 메시지의 링크 생성·발송 직전 본문 보정과 운영 환경 가드만 다룬다. 사용자 요청, 챗봇 요청, 알림 평가/발송, 정기요약 발송은 새 AI 리포트 생성을 트리거하지 않으며 저장된 scheduled report와 market/news cache만 읽는다.
