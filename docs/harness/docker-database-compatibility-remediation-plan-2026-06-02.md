# Docker 데이터베이스 호환성 수정 계획

작성일: 2026-06-02

## 목표

로컬 Docker PostgreSQL과 FastAPI 개발환경의 DB 접속 설정이 어긋나서 backend startup, `/db-check`, Alembic migration, 테스트 검증이 불안정해지는 문제를 해결하기 위한 수정 계획을 정리한다.

이 문서는 구현 변경이 아니라 후속 수정 계획이다. 실제 수정 시에는 현재 `.env` 값이나 DB 비밀번호를 문서/로그/응답에 남기지 않는다.

## 확인 범위

- `git status --short`
- `ARCHITECTURE.md`
- `PROJECT_STRUCTURE_ANALYSIS.md`
- `DEVELOPMENT_DIRECTION.md`
- `backend/DEVELOPMENT_DIRECTION.md`
- `backend/app/core/DEVELOPMENT_DIRECTION.md`
- `backend/app/db/DEVELOPMENT_DIRECTION.md`
- `docs/harness/feature-index.md`
- `docs/harness/features/deployment-runtime.md`
- `ENVIRONMENT_VARIABLE_SETUP.md`
- `.env_example`
- `docker-compose.yml`
- `backend/app/core/config.py`
- `backend/app/db/session.py`
- `backend/app/main.py`
- `backend/alembic/env.py`
- `backend/alembic/versions/*.py`
- `backend/requirements.txt`

`.env`는 열려 있는 파일이지만 시크릿 보호 원칙에 따라 읽지 않았다.

## 현재 관찰

1. `docker-compose.yml`의 `environment`에 DB 사용자, 비밀번호, DB 이름이 직접 적혀 있다.
   - 문제 위치: `docker-compose.yml:8-12`
   - 실제 값은 이 문서에 기록하지 않는다.
   - 이 값은 `docker compose config` 출력에도 그대로 노출된다.

2. `.env_example`의 `DATABASE_URL`은 placeholder 형식이고, Docker DB의 `POSTGRES_*` 값과 자동으로 연결되지 않는다.
   - 문제 위치: `.env_example:78-80` 이후 Database 섹션
   - 사용자가 `.env`의 `DATABASE_URL`과 `docker-compose.yml`의 DB 초기화 값을 수동으로 맞춰야 한다.

3. backend는 `DATABASE_URL`을 그대로 `create_async_engine()`에 전달한다.
   - 문제 위치: `backend/app/core/config.py:10`, `backend/app/db/session.py:17`
   - PostgreSQL runtime에서는 `postgresql+asyncpg://...` 형식이 필요하다.
   - 잘못된 driver scheme, host, port, DB name, credential이 들어가면 DB 연결이 실패한다.

4. local bootstrap 경로는 DB 초기화 실패를 경고 후 건너뛴다.
   - 문제 위치: `backend/app/main.py:133-142`
   - 이 경우 `/health`는 정상처럼 보일 수 있으나 `/db-check`는 실패할 수 있다.
   - 개발자가 "backend는 떴는데 DB만 안 된다"로 오해하기 쉽다.

5. `docker-compose.yml`의 `version` 속성은 Compose v2에서 obsolete 경고를 만든다.
   - 문제 위치: `docker-compose.yml:1`
   - 기능 차단은 아니지만 개발환경 진단 로그에 혼선을 준다.

6. 현재 하네스에서 `docker compose ps`는 Docker Desktop API 권한 문제로 실패했다.
   - 관찰 결과: Docker API named pipe 접근 권한 오류.
   - 저장소 코드만으로 해결되는 문제는 아니지만, 로컬 검증 절차에 "Docker Desktop 실행/권한 확인"을 포함해야 한다.

7. 기존 named volume은 최초 초기화된 DB 계정과 DB 이름을 보존한다.
   - 문제 위치: `docker-compose.yml:15-19`
   - `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`를 바꿔도 기존 `postgres_data` volume이 남아 있으면 새 값으로 DB가 다시 초기화되지 않는다.
   - volume 삭제는 데이터 손실 작업이므로 반드시 사용자 확인 후 진행해야 한다.

## 수정 원칙

