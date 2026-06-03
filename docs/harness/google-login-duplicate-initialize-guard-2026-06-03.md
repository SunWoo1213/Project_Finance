# Google 로그인 initialize() 중복 호출 가드 추가

날짜: 2026-06-03

## 목적

브라우저 콘솔에 다음 GSI 경고가 출력되는 문제를 정리한다.

```
[GSI_LOGGER]: google.accounts.id.initialize() is called multiple times.
This could cause unexpected behavior and only the last initialized instance will be used.
```

`frontend/src/main.jsx`의 `<StrictMode>` 때문에 개발 모드에서 `Login` 컴포넌트의 effect가 두 번 실행되고, 그 과정에서 `window.google.accounts.id.initialize()`가 중복 호출되는 것이 원인이다. 동작 자체가 깨지지는 않지만 경고가 반복 출력되므로 초기화를 한 번만 수행하도록 가드를 추가한다.

## 변경 파일

- `frontend/src/pages/Login.jsx`
  - `isInitializedRef` ref를 추가했다.
  - `window.google.accounts.id.initialize(...)` 호출을 `if (!isInitializedRef.current) { ... }`로 감싸고, 호출 후 `isInitializedRef.current = true`로 표시한다.
  - `renderButton(...)` 호출은 가드 밖에 그대로 두어, 마운트 시 버튼은 계속 렌더링된다.

## 동작 변화

- 개발 모드(StrictMode)에서도 `initialize()`가 컴포넌트 인스턴스당 한 번만 호출되어 GSI 중복 경고가 사라진다.
- 버튼 렌더링·로그인 콜백·에러 처리 동작은 기존과 동일하다.

## 이번 변경으로 다루지 않은 부분 (설정/배포 영역)

콘솔에 함께 나타난 아래 두 증상은 코드가 아니라 환경/Google Cloud Console 설정 문제이며 이번 변경 대상이 아니다.

- `The given client ID is not found.` 및 Google 버튼 리소스 `403`
  - `VITE_GOOGLE_CLIENT_ID` 값이 정상 client ID(`...apps.googleusercontent.com`)인지, 그리고 Google Cloud Console의 **승인된 JavaScript 원본**에 현재 접속 origin(로컬은 `http://localhost:5173`, 배포는 실제 도메인)이 등록돼 있는지 확인해야 한다.
- `frontend/.env` 파일 부재
  - 현재 저장소에는 루트 `.env`만 있고 `frontend/.env`는 없다. `frontend/`에서 직접 Vite를 실행하면 `VITE_GOOGLE_CLIENT_ID`가 주입되지 않으므로, 필요한 경우 `frontend/.env`에 `VITE_API_BASE_URL`, `VITE_GOOGLE_CLIENT_ID` 같은 공개값을 둔다(`ENVIRONMENT_VARIABLE_SETUP.md` 참고). 실제 값과 시크릿은 문서/커밋에 넣지 않는다.

## 검증

- `npm run lint` (frontend) — 통과
- `npm run build` (frontend) — 통과(기존 chunk 크기 경고만 출력, 본 변경과 무관)
- 실제 Google OAuth 성공 smoke는 유효한 `VITE_GOOGLE_CLIENT_ID`, Google OAuth origin 설정, 브라우저 identity flow가 필요해 실행하지 않았다.

## 후속 위험

- 위 "다루지 않은 부분"의 설정이 해결되지 않으면 버튼은 여전히 `403`/`client ID is not found`로 표시될 수 있다. 코드 가드는 중복 경고만 제거한다.
