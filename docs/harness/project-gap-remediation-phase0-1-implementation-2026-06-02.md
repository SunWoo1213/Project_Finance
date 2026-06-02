# 프로젝트 부족점 개선 Phase 0-1 구현 기록

작성일: 2026-06-02

## 목표

`docs/harness/project-gap-remediation-plan-2026-06-02.md`의 우선 실행 범위 중 사용자 승인이나 비용 증가가 필요하지 않은 Phase 0, Phase 1을 시작했다.

## 변경 파일

- `.env_example`
- `frontend/src/pages/Home.jsx`
- `frontend/src/pages/Login.jsx`
- `frontend/src/pages/MarketSnapshot.jsx`
- `docs/harness/features/authentication.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/features/favorites.md`
- `docs/harness/features/frontend-routing-shell.md`
- `docs/harness/features/market-data.md`
- `docs/harness/feature-index.md`
- `docs/harness/project-gap-remediation-phase0-1-implementation-2026-06-02.md`

## 동작 변경

- `.env_example`에 현재 backend 설정과 hosted frontend 설정에 필요한 변수명을 추가했다.
- `.env_example`에 각 환경 변수에 어떤 값을 넣어야 하는지 한국어 설명 주석을 추가했다.
- report scheduler 예시 기본값을 `backend/app/core/config.py`의 현재 기본값인 6시간 interval, 5개 per-run cap, 6시간 cooldown, 대표 ticker 목록과 맞췄다.
- 결제 provider 경계 변수명을 placeholder로 추가했다. 실제 provider secret이나 dashboard 값은 기록하지 않았다.
- `Home.jsx`, `Login.jsx`, `MarketSnapshot.jsx`의 page-level `http://localhost:8000` 직접 호출을 제거하고 `frontend/src/utils/apiClient.js`를 사용하게 했다.
- `favorites.md`의 계정 동기화 Open Risk를 현재 구현 기준으로 수정했다.
- `authentication.md`의 Alembic 관련 stale 문구를 현재 migration workflow 기준으로 수정했다.
- `deployment-runtime.md`, `frontend-routing-shell.md`, `market-data.md`에 `.env_example` 정합성과 shared API client 사용 규칙을 연결했다.

## 검증 수행

- 사용자 요청에 따라 lint, build, pytest, dev server smoke 같은 검증 명령은 실행하지 않았다.
- 코드 실행 없이 파일 내용과 변경 diff만 확인했다.

## 실행하지 않은 명령

- `npm run lint`
- `npm run build`
- `pytest`
- backend/frontend dev server smoke

## 후속 위험

- `VITE_API_BASE_URL`은 Vite frontend root의 환경 파일에도 mirror되어야 local frontend-only 실행에서 반영된다.
- 실제 hosted backend origin, CORS origin, payment provider 값은 아직 product/runtime 결정이 필요하다.
- 결제 provider 구현, scheduler coverage 확대, notification delivery 운영화, DB schema 변경은 계획서의 승인 필요 항목을 먼저 확인해야 한다.

## 관련 기능 문서

- `docs/harness/features/authentication.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/features/favorites.md`
- `docs/harness/features/frontend-routing-shell.md`
- `docs/harness/features/market-data.md`