- 실제 DB 비밀번호, API key, JWT secret, OAuth secret은 문서와 Git에 남기지 않는다.
- Docker DB 초기화 값과 backend `DATABASE_URL`의 기준을 한 곳으로 모은다.
- 개발 편의와 보안 사이의 균형을 위해 예시값은 dummy/local-only 값으로 두고, 실제 값은 `.env` 또는 배포 환경변수에만 둔다.
- 기존 DB volume 삭제나 재초기화는 데이터 손실 가능성이 있으므로 별도 승인 후 수행한다.
- production-like runtime은 계속 Alembic migration과 `ENABLE_DB_SCHEMA_BOOTSTRAP=false`를 기준으로 둔다.

## 권장 수정 계획

### Phase 1: Compose와 환경변수 단일화

목표: Docker DB 초기화 값과 backend 접속 URL이 서로 어긋나는 구조를 줄인다.

예상 변경 파일:

- `docker-compose.yml`
- `.env_example`
- `ENVIRONMENT_VARIABLE_SETUP.md`
- `docs/harness/features/deployment-runtime.md`

작업:

1. `docker-compose.yml`에서 hardcoded DB 사용자/비밀번호/DB 이름을 제거하고 환경변수 interpolation으로 바꾼다.
   - 예: `POSTGRES_USER: ${POSTGRES_USER}`
   - 예: `POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}`
   - 예: `POSTGRES_DB: ${POSTGRES_DB}`
   - 필요하면 `POSTGRES_PORT`도 `ports`에 적용한다.

2. `version: '3.8'`을 제거해 Compose v2 경고를 없앤다.

3. `.env_example`에 Docker용 변수명을 추가한다.
   - `POSTGRES_USER`
   - `POSTGRES_PASSWORD`
   - `POSTGRES_DB`
   - `POSTGRES_PORT`

4. `.env_example`의 `DATABASE_URL` 예시는 위 Docker 변수와 의미가 맞는 local-only placeholder로 안내한다.
   - 실제 비밀번호를 예시 파일에 넣지 않는다.
   - `postgresql+asyncpg://...@localhost:5432/...` 형식을 명확히 유지한다.

완료 기준:

- `docker compose config`가 hardcoded 실제 DB credential을 보여주지 않는다.
- `docker compose config`에서 obsolete `version` 경고가 사라진다.
- 새 개발자는 `.env_example`을 복사한 뒤 같은 변수 묶음으로 Docker와 backend를 맞출 수 있다.

### Phase 2: DB URL 검증과 실패 메시지 개선

목표: DB가 맞지 않을 때 backend가 더 빨리, 더 명확하게 실패하도록 한다.

예상 변경 파일:

- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/tests/`
- `docs/harness/features/deployment-runtime.md`
- 신규 구현 change record under `docs/harness/`

작업:

1. `DATABASE_URL` scheme 검증을 추가한다.
   - PostgreSQL은 `postgresql+asyncpg://`를 허용한다.
   - 테스트용 SQLite는 `sqlite+aiosqlite://`를 허용한다.
   - secret 값 전체를 로그로 출력하지 않고 scheme/host/port 수준만 진단한다.

2. DB bootstrap 실패 처리 정책을 환경별로 명확히 한다.
   - `ENABLE_DB_SCHEMA_BOOTSTRAP=false`는 현재처럼 migration-ready check 실패를 startup failure로 유지한다.
   - local bootstrap 실패도 `/health`만으로 정상 오해가 생기지 않게 `/db-check`와 로그 문구를 강화한다.
   - 필요하면 `ALLOW_DB_BOOTSTRAP_FAILURE` 같은 명시 opt-in 플래그를 검토한다.

3. `/db-check` 실패 응답은 secret을 노출하지 않고 DB 연결 실패임을 분명히 한다.

완료 기준:

- 잘못된 `DATABASE_URL` scheme은 import/startup 초기에 명확한 설정 오류로 드러난다.
- DB 연결 실패가 `/health` 성공과 혼동되지 않는다.
- 테스트에서 valid/invalid URL 검증이 분리되어 통과한다.

### Phase 3: 기존 Docker volume 호환성 처리 절차 문서화

