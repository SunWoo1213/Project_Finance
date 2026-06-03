# 오류 사례집 (Harness Error Casebook)

Date: 2026-06-03

## 목적

`Project_Finance`에서 지금까지 실제로 발생한 오류·장애·버그를 한 곳에 모아, 추후 하네스 엔지니어링이 같은 문제를 **빠르게 식별·재현·해결**하도록 돕는 참조 문서다. 각 사례는 흩어진 변경 기록에서 추출했으며, 원본 문서 링크를 함께 둔다. 새 오류를 해결할 때마다 이 사례집에 항목을 추가한다.

규칙:
- 시크릿(비밀번호, API 키, 토큰, DB URL 값)은 절대 기록하지 않는다. 에러 메시지·스킴·호스트 종류 등 비민감 정보만 남긴다.
- 에러 문자열·파일 경로·명령·API 경로는 원문 유지, 설명은 한국어.
- "증상 → 원인 → 수정 → 예방" 순서로 빠르게 스캔 가능하게 둔다.

## 요약 표

| # | 분류 | 증상(한 줄) | 핵심 원인 | 출처 |
|---|---|---|---|---|
| 1 | AI/스케줄러 | 스케줄 리포트 생성 중 schema 오류 + MissingGreenlet | strict JSON schema 충돌, rollback 후 ORM 재접근 | [report-scheduler-structured-output-error-fix](report-scheduler-structured-output-error-fix-2026-06-02.md) |
| 2 | DB/연결 | `alembic upgrade head` 시 asyncpg 연결 실패 | `?sslmode=` 가 asyncpg에 그대로 전달 | [supabase-asyncpg-url-normalization](supabase-asyncpg-url-normalization-2026-06-03.md) |
| 3 | 배포/CORS | 배포 프론트가 `localhost:8000` 호출 → CORS/PNA 차단 | `VITE_API_BASE_URL` 미설정 fallback + loopback 차단 | [cors-loopback-blocked](cors-loopback-blocked-2026-06-03.md) |
| 4 | 프론트/인증 | `[GSI_LOGGER] initialize() is called multiple times` | React StrictMode 이중 effect | [google-login-duplicate-initialize-guard](google-login-duplicate-initialize-guard-2026-06-03.md) |
| 5 | 배포/설정 | Render 기동 시 `DATABASE_URL must use an async ... scheme` | 값에 따옴표/공백/잘못된 URL | [render-database-url-quote-normalization](render-database-url-quote-normalization-2026-06-03.md) |
| 6 | DB/Docker | Docker DB 값 불일치 + bootstrap 실패가 조용히 통과 | compose 하드코딩 vs `.env` 불일치, 기존 volume 잔존 | [docker-database-compatibility-implementation](docker-database-compatibility-implementation-2026-06-02.md) |
| 7 | 정책/테스트 | 리포트 생성 권한 helper 테스트 401 vs 403 불일치 | endpoint 계약과 helper 단위 계약 혼재 | [project-defect-audit-report](project-defect-audit-report-2026-06-02.md) (D1) |
| 8 | DB/로컬 | `/health`는 정상인데 DB 미연결 (startup warning) | 로컬 PostgreSQL 미기동 + bootstrap 실패 무시 설정 | 런타임 로그(아래 8번) |

---

## 1. 스케줄 리포트 구조화 출력 오류 + MissingGreenlet

- **증상/맥락**: backend 스케줄러 리포트 생성 단계, asyncio event loop에서 DB 접근 시.
- **에러**: OpenAI structured output strict JSON schema 검증 오류(`additionalProperties` 제약), SQLAlchemy `MissingGreenlet`(rollback 이후 ORM 객체 속성 재접근).
- **원인**: `StructuredFacts`가 `dict[str, Any]`·`list` 같은 유연 필드를 포함해 strict schema와 충돌. 스케줄 loop에서 `rollback()` 후 ORM `Asset` 객체를 계속 참조.
- **수정**: LangChain structured output 호출을 `method="function_calling"`으로 고정. loop 시작 전 `asset_id`·`ticker`를 plain 값으로 복사해 사용. 파일: [nodes.py](../../backend/app/services/graph/nodes.py), [ai_service.py](../../backend/app/services/ai_service.py).
- **예방**: schema 유연성이 필요하면 `function_calling` 강제. async event loop에서 **rollback 이후 ORM 객체 재접근 금지**(필요 값은 미리 스칼라로 추출).

## 2. Supabase asyncpg `sslmode` 파라미터 호환성

- **증상/맥락**: `python -m alembic upgrade head` 실행(마이그레이션) 시.
- **에러**: `TypeError: connect() got an unexpected keyword argument 'sslmode'`, `ValueError: invalid literal for int() with base 10: ''`(포트 파싱).
- **원인**: Supabase URL의 `?sslmode=require` query가 SQLAlchemy asyncpg dialect를 거쳐 `asyncpg.connect()`에 그대로 전달됨. asyncpg는 libpq식 `sslmode`를 모름.
- **수정**: `sslmode`(`require/prefer/allow/verify-ca/verify-full`)를 `ssl=<same>`로 정규화. connect_args를 `settings.database_connect_args()`로 통합. Alembic env를 runtime과 동일 옵션으로 통일. 파일: [config.py](../../backend/app/core/config.py), [session.py](../../backend/app/db/session.py), [alembic/env.py](../../backend/alembic/env.py).
- **예방**: pooler/포트 조합은 staging에서 실제 연결로 검증. 마이그레이션 전 대상 환경 재확인. 관련: 5번(같은 `config.py` 정규화 경로).

