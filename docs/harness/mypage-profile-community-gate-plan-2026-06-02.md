# 마이페이지 별명/즐겨찾기/수신동의 및 댓글 작성 게이트 계획

Date: 2026-06-02

## Objective

Google 계정으로 로그인한 사용자가 커뮤니티 댓글을 작성하려 할 때, 마이페이지에서 별명을 직접 설정했는지 확인한다. 별명 설정이 완료되지 않았다면 댓글 작성 대신 마이페이지로 유도하고, 마이페이지에서는 별명 중복 확인, 즐겨찾기 자산 태그 관리, Telegram 및 Google Mail 수신동의 해제를 제공한다.

## Current Context

- 인증은 Google 로그인 전용이며 `POST /api/auth/google`이 앱 JWT와 `id`, `email`, `nickname`을 반환한다.
- `users.nickname`은 현재 `unique`, `nullable=False`이고, 신규 Google 사용자는 Google 프로필 이름 또는 이메일 앞부분을 기반으로 별명이 자동 생성된다.
- 커뮤니티 댓글 작성은 `POST /api/community/{asset_id}/comments`에서 JWT만 확인한 뒤 `current_user.nickname`을 작성자명으로 반환한다.
- 즐겨찾기는 계정 로그인 시 `user_favorite_assets`와 동기화되며, 기존 API는 `GET /api/favorites`, `POST /api/favorites`, `DELETE /api/favorites/{ticker}`를 제공한다.
- 알림 수신 설정은 `notification_preferences`에 `telegram_enabled`, `email_enabled`가 있고, 기존 API는 `GET /api/notifications/preferences`, `PUT /api/notifications/preferences`를 제공한다.
- 프론트엔드에는 `/settings/notifications` 화면이 있지만, 통합 마이페이지 라우트는 아직 없다.

## Product Decisions Needed

1. 자동 생성된 Google 이름을 별명으로 인정할지 여부
   - 권장: 인정하지 않는다. 자동 생성값은 임시 표시명으로만 쓰고, 사용자가 마이페이지에서 저장 버튼을 눌러 확정해야 한다.
2. 기존 가입자 처리
   - 권장: 새 `nickname_confirmed_at` 값이 없는 사용자는 최초 댓글 작성 시 마이페이지로 유도한다.
3. 마이페이지 경로
   - 권장: `/mypage`를 새로 만들고, 기존 `/settings/notifications`는 유지하되 마이페이지에서 알림 섹션을 재사용하거나 링크한다.

## Target UX

1. 로그인 사용자가 종목 토론방 댓글 입력 또는 제출을 시도한다.
2. 프론트엔드는 `user.nickname_confirmed` 또는 `user.profile_complete`가 `false`이면 댓글을 보내지 않고 안내 메시지를 보여준다.
3. 안내 버튼은 `/mypage?next=/detail/{ticker}`로 이동한다.
4. 마이페이지의 별명 섹션에서 사용자는 별명을 입력하고 중복 확인을 한다.
5. 중복 확인을 통과한 별명만 저장할 수 있다.
6. 저장 성공 후 auth store의 `user.nickname`, `nickname_confirmed`를 갱신한다.
7. `next`가 있으면 기존 종목 상세 화면으로 돌아갈 수 있는 CTA를 보여준다.

백엔드는 같은 규칙을 한 번 더 강제한다. 프론트 검사를 우회하더라도 별명이 확정되지 않은 사용자의 댓글 작성 API는 `403` 또는 `409`로 거절하고, 응답 detail에 마이페이지 이동이 필요한 이유를 담는다.

## Backend Plan

### 1. User 모델 확장

대상 파일:

- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/alembic/versions/...`

추가 후보 필드:

- `nickname_confirmed_at: datetime | None`

파생 응답 필드:

- `nickname_confirmed: bool`
- 필요 시 `profile_complete: bool`

이 방식은 현재 `nickname`이 `nullable=False`인 구조를 유지하면서, 자동 생성 별명과 사용자가 확정한 별명을 구분할 수 있다.

### 2. 프로필 API 추가

대상 파일:

- 신규 `backend/app/api/profile.py` 또는 `backend/app/api/users.py`
- `backend/app/main.py`
- `backend/app/schemas.py`

권장 계약:

- `GET /api/profile/me`
  - 현재 사용자 `id`, `email`, `nickname`, `nickname_confirmed`, `nickname_confirmed_at`, 알림 기본 상태 요약을 반환한다.
- `GET /api/profile/nickname-availability?nickname=...`
  - 정규화한 별명의 사용 가능 여부를 반환한다.
  - 본인이 이미 쓰는 별명은 사용 가능으로 본다.
- `PATCH /api/profile/nickname`
  - 별명 유효성 검사와 중복 검사를 수행하고 저장한다.
  - 성공 시 `nickname_confirmed_at`을 현재 시각으로 설정한다.

검증 규칙 초안:

- 앞뒤 공백 제거
- 2자 이상 20자 이하
- 한글, 영문, 숫자, 공백, `_`, `-` 정도만 허용
- 금칙어/운영자 사칭 단어는 추후 정책이 정해지면 별도 리스트로 분리

### 3. 댓글 작성 게이트

대상 파일:

- `backend/app/api/community.py`
- 필요 시 `backend/app/api/deps.py`

변경:

- 댓글 생성 전에 `current_user.nickname_confirmed_at`이 없으면 작성 거절
- 에러 예시:
  - status: `403`
  - detail: `"댓글을 작성하려면 마이페이지에서 별명을 먼저 설정해주세요."`
  - optional code: `"NICKNAME_REQUIRED"`

수정/삭제/좋아요/신고는 이미 존재하는 댓글에 대한 액션이므로 별명 확정 필수 대상에서 제외하는 것을 권장한다. 댓글 작성만 막으면 커뮤니티 진입 장벽을 최소화할 수 있다.

### 4. 인증 응답 확장

대상 파일:

- `backend/app/api/auth.py`
- `backend/app/schemas.py`
- `frontend/src/store/authStore.js`

변경:

- `AuthTokenResponse`에 `nickname_confirmed` 또는 `profile_complete`를 추가한다.
- Google 신규 가입 시 자동 생성 별명은 저장하되 `nickname_confirmed_at=None`으로 둔다.
- 기존 사용자는 DB 값에 따라 응답한다.

## Frontend Plan

### 1. 마이페이지 화면 추가

대상 파일:

- 신규 `frontend/src/pages/MyPage.jsx`
- `frontend/src/App.jsx`
- `frontend/src/components/Header.jsx`
- `frontend/src/store/authStore.js`

화면 구성:

- 프로필 섹션: 이메일, 현재 별명, 별명 입력, 중복 확인, 저장 버튼
- 즐겨찾기 섹션: 현재 즐겨찾기 자산을 태그로 표시하고 각 태그에서 삭제 가능
- 자산 추가 섹션: 시장 데이터 또는 기존 자산 메타데이터에서 검색/선택 후 태그 추가
- 수신동의 섹션: Telegram, Google Mail 수신 체크박스

경로:

- `/mypage`
- 비로그인 사용자는 `/login`으로 안내

### 2. 별명 중복 확인 UI

상태:

- `nicknameDraft`
- `availabilityStatus`: `idle | checking | available | unavailable | invalid`
- `lastCheckedNickname`

동작:

- 사용자가 입력을 바꾸면 이전 중복 확인 결과를 무효화한다.
- 중복 확인 통과 후 입력값이 바뀌지 않은 경우에만 저장 버튼 활성화
- 저장 성공 시 `authStore.login(token, updatedUser)` 또는 별도 `updateUser` 액션으로 localStorage의 `user`를 갱신

### 3. 댓글 작성 유도

대상 파일:

- `frontend/src/pages/AssetDetail.jsx`

변경:

- `authToken`은 있지만 별명이 확정되지 않은 경우 댓글 input placeholder를 `"마이페이지에서 별명을 설정한 후 댓글 작성이 가능합니다"`로 변경
- 제출 버튼 클릭 시 API 호출 전 `/mypage?next=/detail/{ticker}` 안내 CTA 표시
- API에서 `NICKNAME_REQUIRED` 또는 관련 detail이 오면 같은 안내 메시지를 표시

### 4. 즐겨찾기 태그 관리

대상 파일:

- `frontend/src/store/favoriteStore.js`
- 신규 `frontend/src/pages/MyPage.jsx`

기존 store를 최대한 재사용한다.

- 태그 렌더링: `favorites.map`
- 삭제: `removeFavorite(symbol)`
- 추가: `toggleFavorite({ symbol, name, categoryKey })` 또는 중복 없이 `addFavorite` 액션을 새로 분리

권장 개선:

- 마이페이지에서는 토글보다 의미가 명확한 `addFavorite(asset)` 액션을 store에 추가한다.
- 자산 검색 소스는 1차로 `GET /api/market/prices` 결과와 `frontend/src/utils/constants.js`의 이름 해석을 사용한다.
- 이미 추가된 자산은 검색 결과에서 disabled 또는 `"추가됨"`으로 표시한다.

### 5. Telegram / Google Mail 수신동의 해제

대상 파일:

- `frontend/src/pages/MyPage.jsx`
- 기존 `frontend/src/pages/NotificationsSettings.jsx` 재사용 여부 검토
- `backend/app/api/notifications.py`는 기존 `PUT /api/notifications/preferences`로 충분할 가능성이 높다.

동작:

- Telegram 체크 해제: `telegram_enabled=false`
- Google Mail 체크 해제: `email_enabled=false`
- 체크 해제는 채널 연결 삭제가 아니라 수신 비활성화로 처리한다.
- 채널 자체 삭제는 기존 `DELETE /api/notifications/channels/telegram`, `DELETE /api/notifications/channels/email`과 구분한다.

UI 문구는 “수신동의”와 “연결 해제”를 분리한다. 사용자가 체크를 해제해도 검증된 이메일/Telegram 연결 정보는 유지되며, 다시 체크하면 기존 연결을 재사용할 수 있게 한다.

## Data Flow

1. App 시작 또는 로그인 성공 후 auth store가 `nickname_confirmed`를 보유한다.
2. AssetDetail 댓글 작성 시 auth store의 프로필 상태를 확인한다.
3. 미확정이면 `/mypage?next=...`로 안내하고 댓글 API를 호출하지 않는다.
4. MyPage가 `GET /api/profile/me`, `GET /api/favorites`, `GET /api/notifications/preferences`를 병렬 호출한다.
5. 별명 중복 확인은 `GET /api/profile/nickname-availability`를 호출한다.
6. 별명 저장은 `PATCH /api/profile/nickname`을 호출하고 auth store를 갱신한다.
7. 즐겨찾기 추가/삭제는 기존 favorites API를 호출하고 `favoriteStore`를 갱신한다.
8. 수신동의 변경은 `PUT /api/notifications/preferences`를 호출한다.

## Migration Plan

1. Alembic migration으로 `users.nickname_confirmed_at` nullable 컬럼을 추가한다.
2. 기존 사용자에게 자동으로 확정 처리할지 여부를 결정한다.
   - 권장 기본값: backfill하지 않음. 모든 사용자가 댓글 작성 전 별명을 확인하도록 한다.
   - 운영 마찰을 줄이고 싶다면 기존 사용자의 `nickname_confirmed_at`만 migration 시점으로 backfill한다.
3. PostgreSQL 운영 환경은 `python -m alembic upgrade head`를 먼저 실행한다.
4. 로컬 bootstrap이 남아 있다면 개발 편의를 위해 `ENABLE_DB_SCHEMA_BOOTSTRAP=true` 경로에도 컬럼 보강을 추가할지 검토한다.

## Test Plan

Backend:

- Google 로그인 응답에 `nickname_confirmed=false`가 포함되는지 확인
- 중복 별명 availability가 false를 반환하는지 확인
- 본인의 현재 별명은 availability true인지 확인
- 별명 저장 후 `nickname_confirmed_at`이 설정되는지 확인
- 별명 미확정 사용자의 댓글 작성이 실패하는지 확인
- 별명 확정 사용자의 댓글 작성은 기존처럼 성공하는지 확인
- 알림 preference에서 `telegram_enabled`, `email_enabled`를 false로 변경할 수 있는지 확인

Frontend:

- `npm run lint`
- `npm run build`
- 로그인 상태에서 별명 미확정이면 댓글 입력 영역이 마이페이지 설정을 안내하는지 확인
- 마이페이지에서 별명 중복 확인 전 저장 버튼이 비활성화되는지 확인
- 별명 저장 후 댓글 작성 화면으로 돌아와 작성 가능한지 확인
- 즐겨찾기 태그 추가/삭제가 localStorage와 서버 동기화 상태를 모두 갱신하는지 확인
- Telegram, Google Mail 체크 해제가 새로고침 후에도 유지되는지 확인

## Suggested Implementation Order

1. DB 컬럼과 프로필 스키마/API를 추가한다.
2. 인증 응답과 auth store에 `nickname_confirmed`를 연결한다.
3. 커뮤니티 댓글 작성 서버 게이트를 추가한다.
4. `/mypage` 화면을 만들고 별명 설정을 먼저 완성한다.
5. 댓글 작성 UI에서 마이페이지 유도 흐름을 연결한다.
6. 마이페이지에 즐겨찾기 태그 관리 섹션을 추가한다.
7. 마이페이지에 Telegram/Google Mail 수신동의 토글을 추가한다.
8. 관련 기능 문서와 change record를 갱신한다.

## Files Expected To Change During Implementation

- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/app/api/auth.py`
- `backend/app/api/community.py`
- `backend/app/api/profile.py` 또는 `backend/app/api/users.py`
- `backend/app/main.py`
- `backend/alembic/versions/*.py`
- `backend/tests/`
- `frontend/src/App.jsx`
- `frontend/src/components/Header.jsx`
- `frontend/src/pages/AssetDetail.jsx`
- `frontend/src/pages/MyPage.jsx`
- `frontend/src/store/authStore.js`
- `frontend/src/store/favoriteStore.js`
- `docs/harness/features/authentication.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/favorites.md`
- `docs/harness/features/favorite-asset-notifications.md`
- `docs/harness/feature-index.md`

