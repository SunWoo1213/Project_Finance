# Google Login UI Dark Theme Integration Plan

Date: 2026-06-03

## Objective

`/login` 화면의 Google 로그인 버튼이 주변의 어두운 금융 대시보드 UI와 이질적으로 보이는 문제를 줄인다. 인증 플로우, Google ID token 처리, backend 계약은 유지하고, 시각적 통합성과 접근성만 개선한다.

## Current Diagnosis

- `frontend/src/pages/Login.jsx`는 전체 화면을 `bg-slate-900` 계열로 구성한다.
- 로그인 컨테이너도 `bg-slate-900/60`, `border-slate-800`, 흰색 제목, `text-slate-400` 보조 문구를 사용한다.
- Google Identity Services 버튼은 현재 `renderButton` 옵션에서 `theme: "outline"`을 사용한다.
- 결과적으로 버튼 내부가 밝은 기본 Google 스타일로 렌더링되어, 어두운 카드/배경 사이에서 외부 위젯처럼 튀어 보인다.
- Google 버튼은 GIS가 렌더링하는 공식 버튼이므로 내부 CSS를 직접 덮어쓰기보다 Google이 제공하는 `renderButton` 옵션을 사용해야 한다.

## Constraints

- 인증은 계속 Google-only로 유지한다.
- `POST /api/auth/google` 요청 payload와 응답 처리 로직은 변경하지 않는다.
- `VITE_GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_ID` 같은 환경변수 이름만 문서화하고 실제 값은 다루지 않는다.
- Google 공식 버튼의 브랜드/접근성 요구를 훼손하지 않는다.
- 로그인 화면 개선은 `frontend/src/pages/Login.jsx` 중심으로 제한한다. 반복 UI가 생길 때만 `frontend/src/components/`로 분리한다.
- 새 design system, 새 router, 새 auth provider는 도입하지 않는다.

## External Reference

Google Identity Services JavaScript API의 `renderButton`은 `theme`, `size`, `text`, `shape`, `logo_alignment`, `width`, `locale` 옵션을 지원한다. 공식 reference에는 `theme` 값으로 `outline`, `filled_blue`, `filled_black`이 명시되어 있으며, `width`는 최대 400px로 안내되어 있다.

- https://developers.google.com/identity/gsi/web/reference/js-reference
- https://developers.google.com/identity/gsi/web/guides/display-button

## Target Direction

1. Google 버튼 자체는 공식 `filled_black` 테마로 바꾼다.
2. 로그인 카드와 버튼 주변 컨테이너의 대비를 버튼과 자연스럽게 맞춘다.
3. 버튼이 로드되기 전, 설정 누락, 네트워크 오류 상태가 어두운 UI 안에서 같은 시각 언어를 쓰도록 정리한다.
4. 모바일 폭에서 버튼 너비가 어색하게 고정되지 않도록 반응형 컨테이너 기준으로 조정한다.

## Implementation Plan

### 1. Button Render Option 조정

`frontend/src/pages/Login.jsx`의 `window.google.accounts.id.renderButton` 옵션을 다음 방향으로 변경한다.

```js
window.google.accounts.id.renderButton(googleButtonRef.current, {
  theme: "filled_black",
  size: "large",
  type: "standard",
  text: "continue_with",
  shape: "rectangular",
  logo_alignment: "left",
  width: 320,
});
```

검토 포인트:

- `filled_black`이 어두운 배경에서 충분히 구분되는지 확인한다.
- 카드 배경도 어두우므로 버튼 외곽이 묻히면 wrapper에 `ring` 또는 subtle border를 적용한다.
- `width`는 현재 320px을 유지하되, 모바일에서 카드 padding을 감안해 wrapper를 `w-full max-w-[320px]`로 둔다.

### 2. Login Card Visual Tone 정리

카드는 현재보다 약간 더 명확한 레이어로 보이게 만든다.

- 배경: `bg-slate-950/80` 또는 기존 `bg-slate-900/60` 유지 후 border 강화.
- border: `border-slate-700/70` 수준으로 조정해 화면 중앙의 focus 영역을 명확히 한다.
- shadow: 과한 광택 대신 `shadow-2xl shadow-black/30` 정도의 어두운 depth를 사용한다.
- 제목/문구는 유지하되 보조 문구에 "Google 계정으로 계속 진행하세요."처럼 현재 문구를 유지해 auth 의미를 바꾸지 않는다.

