# AGENTS.md

이 문서는 `Project_Finance` 저장소에서 AI coding harness 또는 agent가 안전하게 탐색, 수정, 테스트, 검증하기 위한 운영 지침이다. 에이전트는 실제 코드 구조를 우선하며, 문서와 코드가 충돌할 때는 현재 저장소의 구현을 기준으로 판단한다.

## 1. Project Snapshot

- Product: 글로벌 금융 데이터, AI 투자 리포트, 인증, 커뮤니티 기능을 제공하는 풀스택 웹 애플리케이션.
- Frontend: React + Vite + JavaScript + Tailwind CSS + Zustand + React Router.
- Backend: Python + FastAPI + Async SQLAlchemy + PostgreSQL.
- AI/report pipeline: LangGraph, LangChain, OpenAI API, scheduled/background report generation.
- Database/runtime support: PostgreSQL via `docker-compose.yml`.

주의: `ARCHITECTURE.md`에는 Next.js/TypeScript 기반 설명이 일부 남아 있지만, 현재 실제 프론트엔드 코드는 `frontend/`의 React + Vite + JavaScript 구조이다. 하네스는 실제 코드 기준으로 작업한다.

## 2. Required Pre-Work

작업을 시작하기 전에 다음을 확인한다.

1. `git status --short`로 기존 사용자 변경사항을 확인한다.
2. `.env` 파일과 API 키, DB 비밀번호, JWT secret 등 시크릿은 출력하지 않는다.
3. 관련 작업 범위에 따라 다음 문서를 먼저 참고한다.
   - `ARCHITECTURE.md`
   - `PROJECT_STRUCTURE_ANALYSIS.md` (파일이 존재할 때)
   - 루트 및 하위 폴더의 `DEVELOPMENT_DIRECTION.md`
   - `docs/harness/feature-index.md`
   - 작업 대상 기능의 `docs/harness/features/*.md`
   - 해당 기능에 연결된 `docs/harness/` 변경 기록
4. 요청과 직접 관련된 파일만 수정한다.
5. 사용자 또는 다른 도구가 만든 변경사항을 되돌리지 않는다.

## 3. Repository Map

```text
Project_Finance/
├─ backend/                    # FastAPI backend
│  ├─ app/
│  │  ├─ api/                  # API routers and dependencies
│  │  ├─ core/                 # config, security, cache
│  │  ├─ db/                   # async DB session and Base
│  │  ├─ services/             # market, macro, AI, LangGraph logic
│  │  ├─ main.py               # FastAPI app entrypoint
│  │  ├─ models.py             # SQLAlchemy models
│  │  └─ schemas.py            # Pydantic schemas
│  ├─ tests/                   # backend tests
│  └─ requirements.txt
├─ frontend/                   # React + Vite frontend
│  ├─ src/
│  │  ├─ pages/                # route-level screens
│  │  ├─ components/           # shared UI and feature components
│  │  ├─ store/                # Zustand stores
│  │  ├─ utils/                # constants, formatters, validation
│  │  ├─ App.jsx               # route composition
│  │  └─ main.jsx              # React entrypoint
│  └─ package.json
├─ docker-compose.yml          # PostgreSQL service
├─ ARCHITECTURE.md
├─ PROJECT_STRUCTURE_ANALYSIS.md
└─ test_api.py, test_db.py     # root-level test helpers
```

## 4. Backend Work Rules

- API routes belong in `backend/app/api/`.
- Shared route dependencies belong in `backend/app/api/deps.py`.
- Business logic belongs in `backend/app/services/`, not directly inside route handlers.
- DB models belong in `backend/app/models.py`.
- Request and response contracts belong in `backend/app/schemas.py`.
- Settings, security, cache, and environment handling belong in `backend/app/core/`.
- Async SQLAlchemy patterns should be preserved.
- Authentication changes should review `backend/app/api/auth.py`, `backend/app/api/deps.py`, and `backend/app/core/security.py` together.
- AI report or LangGraph changes should review `backend/app/services/ai_service.py` and `backend/app/services/graph/`.
- Avoid real LLM calls in ordinary tests unless explicitly requested. Prefer narrow tests, mocks, or isolated service checks.

## 5. Frontend Work Rules

- Route definitions live in `frontend/src/App.jsx`.
- Page-level screens live in `frontend/src/pages/`.
- Reusable visual or feature components live in `frontend/src/components/`.
- Zustand stores live in `frontend/src/store/`.
- Shared constants, formatters, and validation schemas live in `frontend/src/utils/`.
- Preserve the existing React + Vite + JavaScript style unless the user explicitly requests migration.
- Keep API integration patterns consistent with the existing code.
- Prefer focused component changes over broad UI rewrites.
- Do not introduce a new design system or routing framework without explicit user approval.

