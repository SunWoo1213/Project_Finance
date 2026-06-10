# 정기요약 알림 링크 localhost 제거 계획

Date: 2026-06-10

## Objective

정기요약 또는 알림 메시지에 포함되는 상세 페이지 링크가 `http://localhost:5173` 같은 로컬 개발 주소로 전달되지 않도록, 백엔드 알림 발송 경로에서 운영 프론트엔드 공개 주소를 사용하게 한다. 이번 문서는 계획서이며 코드 구현은 수행하지 않는다.

관련 기능 문서: `docs/harness/features/favorite-asset-notifications.md`

## Current Findings

- 알림 발송의 주요 경로는 `backend/app/services/notification_service.py`이다.
- `send_pending_notifications()`는 `NotificationEvent.body`를 Telegram/Gmail adapter로 그대로 전달한다.
- 현재 저장소 코드에는 알림 메시지용 프론트엔드 공개 origin 설정이 없다.
- `daily_digest_enabled`는 `backend/app/models.py`, `backend/app/schemas.py`, `frontend/src/pages/MyPage.jsx`, `frontend/src/pages/NotificationsSettings.jsx`에 존재하지만, 별도 일일 요약 생성 job은 아직 확인되지 않았다.
- 현 구현에서 알림 평가는 `market_cache`, `notification_events`, `asset_notification_snapshots`, 저장된 `AIReport`만 읽는다. 사용자 요청이나 알림 발송이 새 AI 리포트 생성을 트리거하면 안 된다.

## Suspected Cause

운영 환경에서 메시지를 만드는 경로가 로컬 개발 기본 URL 또는 이미 저장된 로컬 URL이 포함된 `NotificationEvent.body`를 그대로 사용하고 있을 가능성이 높다. 발송 직전에 URL을 정규화하는 방어 계층이 없기 때문에, 한 번 `localhost`가 이벤트 본문에 들어가면 Gmail/Telegram 메시지에도 그대로 노출된다.

## Target Behavior

- 운영/배포 알림 메시지의 앱 내부 링크는 실제 프론트엔드 origin을 사용한다.
- 예: `https://<frontend-origin>/detail/NVDA`
- 로컬 개발에서는 명시 설정이 없을 때 기존 개발 흐름을 깨지 않는다.
- 운영 환경에서 프론트엔드 공개 주소가 설정되지 않았으면 새 알림 본문에 `localhost` 링크를 만들지 않는다.
- 이미 저장된 pending 이벤트 본문에 `localhost` URL이 있더라도 발송 직전에 실제 origin으로 치환한다.
- 외부 뉴스 링크(`https://news...`)는 변경하지 않는다.

## Recommended Design

1. 설정 추가
   - `backend/app/core/config.py`에 `FRONTEND_PUBLIC_BASE_URL: str | None = None`를 추가한다.
   - 이 값은 공개 origin이며 secret이 아니다.
   - 배포 backend host에 `FRONTEND_PUBLIC_BASE_URL=https://<vercel-frontend-origin>` 형태로 등록한다.
   - 문서에는 실제 값을 남기지 않는다.

2. URL helper 추가
   - `backend/app/services/notification_service.py`에 작은 helper를 둔다.
   - 권장 함수:
     - `_frontend_base_url() -> str | None`
     - `_asset_detail_url(ticker: str) -> str | None`
     - `_normalize_message_links(body: str) -> str`
   - `settings.FRONTEND_PUBLIC_BASE_URL`이 있으면 trailing slash를 제거하고 사용한다.
   - 없고 `settings.ENVIRONMENT == "development"`이면 `http://localhost:5173` fallback을 허용한다.
   - 그 외 환경에서는 `None`을 반환해 새 localhost 링크 생성을 막는다.

3. 이벤트 payload와 본문 정리
   - 가격 변동, 뉴스, AI 리포트 갱신 이벤트의 `payload_json`에 내부 상세 경로를 넣는다.
   - 권장 payload 필드:
     - `app_path`: `/detail/<urlencoded ticker>`
     - `app_url`: `https://<frontend-origin>/detail/<urlencoded ticker>` 가능할 때만
   - 본문에는 가능할 때만 `자세히 보기: <app_url>`을 추가한다.
   - `app_url`을 만들 수 없는 운영 환경에서는 본문에 링크를 넣지 않는다.

