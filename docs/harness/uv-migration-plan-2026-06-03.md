# pip → uv 전환 계획 (백엔드 + 루트 테스트 Python 환경)

Date: 2026-06-03

> 이 문서는 **계획서**다. 이번 단계에서는 코드/설정을 변경하지 않는다. 실제 전환은 사용자 승인 후 별도 구현 단계에서 수행한다.

함께 참고:
- `AGENTS.md` 섹션 6(Standard Commands), 9(Risky Change Protocol), 12·13(문서 동기화)
- `backend/DEVELOPMENT_DIRECTION.md` (Migration Workflow / Deployment Runtime Notes)
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/render-backend-deployment-guide-2026-06-03.md` (현재 빌드 명령이 `pip install -r requirements.txt`)
- `ENVIRONMENT_VARIABLE_SETUP.md` (로컬 `.venv` + pip 명령)

---

## 1. 목적 (Objective)

현재 Python 의존성 관리는 `pip install -r requirements.txt` + 표준 `venv`(`backend/.venv`) 기반이다. 이를 [uv](https://docs.astral.sh/uv/)(Astral의 Rust 기반 Python 패키지·프로젝트 매니저)로 전환한다.

전환으로 얻는 것:
- **결정론적 설치**: `uv.lock` 락파일로 해시·버전 고정 → 로컬/CI/배포 환경 간 의존성 불일치 제거. 현재 `requirements.txt`는 **버전이 전혀 고정되어 있지 않아**([requirements.txt](../../backend/requirements.txt)) 빌드 시점마다 다른 버전이 설치될 수 있다(재현성 위험).
- **빠른 설치**: uv의 병렬 다운로드·전역 캐시로 `langchain`, `pandas` 등 무거운 의존성 설치 시간 단축(Render 첫 빌드 시간 문제 완화 — [render-backend-deployment-guide](render-backend-deployment-guide-2026-06-03.md) Phase 5에서 언급).
- **단일 도구**: 가상환경 생성·의존성 설치·실행(`uv run`)·Python 버전 관리를 하나로 통합.
- **Python 버전 고정**: `.python-version` / `pyproject.toml`의 `requires-python`으로 런타임 버전 명시 → Render 휠 호환 이슈([render-backend-deployment-guide](render-backend-deployment-guide-2026-06-03.md) 트러블슈팅) 예방.

**비목표(이번 전환 범위 아님)**:
- 프론트엔드(`frontend/`, npm)는 그대로 둔다. uv는 Python 전용이다.
- 의존성 자체의 기능적 업그레이드(예: langchain 메이저 업)는 하지 않는다. 가능한 한 **현재 설치된 버전을 그대로 고정**하는 것이 1차 목표다.
- 패키지 빌드/배포(PyPI 발행)는 대상이 아니다. 이 백엔드는 애플리케이션이지 라이브러리가 아니므로 `[project]` 메타데이터는 최소만 둔다.

---

## 2. 현재 동작 / 목표 동작

### 현재 동작 (pip 기반)

| 영역 | 현재 방식 | 근거 파일 |
|---|---|---|
| 의존성 선언 | `backend/requirements.txt` (20개, **버전 미고정**) | [requirements.txt](../../backend/requirements.txt) |
| 락파일 | 없음 (재현성 보장 안 됨) | — |
| 로컬 가상환경 | `backend/.venv` (수동 `python -m venv`), gitignore됨 | [.gitignore:5](../../.gitignore#L5) |
| 로컬 설치 명령 | `pip install -r requirements.txt` | `AGENTS.md` §6, [ENVIRONMENT_VARIABLE_SETUP.md:585](../../ENVIRONMENT_VARIABLE_SETUP.md#L585) |
| 실행 | `uvicorn app.main:app --reload`, `.\.venv\Scripts\python.exe -m uvicorn ...` | `AGENTS.md` §6, [ENVIRONMENT_VARIABLE_SETUP.md:576](../../ENVIRONMENT_VARIABLE_SETUP.md#L576) |
| 테스트 | `pytest` (backend/tests/ 18개 파일) | `AGENTS.md` §6, [backend/tests/](../../backend/tests/) |
| 마이그레이션 | `alembic upgrade head`, `python -m alembic upgrade head` | [backend/DEVELOPMENT_DIRECTION.md:32-48](../../backend/DEVELOPMENT_DIRECTION.md#L32-L48) |
| Python 버전 | 미고정 (Render가 자동 감지) | [render-backend-deployment-guide:50](render-backend-deployment-guide-2026-06-03.md) |
| 배포(Render) 빌드 | `pip install -r requirements.txt` | [render-backend-deployment-guide:51-54](render-backend-deployment-guide-2026-06-03.md) |
| 루트 테스트 헬퍼 | `test_api.py`(`dotenv` 사용), `test_db.py`(backend 모듈 import) | [test_api.py](../../test_api.py), [test_db.py](../../test_db.py) |
| pytest 우회 디렉터리 | `.pytest_deps/` (벤더링된 pytest 보조 모듈, gitignore 안 됨) | [.pytest_deps/py.py](../../.pytest_deps/py.py) |

### 목표 동작 (uv 기반)

| 영역 | 목표 방식 |
|---|---|
| 의존성 선언 | `backend/pyproject.toml`의 `[project.dependencies]` (+ dev 그룹) |
| 락파일 | `backend/uv.lock` (커밋, 결정론적 설치) |
| 가상환경 | `uv sync`가 `backend/.venv` 자동 생성·동기화 (여전히 gitignore) |
| 로컬 설치 | `uv sync` (dev 포함) / `uv sync --no-dev` (런타임만) |
| 실행 | `uv run uvicorn app.main:app --reload` |
| 테스트 | `uv run pytest` |
| 마이그레이션 | `uv run alembic upgrade head` |
| Python 버전 | `backend/.python-version` + `pyproject.toml` `requires-python`로 고정 |
| 배포(Render) 빌드 | `uv sync --no-dev --frozen` (또는 `uv pip install`), 시작은 `uv run uvicorn ...` |

---

## 3. 변경 대상 파일

> 이번 턴은 계획만 — 아래는 구현 단계에서 손댈 파일 목록이다.

### 신규 생성 (사용자 승인 필요 — 신규 파일)
- `backend/pyproject.toml` — 프로젝트 메타데이터 + 의존성(현재 버전 고정값 반영) + dev 의존성 그룹 + (선택) `[tool.pytest.ini_options]`.
- `backend/uv.lock` — `uv lock`이 생성하는 락파일(커밋 대상).
- `backend/.python-version` — 로컬/uv가 사용할 Python 버전 핀.
- (선택) `backend/.uvignore` — 불필요 시 생략.

### 수정
- `backend/requirements.txt` — **즉시 삭제하지 않는다.** 전환 검증이 끝날 때까지 유지하고, 안정화 후 (a) 삭제하거나 (b) `uv export`로 자동 생성되는 호환 파일로 전환할지 결정. 삭제는 파일 삭제이므로 사용자 확인 필요(§5).
- `AGENTS.md` 섹션 6 (Standard Commands) — Backend 명령을 uv 기반으로 교체/병기.
- `CLAUDE.md` 전용 운영 노트 — 표준 명령 언급이 있으면 uv로 보강.
- `backend/DEVELOPMENT_DIRECTION.md` — Migration Workflow / Deployment Runtime Notes의 명령을 uv 기반으로.
- `ENVIRONMENT_VARIABLE_SETUP.md` — 로컬 설치/실행 명령([576](../../ENVIRONMENT_VARIABLE_SETUP.md#L576), [585](../../ENVIRONMENT_VARIABLE_SETUP.md#L585) 부근)을 uv로.
- `docs/harness/render-backend-deployment-guide-2026-06-03.md` 및 `backend-persistent-host-deployment-plan-2026-06-03.md` — 빌드/시작 명령을 uv 기반으로 갱신(또는 새 구현 기록에서 정정 링크).
- `.claude/settings.json` — pip 관련 permission allow 규칙이 있으면 uv 명령 allow를 추가(있을 때만; 시크릿/`.env` 차단 규칙은 건드리지 않음).
- 루트 `test_api.py` — `dotenv`(python-dotenv) import 사용 중인데 현재 `requirements.txt`에 **없다**. uv 전환 시 의존성 그룹에 명시적으로 추가할지, 아니면 이 헬퍼를 backend 프로젝트 밖의 1회성 스크립트로 분류할지 결정(§6 정책).

### 설정/인프라 (저장소 외부 — 사용자가 대시보드에서 수행)
- **Render Web Service Build/Start Command** 변경(저장소 코드 아님, 사용자 작업). 구현 단계에서 정확한 명령을 안내.

### 손대지 않음
- `frontend/` 전체(npm 유지).
- `.env` 및 모든 시크릿.
- DB 스키마, Alembic 리비전 내용(`alembic upgrade head` 호출 방식만 `uv run`으로 prefix).
- `.pytest_deps/` — 이 디렉터리의 정체를 먼저 확정한 뒤 처리(§7 미해결 항목).

---

## 4. 단계별 구현 계획 (이번 턴 미실행)

### Phase 0 — 사전 조사·동결 (구현 직전)
1. `git status --short`로 미커밋 변경 확인.
2. **현재 설치된 정확한 버전 캡처**: 활성 `backend/.venv`에서 `uv pip freeze`(uv 설치 후) 또는 `pip freeze`로 현재 해석된 버전 스냅샷을 확보 → 이 버전을 락의 기준으로 삼아 "기능 변화 없는 전환"을 보장.
3. 대상 Python 버전 확정(현재 `backend/.venv/pyvenv.cfg`에 기록된 버전을 기준으로, Render가 지원하는 안정 버전으로 정렬). 사용자에게 확인.
4. uv 설치 방식 확정(Windows: `pip install uv` 또는 standalone installer). 로컬·CI·Render 각각에서 어떻게 들어오는지 명시.

### Phase 1 — `pyproject.toml` 작성
1. `[project]` 최소 메타데이터: `name = "project-finance-backend"`, `version`, `requires-python = ">=X.Y"`.
2. `[project.dependencies]`에 현재 `requirements.txt`의 20개를 옮기되, **Phase 0에서 캡처한 버전으로 하한/정확 핀**을 건다(예: `fastapi==<현재버전>`). 처음에는 보수적으로 `==`로 고정해 무변경 전환을 목표로 하고, 안정화 후 `>=`로 완화 검토.
   - `python-jose[cryptography]`의 extras 표기 유지.
3. dev 의존성 그룹 분리: `pytest`, `pytest-asyncio`를 `[dependency-groups]`의 `dev` 그룹으로 이동(런타임 이미지에서 제외 가능 → Render 메모리/용량 이점).
4. `dotenv`(python-dotenv) 처리: 루트 `test_api.py`가 쓰므로(§6) dev 그룹에 추가하거나 헬퍼를 정리. **현재 requirements에 누락된 상태이므로 이번에 명시화**.
5. (선택) `[tool.pytest.ini_options]`로 pytest 설정을 pyproject에 통합(현재 프로젝트엔 pytest 설정 파일이 없음).

### Phase 2 — 락 생성·환경 동기화
1. `cd backend; uv lock` → `uv.lock` 생성.
2. `uv sync` → `.venv` 재구성(dev 포함). 기존 `.venv`는 uv가 관리하도록 재생성하거나 새 경로 사용.
3. `uv lock` 결과의 해석 버전을 Phase 0 스냅샷과 **diff** → 의도치 않은 버전 이동이 없는지 확인. 차이가 있으면 핀 조정.

### Phase 3 — 명령 체계 전환(문서·런타임)
1. 로컬 표준 명령 매핑:
   - `pip install -r requirements.txt` → `uv sync`
   - `uvicorn app.main:app --reload` → `uv run uvicorn app.main:app --reload`
   - `pytest` → `uv run pytest`
   - `alembic upgrade head` → `uv run alembic upgrade head`
2. `AGENTS.md` §6, `CLAUDE.md`, `backend/DEVELOPMENT_DIRECTION.md`, `ENVIRONMENT_VARIABLE_SETUP.md` 갱신.

### Phase 4 — 배포(Render) 전환
1. Build Command 후보(택1, 구현 단계에서 사용자와 확정):
   - `uv sync --no-dev --frozen` (권장: 락 기준, dev 제외)
   - 또는 `uv pip install --system -r requirements.txt`(최소 변경, 락 미사용 — 비권장)
2. Start Command: `uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
3. uv를 Render 빌드 환경에 들이는 방법 확정(빌드 명령 앞단에서 `pip install uv` 또는 Render의 uv 지원/`PYTHON_VERSION`+installer).
4. `--frozen`으로 CI/배포에서 락 불일치 시 빌드 실패하게 해 드리프트 방지.
5. **staging부터** 적용 후 `/health`, `/db-check`, `/api/market/prices` smoke([render-backend-deployment-guide](render-backend-deployment-guide-2026-06-03.md) Phase 5).

