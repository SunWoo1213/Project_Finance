# Store 개발 방향성

이 폴더는 전역 클라이언트 상태를 관리합니다.

## 현재 책임

- `authStore.js`: JWT token, user 정보, login/logout 상태를 localStorage와 동기화
- `favoriteStore.js`: 즐겨찾기 자산 목록을 localStorage와 동기화

## 개발 원칙

전역 상태에는 여러 화면에서 공유해야 하는 값만 둡니다. 특정 페이지에서만 쓰는 로딩 상태, 입력값, 선택 탭은 해당 페이지의 local state로 유지합니다.

인증 상태는 token과 user 구조가 함께 움직여야 합니다. login/logout을 수정할 때는 localStorage와 Zustand state가 불일치하지 않도록 확인합니다.

민감한 사용자 정보를 localStorage에 추가로 저장하지 않습니다. 현재처럼 UI 표시와 인증에 필요한 최소 정보만 저장하는 방향을 유지합니다.

즐겨찾기는 현재 브라우저 로컬 상태입니다. 계정 간 동기화가 필요해지면 백엔드 모델/라우트와 마이그레이션 계획을 먼저 정리합니다.

## 하네스 문서 연계

`authStore.js` 변경 전에는 `docs/harness/features/authentication.md`와 `docs/harness/features/frontend-routing-shell.md`를 확인합니다.

`favoriteStore.js` 변경 전에는 `docs/harness/features/favorites.md`와 `docs/harness/features/frontend-routing-shell.md`를 확인합니다.

token 저장 키, user shape, localStorage 동기화, logout 동작이 바뀌면 두 기능 문서의 `Contracts`와 `Data Flow`를 갱신하고 `docs/harness/`에 변경 기록을 남깁니다.
