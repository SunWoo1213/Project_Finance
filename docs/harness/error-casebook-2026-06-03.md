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
| 9 | 시장데이터/배포 | Render에서 Yahoo Finance 401 `Invalid Crumb` 또는 429 | 데이터센터 IP 기반 차단/제한과 동시 provider 호출 폭주 | [market-data-provider-migration-implementation](market-data-provider-migration-implementation-2026-06-03.md) |
| 10 | 시장데이터/워밍업 | 모든 HTTP가 `200 OK`인데 다수 종목이 빈 `failed:`로 실패 | provider별 `Semaphore(1)` 직렬화 + per-asset 타임아웃(15s/8s) 충돌, `str(TimeoutError())`가 빈 문자열 | [market-data-warmup-provider-throttle-timeout-implementation](market-data-warmup-provider-throttle-timeout-implementation-2026-06-04.md) |
| 11 | AI/스케줄러 | `NVDA 리포트 실패: No cached market data found` | startup report job이 비차단 market warm-up 완료 전에 실행 | [report-scheduler-market-cache-miss-fallback](report-scheduler-market-cache-miss-fallback-2026-06-04.md) |
| 12 | AI/품질게이트 | `/api/reports/NVDA` 영구 404 (생성은 매번 실패) | writer 환각 숫자 → fact_checker 반복 거부 → revision 한계 초과 미저장 | [report-404-and-secret-log-leak-remediation-implementation](report-404-and-secret-log-leak-remediation-implementation-2026-06-04.md) |
| 13 | 보안/로깅 | 런타임 로그/응답에 외부 API 키 평문 노출 | httpx INFO + 앱 로거가 예외(URL 포함)를 그대로 출력, `detail=str(e)` | [report-404-and-secret-log-leak-remediation-implementation](report-404-and-secret-log-leak-remediation-implementation-2026-06-04.md) |
| 14 | AI/품질게이트 | NVDA 404 지속 (`Unsupported numbers: 3.62%, 22` 반복) | fact_checker 부호 비대칭 오탐(`-3.62`≠`3.62`) + writer 환각(`22`)이 합쳐져 revision 소진 미저장 | [nvda-factchecker-loop-404-remediation-implementation](nvda-factchecker-loop-404-remediation-implementation-2026-06-04.md) |

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

## 9. Render 시장 데이터 yfinance/Yahoo 차단

- **증상/맥락**: Render 배포 환경에서 시장 가격/뉴스 warm-up 또는 scheduler 실행 시.
- **에러**: `HTTP Error 401: ... "Invalid Crumb"`, `"User is unable to access this feature"`, `Too Many Requests. Rate limited.`, `argument of type 'NoneType' is not a container or iterable`.
- **원인**: Yahoo Finance가 Render 데이터센터 IP에서 들어오는 yfinance 요청을 차단하거나 제한. 기존 가격 작업은 여러 자산군을 동시에 `gather`해 무료 provider rate limit에도 취약했다.
- **수정**: production code path와 `backend/requirements.txt`에서 yfinance 제거. `price_providers.py`로 Finnhub, CoinGecko Demo, 공공데이터포털, Stooq key 기반 daily CSV, open.er-api.com, Naver 뉴스 provider를 분리하고 provider별 cache/cooldown을 적용. 파일: [price_providers.py](../../backend/app/services/price_providers.py), [market_service.py](../../backend/app/services/market_service.py), [macro_service.py](../../backend/app/services/macro_service.py), [main.py](../../backend/app/main.py).
- **예방**: 데이터센터 IP에서 차단될 수 있는 비공식 scraping/provider를 production 핵심 경로로 두지 않는다. 무료 API는 key 미설정/429/빈 응답을 정상 edge case로 보고 cache, cooldown, degrade를 함께 구현한다.

## 10. 워밍업/스케줄러에서 다수 종목이 빈 `failed:`로 실패 (provider 직렬화 + 타임아웃 충돌)