## Risks And Follow-Ups

- 이 계획은 `users` 테이블 컬럼 추가가 필요하므로 실제 구현 전 DB migration 확인이 필요하다.
- 현재 코드에는 자동 생성 별명이 이미 존재하므로, 별명 “미설정”의 기준을 `nickname` 공백이 아니라 `nickname_confirmed_at`으로 잡아야 한다.
- 기존 사용자에게도 별명 확인을 요구하면 첫 댓글 작성 시 마찰이 생길 수 있다.
- Google Mail은 실제 Gmail API 수신이 아니라 현재 계정 이메일 기반 알림 채널로 해석한다. 실제 Gmail OAuth 연동을 뜻한다면 별도 외부 연동 설계가 필요하다.
- 마이페이지가 알림 설정 화면을 흡수할 경우 `/settings/notifications`와 기능 중복이 생길 수 있으므로, 기존 화면을 유지할지 리다이렉트할지 제품 결정을 해야 한다.

## Verification Performed For This Plan

- `git status --short`로 기존 변경사항이 있는 것을 확인했다.
- `ARCHITECTURE.md`, `DEVELOPMENT_DIRECTION.md`, `docs/harness/feature-index.md`를 확인했다.
- 관련 기능 문서 `authentication.md`, `asset-detail-ai-community.md`, `favorites.md`, `favorite-asset-notifications.md`, `feature-documentation-guide.md`를 확인했다.
- 실제 코드 `backend/app/models.py`, `backend/app/schemas.py`, `backend/app/api/auth.py`, `backend/app/api/community.py`, `backend/app/api/favorites.py`, `backend/app/api/notifications.py`, `frontend/src/App.jsx`, `frontend/src/pages/AssetDetail.jsx`, `frontend/src/pages/NotificationsSettings.jsx`, `frontend/src/store/authStore.js`, `frontend/src/store/favoriteStore.js`를 확인했다.

## Commands Not Run

- 테스트와 빌드는 실행하지 않았다. 이번 작업은 구현이 아니라 계획 문서 작성이며 런타임 동작을 변경하지 않는다.
