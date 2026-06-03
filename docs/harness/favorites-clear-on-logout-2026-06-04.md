# 로그아웃 시 즐겨찾기 초기화

Date: 2026-06-04

## 목적

로그아웃 후에도 이전 계정의 즐겨찾기 토글 상태가 그대로 유지되는 문제를 해결한다. 즐겨찾기는 계정에 귀속되어야 하며, 로그아웃하면 화면에서 사라져야 한다.

## 원인

- 즐겨찾기는 `favoriteAssets` localStorage 키와 `favoriteStore`의 메모리 상태에 저장된다.
- `authStore.logout`은 `token`, `user`만 제거하고 즐겨찾기는 비우지 않았다.
- 따라서 로그아웃 후에도 `favoriteAssets`와 메모리 `favorites`가 남아 토글이 켜진 상태로 유지됐다.

## 변경 파일

- `frontend/src/store/favoriteStore.js`
  - `clearFavorites` 액션 추가: `favoriteAssets` localStorage 키를 제거하고 `favorites`를 빈 배열로, `isSyncing`/`syncError`를 초기화한다.
- `frontend/src/store/authStore.js`
  - `favoriteStore`를 import하고, `logout`에서 `useFavoriteStore.getState().clearFavorites()`를 호출하도록 추가했다.

## 동작 변화

- 로그아웃하면 즐겨찾기 localStorage 및 메모리 상태가 즉시 비워져 모든 화면에서 토글이 해제된다.
- 다른 계정으로 다시 로그인하면 localStorage가 비어 있으므로 `App.jsx`의 `syncWithServer(token)`가 `GET /api/favorites`로 해당 계정의 즐겨찾기를 불러온다(이전 계정 데이터가 새 계정으로 병합되지 않는다).
- 게스트(비로그인) 즐겨찾기 기능은 그대로 유지된다. 초기화는 명시적 로그아웃 액션에서만 수행하며, App.jsx의 비로그인(`else`) 분기에서는 초기화하지 않으므로 게스트가 모은 로컬 즐겨찾기는 보존되어 로그인 시 `import-local`로 병합된다.

## 순환 참조 점검

- `authStore` → `favoriteStore` → `utils/apiClient`(axios만 import). `apiClient`는 `authStore`를 import하지 않으므로 순환 참조가 없다.

## 검증

- `cd frontend; npm run lint` — 통과.

## 미실행 명령

- `npm run build` — 미실행(린트로 충분히 확인). 필요 시 후속 검증 권장.
- 수동 브라우저 확인(로그인 → 즐겨찾기 → 로그아웃 → 토글 해제 확인) — 미실행.

## 후속 위험

- 토큰 만료 등으로 `authStore.logout`을 거치지 않고 인증이 풀리는 경로가 추가되면 즐겨찾기가 남을 수 있다. 그런 경로가 생기면 동일하게 `clearFavorites`를 호출해야 한다.