## 3. 배포 프론트의 loopback 호출 차단 (CORS / Private Network Access)

- **증상/맥락**: Vercel 배포 프론트엔드에서 backend API 호출 시.
- **에러**: `... has been blocked by CORS policy: Permission was denied for this request to access the loopback address space`, `net::ERR_FAILED`, `AxiosError: Network Error`.
- **원인**: Vercel 빌드에서 `VITE_API_BASE_URL`이 비어 fallback `http://localhost:8000`이 프로덕션 번들에 박힘 + Chromium PNA(공개 origin→loopback 차단)가 동시 작용.
- **수정**(코드 변경 없음, 환경 설정): Vercel에 `VITE_API_BASE_URL=https://<backend-host>` 설정 후 **재배포**(캐시 재사용 안 됨). backend의 `BACKEND_CORS_ORIGINS`에 프론트 origin 등록 확인. `frontend/src/utils/apiClient.js`의 localhost fallback은 로컬 개발용이라 유지.
- **예방**: 배포 환경변수에 실제 backend HTTPS origin 명시. `VITE_` 값은 빌드 타임 주입이므로 변경 시 재빌드 필수.

## 4. Google 로그인 `initialize()` 중복 호출 경고

- **증상/맥락**: 개발(StrictMode)/로컬 dev 서버에서 Login 렌더링 시.
- **에러**: `[GSI_LOGGER]: google.accounts.id.initialize() is called multiple times...`
- **원인**: React 18 StrictMode가 dev에서 effect를 2회 실행 → `window.google.accounts.id.initialize()` 중복.
- **수정**: `isInitializedRef` ref 가드로 `initialize()`는 1회만, `renderButton()`은 가드 밖에서 매 마운트 수행. 파일: [Login.jsx](../../frontend/src/pages/Login.jsx).
- **예방**: 외부 SDK 초기화는 ref 기반 single-instance guard. 단, UI 렌더링 호출은 가드에서 제외.

## 5. Render `DATABASE_URL` 따옴표/공백 정규화 실패

- **증상/맥락**: Render 백엔드 배포 기동 시 `app.main` import 중 `Settings()` 생성. 빌드는 성공, 런타임 검증에서만 실패.
- **에러**: `pydantic_core._pydantic_core.ValidationError: ... DATABASE_URL must use an async SQLAlchemy driver scheme. Allowed schemes after normalization: postgresql+asyncpg, sqlite+aiosqlite.`
- **원인**: 대시보드에 따옴표로 감싼 값(`"postgresql://..."`) 입력 → 따옴표 리터럴 저장; 앞뒤 공백/개행; 플레이스홀더 또는 `https://` API URL을 DB 연결 문자열 대신 입력.
- **수정**: `normalize_database_url`이 `strip()` + 감싼 따옴표 제거 후 스킴 변환. `resolve_database_url`이 실패 시 감지 스킴을 에러에 노출. 테스트 2건 추가. 파일: [config.py](../../backend/app/core/config.py), [test_database_config.py](../../backend/tests/test_database_config.py).
- **예방**: Render `DATABASE_URL`이 `postgresql://`/`postgres://`로 시작하는 **DB 연결 문자열**인지 확인(Supabase `https://` API URL 아님). 비밀번호 특수문자는 URL 인코딩 또는 영숫자 재설정.

## 6. Docker DB 설정 불일치 + bootstrap 실패 무시

- **증상/맥락**: 로컬 Docker PostgreSQL 초기화 및 backend 설정 로드.
- **에러**: 명시적 예외보다 "조용한 통과"가 문제 — bootstrap 실패 시 warning만 남기고 계속 실행, `/health`는 정상처럼 보임.
- **원인**: `docker-compose.yml`의 하드코딩 DB 자격과 `.env` 값 불일치 가능. 기존 `postgres_data` volume이 남으면 새 `POSTGRES_*`로 재초기화 안 됨.
- **수정**: compose가 `.env`의 `POSTGRES_USER/PASSWORD/DB/PORT` 사용. `config.py`에 DATABASE_URL scheme 검증 추가. `/health`에 `database: "not_checked"`, DB 상태는 `/db-check`로 분리. credential 비노출 진단(`database_url_diagnostics()`). 파일: `docker-compose.yml`, `.env_example`, [config.py](../../backend/app/core/config.py), [main.py](../../backend/app/main.py).
- **예방**: `/health`=app liveness, `/db-check`=DB readiness로 분리 이해. 기존 volume 삭제는 데이터 손실 → 사용자 확인 필수. `POSTGRES_*` 변경 시 재초기화 필요 여부 점검.