- **증상/맥락**: Render 배포 워밍업/스케줄러 실행 시. httpx 로그는 모든 외부 요청이 `200 OK`인데도 `[update_prices_task] MSFT(MSFT, STOCK_US) failed:` 처럼 **콜론 뒤가 빈** 실패가 KR 주식 전체·KR 지수·AAPL 제외 US 주식 전부·일부 KR 뉴스에서 대량 발생.
- **에러**: `[update_prices_task] {label}(...) failed: ` (메시지 없음). 원인 예외는 `asyncio.TimeoutError`이며 `str(asyncio.TimeoutError())`가 빈 문자열이라 로그에 아무것도 안 남았다.
- **원인**: [price_providers.py](../../backend/app/services/price_providers.py)의 `_provider_semaphore()`가 provider마다 `asyncio.Semaphore(1)`을 두어 **provider당 동시 1건**으로 직렬화. [market_service.py](../../backend/app/services/market_service.py)의 워밍업은 전 종목을 동시에 `gather`하지만, 같은 provider(`data_go_kr`=KR 주식+지수, `stooq`=US history, `naver_news`)로 가는 요청이 1칸 큐를 직렬 통과한다. 한 provider에 종목이 몰리면 큐 드레인 시간이 per-asset 타임아웃(가격 15s/뉴스 8s)을 넘겨, 순번을 못 받은 종목이 `TimeoutError`로 떨어진다. 워밍업이 `await`로 port 바인딩 전에 동기 실행돼 startup도 지연됐다.
- **수정**: (1) 로그를 `failed: timeout after Ns` / `{exc!r}`로 구분 출력. (2) per-asset 타임아웃을 env로 상향(`MARKET_PRICE_FETCH_TIMEOUT_SECONDS=30`, `MARKET_NEWS_FETCH_TIMEOUT_SECONDS=20`, 최소 5s) 해 직렬 큐가 1회 실행 안에 드레인되게 함. (3) 워밍업을 `asyncio.create_task`로 비차단화해 port 즉시 바인딩. **provider 동시성(Semaphore)은 rate limit/차단 위험 때문에 변경하지 않음.** 파일: [config.py](../../backend/app/core/config.py), [market_service.py](../../backend/app/services/market_service.py), [main.py](../../backend/app/main.py), [test_market_warmup_timeout.py](../../backend/tests/test_market_warmup_timeout.py). 출처: [market-data-warmup-provider-throttle-timeout-implementation](market-data-warmup-provider-throttle-timeout-implementation-2026-06-04.md).
- **예방**: `asyncio.wait_for` 실패 로그는 `{exc!r}`로 남겨 빈 `TimeoutError`를 식별 가능하게 한다. provider별 직렬화가 있으면 "한 provider에 묶인 종목 수 × provider 응답시간 < per-asset 타임아웃" 관계를 점검한다. 동시성 상향은 무료/비공식 provider rate limit/IP 차단을 자극할 수 있어 공식 API 한정으로만 단계적으로 올린다.

## 11. startup 리포트 job의 시장 캐시 miss

- **증상/맥락**: Render backend 시작 직후 AI report startup job 실행 시.
- **에러**: `NVDA 리포트 실패: No cached market data found for ticker: NVDA`.
- **원인**: market warm-up은 서버 health check를 빠르게 통과시키기 위해 백그라운드 `asyncio.create_task`로 실행된다. AI report startup job은 scheduler에 즉시 실행(`run_date=datetime.now()`)으로 등록되어, `market_cache["prices"]`가 아직 `NVDA`를 포함하기 전에 먼저 실행될 수 있다.
- **수정**: `market_service.ensure_price_cache_for_ticker()`로 scheduled report 대상 ticker 하나만 캐시 보강하고, `generate_report_for_ticker()`가 가격 캐시 miss 시 이 보강을 한 번 시도한 뒤 다시 조회한다. 파일: [market_service.py](../../backend/app/services/market_service.py), [ai_service.py](../../backend/app/services/ai_service.py).
- **예방**: startup report job은 broad market warm-up 완료를 가정하지 않는다. 캐시 miss는 ticker-level fill로 흡수하되, provider key 미설정/외부 장애는 readiness-blocked report로 처리하고 데이터를 지어내지 않는다. 관련 기록: [report-scheduler-market-cache-miss-fallback](report-scheduler-market-cache-miss-fallback-2026-06-04.md).

## 12. fact_checker 환각 숫자 거부 루프로 인한 리포트 영구 404

