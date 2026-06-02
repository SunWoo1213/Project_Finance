# Claude Code 하네스 통합 변경 기록

Date: 2026-06-02

## 목적

기존에 Codex 기반으로만 운영되던 하네스 엔지니어링 구조를 **Claude Code**에서도 동일하게 사용할 수 있도록 진입점·권한·워크플로우 도구를 추가한다. 운영 규칙의 단일 진실 소스는 기존 `AGENTS.md`로 유지하고, Claude Code는 이를 재사용하면서 Codex와 같은 문서 체계(`docs/harness/`)에 기록을 남기도록 한다.

## 설계 원칙

- 규칙 본문은 `AGENTS.md` 한 곳에만 둔다. `CLAUDE.md`는 `@AGENTS.md` import로 전체 규칙을 로드하고 Claude Code 환경 전용 보강만 추가한다. 두 하네스가 항상 같은 규칙으로 동작한다.
- Codex의 plan → implement → verify → 문서화 흐름을 Claude Code 슬래시 커맨드와 서브에이전트로 재현한다.

## 변경 파일

- `CLAUDE.md` (신규)
  - `@AGENTS.md` import로 운영 규칙 재사용.
  - Claude Code 전용 노트: Windows/PowerShell 환경, 전용 도구 사용, 클릭 가능한 파일 링크 규칙, 하네스 슬래시 커맨드 안내, 문서 동기화 규율, 절대 규칙 요약.
- `.claude/settings.json` (신규)
  - `permissions.deny`: `.env` 계열 읽기 차단(루트/backend/frontend/하위 전체).
  - `permissions.ask`: 파괴적 명령 확인(`git reset --hard`, 광범위 `git checkout`, `git clean`, `git push`, 파일 삭제, `docker compose down`, `docker volume rm`, `alembic downgrade`, `dropdb`).
  - `permissions.allow`: 읽기/편집/쓰기, 안전한 git 조회, `pytest`, `uvicorn`, `alembic upgrade`, npm lint/build/dev, `docker compose up/ps/logs` 등 표준 검증 명령.
- `.claude/commands/harness-plan.md` (신규) — `/harness-plan`. 필수 읽기 순서대로 문서를 읽고 계획 문서를 작성, Risky Change면 승인 요청.
- `.claude/commands/harness-implement.md` (신규) — `/harness-implement`. AGENTS.md 규칙대로 구현 후 변경 기록·feature 문서·`feature-index.md` 동기화.
- `.claude/commands/harness-verify.md` (신규) — `/harness-verify`. 변경에 맞는 최소 검증 실행 후 검증 기록 작성.
- `.claude/commands/feature-doc.md` (신규) — `/feature-doc`. `docs/harness/features/` 기능 문서 생성·갱신 및 색인 연계.
- `.claude/agents/harness-doc-writer.md` (신규) — 한국어 변경 기록/기능 문서 작성 전문 서브에이전트.
- `.claude/agents/harness-verifier.md` (신규) — 최소 검증 실행 전용 서브에이전트.
- `docs/harness/feature-index.md` — Documentation Workflow 목록에 본 기록과 Claude Code 진입점을 추가.

## 동작 변화

런타임 동작은 바뀌지 않는다. 하네스 운영 도구와 문서만 추가한 변경이다. Claude Code로 저장소를 열면 `CLAUDE.md`가 자동 로드되어 `AGENTS.md` 규칙을 따르고, `.claude/settings.json` 권한 정책과 슬래시 커맨드/서브에이전트를 사용할 수 있다.

## 검증 수행

- `.claude/settings.json` JSON 유효성 검사 통과(`py -c json.load`).
- 생성 파일 목록 확인(`.claude/` 7개 파일 + `CLAUDE.md`).

## 실행하지 않은 명령

- 백엔드 `pytest`, 프론트 `npm run lint/build`는 실행하지 않았다. 애플리케이션 런타임 코드가 바뀌지 않았기 때문이다.

## 후속 위험

- Claude Code의 `@path` import와 `.claude/` 권한·커맨드·서브에이전트 동작은 사용 중인 Claude Code 버전에 따라 다를 수 있다. 첫 세션에서 `CLAUDE.md`가 `AGENTS.md`를 정상 로드하는지, 슬래시 커맨드가 노출되는지 확인이 필요하다.
- `AGENTS.md`가 규칙의 단일 소스이므로, 규칙을 바꿀 때는 `CLAUDE.md`가 아니라 `AGENTS.md`를 수정해야 한다. Claude 전용 보강만 `CLAUDE.md`에 둔다.
- `permissions.ask`/`allow` 패턴은 PowerShell 별칭(`Remove-Item`, `del`)을 일부만 포괄한다. 실제 차단/확인 동작은 사용하며 보완한다.
