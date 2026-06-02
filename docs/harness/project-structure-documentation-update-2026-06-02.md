# 프로젝트 구조 문서 업데이트

Date: 2026-06-02

## Objective

현재 저장소 구현 기준으로 프로젝트 구조 문서를 갱신했다. 오래된 Next.js/TypeScript 중심 설명을 React/Vite + FastAPI 구조로 교체하고, future harness 작업자가 먼저 읽을 수 있는 구조 분석 문서를 추가했다.

## Files Changed

- `ARCHITECTURE.md`
- `PROJECT_STRUCTURE_ANALYSIS.md`
- `docs/harness/feature-index.md`
- `docs/harness/project-structure-documentation-update-2026-06-02.md`

## Behavior Changes

- 코드 동작 변경 없음.
- `ARCHITECTURE.md`가 현재 런타임, 프론트엔드 라우트, 백엔드 라우터/API, DB 모델, 스케줄러/AI 리포트 정책, 설정 경계를 설명하도록 갱신됨.
- `ARCHITECTURE.md`를 한국어 중심 문서로 번역하고, 파일 경로/API 경로/환경변수명은 원문 식별자를 유지함.
- `PROJECT_STRUCTURE_ANALYSIS.md`가 새로 추가되어 저장소 폴더별 책임과 기능 문서 탐색 경로를 빠르게 확인할 수 있음.
- `docs/harness/feature-index.md`의 Documentation Workflow에 구조 문서와 이번 변경 기록 링크를 추가함.
- 사용자 요청과 챗봇 요청은 저장된 scheduled report를 읽는 구조이며, 일반 사용자 요청이 새 AI 리포트 생성을 트리거하지 않는다는 점을 명시함.

## Verification Performed

- `git status --short`로 시작 전 작업 트리 상태를 확인함.
- `frontend/package.json`, `frontend/src/App.jsx`, `frontend/src/utils/apiClient.js`, `backend/requirements.txt`, `backend/app/main.py`, `backend/app/api/*.py`, `backend/app/core/config.py`, `backend/app/models.py`, `backend/app/schemas.py`, `backend/alembic/versions/20260601_0001_add_subscription_billing_tables.py`를 확인해 문서 내용을 현재 코드에 맞춤.
- `ARCHITECTURE.md` 번역 후 문서 본문을 다시 읽어 주요 코드 식별자가 유지되는지 확인함.

## Commands Not Run

- 테스트/빌드 명령은 실행하지 않았다. 이번 변경은 문서 전용이며 런타임 코드, 의존성, 설정 파일을 수정하지 않았다.

## Follow-Up Risks

- 일부 기존 한글 문서와 코드 주석은 터미널에서 mojibake로 보일 수 있다. 기능 변경 시 해당 영역 문서를 UTF-8 기준으로 점진 정리하는 것이 좋다.
- 로컬 실행용 설정 파일에 실제 DB 자격 증명이 들어 있다면 값을 노출하지 말고 즉시 회전한 뒤 환경변수 기반 구성으로 옮겨야 한다.
- `backend/app/main.py`에 market/report 라우트가 남아 있다. 기능 확장 시 `backend/app/api/`로 분리할지 검토한다.

## Related Feature Documents

- `docs/harness/feature-index.md`
- `docs/harness/features/frontend-routing-shell.md`
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/subscription-billing.md`
- `docs/harness/features/deployment-runtime.md`
