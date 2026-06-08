# 백엔드 AI 리포트 미생성 원인 분석

Date: 2026-06-08
Status: Audit only - 코드/환경 변경 없음
Related features:
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/deployment-runtime.md`

## Objective

백엔드가 여전히 `AIReport`를 작성하지 못해 `GET /api/reports/{ticker}`가 404를 반환하는 이유를 현재 코드 기준으로 정리한다. 이 문서는 시크릿 값이나 `.env` 내용을 확인하지 않고, 저장소 구현과 기존 harness 기록을 근거로 실패 지점을 분류한다.

## 결론 요약

현재 구조에서 404는 "사용자 요청이 리포트를 생성하지 못했다"가 아니라 **해당 ticker의 저장된 `AIReport` 행이 아직 없다**는 뜻이다. 사용자-facing 경로는 의도적으로 리포트를 생성하지 않는다.

- `POST /api/ai/generate/{ticker}`는 항상 403을 반환한다. 수동 생성은 비활성이다.
- `GET /api/reports/{ticker}`는 DB에 저장된 최신 리포트만 조회하고, 없으면 404를 반환한다.
- 실제 생성은 `ENABLE_SCHEDULER=true`와 `ENABLE_AI_REPORT_GENERATION=true`일 때 등록되는 APScheduler job이 담당한다.
- 생성 job이 떠도 필수 가격/수익률 계열 데이터가 0 또는 누락되면 readiness 단계에서 `ReportReadinessError`가 발생하고 저장하지 않는다.
- readiness를 통과해도 LangGraph writer/evaluator LLM 호출, 포맷 검증, 숫자 fact checker, 정성 claim checker, evaluator를 모두 통과해야만 `ai_reports`에 commit된다.

따라서 현재 미생성의 핵심은 **생성 trigger, provider readiness, LLM/품질 gate, DB 저장** 중 어디에서 끊기는지 로그로 분리해야 한다. 기존 2026-06-08 기록과 현재 코드상으로는 provider/env readiness와 실패 관측성 부족이 가장 큰 잔여 원인이다.

## 현재 코드 경로

### 1. 사용자 요청은 리포트 생성을 트리거하지 않음

`backend/app/main.py`의 `ensure_report_generation_allowed()`는 무조건 403을 발생시킨다. 즉 사용자 버튼, 상세 페이지, 챗봇 요청은 리포트 생성 경로가 아니다.

관련 코드:
- `backend/app/main.py:464` - `ensure_report_generation_allowed`
- `backend/app/main.py:471` - `POST /api/ai/generate/{ticker}`
- `backend/app/main.py:497` - `GET /api/reports/{ticker}`
- `backend/app/main.py:513` - 저장 리포트가 없으면 404

AGENTS.md 14번 규칙과 현재 feature 문서의 목표도 동일하다. **사용자-facing 요청은 저장된 scheduled report만 읽어야 하며, 새 리포트를 생성하면 안 된다.**

### 2. 생성 job은 두 개의 스위치를 모두 통과해야 등록됨

`backend/app/main.py` lifespan에서 scheduler가 켜진 뒤, `ENABLE_AI_REPORT_GENERATION=true`일 때만 `generate_daily_reports` job이 등록된다. 현재 코드는 interval job에 `next_run_time=datetime.now() + REPORT_SCHEDULER_STARTUP_DELAY_SECONDS`를 지정하므로 과거의 "+1주기 뒤 첫 실행" 문제는 완화되어 있다.

관련 코드:
- `backend/app/main.py:183` - `ENABLE_SCHEDULER` 분기
- `backend/app/main.py:204` - `ENABLE_AI_REPORT_GENERATION` 분기
- `backend/app/main.py:217` - report interval job 등록
- `backend/app/main.py:225` - 첫 실행 시각 지정
- `backend/app/core/config.py:119` - `ENABLE_AI_REPORT_GENERATION`
- `backend/app/core/config.py:125` - `REPORT_SCHEDULER_STARTUP_DELAY_SECONDS` 기본값 60

남는 실패 가능성:
- 배포 환경에서 `ENABLE_SCHEDULER=false` 또는 `ENABLE_AI_REPORT_GENERATION=false`.
- 프로세스가 첫 실행 delay 이전에 재시작/종료.
- scheduler 로그는 보이지만 `AI 리포트 생성 시작` 로그가 없다면 job 미등록 또는 첫 발화 전 종료다.

### 3. 생성 대상은 기본 5개로 제한됨

`REPORT_SCHEDULER_TARGET_TICKERS` 기본값은 `DGS10,XAU,BTC-USD,NVDA,005930.KS`다. `REPORT_SCHEDULER_COVERAGE`가 `conservative`가 아니어도 broad scheduled generation은 정책상 경고만 남기고 넓히지 않는다.

관련 코드:
- `backend/app/core/config.py:128` - 기본 target ticker
- `backend/app/services/ai_service.py:945` - coverage 확인
- `backend/app/services/ai_service.py:948` - broad generation disabled 경고
- `backend/app/services/ai_service.py:951` - scheduled target asset 보장

따라서 기본 타깃 밖의 자산 상세 페이지는 scheduler가 리포트를 만들지 않는다. 그런 자산의 404는 현재 설계상 정상적인 pending 상태다.

### 4. 가격 또는 primary fact가 없으면 readiness에서 저장 전 차단됨

`generate_report_for_ticker()`는 market cache에서 ticker payload를 찾고, 없으면 `ensure_price_cache_for_ticker()`로 단일 ticker cache fill을 시도한다. 그 뒤 `_build_report_facts()`와 `_grade_report_readiness()`를 통과해야 LangGraph로 넘어간다.

관련 코드:
- `backend/app/services/ai_service.py:775` - market cache 조회
- `backend/app/services/ai_service.py:779` - ticker-level cache fill
- `backend/app/services/ai_service.py:798` - report facts 구성
- `backend/app/services/ai_service.py:799` - readiness 평가
- `backend/app/services/ai_service.py:830` - blocked이면 `ReportReadinessError`

readiness는 `price`, `index_level`, `yield_level`, `spot_or_futures_price`를 blocking primary facts로 본다. 가격 값이 `None`, 빈 문자열, `0`이면 생성은 중단된다.

관련 코드:
- `backend/app/services/ai_service.py:85` - `PRIMARY_FACT_KEYS`
- `backend/app/services/ai_service.py:437` - `_grade_report_readiness`
- `backend/app/services/ai_service.py:451` - 가격 0/누락 차단
- `backend/app/services/ai_service.py:454` - blocking fact 누락 차단

기존 로그 기록에서 확인된 provider 문제:
- Finnhub quote 502.
- FMP quote/history 402 Payment Required.
- Stooq fallback은 opt-in이며 기본값이 false.
- CoinGecko, FRED, data.go.kr key 또는 rate limit 문제도 target별 readiness를 막을 수 있다.

현재 코드에는 US stock 현재가 fallback과 stale snapshot 유지가 추가되어 있지만, 직전 유효 캐시가 없는 첫 실행에서는 provider가 모두 실패하면 여전히 가격 0으로 끝난다.

관련 코드:
- `backend/app/services/price_providers.py:604` - US stock snapshot
- `backend/app/services/price_providers.py:629` - Finnhub 실패 시 FMP quote fallback
- `backend/app/services/price_providers.py:675` - Stooq history fallback은 opt-in
- `backend/app/services/price_providers.py:1076` - snapshot dispatcher
- `backend/app/services/price_providers.py:1107` - 가격 0 캐시 고착 방지
- `backend/app/services/price_providers.py:1113` - stale snapshot fallback

### 5. readiness 통과 후에도 LLM/품질 gate 실패는 저장하지 않음

readiness가 `limited` 또는 `ready`면 LangGraph가 실행된다. writer와 evaluator는 OpenAI LLM을 호출한다.

관련 코드:
- `backend/app/services/graph/llm.py:6` - `ChatOpenAI`
- `backend/app/services/graph/nodes.py:873` - `writer_node`
- `backend/app/services/graph/nodes.py:1043` - `evaluator_node`
- `backend/app/services/graph/graph.py:93` 이후 - format/fact/qualitative/evaluator loop

실패 시나리오:
- `OPENAI_API_KEY`가 없거나 잘못됨.
- OpenAI 호출 timeout/rate limit/모델 오류.
- writer가 고정 Markdown 섹션을 누락.
- writer가 structured facts에 없는 숫자를 생성.
- 정성 claim checker가 근거 없는 고위험 주장을 감지.
- evaluator가 `is_pass=false`를 반환.

이 경우 `ReportQualityError`가 발생하고 DB commit 전에 rollback된다. 숫자 fact checker만 실패한 일부 경우에는 deterministic sanitization fallback을 시도하지만, 재검증 통과분만 저장된다.

관련 코드:
- `backend/app/services/ai_service.py:877` - `is_pass` 확인
- `backend/app/services/ai_service.py:878` - 숫자 정제 fallback
- `backend/app/services/ai_service.py:891` - `ReportQualityError`
- `backend/app/services/ai_service.py:930` - 통과한 경우에만 `db.add(report)`
- `backend/app/services/ai_service.py:931` - commit

### 6. 실패 결과가 DB에 남지 않아 운영자가 404만 보게 됨

현재 실패한 시도는 `ai_reports`에 저장되지 않는다. scheduler 로그에는 `failure_type=readiness_blocked`, `quality_failed`, `provider_unavailable` 등이 남지만, DB나 API로 최근 실패 원인을 조회할 수 있는 저장소가 없다.

결과적으로 프론트엔드와 챗봇은 "아직 scheduled report가 준비되지 않음"만 보여줄 수 있고, 운영자는 배포 로그를 직접 봐야 한다. 이 관측성 부족 때문에 같은 404가 다음 원인 중 무엇인지 즉시 구분하기 어렵다.

- scheduler job이 등록되지 않음.
- job 첫 실행 전에 프로세스 종료.
- target list에 ticker가 없음.
- provider key/rate limit/유료 endpoint 문제.
- readiness blocked.
- OpenAI 호출 실패.
- 품질 gate 실패.
- DB schema/migration/save 실패.

## 가능성이 높은 현재 원인 순위

1. **환경 스위치 또는 scheduler 발화 확인 미완료**
   - 운영 env를 직접 확인하지 않았으므로 확정할 수 없다.
   - 로그에서 `scheduler started (... reports: in 60s then every ...)`와 `AI 리포트 생성 시작`이 모두 필요하다.

2. **provider readiness 부족**
   - 기본 target 5개는 서로 다른 provider를 요구한다.
   - 무료 tier에서 FMP 402, Finnhub 502, Stooq disabled, provider key 누락이 겹치면 target별 primary price가 0이 되어 readiness blocked가 난다.
   - 특히 `XAU`와 미국 지수/원자재 계열은 FMP 유료 제한과 Stooq opt-in 정책의 영향을 크게 받는다.

3. **LLM/품질 gate 통과 실패**
   - readiness 이후에도 writer/evaluator는 OpenAI key와 안정적 응답이 필요하다.
   - 품질 gate 실패는 의도적으로 저장하지 않으므로 404가 계속된다.

4. **실패 관측성 부족**
   - 실패 시도 metadata를 보존하지 않아, 운영자가 로그 없이 원인을 재현하기 어렵다.

## 로그 판별표

| 로그/증상 | 의미 |
| --- | --- |
| `AI report generation scheduler skipped because ENABLE_AI_REPORT_GENERATION=false` | 리포트 생성 스위치가 꺼져 job 미등록 |
| `scheduler started (... reports: in 60s then every ...)`는 있으나 `AI 리포트 생성 시작`이 없음 | 첫 발화 전 종료/재시작 또는 로그 범위 부족 |
| `AI 리포트 생성 시작` 이후 target별 `리포트 생성 시작` 없음 | scheduled asset 준비 또는 loop 진입 전 실패 |
| `failure_type=provider_unavailable` | market cache fill 또는 provider payload 부재 |
| `failure_type=readiness_blocked` | 가격/primary fact 0 또는 필수 데이터 누락 |
| `failure_type=quality_failed` | LangGraph 품질 gate 실패로 저장 안 됨 |
| `리포트 생성 완료` 이후에도 404 | 다른 DB에 저장했거나 migration/schema/query ticker 문제 가능 |

## Files Inspected

- `backend/app/main.py`
- `backend/app/core/config.py`
- `backend/app/services/ai_service.py`
- `backend/app/services/market_service.py`
- `backend/app/services/price_providers.py`
- `backend/app/services/graph/llm.py`
- `backend/app/services/graph/graph.py`
- `backend/app/services/graph/nodes.py`
- `backend/alembic/versions/20260601_0001_add_subscription_billing_tables.py`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/report-generation-scheduler-not-firing-log-audit-2026-06-08.md`

## Verification

코드 변경이 없는 분석 문서 작성 작업이므로 test/build는 실행하지 않았다. `git status --short`, `rg`, `Get-Content`로 작업트리와 관련 코드/문서를 확인했다.

## Follow-up

해결 계획은 `docs/harness/report-backend-generation-remediation-plan-2026-06-08.md`에 분리했다. 실제 해결은 provider/env 점검과 일부 관측성 개선을 포함할 수 있으며, scheduler cadence 또는 AI 호출 비용에 영향을 주는 변경은 사용자 확인 후 진행해야 한다.
