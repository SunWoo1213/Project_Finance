# 백엔드 AI 리포트 생성 복구 계획

Date: 2026-06-08
Status: Plan only - 구현 전 승인 필요 항목 포함
Related analysis:
- `docs/harness/report-backend-generation-failure-analysis-2026-06-08.md`

Related features:
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/deployment-runtime.md`

## Objective

사용자-facing 요청이 새 리포트를 생성하지 않는 현재 정책은 유지하면서, 백엔드 scheduler가 최소 target ticker에 대해 `AIReport`를 안정적으로 생성하고 저장하도록 복구한다. 성공 기준은 배포 로그에서 target별 생성 완료가 확인되고, Plus/Pro 권한 사용자의 `GET /api/reports/{ticker}`가 저장된 리포트를 200으로 반환하는 것이다.

## 원칙

- 일반 사용자, 상세 페이지, 챗봇 요청은 리포트를 생성하지 않는다.
- 생성은 backend scheduled/background 경로에 한정한다.
- target과 cadence 확대는 LLM 비용과 provider rate limit을 증가시키므로 별도 확인 후 진행한다.
- `.env`, provider key, DB URL, JWT secret 등 시크릿 값은 문서/로그/응답에 남기지 않는다.
- provider가 비어 있거나 불안정할 때 숫자나 리포트를 조작해 저장하지 않는다. readiness 또는 품질 실패는 실패로 남긴다.

## Phase 0 - 증거 수집

목표: 같은 404가 어떤 단계의 실패인지 분리한다.

1. 배포 로그에서 다음 문자열을 확인한다.
   - `scheduler started`
   - `reports: in`
   - `AI 리포트 생성 시작`
   - `{ticker} 리포트 생성 시작`
   - `{ticker} 리포트 생성 완료`
   - `failure_type=readiness_blocked`
   - `failure_type=quality_failed`
   - `failure_type=provider_unavailable`
2. 운영 DB에서 `assets`, `ai_reports` 행 수와 target ticker별 최신 report 존재 여부를 확인한다.
3. `/db-check`로 backend가 의도한 DB에 연결되는지 확인한다. 응답의 sanitized source/scheme/host만 확인하고 credentials는 출력하지 않는다.
4. 환경 스위치 이름만 확인한다.
   - `ENABLE_SCHEDULER`
   - `ENABLE_AI_REPORT_GENERATION`
   - `REPORT_SCHEDULER_TARGET_TICKERS`
   - `REPORT_SCHEDULER_STARTUP_DELAY_SECONDS`
   - `REPORT_SCHEDULER_MAX_REPORTS_PER_RUN`
   - `REPORT_SCHEDULER_ASSET_COOLDOWN_HOURS`
5. provider key의 존재 여부만 확인한다. 값은 절대 출력하지 않는다.
   - `OPENAI_API_KEY`
   - `FRED_API_KEY`
   - `FINNHUB_API_KEY`
   - `COINGECKO_DEMO_API_KEY`
   - `DATA_GO_KR_API_KEY`
   - `FMP_API_KEY`
   - `STOOQ_API_KEY`
   - `ENABLE_STOOQ_FALLBACK`

완료 기준:
- 실패 단계가 "job 미발화", "provider/readiness", "LLM/quality", "DB 저장/조회" 중 하나로 분류된다.

## Phase 1 - 최소 생성 경로 복구

목표: 가장 안정적인 1개 target부터 실제 저장을 확인한다.

1. hosted runtime에서 다음 조합을 의도적으로 설정한다.
   - `ENABLE_SCHEDULER=true`
   - `ENABLE_AI_REPORT_GENERATION=true`
   - `REPORT_SCHEDULER_MAX_REPORTS_PER_RUN=1`
   - `REPORT_SCHEDULER_TARGET_TICKERS=<검증용 단일 ticker>`
2. 검증용 ticker는 provider 준비 상태에 맞춰 선택한다.
   - FRED가 안정적이면 `DGS10`.
   - Finnhub/OpenAI가 준비되어 있으면 `NVDA`.
   - CoinGecko demo key가 준비되어 있으면 `BTC-USD`.
   - data.go.kr key가 준비되어 있으면 `005930.KS`.
   - `XAU`는 FMP 402/Stooq opt-in의 영향을 크게 받으므로 첫 복구 target으로는 후순위.
3. Alembic migration 적용 여부를 확인한다.
   - hosted DB는 `ENABLE_DB_SCHEMA_BOOTSTRAP=false`와 migration-managed 운영을 목표로 한다.
   - `ai_reports` metadata columns는 `20260601_0001`에 포함되어 있어야 한다.
4. 첫 실행 지연은 기본 60초를 유지한다. 더 짧게 줄이거나 cadence를 넓히는 변경은 비용/운영 영향이 있으므로 별도 확인 후 진행한다.

완료 기준:
- 로그에 `{ticker} 리포트 생성 완료`가 남는다.
- DB에 해당 ticker의 `AIReport`가 저장된다.
- `GET /api/reports/{ticker}`가 Plus/Pro 권한에서 200을 반환한다.

## Phase 2 - Provider readiness 안정화

목표: target별 primary fact가 0으로 끝나는 경우를 줄인다.

1. target별 provider matrix를 운영 설정과 맞춘다.
   - `DGS10`: FRED 필요.
   - `NVDA`: Finnhub quote 우선, FMP quote/history 또는 Stooq history fallback 보조.
   - `BTC-USD`: CoinGecko demo key 필요.
   - `005930.KS`: data.go.kr key 필요.
   - `XAU`: FMP 또는 `ENABLE_STOOQ_FALLBACK=true` + Stooq key 필요.
2. `ENABLE_STOOQ_FALLBACK`는 기본 false로 유지하되, FMP 402가 반복되는 target에서 opt-in으로 켜는 방안을 검토한다.
3. Stooq를 켜는 경우 `STOOQ_FETCH_TIMEOUT_SECONDS`를 20~30초로 조정할지 로그 기반으로 판단한다.
4. 첫 성공 캐시가 생기기 전 provider가 모두 실패하면 stale fallback이 작동할 수 없다는 점을 운영 문서에 명시한다.
5. provider 실패가 반복되는 target은 임시로 `REPORT_SCHEDULER_TARGET_TICKERS`에서 제외하고, 안정 target부터 저장 성공률을 확보한다.

완료 기준:
- readiness blocked 로그의 `blocking_reasons`가 target별로 사라지거나 명확히 줄어든다.
- 실패 target은 provider 원인과 다음 조치가 문서화된다.

## Phase 3 - 실패 관측성 개선

목표: 404만 보고도 backend가 왜 생성하지 못했는지 추적할 수 있게 한다.

구현 후보:

1. 구조화 로그 보강.
   - scheduler run id, ticker, stage, provider status, readiness status, quality status를 한 줄 JSON 형태로 남긴다.
   - 시크릿 query string은 기존 `redact_secrets()` 경로를 유지한다.
2. 실패 시도 저장 테이블 추가.
   - 예: `ai_report_generation_attempts`.
   - 필드 후보: ticker, stage, status, failure_type, blocking_reasons, missing_required_facts, revision_count, created_at.
   - 이 항목은 DB schema 변경이므로 구현 전 사용자 확인과 Alembic migration이 필요하다.
3. 관리자용 read-only diagnostics endpoint 추가.
   - 인증/권한 설계가 필요하다.
   - 일반 사용자나 챗봇이 generation을 trigger하지 않도록 조회 전용으로 제한한다.

권장 순서:
- 먼저 구조화 로그를 보강한다.
- 로그만으로 운영이 어렵다면 attempt table을 추가한다.

완료 기준:
- `GET /api/reports/{ticker}` 404가 발생해도 최근 scheduler 실패 단계와 원인을 운영자가 확인할 수 있다.

## Phase 4 - 품질 gate 안정화

목표: readiness 통과 후 `ReportQualityError`로 저장되지 않는 비율을 낮춘다.

1. target별 실제 `quality_failed` feedback을 수집한다.
2. 실패가 반복되는 gate를 분리한다.
   - format section 누락.
   - unsupported numeric token.
   - unsupported qualitative claim.
   - evaluator `is_pass=false`.
3. prompt 또는 deterministic fallback은 최소 범위로 수정한다.
4. 실제 OpenAI 호출 없는 단위 테스트를 추가한다.
   - `_grade_report_readiness`
   - 숫자 sanitizer fallback
   - graph route 조건
   - provider payload normalization
5. 실제 LLM smoke는 운영자가 비용을 승인한 환경에서 target 1개로만 수행한다.

완료 기준:
- 동일 target에서 quality gate 실패가 반복되지 않는다.
- 실패하더라도 feedback이 다음 수정으로 이어질 만큼 구체적이다.

## Phase 5 - 점진적 rollout

1. `REPORT_SCHEDULER_MAX_REPORTS_PER_RUN=1`로 단일 target 성공을 확인한다.
2. target을 2~3개로 늘린다.
3. 기본 target 5개 전체로 복구한다.
4. `REPORT_SCHEDULER_INTERVAL_HOURS`와 cooldown을 비용/신선도 정책에 맞춰 확정한다.
5. target 확대 또는 broad generation은 별도 승인 전까지 하지 않는다.

완료 기준:
- 기본 target 5개 중 provider가 준비된 target은 24시간 내 최소 1회 저장된다.
- provider가 준비되지 않은 target은 readiness blocked로 명확히 분류된다.
- 프론트엔드와 챗봇은 저장 리포트만 읽는다.

## Verification Plan

문서 작성 단계에서는 실행하지 않았다. 구현 단계에서 다음을 사용한다.

- Backend import check: `python -m compileall app`
- Backend targeted tests: `python -m pytest tests/test_price_providers.py tests/test_market_history_route.py tests/test_macro_service.py`
- Report service tests가 추가되면 해당 파일만 우선 실행.
- Hosted DB readiness: `/db-check`
- Hosted log smoke: scheduler start, target start, target completion/failure type 확인.
- Frontend 변경이 있을 때만 `npm run lint`, `npm run build`.

## Risks

- `ENABLE_AI_REPORT_GENERATION=true`와 scheduler 활성화는 OpenAI 비용과 provider 호출량을 증가시킨다.
- target 확대, interval 단축, startup delay 축소는 비용/부하/제한 초과 가능성을 높인다.
- attempt table 추가는 schema migration이 필요하다.
- provider key가 없거나 무료 tier endpoint 제한이 있으면 코드만으로 모든 target을 생성할 수 없다.
- 실패 리포트를 억지로 저장하면 제품 신뢰성이 떨어지므로 readiness/quality gate는 유지해야 한다.

## Documentation Follow-up

구현이 진행되면 이 계획과 별도로 `docs/harness/report-backend-generation-remediation-implementation-YYYY-MM-DD.md`를 작성하고, 다음 문서의 Change Records에 연결한다.

- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/feature-index.md`
