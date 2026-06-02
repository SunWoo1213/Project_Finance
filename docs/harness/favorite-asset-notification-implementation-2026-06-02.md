# 즐겨찾기 자산 알림 구현

Date: 2026-06-02

## Objective

`docs/harness/favorite-asset-notification-plan-2026-06-02.md`의 MVP 기반을 구현했다. 계정 기반 즐겨찾기, 알림 설정, 채널 연결, 알림 이력, 가격/뉴스/저장 리포트 변경 감지, 안전한 발송 adapter와 프론트 설정 화면을 추가했다.

## Files Changed

- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/app/api/favorites.py`
- `backend/app/api/notifications.py`
- `backend/app/services/favorite_service.py`
- `backend/app/services/notification_service.py`
- `backend/alembic/versions/20260602_0001_add_favorite_notification_tables.py`
- `backend/tests/test_favorites_api.py`
- `backend/tests/test_notifications_api.py`
- `backend/tests/test_notification_service.py`
- `.env_example`
- `frontend/src/App.jsx`
- `frontend/src/store/favoriteStore.js`
- `frontend/src/pages/CategoryView.jsx`
- `frontend/src/pages/NotificationsSettings.jsx`
- `docs/harness/features/favorite-asset-notifications.md`
- `docs/harness/features/favorites.md`
- `docs/harness/features/market-data.md`
- `docs/harness/features/authentication.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/feature-index.md`

## Behavior Changes

- 로그인 사용자의 즐겨찾기가 `user_favorite_assets`에 저장된다.
- 로그인 직후 기존 `localStorage.favoriteAssets`가 서버 즐겨찾기와 병합된다.
- `/api/notifications/preferences`에서 가격 변동률 기준, 뉴스/리포트/채널 toggle을 관리한다.
- `/api/notifications/channels/*`에서 Telegram/email 채널 검증 상태를 저장한다.
- `/api/notifications/history`에서 최근 알림 이력을 조회한다.
- `/settings/notifications` 화면에서 알림 조건, 채널 연결, 테스트 알림, 이력을 관리한다.
- notification evaluator는 캐시된 가격/뉴스와 저장된 `AIReport`만 읽는다. 사용자 요청 또는 알림 job이 AI 리포트 생성을 트리거하지 않는다.
- `ENABLE_NOTIFICATION_SCHEDULER=false`가 기본값이므로 운영자가 명시적으로 켜기 전까지 알림 scheduler는 자동 실행되지 않는다.

## Verification Performed

구현 후 다음 검증을 수행했다.

- `python -m pytest tests/test_favorites_api.py tests/test_notifications_api.py tests/test_notification_service.py`: passed, 5 tests.
- `python -m alembic upgrade head`: local package entrypoint 문제로 실패했다.
- `python -c "from alembic.config import main; main(argv=['upgrade','head'])"` with test env and `PYTHONPATH=C:\Tmp\project_finance_pydeps`: passed against disposable SQLite DB.
- `npm run lint`: passed.
- `npm run build`: passed. Vite reported the existing large chunk warning after a successful build.
- `git diff --check`: passed. Git printed line-ending normalization warnings only.

## Follow-up Risks

- Telegram bot의 실제 `/start <code>` webhook/polling handler는 아직 별도 작업이다. 현재 verify endpoint는 수동 검증 prototype이다.
- Email 확인 코드는 prototype 편의를 위해 응답으로 반환된다. 운영에서는 provider 발송과 확인 링크로 전환해야 한다.
- 외부 Telegram/SMTP provider가 설정되지 않으면 pending 발송은 failed 이력으로 남는다.
- 뉴스 알림 coverage는 현재 캐시에 들어온 뉴스 범위에 좌우된다.
