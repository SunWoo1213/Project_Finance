# Vercel Supabase 연동 문서화 기록

Date: 2026-06-03

## Objective

Vercel을 통해 Supabase를 연동하는 방법과 이후 실행 계획을 문서화한다.

## Files Changed

- `VERCEL_SUPABASE_INTEGRATION_GUIDE.md`
- `docs/harness/vercel-supabase-integration-next-plan-2026-06-03.md`
- `docs/harness/vercel-supabase-integration-documentation-2026-06-03.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/feature-index.md`

## Behavior Changes

- 애플리케이션 런타임 동작 변경 없음.
- Vercel Supabase Marketplace 설치, Vercel env 동기화 확인, backend `DATABASE_URL` 변환, migration, smoke test 순서를 문서화했다.
- 현재 프로젝트의 권장 구조가 `Vercel frontend + persistent FastAPI backend + Supabase PostgreSQL`임을 명확히 했다.
- Supabase integration이 자동 동기화하는 `POSTGRES_URL` 계열 변수와 이 backend가 실제로 읽는 `DATABASE_URL`의 차이를 설명했다.
- Supabase secret, service role key, DB URL을 `VITE_` 변수나 browser bundle로 노출하지 않도록 주의점을 정리했다.

## Verification Performed

- `git status --short`로 기존 변경사항을 확인했다.
- `.env` 값은 읽거나 출력하지 않았다.
- 기존 `docs/harness/vercel-supabase-deployment-plan-2026-06-01.md`, `docs/harness/features/deployment-runtime.md`, `frontend/vercel.json`, `frontend/package.json`을 확인했다.
- 공식 문서 기준으로 Vercel Supabase Marketplace, Vercel environment variables, Supabase Postgres connection mode, Vercel/Supabase environment scope 설명을 확인했다.

## Commands Not Run

- `npm run build`: 문서 추가만 수행했으므로 실행하지 않았다.
- `pytest`: 코드 변경이 없으므로 실행하지 않았다.
- backend/frontend dev server: 런타임 변경이 아니어서 실행하지 않았다.
- `vercel` CLI: 실제 Vercel/Supabase 계정 연결과 env 조회가 필요하므로 실행하지 않았다.

## Follow-up Risks

- Vercel/Supabase billing owner와 backend hosting provider를 확정해야 실제 연결을 진행할 수 있다.
- Supabase direct connection, session pooler, transaction pooler 중 어떤 연결을 쓸지는 backend host 네트워크와 staging 검증 결과에 따라 확정해야 한다.
- Vercel env 변경은 기존 deployment에 소급 적용되지 않으므로 env 변경 후 반드시 새 deployment가 필요하다.
- Production scheduler와 AI report generation은 비용과 rate limit 검증 후 단계적으로 켜야 한다.