### Phase 5 — 정리
1. `requirements.txt` 거취 결정: 삭제(사용자 확인) vs `uv export --no-dev -o requirements.txt`로 자동 생성 호환본 유지(다른 도구 호환용).
2. `.pytest_deps/` 정체 확정 후 제거 가능 여부 판단(§7). 제거는 파일 삭제 → 사용자 확인.
3. `.gitignore` 점검: `.venv`는 이미 무시됨([.gitignore:5](../../.gitignore#L5)). `uv.lock`·`pyproject.toml`·`.python-version`은 **커밋**(무시하면 안 됨). uv 캐시 경로가 저장소 안에 생기면 추가.

---

## 5. 위험과 Risky Change 여부 (AGENTS.md 섹션 9)

이 전환은 DB 스키마·인증·스케줄러/리포트 비용을 직접 바꾸지 않으므로 §9의 "반드시 사용자 확인" 항목 다수에는 해당하지 않는다. 그러나 다음은 **사용자 사전 승인이 필요**하다:

1. **신규 설정 파일 추가** — `pyproject.toml`/`uv.lock`/`.python-version` 추가. (CLAUDE.md: 새 설정 파일·도구 도입은 사용자 승인.)
2. **배포 빌드/시작 명령 변경(Render)** — 빌드 명령을 잘못 바꾸면 배포 실패. 저장소 외부 대시보드 설정이라 사용자 협조 필수. staging 우선.
3. **의존성 버전 고정으로 인한 버전 이동** — 현재 비고정이라 락 시점에 일부 패키지가 현재 설치본과 다르게 해석될 수 있음(특히 `langchain`, `langgraph` 계열은 변동이 잦음). → 무변경 전환을 위해 Phase 0 스냅샷 기준 `==` 고정으로 시작.
4. **파일 삭제** — `requirements.txt`, `.pytest_deps/` 제거는 §7(파일 삭제) → 명시적 승인 후.
5. **Python 버전 핀** — Render 자동 감지 버전과 다르면 휠 호환/빌드 영향. 현재 `.venv` 버전과 정렬.

비용·네트워크: 패키지 재다운로드(1회) 외 상시 비용 증가 없음. 유료 API/스케줄러 무관.

---

## 6. 결정이 필요한 정책 항목 (구현 전 합의)

1. **버전 고정 강도**: 무변경 우선 `==` 핀 vs 유연한 `>=` 핀. (권장: `==`로 전환→안정화 후 완화)
2. **루트 `test_api.py`/`test_db.py` 소속**: backend 프로젝트의 dev 의존성으로 포함할지, 별도 1회성 스크립트로 둘지. `test_api.py`의 `dotenv` 누락 의존성을 어디서 선언할지 직결.
3. **requirements.txt 유지 여부**: 삭제 vs `uv export` 호환본 유지(Render가 uv 미지원 시 fallback).
4. **uv 단일 프로젝트 vs 워크스페이스**: backend만 uv화(권장, 단순) vs 루트에 uv 워크스페이스 구성(루트 테스트까지 포함).
5. **Render에 uv 도입 방식**: 빌드 명령 prefix `pip install uv` vs installer vs uv 미사용(`uv export`→pip).

---

## 7. 미해결·선행 조사 항목

- **`.pytest_deps/` 정체**: pytest 보조 모듈(`py` 셰임 등)을 벤더링한 우회 디렉터리로 보임([.pytest_deps/py.py](../../.pytest_deps/py.py)). 어떤 명령/경로가 이걸 참조하는지(예: `PYTHONPATH`, conftest, CI 스크립트) 구현 전 확인 필요. uv가 정상적으로 `pytest`/`pytest-asyncio`를 설치하면 이 우회가 불필요해질 가능성이 큼 → 제거 후보지만 참조처 확인 후 판단.
- **현재 활성 Python 버전**: `backend/.venv/pyvenv.cfg`에서 정확 버전 확인 후 핀 기준 확정.
- **`python-jose[cryptography]` 등 extras**가 락에서 올바르게 해석되는지 확인.

---

## 8. 검증 계획 (AGENTS.md 섹션 6)

구현 단계에서 변경 범위에 맞춰 최소 검증:

### 백엔드 (의존성/실행 체계 변경)
- `cd backend; uv sync` 성공.
- `cd backend; uv run pytest` — 기존 18개 테스트 파일이 pip 환경과 **동일 통과**([backend/tests/](../../backend/tests/)). (전환 전후 결과 비교가 핵심 검증.)
- `cd backend; uv run python -c "import app.main"` 또는 `uv run uvicorn app.main:app --reload`로 앱 import/기동 확인(실 LLM/외부 호출 없이).
- `uv run alembic upgrade head`는 disposable staging DB에서만(실 DB 변경 금지, 사용자 확인).
- 버전 diff: Phase 0 스냅샷 ↔ `uv.lock` 해석본 비교.

### 프론트엔드
- 변경 없음 → `npm run lint`/`npm run build`는 생략(사유: 프론트 무관). 단, 동일 PR에 프론트 변경이 섞이면 실행.

### 배포
- staging Render에서 빌드 성공 + `/health` ok + `/db-check` db_connected.

### 실행 못 하는 경우
- 네트워크/패키지 인덱스 접근 불가, 시크릿/DB 미가용 시 그 사유를 검증 기록에 명시.

---

## 9. 갱신할 문서 (AGENTS.md 섹션 12·13)

구현 단계에서 함께 갱신:

- **신규 구현 기록**: `docs/harness/uv-migration-implementation-2026-XX-XX.md` (날짜·목적·변경 파일·동작 변화·검증·미실행 명령·후속 위험).
- **`docs/harness/features/deployment-runtime.md`**: 백엔드 빌드/실행이 uv 기반으로 바뀐 점을 Current Behavior/Ownership Map/Open Risks에 반영, 이 계획서와 구현 기록을 Change Records에 추가.
- **`docs/harness/feature-index.md`**: "Deployment and hosted runtime" 행과 Deployment/runtime plans 목록에 이 계획서(`uv-migration-plan-2026-06-03.md`)와 후속 구현 기록 링크 추가.
- **`backend/DEVELOPMENT_DIRECTION.md`**: Migration Workflow / Deployment Runtime Notes 명령을 uv로.
- **`AGENTS.md` §6, `CLAUDE.md`, `ENVIRONMENT_VARIABLE_SETUP.md`**: 표준 명령 uv화.
- **`docs/harness/render-backend-deployment-guide-2026-06-03.md`, `backend-persistent-host-deployment-plan-2026-06-03.md`**: 빌드/시작 명령 정정 또는 구현 기록 링크.
- 폴더 소유권 변화는 없음 → 별도 `DEVELOPMENT_DIRECTION.md` 신설 불필요.

---

## References Checked

- 코드/설정: [backend/requirements.txt](../../backend/requirements.txt), [docker-compose.yml](../../docker-compose.yml), [test_api.py](../../test_api.py), [test_db.py](../../test_db.py), [.gitignore](../../.gitignore), [backend/tests/](../../backend/tests/), [.pytest_deps/py.py](../../.pytest_deps/py.py), `backend/.venv/pyvenv.cfg`(존재 확인)
- 문서: `AGENTS.md`, `CLAUDE.md`, `DEVELOPMENT_DIRECTION.md`, [backend/DEVELOPMENT_DIRECTION.md](../../backend/DEVELOPMENT_DIRECTION.md), [docs/harness/feature-index.md](feature-index.md), [docs/harness/render-backend-deployment-guide-2026-06-03.md](render-backend-deployment-guide-2026-06-03.md), [docs/harness/backend-persistent-host-deployment-plan-2026-06-03.md](backend-persistent-host-deployment-plan-2026-06-03.md), [ENVIRONMENT_VARIABLE_SETUP.md](../../ENVIRONMENT_VARIABLE_SETUP.md)
- 외부(구현 직전 재확인): uv 공식 문서(`uv sync`/`uv lock`/`uv run`/`dependency-groups`/`--frozen`), Render의 Python 빌드 환경에서의 uv 사용법
