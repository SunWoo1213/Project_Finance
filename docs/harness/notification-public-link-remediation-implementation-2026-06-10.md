# 정기요약 알림 링크 localhost 제거 구현 기록

Date: 2026-06-10

관련 계획서: `docs/harness/notification-public-link-remediation-plan-2026-06-10.md`
관련 기능 문서: `docs/harness/features/favorite-asset-notifications.md`

## Objective

정기요약 또는 즐겨찾기 자산 알림 메시지에 포함되는 앱 내부 링크가 `http://localhost:5173` 같은 로컬 개발 주소로 발송되지 않도록, 백엔드 알림 생성/발송 경로에 공개 프론트엔드 origin 설정과 발송 직전 링크 보정 계층을 추가했다.

## Files Changed

- `backend/app/core/config.py`
- `backend/app/services/notification_service.py`
- `backend/tests/test_notification_service.py`
- `docs/harness/features/favorite-asset-notifications.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/feature-index.md`
- `docs/harness/notification-public-link-remediation-implementation-2026-06-10.md`

## Behavior Changes

- backend 설정에 `FRONTEND_PUBLIC_BASE_URL`을 추가했다.
  - 예: `https://<frontend-origin>`
  - 이 값은 backend가 Gmail/Telegram 알림 본문에 넣을 공개 프론트엔드 origin이다.
  - `VITE_API_BASE_URL`은 frontend가 호출할 backend origin이므로 서로 바꿔 쓰면 안 된다.
- `notification_service.py`에 앱 상세 링크 helper를 추가했다.
  - `_frontend_base_url()`
  - `_asset_detail_path()`
  - `_asset_detail_url()`
  - `_notification_payload_with_asset_link()`
  - `_append_asset_detail_link()`
  - `_normalize_message_links()`
- 가격 변동, 뉴스, AI 리포트 갱신 알림 payload에 `app_path`를 추가하고, 공개 origin을 만들 수 있을 때만 `app_url`을 추가한다.
- 공개 origin이 있을 때 알림 본문에 `자세히 보기: <app_url>`을 추가한다.
- `FRONTEND_PUBLIC_BASE_URL`이 없고 `ENVIRONMENT != development`인 경우 새 알림 본문에는 localhost 앱 링크를 추가하지 않는다.
- Gmail/Telegram 발송 직전에 기존 pending 이벤트 본문에 남아 있을 수 있는 `http://localhost:5173` 및 `http://127.0.0.1:5173` 앱 내부 링크를 `FRONTEND_PUBLIC_BASE_URL`로 치환한다.
- 외부 뉴스 링크는 치환하지 않는다.

## Verification Performed

```powershell
cd backend
python -m pytest tests/test_notifications_api.py tests/test_notification_service.py
```

결과:

- `13 passed`
- 경고: SQLAlchemy/Python `datetime.utcnow()` deprecation warning이 발생했다. 이번 링크 보정 변경과 무관한 기존 시간 처리 방식에서 나온 경고다.

## Commands Not Run

- 프론트엔드 파일은 변경하지 않았으므로 `npm run lint`, `npm run build`는 이번 변경의 필수 검증이 아니다.
- 실제 Gmail/Telegram 발송 smoke는 provider credential과 외부 네트워크가 필요하므로 로컬 자동 검증 범위에서 제외한다.
- Alembic migration은 schema 변경이 없으므로 실행 대상이 아니다.

## Additional Check

문서 갱신 후 아래 명령으로 whitespace 문제를 확인한다.

```powershell
git diff --check
```

결과: whitespace 오류 없음. Windows 줄바꿈 변환 경고만 표시됨.

## Deployment Notes

- backend host 환경변수에 `FRONTEND_PUBLIC_BASE_URL=https://<vercel-frontend-origin>`을 추가해야 운영 알림에 실제 페이지 링크가 들어간다.
- `FRONTEND_PUBLIC_BASE_URL`은 secret은 아니지만 환경별 운영 정보이므로 문서와 로그에 실제 값을 반복 노출하지 않는다.
- 기존 Vercel frontend의 `VITE_API_BASE_URL`은 계속 backend API origin을 가리켜야 한다.
- 이미 발송 완료된 과거 이메일/Telegram 메시지는 수정할 수 없다. pending 이벤트는 발송 직전 보정으로 보호된다.

## Follow-up Risks

- `daily_digest_enabled` 설정은 존재하지만 별도 일일 요약 job은 아직 확인되지 않았다. 향후 별도 digest job이 추가되면 이번 helper를 재사용해야 한다.
- 운영 환경에서 `FRONTEND_PUBLIC_BASE_URL`이 비어 있으면 알림 본문에 앱 상세 링크를 새로 넣지 않는다. 링크가 꼭 필요하다면 env 설정 후 재배포해야 한다.

## AI Report Generation Rule

이번 변경은 알림 메시지의 링크 생성과 발송 직전 본문 보정만 다룬다. 사용자 요청, 챗봇 요청, 알림 평가/발송, 정기요약 발송은 새 AI 리포트 생성을 트리거하지 않는다. AI 리포트 갱신 알림은 기존처럼 저장된 `AIReport`만 읽는다.
