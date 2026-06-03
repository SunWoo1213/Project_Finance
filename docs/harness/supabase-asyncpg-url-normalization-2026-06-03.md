# Supabase asyncpg URL 정규화 수정

Date: 2026-06-03

## Objective

Supabase PostgreSQL connection string으로 `python -m alembic upgrade head`를 실행할 때 `asyncpg`가 `sslmode` query parameter를 받지 못해 실패하는 문제를 수정한다.

## Error Observed

사용자가 붙여준 Alembic 실행 로그에서 아래 오류가 확인됐다.

```text
TypeError: connect() got an unexpected keyword argument 'sslmode'
```

이 오류는 Supabase/libpq 스타일 URL의 `?sslmode=require`가 SQLAlchemy asyncpg dialect를 통해 `asyncpg.connect()`에 그대로 전달될 때 발생한다. `asyncpg`에는 `sslmode`가 아니라 asyncpg가 이해하는 SSL 옵션이 필요하다.

두 번째 로그에는 포트가 비어 있는 DB URL로 보이는 설정 오류도 있었다.

```text
ValueError: invalid literal for int() with base 10: ''
```

이 경우 실제 `.env`의 `DATABASE_URL` 또는 fallback URL에서 host와 port 구간을 다시 확인해야 한다. 문서나 채팅에는 전체 URL을 붙여넣지 않는다.

## Files Changed

- `backend/app/core/config.py`
- `backend/app/db/session.py`
- `backend/alembic/env.py`
- `backend/tests/test_database_config.py`
- `VERCEL_SUPABASE_INTEGRATION_GUIDE.md`
- `ENVIRONMENT_VARIABLE_SETUP.md`
- `docs/harness/supabase-console-tasks-2026-06-03.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/feature-index.md`
- `docs/harness/supabase-asyncpg-url-normalization-2026-06-03.md`

## Behavior Changes

- `DATABASE_URL`, `POSTGRES_URL_NON_POOLING`, `POSTGRES_URL`이 `postgresql://...` 또는 `postgres://...`로 들어오면 기존처럼 `postgresql+asyncpg://...`로 정규화한다.
- PostgreSQL URL query에 `sslmode=require`, `sslmode=prefer`, `sslmode=allow`, `sslmode=verify-ca`, `sslmode=verify-full`이 있으면 `sslmode`를 제거하고 `ssl=<same-mode>`로 정규화한다.
- `asyncpg`에 전달할 `connect_args` 생성 로직을 `settings.database_connect_args()`로 모았다.
- Runtime DB session과 Alembic migration이 같은 `DB_PREPARED_STATEMENT_CACHE_SIZE` connect arg를 사용한다.
- Alembic online migration은 `async_engine_from_config()` 대신 `create_async_engine(settings.DATABASE_URL, ...)`을 사용해 runtime과 같은 엔진 옵션을 명시한다.

## Verification Performed

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_database_config.py
```

결과:

- `10 passed`
- Pytest cache write warning 1건이 있었지만 테스트 자체는 통과했다. 경고는 sandbox 권한 때문에 `.pytest_cache`를 만들지 못한 것으로 보인다.

## Commands Not Run

- `python -m alembic upgrade head`: 실제 DB schema를 변경할 수 있는 명령이므로 사용자 승인 없이 실행하지 않았다.
- 전체 backend test suite: 이번 변경은 DB URL 설정 계층에 한정되어 우선 관련 단위 테스트만 실행했다.

## Follow-up Risks

- 실제 Supabase URL에 포트가 비어 있으면 코드 수정과 별개로 URL 자체를 고쳐야 한다. Supabase 콘솔에서 host, port, database name을 다시 확인한다.
- Transaction pooler를 쓰는 경우 prepared statement cache 설정은 staging에서 실제 연결로 확인해야 한다.
- 실제 DB에 migration을 적용하기 전에는 대상이 staging인지 production인지 다시 확인한다.
