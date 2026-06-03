# Google 로그인 UI 다크 테마 구현

Date: 2026-06-03

## Objective

`/login` 화면의 Google Identity Services 공식 로그인 버튼이 어두운 금융 대시보드 UI와 더 자연스럽게 이어지도록 시각 톤, 로딩 상태, 오류 상태를 정리했다. Google-only 인증 흐름과 `POST /api/auth/google` 계약은 변경하지 않았다.

## Files Changed

- `frontend/src/pages/Login.jsx`
- `docs/harness/features/authentication.md`
- `docs/harness/feature-index.md`
- `docs/harness/google-login-ui-dark-theme-implementation-2026-06-03.md`

## Behavior Changes

- GIS `renderButton` 옵션의 `theme`을 `outline`에서 `filled_black`으로 변경했다.
- Google 공식 버튼의 `type`, `text`, `shape`, `width`는 유지하고 `logo_alignment: "left"`를 추가했다.
- 로그인 카드 배경, border, shadow를 어두운 화면 안에서 더 명확한 레이어로 조정했다.
- 버튼 영역을 `w-full max-w-[320px]` wrapper로 감싸 모바일 폭에서 넘침 위험을 줄였다.
- GIS script/render 완료 전에는 `로그인 준비 중...` placeholder를 보여 빈 버튼 영역을 줄였다.
- `VITE_GOOGLE_CLIENT_ID` 누락, GIS load 실패, backend/network 오류는 동일한 다크 카드 안의 alert 스타일로 표시한다.
- Google credential callback, `/api/auth/google` payload, JWT/Zustand 저장 흐름은 그대로 유지했다.

## Verification Performed

- `cd frontend; npm.cmd run lint`: 통과.
- `cd frontend; npm.cmd run build`: 통과. Vite 기본 chunk size warning은 남았지만 빌드는 성공했다.
- `npm.cmd run dev -- --host 127.0.0.1`: sandbox 내부에서는 `spawn EPERM`으로 실패했으나, 승인 후 sandbox 밖 실행에서 Vite dev server가 `http://127.0.0.1:5173/`로 정상 기동했다.
- `Invoke-WebRequest http://127.0.0.1:5173/login`: `200` 응답 확인.

## Commands Not Run

- `agent-browser` 시각 검증은 이 셸에서 `agent-browser` 명령을 찾을 수 없어 실행하지 못했다.
- 실제 Google OAuth 성공 smoke는 유효한 `VITE_GOOGLE_CLIENT_ID`, Google OAuth origin 설정, 브라우저 identity flow가 필요해 실행하지 않았다.

## Follow-Up Risks

- GIS 버튼은 외부 script가 렌더링하므로 내부 spacing과 locale별 텍스트 폭은 완전히 통제할 수 없다.
- 실제 Google OAuth client ID가 없는 로컬 환경에서는 fallback/placeholder 중심으로만 확인될 수 있다.
- 실제 Google 로그인 성공 smoke는 유효한 OAuth origin과 client 설정이 필요하다.

## Related Feature Docs

- `docs/harness/features/authentication.md`
- `docs/harness/feature-index.md`
