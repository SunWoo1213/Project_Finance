# 코드 이해 문서 신설 및 최신화 규칙 추가 (2026-06-10)

## 목적
저장소를 처음 보는 개발자·하네스 에이전트가 전체 구조와 데이터 흐름을 한 번에 이해할 수 있도록, 루트에 단일 코드 이해 문서를 작성한다. 또한 향후 코드 수정 시 이 문서를 하네스 엔지니어링 규율에 따라 함께 최신화하도록 규칙을 추가한다.

## 변경 파일
- `CODE_UNDERSTANDING.md` (신규): 프로젝트 개요, 저장소 구조, 백엔드(진입점·API·서비스·스케줄러·AI 파이프라인·모델·core), 프론트엔드(라우트·스토어·유틸·컴포넌트), 핵심 데이터 흐름(인증/시장/리포트/결제/알림), 빌드·검증 명령, 작업 규칙, 문서 유지보수 규칙, 변경 이력을 정리.
- `CLAUDE.md` (수정): "문서 동기화 규율" 절에 5번 항목 추가 — 저장소 구조가 바뀌면 `CODE_UNDERSTANDING.md`도 함께 최신화하도록 명시.

## 동작 변화
- 코드 동작 변화 없음. 문서/하네스 규칙만 추가.
- 이후 라우트·서비스·데이터 모델·스케줄러·핵심 흐름 변경 시 `CODE_UNDERSTANDING.md` 해당 절을 갱신하는 것이 하네스 워크플로우 문서화 단계의 일부가 됨.

## 작성 근거
- `Explore` 서브에이전트 3개로 backend / frontend / docs·config를 읽어 사실 기반으로 정리. 실제 코드(`backend/app/main.py`, `api/`, `services/`, `models.py`, `frontend/src/`)와 기존 문서(`AGENTS.md`, `feature-index.md`, `feature-documentation-guide.md`)를 대조.
- 구식 정보(`ARCHITECTURE.md`의 Next.js/TypeScript 설명)는 배경 자료로 표기하고 실제 React+Vite+JavaScript 스택을 기준으로 작성.

## 검증
- 문서 전용 변경이라 코드 테스트는 실행하지 않음.
- 시크릿(.env, API 키, 비밀번호, 토큰)은 본문에 포함하지 않았으며 환경 변수는 이름만 언급.

## 미실행 명령 / 사유
- `pytest`, `npm run lint/build`: 코드 변경이 없어 생략.

## 후속 위험 / 주의
- `CODE_UNDERSTANDING.md`는 요약 지도이므로 세부 진실 소스는 여전히 `AGENTS.md`와 `docs/harness/`다. 구조 변경 시 갱신을 빠뜨리면 실제 코드와 어긋날 수 있으므로, `CLAUDE.md`에 추가한 5번 규칙과 문서 §8 절차를 따른다.
- feature-index.md의 기능 문서들과는 별개의 상위 개요 문서이므로, 두 문서 사이 중복이 늘면 한쪽을 링크로 위임하도록 정리 필요.
