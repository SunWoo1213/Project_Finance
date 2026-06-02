# Docker 데이터베이스 호환성 구현 기록

작성일: 2026-06-02

## 목표

로컬 Docker PostgreSQL 초기화 값과 FastAPI `DATABASE_URL` 설정이 어긋나기 쉬운 구조를 줄이고, DB 준비 상태를 `/health`와 혼동하지 않도록 런타임 진단 메시지를 개선했다.

기준 계획 문서: `docs/harness/docker-database-compatibility-remediation-plan-2026-06-02.md`

## 변경 파일

- `docker-compose.yml`
- `.env_example`
- `ENVIRONMENT_VARIABLE_SETUP.md`
- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/tests/test_database_config.py`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/feature-index.md`
- `docs/harness/docker-database-compatibility-implementation-2026-06-02.md`

## 동작 변경

1. `docker-compose.yml`에서 DB 사용자, 비밀번호, DB 이름의 하드코딩을 제거하고 `.env`의 `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT`를 사용하도록 변경했다.
2. Compose v2 obsolete 경고를 줄이기 위해 top-level `version` 속성을 제거했다.
3. `.env_example`에 로컬 Docker DB용 `POSTGRES_*` 변수를 추가하고, `DATABASE_URL` 예시를 `postgresql+asyncpg://...` 형식으로 명확히 했다.
4. `backend/app/core/config.py`에서 `DATABASE_URL` scheme 검증을 추가했다.
   - PostgreSQL: `postgresql+asyncpg://`
   - 테스트용 SQLite: `sqlite+aiosqlite://`
   - sync PostgreSQL scheme인 `postgresql://`는 설정 오류로 처리한다.
5. `settings.database_url_diagnostics()`를 추가해 DB 진단 시 URL 전체, username, password를 노출하지 않고 `scheme`, `host`, `port`만 반환하도록 했다.
6. local DB bootstrap 실패 로그를 개선해 `/health`가 app liveness 전용이며 DB 준비 상태는 `/db-check`로 확인해야 한다는 점을 남긴다.
7. `/health` 응답에 DB를 확인하지 않는다는 의미의 `database: "not_checked"`와 `database_check: "/db-check"`를 추가했다.
8. `/db-check`는 DB 연결 실패 또는 예상 밖 결과를 `503`으로 반환하고, credential을 제외한 DB target 진단만 포함한다.
9. 기존 `postgres_data` volume은 최초 초기화 값을 유지하므로 `POSTGRES_*` 변경만으로 DB가 재초기화되지 않는다는 점을 문서화했다.

## 검증

사용자가 “검증은 하지 마세요”라고 요청했으므로 검증 명령은 실행하지 않았다.

실행하지 않은 명령:

- `docker compose config`
- `docker compose up -d db`
- `docker compose ps db`
- `cd backend; python -m alembic upgrade head`
- `cd backend; pytest`
- backend `/health`, `/db-check` smoke check

## 후속 위험

- 기존 로컬 `postgres_data` volume에는 이전 DB user/password/name과 데이터가 남아 있을 수 있다. 삭제 또는 재초기화는 데이터 손실 작업이므로 사용자 확인 없이 수행하면 안 된다.
- `.env`는 시크릿 보호 원칙에 따라 읽지 않았으므로 현재 실제 `DATABASE_URL`과 새 `POSTGRES_*` 값의 일치 여부는 확인하지 않았다.
- `docker compose config`는 환경변수 interpolation 이후의 실제 값을 출력할 수 있으므로, 실행 결과를 문서나 채팅에 붙여넣지 않는다.
- `DATABASE_URL` scheme 검증이 추가되었으므로 기존 `.env`가 `postgresql://` 같은 sync scheme을 쓰고 있다면 backend 설정 로드 단계에서 실패한다. 이 경우 `postgresql+asyncpg://`로 바꿔야 한다.

## 연결 문서

- `docs/harness/features/deployment-runtime.md`
- `docs/harness/feature-index.md`
- `ENVIRONMENT_VARIABLE_SETUP.md`