목표: 이미 생성된 `postgres_data` volume 때문에 새 설정이 반영되지 않는 문제를 안전하게 처리한다.

예상 변경 파일:

- `ENVIRONMENT_VARIABLE_SETUP.md`
- `docs/harness/features/deployment-runtime.md`
- 필요 시 `docs/harness/docker-database-local-reset-guide-2026-06-02.md`

작업:

1. 기존 volume이 있으면 `POSTGRES_*` 변경이 DB 재초기화를 의미하지 않는다는 점을 문서화한다.

2. 로컬 데이터 보존이 필요 없는 경우의 재초기화 절차를 별도 "위험 작업"으로 문서화한다.
   - 실행 전 사용자 확인 필수.
   - 삭제 대상 volume 이름을 먼저 확인.
   - 실제 삭제 명령은 계획서에 바로 실행하지 않는다.

3. 데이터 보존이 필요한 경우에는 새 DB/user 생성 또는 dump/restore 절차를 후속 검토로 분리한다.

완료 기준:

- credential/DB name 변경 후에도 같은 volume을 써서 발생하는 "비밀번호가 맞는데도 안 됨" 유형의 혼선을 줄인다.
- 데이터 삭제가 필요한 조치는 명확히 위험 작업으로 분류된다.

### Phase 4: 검증 절차 정리

목표: 로컬 개발자가 DB 호환성을 같은 순서로 확인할 수 있게 한다.

예상 변경 파일:

- `ENVIRONMENT_VARIABLE_SETUP.md`
- `docs/harness/features/deployment-runtime.md`

권장 검증 순서:

```powershell
git status --short
docker compose config
docker compose up -d db
docker compose ps db
cd backend
python -m alembic upgrade head
$env:ENABLE_MARKET_WARMUP="false"
$env:ENABLE_SCHEDULER="false"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

다른 터미널:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:8000/db-check -UseBasicParsing
```

완료 기준:

- `/health`는 app liveness만 확인한다.
- `/db-check`는 DB 연결 성공을 확인한다.
- Alembic migration이 local Docker PostgreSQL에 적용된다.
- 검증 로그와 문서에 secret 값이 남지 않는다.

## 예상 우선순위

| 우선순위 | 작업 | 이유 |
| --- | --- | --- |
| P0 | `docker-compose.yml` hardcoded credential 제거 | Git/로그 노출 위험과 설정 불일치의 직접 원인 |
| P0 | `.env_example`에 Docker DB 변수와 `DATABASE_URL` 정합성 안내 추가 | 새 개발환경 구성 실패를 줄임 |
| P1 | 기존 volume 재초기화/보존 절차 문서화 | 설정을 바꿔도 DB가 그대로인 문제 방지 |
| P1 | `DATABASE_URL` scheme 검증 | async SQLAlchemy 연결 실패를 빠르게 발견 |
| P2 | local bootstrap 실패 메시지와 `/db-check` 안내 개선 | health와 DB readiness 혼동 방지 |
| P2 | Compose `version` 제거 | 진단 로그 소음 제거 |

## 남은 위험

- 현재 `docker-compose.yml`에 실제처럼 보이는 DB credential이 이미 기록되어 있으므로, 실제로 사용한 값이라면 교체와 회전을 권장한다.
- 기존 `postgres_data` volume에는 이전 credential과 데이터가 남아 있을 수 있다. 삭제는 데이터 손실 작업이므로 후속 구현 단계에서 사용자 승인 후 진행한다.
- 하네스 환경에서는 Docker API 접근 권한 문제로 컨테이너 상태를 확인하지 못했다. 로컬 Docker Desktop 실행 상태와 권한은 사용자 환경에서 별도 확인이 필요하다.
- `.env`는 읽지 않았으므로 현재 실제 `DATABASE_URL`과 Docker DB 값의 일치 여부는 이 문서에서 확정하지 않는다.

## 후속 구현 시 문서 갱신

실제 수정을 수행하면 다음 문서를 함께 갱신한다.

- `docs/harness/features/deployment-runtime.md`
- `ENVIRONMENT_VARIABLE_SETUP.md`
- 필요 시 `.env_example`
- 신규 구현 change record under `docs/harness/`

