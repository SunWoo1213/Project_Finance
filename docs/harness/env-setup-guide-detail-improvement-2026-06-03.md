# 환경변수 설정 가이드 상세화 기록

Date: 2026-06-03

## Objective

`ENVIRONMENT_VARIABLE_SETUP.md`를 처음 보는 사람이 환경변수의 공개 범위, 저장 위치, 발급 경로, 검증 순서를 더 쉽게 이해하도록 보강한다.

## Files Changed

- `ENVIRONMENT_VARIABLE_SETUP.md`
- `docs/harness/env-setup-guide-detail-improvement-2026-06-03.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/feature-index.md`

## Behavior Changes

- 애플리케이션 런타임 동작 변경 없음.
- 환경변수 가이드 상단에 핵심 요약 섹션을 추가해 앱 기본값, frontend 공개값, DB 접속값, 인증 secret, 외부 provider key, 운영 정책값을 구분했다.
- 처음 로컬 실행에 필요한 최소 변수 묶음과 기능별로 나중에 추가할 변수 묶음을 분리해 설명했다.
- `VITE_` 변수, DB URL, scheduler, 결제, 알림 provider 값의 공개 범위와 위험도를 더 쉬운 문장으로 보강했다.
- 주소 입력 시 origin과 path를 구분하는 예시를 추가했다.
- 검증 중 오류를 공유할 때 secret이 포함되지 않은 정보만 공유하도록 안내를 추가했다.

## Verification Performed

- `git status --short`로 기존 사용자 변경사항을 확인했다.
- `.env` 내용은 읽지 않았다.
- `ENVIRONMENT_VARIABLE_SETUP.md`, `.env_example`, `docs/harness/env-setup-guide-documentation-2026-06-02.md`, `docs/harness/features/deployment-runtime.md`, `docs/harness/feature-index.md`를 참고했다.

## Commands Not Run

- `npm run build`: 문서 설명 변경만 수행했으므로 frontend build는 실행하지 않았다.
- `pytest`: backend 코드 동작 변경이 없으므로 테스트는 실행하지 않았다.
- backend/frontend dev server: 런타임 검증이 필요한 변경이 아니어서 실행하지 않았다.

## Follow-up Risks

- 새 환경변수가 추가되면 `.env_example`, `ENVIRONMENT_VARIABLE_SETUP.md`, 관련 feature document, 변경 기록을 함께 갱신해야 한다.
- 실제 `.env`, provider dashboard, 배포 secret store의 값은 계속 별도로 관리해야 하며 문서에는 남기지 않는다.
