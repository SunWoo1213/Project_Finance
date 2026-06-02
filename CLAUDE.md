# CLAUDE.md

이 문서는 **Claude Code**가 `Project_Finance` 저장소에서 작업할 때의 진입점이다. 이 프로젝트는 AI coding harness 기반으로 운영되며, 운영 규칙의 **단일 진실 소스(single source of truth)는 `AGENTS.md`** 이다. Claude Code는 Codex와 동일한 하네스 규칙을 따르고, 같은 문서 체계(`docs/harness/`)에 기록을 남긴다.

## 운영 규칙 (AGENTS.md 재사용)

아래 import로 `AGENTS.md` 전체 규칙을 그대로 로드한다. Project Snapshot, Required Pre-Work, Repository Map, Backend/Frontend Work Rules, Standard Commands, Harness Safety Rules, Secret Handling, Risky Change Protocol, Testing Expectations, Response Expectations, Harness Change Records, Feature Documentation, AI Report Generation Rule는 모두 `AGENTS.md`를 기준으로 한다.

@AGENTS.md

규칙이 충돌하면 `AGENTS.md`와 현재 코드가 우선한다. 이 파일에는 규칙을 복제하지 않고 Claude Code 환경에서만 필요한 보강 사항만 둔다.

## Claude Code 전용 운영 노트

### 환경
- 플랫폼은 **Windows + PowerShell**이다. 쉘 명령은 PowerShell 문법을 쓴다(`$null`, `$env:VAR`, 줄 연속은 백틱). POSIX 스크립트가 필요하면 Bash 도구를 쓴다.
- 파일 탐색은 Glob, 내용 검색은 Grep, 읽기는 Read, 편집은 Edit/Write를 쓴다. `cat`/`find`/`grep`/`sed`를 쉘로 돌리지 않는다.
- `AGENTS.md`의 Standard Commands(섹션 6)에 있는 검증 명령을 그대로 사용한다.

### 문서를 클릭 가능한 링크로 참조
파일/위치를 언급할 때 마크다운 링크 문법을 쓴다: `[AGENTS.md](AGENTS.md)`, `[nodes.py:42](backend/app/services/graph/nodes.py#L42)`. 백틱 경로는 쓰지 않는다.

### 하네스 워크플로우 (slash commands)
Codex의 plan → implement → verify → 문서화 흐름을 Claude Code에서 슬래시 커맨드로 제공한다.

- `/harness-plan <작업>` — 필수 문서를 정해진 순서로 읽고, 변경 범위·파일·검증 계획을 한국어 계획 문서로 `docs/harness/`에 남긴다.
- `/harness-implement <작업>` — `AGENTS.md` 규칙대로 구현하고, 구현 기록을 작성하며 관련 feature 문서와 `feature-index.md`를 함께 갱신한다.
- `/harness-verify <작업>` — 변경에 맞는 최소 검증 명령을 실행하고 검증 기록을 남긴다.
- `/feature-doc <기능>` — `docs/harness/features/`에 기능 문서를 만들거나 갱신하고 색인에 연결한다.

복잡한 문서 작성과 검증은 서브에이전트(`harness-doc-writer`, `harness-verifier`)에 위임할 수 있다.

### 문서 동기화 규율 (반드시 지킬 것)
코드를 의미 있게 바꾸면 `AGENTS.md` 섹션 12·13과 `docs/harness/feature-documentation-guide.md`에 따라:
1. `docs/harness/`에 한국어 변경 기록을 만든다(날짜·목적·변경 파일·동작 변화·검증·미실행 명령·후속 위험).
2. 해당 `docs/harness/features/*.md`를 갱신하고 그 변경 기록 링크를 `Change Records`에 추가한다.
3. `docs/harness/feature-index.md`의 항목을 갱신한다.
4. 폴더 소유권이 바뀌면 가장 가까운 `DEVELOPMENT_DIRECTION.md`를 갱신한다.

### 절대 규칙 (요약, 상세는 AGENTS.md)
- `.env` 및 모든 시크릿(API 키, DB 비밀번호, JWT secret)을 출력·복사·커밋하지 않는다. `.claude/settings.json`에서 `.env` 읽기는 차단되어 있다.
- 사용자 변경을 되돌리거나 파괴적 git 명령(`git reset --hard`, 광범위 `git checkout`), 파일 삭제, DB/볼륨 드롭을 임의로 하지 않는다.
- 사용자/챗봇 요청이 AI 리포트를 실시간 생성하지 않는다. 저장된 스케줄 리포트를 읽는 것이 기본이다(`AGENTS.md` 섹션 14).
- 하네스 보고서·계획·구현·검증·변경 기록은 한국어로 작성한다. 코드 식별자·파일 경로·명령·API 경로·에러 문자열은 원문 유지.