- **증상/맥락**: `/api/reports/NVDA`가 계속 404. Render 로그상 NVDA 실데이터(Finnhub)는 정상 수신되므로 데이터 부족(blocked)이 아니라 생성 자체가 매번 실패.
- **에러(로그)**: `Fact checker failed: ... Unsupported numbers: 3.62%, 21` 반복 → `revision_count >= 3` → `ReportQualityError` → DB 미저장 → 조회 API 404.
- **원인**: `writer_node` 프롬프트에 "넘겨받지 않은 숫자를 만들지 말라"는 부정형 한 줄만 있고 허용 숫자 목록은 없었다. `fact_checker_node`는 `_collect_supported_numbers()`(fact 소스 숫자 + 0~10 + 연도) 외 숫자를 전부 거부. 데이터가 적은 자산일수록 writer가 학습지식 숫자로 빈틈을 메워 거부 루프에 빠졌다.
- **수정**: fact_checker 판정·허용 집합은 그대로 두고(엄격성 불변), `_describe_supported_numbers(state)` 헬퍼로 같은 fact 소스의 **원문 숫자 토큰**을 모아 `writer_node` 프롬프트에 `allowed_numbers` 화이트리스트로 주입. "이 목록과 0~10·연도 외 숫자는 금지, 필요하면 정성 서술/데이터 한계로" 규율 강화. 파일: [nodes.py](../../backend/app/services/graph/nodes.py), [test_ai_report_quality_gate.py](../../backend/tests/test_ai_report_quality_gate.py). 출처: [report-404-and-secret-log-leak-remediation-implementation](report-404-and-secret-log-leak-remediation-implementation-2026-06-04.md).
- **예방**: 품질 게이트를 "거부 사유만" 피드백하지 말고 **허용 입력을 명시적으로 제공**해 첫 초안 통과율을 올린다. 게이트(검증자)와 생성자(writer)가 같은 fact 소스에서 파생된 허용 집합을 공유해 둘이 어긋나지 않게 한다. 게이트를 약화시키지 말고 입력을 친절하게 한다.

## 13. 런타임 로그/응답에 외부 API 키 평문 노출 + 과도한 SQL echo

- **증상/맥락**: Render 배포 런타임 로그. 외부 데이터 호출 실패 시.
- **에러(로그)**: `app.services.price_providers` **WARNING** 라인에 `... for url 'https://apis.data.go.kr/...?serviceKey=<평문키>&...'`가 그대로 출력(2026-06-03 로그로 직접 확인). 추가로 `httpx`/`sqlalchemy.engine.Engine`가 INFO로 외부 URL·SQL echo를 과도하게 출력.
- **원인(두 갈래)**:
  1. **로거 레벨**: root가 INFO라 `httpx` 로거가 모든 외부 요청 URL(쿼리스트링 키 포함)을 INFO로 찍고, `SQLALCHEMY_ECHO=true`로 SQL echo가 켜져 있었다.
  2. **애플리케이션 레벨 예외 로깅(실제 확인된 누수)**: provider/macro 서비스가 `logger.warning(..., %r, exc)` / `logger.error(..., exc)`로 `HTTPStatusError`를 그대로 출력하는데, 이 예외 문자열에 요청 URL 전체(키 포함)가 들어 있다. `main.py`의 `/api/market/history` 500 핸들러는 `detail=str(e)`로 FRED 예외(api_key 쿼리)를 **HTTP 응답 본문**으로까지 노출할 수 있었다. 이 경로는 1차 로거 레벨 조정으로는 막히지 않는다.
- **수정**: (1) `main.py`에서 `httpx`/`httpcore`/`sqlalchemy.engine` 로거 레벨을 `WARNING`으로 낮춤. (2) `app/core/log_sanitizer.py`의 `redact_secrets()`로 민감 쿼리 파라미터 값과 리터럴 키(ECOS는 URL 경로에 키가 들어감)를 `***`로 마스킹하고, price_providers 4곳·macro_service 3곳의 예외 로그와 `main.py` 500 핸들러 `detail`에 적용. `SQLALCHEMY_ECHO=false` 확인은 운영. 파일: [main.py](../../backend/app/main.py), [log_sanitizer.py](../../backend/app/core/log_sanitizer.py), [price_providers.py](../../backend/app/services/price_providers.py), [macro_service.py](../../backend/app/services/macro_service.py), [test_log_sanitizer.py](../../backend/tests/test_log_sanitizer.py). 출처: [report-404-and-secret-log-leak-remediation-implementation](report-404-and-secret-log-leak-remediation-implementation-2026-06-04.md).
- **예방**: 외부 호출 예외를 로그/응답에 그대로 출력하지 않는다 — URL에 키가 박힌다. **로거 레벨 낮추기만으로는 부족**하고, 애플리케이션이 직접 찍는 예외/응답 detail은 `redact_secrets()`로 마스킹해야 한다. 키가 쿼리가 아닌 **경로**에 들어가는 provider(ECOS)는 리터럴 마스킹 필요. 노출된 키는 AGENTS.md 8절에 따라 손상으로 간주·로테이션. data.go.kr `serviceKey`는 로그로 노출 확인됐으므로 재발급 대상.