### 3. Button Loading/Fallback 상태 추가

현재는 GIS script가 로드되기 전 버튼 영역이 빈 상태일 수 있다. 시각적 이질감 개선과 함께 빈 공간 문제도 줄인다.

- `isGoogleReady` 상태를 추가해 script/render 완료 전 skeleton 또는 disabled placeholder를 보여준다.
- placeholder는 실제 Google 버튼을 흉내 내지 않는다. 예: `로그인 준비 중...`
- `missingConfig`, `genericError`, `networkError` 메시지는 기존 문구를 유지하되 같은 어두운 card 안에서 일관된 alert 스타일을 적용한다.

### 4. Responsive Layout 확인

- 로그인 card는 `max-w-md`를 유지한다.
- Google 버튼 wrapper는 `w-full max-w-[320px]`로 만들고 가운데 정렬한다.
- 360px 내외 모바일 폭에서도 버튼 iframe이 card 밖으로 넘치지 않는지 확인한다.
- 넓은 desktop에서도 버튼이 지나치게 작아 보이면 카드 제목/간격을 미세 조정한다.

### 5. Optional Polish

필요할 때만 적용한다.

- 로그인 카드 상단에 작은 금융 앱 브랜드 톤 문구를 추가할 수 있으나, 불필요한 marketing hero처럼 만들지 않는다.
- 배경에 장식용 gradient blob이나 orb는 추가하지 않는다.
- Google 버튼 주변에 별도 커스텀 CTA 버튼을 만들지 않는다. 공식 GIS 버튼을 실제 클릭 대상 그대로 유지한다.

## Files To Change

- `frontend/src/pages/Login.jsx`
  - Google button `theme` 변경.
  - 버튼 wrapper의 반응형 폭과 dark-theme framing 조정.
  - 필요 시 loading placeholder 상태 추가.
- `docs/harness/features/authentication.md`
  - 구현 시 Change Records에 구현 기록 링크 추가.
- `docs/harness/feature-index.md`
  - 구현 시 인증 feature의 change records에 구현 기록 링크 추가.
- `docs/harness/google-login-ui-dark-theme-implementation-2026-06-03.md`
  - 구현 완료 시 생성할 변경 기록 후보.

## Acceptance Criteria

- `/login` 화면에서 Google 로그인 버튼이 어두운 card와 같은 시각 계층 안에 들어온다.
- Google 공식 버튼 브랜드 요소와 클릭 동작이 유지된다.
- Google credential callback과 `POST /api/auth/google` 요청 동작이 변경되지 않는다.
- `VITE_GOOGLE_CLIENT_ID`가 없을 때 기존처럼 설정 누락 메시지가 표시된다.
- script load 실패나 backend 오류 메시지가 기존보다 시각적으로 어색하지 않게 표시된다.
- 모바일 폭에서 버튼 또는 오류 문구가 card 밖으로 넘치지 않는다.

## Verification Plan

1. Frontend build:

```powershell
cd frontend
npm run build
```

2. Login route visual check:

```powershell
cd frontend
npm run dev
```

- `http://127.0.0.1:<port>/login`에서 desktop/mobile 폭을 확인한다.
- Google client ID가 설정된 환경에서는 실제 Google 버튼이 표시되는지 확인한다.
- 설정이 없는 환경에서는 `Google 로그인 설정이 필요합니다.` fallback이 표시되는지 확인한다.

3. Auth behavior smoke check:

- Google 로그인 성공 후 root route로 이동하는지 확인한다.
- localStorage/Zustand token 저장 방식이 기존과 동일한지 확인한다.
- backend 계약은 변경하지 않았으므로 backend test는 구현 범위가 UI에만 머무르면 필수는 아니다.

## Follow-Up Risks

- GIS 버튼은 iframe/외부 렌더링 영역이므로 내부 스타일을 CSS로 완전히 통제할 수 없다.
- `filled_black` 테마가 카드 배경과 너무 가까워 보이면 버튼 wrapper에 subtle border/ring을 추가해야 한다.
- 브라우저 locale 또는 Google account 상태에 따라 버튼 텍스트 폭이 달라질 수 있다. `width`와 wrapper 제약을 함께 확인해야 한다.
- 실제 Google OAuth 설정이 없는 로컬 환경에서는 fallback 상태만 검증 가능하다.

## Related Feature Docs

- `docs/harness/features/authentication.md`
- `docs/harness/feature-index.md`
