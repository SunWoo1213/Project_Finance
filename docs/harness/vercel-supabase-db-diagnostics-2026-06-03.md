# Vercel Supabase DB 진단 보강 구현 기록

Date: 2026-06-03

## Objective

Vercel/Supabase integration 도입 준비 중 backend가 `DATABASE_URL`, `POSTGRES_URL_NON_POOLING`, `POSTGRES_URL` 중 어떤 DB URL 변수를 선택했는지 secret 노출 없이 확인할 수 있게 한다.

## Files Changed

- `backend/app/core/config.py`
- `backend/tests/test_database_config.py`
- `.env_example`
- `ENVIRONMENT_VARIABLE_SETUP.md`
- `VERCEL_SUPABASE_INTEGRATION_GUIDE.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/feature-index.md`
- `docs/harness/vercel-supabase-db-diagnostics-2026-06-03.md`

## Behavior Changes

- Backend 설정 로드가 DB URL 선택 source를 내부적으로 추적한다.
- `settings.database_url_diagnostics()`가 기존 `scheme`, `host`, `port`에 더해 선택된 변수명인 `source`를 반환한다.
- `/db-check`의 sanitized database 진단에서도 `DATABASE_URL`, `POSTGRES_URL_NON_POOLING`, `POSTGRES_URL` 중 어떤 변수가 쓰였는지 확인할 수 있다.
- URL 전체, username, password, query credential은 계속 반환하지 않는다.
- `POSTGRES_URL_NON_POOLING` 우선 fallback과 `POSTGRES_URL` fallback을 검증하는 테스트 케이스를 추가했다.

## Verification Performed

- 사용자가 검증 금지를 명시했으므로 lint, build, pytest, Alembic, backend smoke, Vercel CLI, Supabase 연결 검증은 실행하지 않았다.
- `.env` 값은 읽거나 출력하지 않았다.

## Commands Not Run

- `pytest backend/tests/test_database_config.py`: 검증 금지 요청 때문에 실행하지 않았다.
- `npm run lint`: frontend 변경이 아니며 검증 금지 요청 때문에 실행하지 않았다.
- `npm run build`: frontend 변경이 아니며 검증 금지 요청 때문에 실행하지 않았다.
- `python -m alembic upgrade head`: DB 검증 금지 요청 때문에 실행하지 않았다.
- `vercel env ls`, `vercel env pull`: 실제 계정/env 조회가 필요하고 검증 금지 요청이 있으므로 실행하지 않았다.

## Follow-up Risks

- 실제 Supabase connection mode는 backend hosting provider가 정해진 뒤 staging에서 확인해야 한다.
- `/db-check`는 여전히 DB readiness 검증 endpoint이므로, 운영 전에는 반드시 별도 smoke에서 확인해야 한다.
- `database.source`는 변수명만 알려 주며, 해당 변수의 값이 올바른 Supabase project를 가리키는지는 외부 secret store와 실제 연결 검증이 필요하다.

## Linked Feature Documents

- `docs/harness/features/deployment-runtime.md`