## 14. fact_checker 부호 비대칭 오탐 + writer 환각으로 NVDA 404 지속 (사례 12 후속)

- **증상/맥락**: 사례 12(allowed_numbers 화이트리스트 1차 도입) 이후에도 `/api/reports/NVDA`가 계속 404. 로그상 데이터는 정상 수신.
- **에러(로그)**: `fact_checker_node fail (ticker=NVDA, unsupported=22)` → `unsupported=3.62%, 22` → `unsupported=-3.62%, 22`로 **부호만 진동**하며 반복 → `revision_count>=3` → `ReportQualityError` → 미저장. 단, 그 뒤 `AI 리포트 생성 종료` 로그가 정상 출력되어 **무료 배포 프로세스 강제 종료가 아님이 확정**(가설 반증).
- **원인(두 갈래)**:
  1. **fact_checker 정규화 부호 비대칭**: `_normalize_numeric_token`이 `,`/`%`/`+`만 제거하고 선행 `-`는 보존해, 데이터의 `change_pct=-3.62`(→`-3.62`)와 writer의 "3.62% 하락"(→`3.62`)이 다른 토큰으로 취급돼 **데이터에 실재하는 등락률이 미지원으로 오탐**.
  2. **writer 환각**: 어떤 fact 소스에도 없는 `22`를 매 재작성마다 반복 생성(누적 feedback에 명시해도 재발). allowed_numbers cap(40)도 데이터 풍부 자산에서 필요한 토큰을 누락시킬 위험.
- **수정**: (1) `_normalize_numeric_token`에 `abs()`를 적용해 **부호 비민감(절댓값) 매칭**으로 정합화(방향 검증은 evaluator/qualitative 책임). (2) `ALLOWED_NUMBERS_LIMIT=150`으로 화이트리스트 cap 상향 + `_fact_number_payload`로 소스 공유. (3) 루프 소진 시(`format_check_pass=True && fact_check_pass=False`) `sanitize_unsupported_numbers`로 미지원 숫자만 `(수치 미확인)`으로 결정적 치환 후 **포맷·프레임워크·숫자·정성 게이트 전부 재검증, 통과분만 저장**(LLM 재호출 없음, 미통과 시 미저장 유지). 파일: [nodes.py](../../backend/app/services/graph/nodes.py), [ai_service.py](../../backend/app/services/ai_service.py), [test_ai_report_quality_gate.py](../../backend/tests/test_ai_report_quality_gate.py). 원인 분석: [nvda-report-factchecker-loop-root-cause](nvda-report-factchecker-loop-root-cause-2026-06-04.md). 출처: [nvda-factchecker-loop-404-remediation-implementation](nvda-factchecker-loop-404-remediation-implementation-2026-06-04.md).
- **예방**: 숫자 검증의 "동일성" 정의를 명확히 — 크기 검증과 방향 검증을 한 정규화에 섞지 않는다(부호는 절댓값 게이트의 책임이 아님). 로그 종료 패턴(정상 트레이스백 + 종료 로그)으로 "코드가 던진 예외"와 "외부 프로세스 킬"을 구분한다. 결정적 폴백은 "실패본 저장"이 아니라 **재검증 통과분만 저장**으로 게이트 정신을 보존한다.

## 15. 리포트 스케줄러 잡이 인스턴스 수명보다 늦게 발화해 NVDA 404 지속 (사례 14와 다른 실패 모드)