4. 발송 직전 방어
   - `_send_telegram()`과 `_send_email()` 또는 그 공통 직전 단계에서 `event.body`를 `_normalize_message_links()`로 보정한다.
   - 치환 대상은 앱 내부 localhost만 제한한다.
   - 권장 치환 대상:
     - `http://localhost:5173`
     - `http://127.0.0.1:5173`
   - 치환 origin은 `FRONTEND_PUBLIC_BASE_URL`이 있을 때만 사용한다.
   - 일반 외부 링크나 backend API URL은 치환하지 않는다.

5. 정기요약 구현 확인
   - 다음 구현 시 `daily_digest_enabled`를 실제로 사용하는 별도 job이 있는지 다시 검색한다.
   - 별도 job이 없다면 이번 수정은 현재 알림 이벤트 발송 경로에 적용한다.
   - 별도 job이 추가되어 있다면 동일 helper를 재사용한다.

## Files To Change Later

- `backend/app/core/config.py`
  - `FRONTEND_PUBLIC_BASE_URL` 설정 추가.
- `backend/app/services/notification_service.py`
  - 프론트엔드 링크 helper 추가.
  - 알림 이벤트 생성 시 내부 상세 URL 추가.
  - Gmail/Telegram 발송 직전 localhost URL 보정.
- `backend/tests/test_notification_service.py`
  - URL helper, 이벤트 payload, 발송 직전 치환 테스트 추가.
- `docs/harness/features/favorite-asset-notifications.md`
  - 런타임 변수 목록과 Change Records 업데이트.
- 필요 시 배포 문서
  - `docs/harness/features/deployment-runtime.md` 또는 실제 배포 가이드에 `FRONTEND_PUBLIC_BASE_URL` 등록 항목 추가.

## Test Plan

백엔드 단위 테스트:

```powershell
cd backend
python -m pytest tests/test_notification_service.py
```

권장 테스트 케이스:

- `FRONTEND_PUBLIC_BASE_URL=https://app.example.com`일 때 `localhost:5173/detail/NVDA`가 `https://app.example.com/detail/NVDA`로 치환된다.
- `FRONTEND_PUBLIC_BASE_URL`이 없고 `ENVIRONMENT=production`이면 새 이벤트 본문에 localhost 링크를 추가하지 않는다.
- 외부 뉴스 링크는 치환하지 않는다.
- Gmail/Telegram adapter에 전달되는 body가 보정된 body인지 확인한다.
- AI 리포트 갱신 알림은 저장된 `AIReport`만 읽고 새 리포트를 생성하지 않는다.

확장 검증:

```powershell
cd backend
python -m pytest tests/test_notifications_api.py tests/test_notification_service.py
```

프론트엔드 변경이 없으면 `npm run lint`/`npm run build`는 필수는 아니지만, MyPage 문구나 알림 설정 UI를 건드리면 실행한다.

## Deployment Notes

- backend host 환경변수에 `FRONTEND_PUBLIC_BASE_URL`을 추가해야 한다.
- Vercel frontend에는 기존처럼 `VITE_API_BASE_URL`을 backend origin으로 둔다.
- `FRONTEND_PUBLIC_BASE_URL`은 backend가 사용자에게 보여줄 frontend origin이고, `VITE_API_BASE_URL`은 frontend가 호출할 backend origin이다. 두 값을 혼동하지 않는다.
- 실제 origin 값은 문서나 로그에 반복 노출하지 않는다. secret은 아니지만 환경별 운영 정보로 취급한다.

## Risks And Follow-up

- 이미 DB에 저장된 `NotificationEvent.body` 중 `localhost` URL이 포함된 pending 이벤트는 발송 전 보정으로 해결한다. 이미 sent 처리된 과거 이메일/Telegram 메시지는 수정할 수 없다.
- `daily_digest_enabled`의 실제 job이 아직 없다면 사용자가 말한 "정기요약"이 현재 알림 테스트/리포트 갱신 알림을 가리키는지 운영 DB 이벤트 타입으로 확인해야 한다.
- 운영 환경에서 `FRONTEND_PUBLIC_BASE_URL`이 비어 있으면 링크를 넣지 않는 것이 localhost를 보내는 것보다 안전하다.

## AI Report Generation Rule

이 계획은 알림 메시지의 링크 생성과 발송 전 본문 보정만 다룬다. 사용자 요청, 챗봇 요청, 알림 평가/발송, 정기요약 발송은 새 AI 리포트 생성을 트리거하면 안 되며 저장된 scheduled report와 market/news cache만 읽어야 한다.
