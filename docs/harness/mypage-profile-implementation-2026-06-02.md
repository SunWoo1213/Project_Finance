# 마이페이지 프로필/즐겨찾기/수신 동의 구현 기록

Date: 2026-06-02

## Objective

마이페이지 계획 문서에 따라 `/mypage`를 구현하고, 댓글 작성 전 닉네임 확정 게이트를 백엔드와 프론트엔드 양쪽에 연결했다. 즐겨찾기 자산 태그 관리와 Telegram/Google Mail 수신 동의 해제도 마이페이지에서 처리하도록 통합했다.

## Files Changed

- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/app/api/auth.py`
- `backend/app/api/community.py`
- `backend/app/api/profile.py`
- `backend/app/api/DEVELOPMENT_DIRECTION.md`
- `backend/app/main.py`
- `backend/app/services/profile_service.py`
- `backend/alembic/versions/20260602_0002_add_user_nickname_confirmed_at.py`
- `backend/tests/test_profile_api.py`
- `frontend/src/App.jsx`
- `frontend/src/components/Header.jsx`
- `frontend/src/pages/AssetDetail.jsx`
- `frontend/src/pages/MyPage.jsx`
- `frontend/src/pages/DEVELOPMENT_DIRECTION.md`
- `frontend/src/pages/CategoryView.jsx`
- `frontend/src/store/authStore.js`
- `frontend/src/store/favoriteStore.js`
- `frontend/src/utils/constants.js`
- `docs/harness/features/mypage-profile.md`
- `docs/harness/feature-index.md`
- `docs/harness/features/authentication.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/favorites.md`
- `docs/harness/features/favorite-asset-notifications.md`

## Behavior Changes

- `users.nickname_confirmed_at` nullable 컬럼을 추가했다.
- Google 로그인 응답에 `nickname_confirmed`, `profile_complete`를 추가했다.
- `GET /api/profile/me`, `GET /api/profile/nickname-availability`, `PATCH /api/profile/nickname`를 추가했다.
- 댓글 생성 API는 닉네임 미확정 사용자에게 `403`과 `NICKNAME_REQUIRED`를 반환한다.
- `/mypage`에서 닉네임 중복 확인 후 저장, 즐겨찾기 추가/삭제, Telegram/Google Mail 수신 동의 토글을 제공한다.
- `/settings/notifications`는 `/mypage`와 같은 화면을 렌더링한다.
- Asset detail 댓글 입력은 닉네임 미확정 상태에서 마이페이지 CTA를 보여준다.

## Verification Performed

`python -m pytest tests/test_profile_api.py` 통과.

- 결과: 2 passed.
- 참고: `datetime.utcnow()` 사용에 대한 Python 3.13 deprecation warning 5건이 출력되었으나 테스트 실패는 아니다.

`npm run lint` 통과.

`npm run build` 통과.

- 참고: Vite가 production chunk 500 kB 초과 경고를 출력했으나 빌드는 성공했다.

## Commands Not Run

- 브라우저 수동 검증

검증 미실행 사유: 이번 검증은 문서/코드 계약과 자동화 명령 확인에 집중했으며, 브라우저 상호작용 검증은 별도로 요청되지 않았다.

## Follow-Up Risks

- 운영 DB는 `python -m alembic upgrade head`로 `users.nickname_confirmed_at` 컬럼을 적용해야 한다.
- 기존 사용자는 다음 댓글 작성 전에 마이페이지에서 닉네임을 확정해야 한다.
- 기존 `frontend/src/pages/NotificationsSettings.jsx`는 별도 라우트에서 더 이상 직접 import하지 않지만, 독립 화면으로 다시 쓸 계획이면 문구와 UI를 정리해야 한다.

## Linked Feature Documents

- `docs/harness/features/mypage-profile.md`
- `docs/harness/features/authentication.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/favorites.md`
- `docs/harness/features/favorite-asset-notifications.md`