- **증상/맥락**: Render 배포에서 `GET /api/reports/NVDA` 404가 "항상" 발생. 2026-06-08 01:03~01:05 UTC 로그 분석.
- **에러(로그)**: 로그 전체에 `"AI 리포트 생성 시작"`이 **단 한 번도 없음**. 1분 간격 `Notification delivery`만 발화(01:04:18, 01:05:18). 01:04:23에 `Shutting down` → `Scheduler has been shut down` → `Finished server process [64]` 후 재기동. 추가로 `FMP history unavailable (... 402 Payment Required)` 다수.
- **원인(두 갈래)**:
  1. **스케줄러 리포트 잡 미발화(1순위)**: `generate_daily_reports` 주기 잡은 `interval` 6시간이라 **최초 발화가 기동 +6시간 후**다(`next_run_time` 미지정). 실질 경로인 startup 잡은 `run_date=now()+180초`인데, Render sleep/재시작형 인스턴스가 **180초를 연속 가동하지 못하고** 종료·재기동하며 타이머가 0부터 다시 시작 → 리포트 잡이 영영 발화하지 못하고 `ai_reports`가 비어 404. 1분 알림 잡만 종료 전에 발화하므로 로그에 보임.
  2. **FMP 402(2순위, 직접 차단 아님)**: `historical-price-eod/full`이 플랜 미포함이라 history 결측. 단 NVDA(STOCK_US)는 가격이 있으면 readiness가 `blocked`가 아닌 `limited`(blocking은 가격뿐, `_grade_report_readiness`)라 생성은 진행. XAU/BTC-USD(COMMODITY/CRYPTO)는 필수 3개 이상 결측 시 `blocked` 유발 가능.
- **수정**: (분석 단계, 코드 미변경) 방향 — startup delay 단축 또는 `interval` 잡에 `next_run_time=now()` 부여, 상시 가동 런타임 전환(Option A), 또는 리포트 생성을 token-protected task endpoint + 외부 cron으로 분리(Option B). 모두 cadence/비용/런타임 변경이라 사용자 승인 필요. 분석: [report-generation-scheduler-not-firing-log-audit](report-generation-scheduler-not-firing-log-audit-2026-06-08.md). 선행 계획: [report-generation-deployment-failure-remediation-plan](report-generation-deployment-failure-remediation-plan-2026-06-07.md).
- **수정(2026-06-08)**: `generate_daily_reports`(interval) 잡에 `next_run_time=now()+STARTUP_DELAY`를 부여해 기동 직후 1회 발화하도록 하고 중복 startup date 잡을 제거, `REPORT_SCHEDULER_STARTUP_DELAY_SECONDS` 기본값 180→60초로 단축. 파일: [main.py](../../backend/app/main.py), [config.py](../../backend/app/core/config.py), [test_ai_report_generation_switch.py](../../backend/tests/test_ai_report_generation_switch.py). 출처: [report-scheduler-startup-firing-fix-implementation](report-scheduler-startup-firing-fix-implementation-2026-06-08.md). 단 인스턴스가 60초 전에 죽으면 여전히 발화 못 함 → 근본 안정화는 상시 가동 런타임 또는 외부 cron 필요.
- **예방**: in-process scheduler는 **상시 가동 프로세스를 전제**한다 — sleep/재시작형(Render Free 등) 런타임에서는 startup 지연 잡과 장주기 `interval` 잡이 발화 전 죽는다. "잡이 돌았는데 실패"(사례 14: `AI 리포트 생성 시작/종료` 존재)와 "잡이 애초에 발화 못함"(이번: 시작 로그 부재 + `Finished server process`)을 **로그 한 줄로 구분**한다. APScheduler `interval`의 최초 발화는 +1주기 후이므로, 기동 직후 발화가 필요하면 `next_run_time`을 명시.

## 16. 상위 provider 전면 장애(Finnhub 502 + FMP 402) → 가격 0 캐시 → readiness blocked로 리포트 미생성 (사례 15와 다른 차단 지점)