## 7. 리포트 생성 권한 helper 401 vs 403 계약 불일치

- **증상/맥락**: backend 테스트 실행 시 권한 helper 단위 테스트 실패.
- **에러**: `backend/tests/test_ai_report_quality_gate.py::test_report_generation_policy_rejects_missing_user` — 기대 `401`, 실제 `403`.
- **원인**: [main.py:440](../../backend/app/main.py#L440)의 `ensure_report_generation_allowed(user)`가 `user`를 무시하고 항상 `403`. endpoint는 `Depends(get_current_user)`로 미인증 시 `401`이 될 수 있어 계약이 혼재.
- **수정**(현재 문서 지적 단계): endpoint 수준 vs helper 단위 계약 분리, helper의 `None` 입력 시 `401`/`403` 정책 확정 필요. 파일: [main.py:440](../../backend/app/main.py#L440), `backend/tests/test_ai_report_quality_gate.py:231`.
- **예방**: 권한 검사는 "엔드포인트 인증(401)"과 "엔타이틀먼트/정책(403)"을 분리. "사용자-facing 요청은 fresh report generation을 트리거하지 않는다"는 규칙 유지(AGENTS.md 14절).

## 8. 로컬 DB 미연결인데 `/health`는 정상 (startup warning)

- **증상/맥락**: 로컬 backend 기동 시(예: PostgreSQL 컨테이너 미기동). `.codex-runtime/backend_market_debug.err.log`에 기록됨.
- **에러(로그)**: `WARNING | app.main | Database bootstrap failed and startup continued because ENABLE_DB_SCHEMA_BOOTSTRAP=true. /health only checks app liveness; use /db-check for database readiness.` 이후 `Application startup complete.`로 정상 기동.
- **원인**: 로컬 DB 미기동/연결 불가 상태에서 `ENABLE_DB_SCHEMA_BOOTSTRAP=true`라 bootstrap 실패를 warning으로 흡수하고 계속 진행. 이후 마켓 API가 DB 의존 시 런타임 오류로 이어짐.
- **수정/대응**: 코드 변경 아님. 작업 전 `docker compose up -d db`로 DB 기동, `/db-check`로 연결 확인(503 + sanitized 진단이면 미연결). 6번 항목의 분리 정책과 한 쌍.
- **예방**: DB 의존 작업 전 `/health`가 아닌 **`/db-check`로 readiness 확인**. 프로덕션은 `ENABLE_DB_SCHEMA_BOOTSTRAP=false`로 두어 실패 시 빠르게 드러나게 함.

---

## 교차 교훈 / 예방 체크리스트 (배포·DB 작업 전)

1. **환경변수 형식**: `DATABASE_URL`/`VITE_API_BASE_URL` 등은 따옴표·공백 없이, 올바른 스킴/origin인지 확인. (사례 3·5)
2. **DB URL은 연결 문자열, API URL 아님**: Supabase `https://<ref>.supabase.co`는 DB 연결에 쓰지 않는다. (사례 5)
3. **asyncpg는 `sslmode`를 모른다**: PostgreSQL URL은 `postgresql+asyncpg://`로 정규화되고 `sslmode→ssl` 변환이 적용됨을 전제. (사례 2)
4. **liveness ≠ readiness**: `/health`만 보고 정상이라 판단하지 말고 DB는 `/db-check`로 확인. (사례 6·8)
5. **빌드 타임 주입 값**: `VITE_*`는 재빌드/재배포해야 반영. 캐시 재사용 주의. (사례 3)
6. **async + ORM**: rollback 이후 ORM 객체 재접근 금지, 필요한 값은 미리 스칼라로 추출. (사례 1)
7. **외부 SDK 초기화**: StrictMode 이중 실행 대비 ref 가드. (사례 4)
8. **권한 계약 분리**: 인증(401)과 엔타이틀먼트/정책(403)을 섞지 않기. (사례 7)
9. **파괴적 작업 확인**: `postgres_data` volume 삭제 등 데이터 손실 작업은 사용자 확인 필수(AGENTS.md 9절). (사례 6)
10. **새 오류는 이 문서에 추가**: 해결 즉시 "증상→원인→수정→예방" 항목으로 누적.

## References Checked

- 변경 기록: `report-scheduler-structured-output-error-fix-2026-06-02.md`, `supabase-asyncpg-url-normalization-2026-06-03.md`, `cors-loopback-blocked-2026-06-03.md`, `google-login-duplicate-initialize-guard-2026-06-03.md`, `render-database-url-quote-normalization-2026-06-03.md`, `docker-database-compatibility-implementation-2026-06-02.md`, `project-defect-audit-report-2026-06-02.md`
- 런타임 로그: `.codex-runtime/backend_market_debug.err.log`(commit 5a04dc1)
- 코드: `backend/app/core/config.py`, `backend/app/main.py`, `backend/app/db/session.py`, `backend/app/services/graph/nodes.py`, `frontend/src/pages/Login.jsx`, `frontend/src/utils/apiClient.js`