## 6. Standard Commands

Run commands from the repository root unless a command says otherwise.

### Database

```powershell
docker compose up -d db
```

### Backend

```powershell
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
pytest
```

### Frontend

```powershell
cd frontend
npm install
npm run lint
npm run build
npm run dev
```

Use the smallest verification set that matches the change:

- Backend API/service change: run relevant `pytest` tests.
- Frontend change: run `npm run lint` and `npm run build` when feasible.
- Cross-stack change: verify backend and frontend together.
- DB-dependent change: ensure PostgreSQL is running first.

## 7. Harness Safety Rules

The harness may:

- Read source files and project documentation.
- Create or update focused source files for the requested task.
- Run lint, build, and tests.
- Start local development servers when needed for verification.

The harness must not:

- Print, summarize, copy, or commit `.env` contents.
- Revert user changes without explicit instruction.
- Run destructive Git commands such as `git reset --hard` or broad checkout operations.
- Delete files, clear databases, or drop volumes without explicit user approval.
- Perform large unrelated refactors.
- Modify generated logs unless the task specifically concerns logging output.
- Treat `ARCHITECTURE.md` as more authoritative than current code when they conflict.

## 8. Secret Handling

- Never inspect `.env` unless the user explicitly asks and the task cannot be completed otherwise.
- Never include API keys, tokens, DB passwords, or JWT secrets in responses.
- If a secret appears in chat, logs, screenshots, or source, assume it is compromised and advise rotation.
- Prefer environment variables for credentials and configuration.
- Do not move secrets into committed files.

## 9. Risky Change Protocol

Ask for confirmation before:

- DB schema changes that require migrations or data resets.
- Deleting files or directories.
- Changing authentication or password hashing behavior.
- Changing scheduler frequency or AI report generation behavior in a way that may increase cost.
- Adding paid APIs or network-heavy workflows.
- Replacing the frontend framework, backend framework, or database layer.

When a risky change is required, explain the risk, the intended files, and the verification plan before editing.

## 10. Testing Expectations

- Add or update tests when behavior changes.
- Keep tests close to the changed layer.
- For backend service changes, prefer tests under `backend/tests/`.
- For root helper scripts, use the existing root-level test files only when they are directly relevant.
- If tests cannot run because of missing services, dependencies, network, or secrets, report that clearly.

## 11. Response Expectations

When reporting work back to the user:

- Mention the files changed.
- Mention the verification commands run and their results.
- Mention any commands not run and why.
- Call out any remaining risks or manual follow-up.
- Do not expose secrets or sensitive configuration values.

## 12. Harness Change Records

When code changes are made, create or update a Markdown change record so future harness engineering work can reuse the context.

- Store change records under `docs/harness/`.
- Use one focused file per meaningful change, for example `docs/harness/google-login-only.md`.
- Include the date, objective, files changed, behavior changes, verification performed, and follow-up risks.
- Do not include secrets, raw environment values, access tokens, database passwords, or API keys.
- Keep the record practical: write what changed and how a future agent should reason about it.

## 13. Harness Feature Documentation

Future harness work must keep feature explanations and modification records linked.

- Use `docs/harness/feature-documentation-guide.md` as the documentation workflow.
- Use `docs/harness/feature-index.md` to find the feature document for the work area.
- Feature explanations live under `docs/harness/features/`.
- When a feature is changed, update the matching feature document and add the change-record link to its `Change Records` section.
- When a new feature area, route group, service boundary, or external integration is added, create a new feature document and add it to `docs/harness/feature-index.md`.
- When folder ownership changes, update the nearest `DEVELOPMENT_DIRECTION.md` so the feature document and code location remain connected.
- If existing product specs conflict with the current code or feature docs, inspect the current implementation first and update the stale documentation as part of the task.

## 14. AI Report Generation Documentation Rule

- Any audit, plan, or implementation touching AI report scheduler cadence, scheduler coverage, report cooldowns, manual generation endpoints, asset-detail report loading, or chatbot report responses must be documented under `docs/harness/`.
- Link the document from the affected feature docs and `docs/harness/feature-index.md`.
- State explicitly whether user-facing requests can trigger report generation.
- The target rule is that users and the chatbot read stored scheduled reports only; ordinary user requests should not generate a fresh report.