- **증상/맥락**: 2026-06-08 01:23 UTC 재배포 로그. 이번엔 스케줄러가 정상 기동(`Scheduler started`, `service is live`, `reports: every 12 hours`)했는데도 워밍업에서 시장 데이터가 전면 실패. `GET /api/reports/{ticker}` 404 지속.
- **에러(로그)**: `Market snapshot provider failed (ticker=AAPL/NVDA/MSFT/.../TSLA, category=STOCK_US): 502 Bad Gateway (finnhub.io/quote)` — US 주식 전 종목. `FMP quote/history unavailable (^NDX): 402 Payment Required`.
- **원인**: STOCK_US 경로(`_fetch_finnhub_stock_snapshot`)는 **현재가(quote) 호출에 폴백이 없다**. `_get_json("finnhub", ".../quote")`이 502로 던지면 함수 내 try/except(market_cap·history 폴백)를 거치지 못하고 dispatcher의 `except`까지 전파되어 `DEFAULT_RESPONSE`(가격 0)를 캐시한다(`price_providers.py:609-613, 1051-1071`). 가격 0 → `_grade_report_readiness`가 `price_value in (None,"",0)`로 `blocked`(`ai_service.py:451-452`) → `ReportReadinessError` → 미저장 → 404. FMP는 402로 폴백 불가, Stooq는 opt-in이고 history만 보강(live quote 대체 못 함).
- **수정**: (분석 단계, 코드 미변경) 방향 — (1) STOCK_US 현재가 폴백 추가(Finnhub→FMP→Stooq 종가), (2) 전 provider 실패 시 `DEFAULT_RESPONSE`(가격 0)를 캐시에 덮지 말고 직전 유효값 유지(stale 허용), (3) 일시적 502에 짧은 재시도/백오프, (4) FMP 402 플랜 점검. 분석: [report-generation-scheduler-not-firing-log-audit](report-generation-scheduler-not-firing-log-audit-2026-06-08.md)(추가 분석 섹션).
- **예방**: 리포트 미생성은 스케줄러뿐 아니라 **데이터 파이프라인 끝단(가격 0)** 에서도 발생한다 — 두 차단 지점은 독립적이며 둘 다 해소해야 한다. "스냅샷 실패 → 가격 0 캐시 → readiness blocked"가 굳지 않도록, 핵심 자산의 현재가는 단일 provider 장애에 폴백/stale-유지로 견디게 한다. 워밍업 직후 1회 provider 장애가 6~12시간 readiness 차단으로 고착될 수 있음을 인지.

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
10. **provider 직렬화 vs 타임아웃**: provider별 `Semaphore(1)` 직렬화가 있으면 "한 provider 종목 수 × 응답시간 < per-asset 타임아웃"인지 점검. `asyncio.wait_for` 실패 로그는 `{exc!r}`로 남겨 빈 `TimeoutError`를 식별 가능하게. (사례 10)
11. **startup job은 warm-up 완료를 가정하지 않기**: 비차단 warm-up과 즉시 실행 scheduler job이 함께 있으면 캐시 miss race가 생긴다. (사례 11)
12. **품질 게이트는 거부만 하지 말고 허용 입력 제공**: 검증자(fact_checker)와 생성자(writer)가 같은 fact 소스 허용 집합을 공유해 첫 초안 통과율을 올린다. 게이트를 약화시키지 않는다. (사례 12)
13. **로그에 외부 URL/키 남기지 않기**: `httpx`/`sqlalchemy.engine` 로거를 WARNING으로. 노출 키는 손상 간주·로테이션. (사례 13)
14. **숫자 게이트의 동일성 정의 분리**: 크기(절댓값) 검증과 방향(부호) 검증을 한 정규화에 섞지 말 것. 부호 비대칭은 데이터에 실재하는 값도 오탐시킨다. 결정적 폴백은 재검증 통과분만 저장해 게이트를 약화시키지 않는다. 로그 종료 패턴으로 "코드 예외"와 "프로세스 킬"을 구분. (사례 14)
15. **in-process scheduler는 상시 가동 전제**: sleep/재시작형 런타임에서는 startup 지연 잡과 장주기 `interval` 잡이 발화 전 죽는다. `interval`의 최초 발화는 +1주기 후. "잡 실행 후 실패"와 "잡 미발화"를 시작 로그 유무로 구분. (사례 15)
16. **핵심 자산 현재가는 단일 provider 장애에 견디게**: STOCK_US 현재가 폴백 부재 시 Finnhub 502 하나로 가격 0이 캐시되고 readiness blocked로 굳는다. 폴백/stale-유지로 보완. 리포트 미생성은 스케줄러와 데이터 끝단 두 곳에서 독립적으로 발생. (사례 16)
17. **새 오류는 이 문서에 추가**: 해결 즉시 "증상→원인→수정→예방" 항목으로 누적.

## References Checked

- 변경 기록: `report-scheduler-structured-output-error-fix-2026-06-02.md`, `supabase-asyncpg-url-normalization-2026-06-03.md`, `cors-loopback-blocked-2026-06-03.md`, `google-login-duplicate-initialize-guard-2026-06-03.md`, `render-database-url-quote-normalization-2026-06-03.md`, `docker-database-compatibility-implementation-2026-06-02.md`, `project-defect-audit-report-2026-06-02.md`
- 런타임 로그: `.codex-runtime/backend_market_debug.err.log`(commit 5a04dc1)
- 코드: `backend/app/core/config.py`, `backend/app/main.py`, `backend/app/db/session.py`, `backend/app/services/graph/nodes.py`, `frontend/src/pages/Login.jsx`, `frontend/src/utils/apiClient.js`
