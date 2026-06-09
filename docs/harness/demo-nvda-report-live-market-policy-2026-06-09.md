# 데모 환경 NVDA 단일 리포트와 제한 live market 정책

Date: 2026-06-09
Status: Documentation only - 코드/환경 변경 없음
Related plan:
- `docs/harness/demo-nvda-report-live-market-remediation-plan-2026-06-09.md`

Related features:
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/deployment-runtime.md`

## Objective

데모 환경에서 AI 리포트 생성 범위와 시장 데이터 live provider 범위를 분리해 운영하는 정책을 정리한다. 목표 운영 형태는 다음과 같다.

- AI 리포트는 `NVDA` 한 종목만 backend scheduler가 작성한다.
- live provider 시장 데이터는 `NVDA`, 미국채 10년(`DGS10`), 비트코인(`BTC-USD`), 금(`XAU`), 삼성전자(`005930.KS`), 메인 대시보드 4개 지표(`^GSPC`, `^NDX`, `KRW=X`, `^KS11`)만 가져온다.
- 그 외 자산의 가격, 뉴스, latest-context, history는 deterministic `demo_mock` 값을 사용한다.
- 사용자 화면, 상세 페이지, 챗봇은 새 리포트를 직접 생성하지 않고 저장된 scheduled report만 읽는다.

## 핵심 구분

`MARKET_LIVE_TICKERS`와 `REPORT_SCHEDULER_TARGET_TICKERS`는 목적이 다르다.

| 환경변수 | 역할 | 데모 권장값 |
| --- | --- | --- |
| `MARKET_LIVE_TICKERS` | 외부 시장 provider 호출 허용 ticker allowlist. allowlist 밖은 `demo_mock`으로 응답한다. | `DGS10,XAU,BTC-USD,NVDA,005930.KS,^GSPC,^NDX,KRW=X,^KS11` |
| `REPORT_SCHEDULER_TARGET_TICKERS` | backend AI 리포트 scheduler가 생성할 ticker 목록. | `NVDA` |
| `REPORT_SCHEDULER_MAX_REPORTS_PER_RUN` | scheduler 1회 실행당 최대 생성 개수. | `1` |

`REPORT_SCHEDULER_TARGET_TICKERS=NVDA`만 설정하면 리포트 대상은 줄어들지만, 리포트가 반드시 저장되는 것은 아니다. `NVDA` 리포트 생성은 `market_cache`의 가격 데이터, latest context, OpenAI writer/evaluator, 품질 gate, DB 저장을 모두 통과해야 한다.

반대로 `MARKET_LIVE_TICKERS=*`는 모든 자산을 live provider로 보내므로 이 데모 정책과 맞지 않는다. 무료 API quota와 provider rate limit을 빠르게 소모할 수 있다.

## 권장 데모 환경변수

아래 값은 시크릿을 제외한 정책 변수 예시다. 실제 API key 값은 문서나 로그에 남기지 않는다.

```env
ENABLE_MARKET_WARMUP=true
ENABLE_SCHEDULER=true
ENABLE_AI_REPORT_GENERATION=true

MARKET_LIVE_TICKERS=DGS10,XAU,BTC-USD,NVDA,005930.KS,^GSPC,^NDX,KRW=X,^KS11
MARKET_PRICES_REFRESH_MINUTES=5
MARKET_NEWS_REFRESH_MINUTES=60
MARKET_LATEST_CONTEXT_TTL_MINUTES=10
MARKET_PRICE_FETCH_TIMEOUT_SECONDS=55
MARKET_NEWS_FETCH_TIMEOUT_SECONDS=20

REPORT_SCHEDULER_COVERAGE=conservative
REPORT_SCHEDULER_TARGET_TICKERS=NVDA
REPORT_SCHEDULER_MAX_REPORTS_PER_RUN=1
REPORT_SCHEDULER_INTERVAL_HOURS=6
REPORT_SCHEDULER_STARTUP_DELAY_SECONDS=180
REPORT_SCHEDULER_ASSET_COOLDOWN_HOURS=6
```

필수 또는 관련 provider key 존재 여부:

- `OPENAI_API_KEY`: NVDA 리포트 writer/evaluator 실행에 필요하다.
- `FINNHUB_API_KEY`: NVDA 현재가 primary quote와 뉴스/이벤트에 필요하다.
- `FMP_API_KEY`: NVDA history/profile fallback, `^GSPC`, `^NDX`, `XAU`의 FMP quote/history에 필요하다.
- `FRED_API_KEY`: `DGS10`에 필요하다.
- `COINGECKO_DEMO_API_KEY`: `BTC-USD`에 필요하다.
- `DATA_GO_KR_API_KEY`: `005930.KS`와 `^KS11`에 필요하다.
- `ENABLE_STOOQ_FALLBACK=false`: 기본값 유지. FMP 402 또는 history 공백이 반복될 때만 별도 승인 후 true를 검토한다.

## 환경변수 변경 후 리포트가 작성되지 않는 대표 원인

1. `ENABLE_SCHEDULER=false`
   - 가격/news scheduler뿐 아니라 report scheduler 등록도 막는다.

2. `ENABLE_AI_REPORT_GENERATION=false`
   - scheduler는 떠도 AI 리포트 job이 등록되지 않는다.
   - 로그에 `AI report generation scheduler skipped because ENABLE_AI_REPORT_GENERATION=false`가 남는다.

3. `REPORT_SCHEDULER_TARGET_TICKERS`가 비어 있거나 `NVDA`가 없다.
   - scheduled asset seed 목록이 비어 리포트 생성 loop가 실질적으로 돌지 않는다.

4. `REPORT_SCHEDULER_MAX_REPORTS_PER_RUN=0`
   - target이 있어도 회당 생성 상한 때문에 즉시 중단된다.

5. `REPORT_SCHEDULER_ASSET_COOLDOWN_HOURS` 안에 이미 저장된 NVDA 리포트가 있다.
   - 정상 동작으로 건너뛴다. 로그에 `NVDA 오늘 리포트 이미 존재 - 건너뜀`이 남는다.

6. `MARKET_LIVE_TICKERS`에서 `NVDA`를 제거했다.
   - 리포트 대상은 `NVDA`여도 시장 데이터는 mock 경로로 떨어진다.
   - mock 가격은 0이 아니어서 readiness를 통과할 수는 있지만, 데모 목표인 "NVDA 리포트는 live provider 기반"과 어긋난다.
   - latest context도 `source_status=mocked_by_market_live_tickers`가 되어 리포트 metadata에 데이터 제한으로 남는다.

7. NVDA provider readiness 실패
   - Finnhub quote와 FMP fallback이 모두 실패하거나 key가 없으면 가격이 0이 될 수 있다.
   - `generate_report_for_ticker()`는 가격이 0/누락이면 `ReportReadinessError`로 저장 전 차단한다.

8. OpenAI 또는 품질 gate 실패
   - readiness 이후에도 writer/evaluator 호출, 포맷 검증, 숫자 fact checker, 정성 claim checker, evaluator를 통과해야만 `ai_reports`에 저장된다.
   - 실패하면 DB commit 전 rollback되고 `GET /api/reports/NVDA`는 계속 404다.

9. DB schema 또는 DB 연결 불일치
   - 다른 DB에 저장했거나 migration이 부족하면 생성 완료 로그와 조회 결과가 어긋날 수 있다.
   - hosted DB는 Alembic migration 적용 여부와 `/db-check` sanitized 결과를 확인한다.

## 로그 판별표

| 로그/증상 | 의미 |
| --- | --- |
| `scheduler skipped` | `ENABLE_SCHEDULER=false` |
| `reports: disabled by ENABLE_AI_REPORT_GENERATION` | `ENABLE_AI_REPORT_GENERATION=false` |
| `scheduler started (... reports: in ... then every ...)` | report job 등록됨 |
| `AI 리포트 생성 시작` 없음 | 첫 발화 전 종료, 로그 범위 부족, 또는 job 미등록 |
| `리포트 생성 대상 자산 수: 0` | `REPORT_SCHEDULER_TARGET_TICKERS`가 비었거나 parsing 결과가 없음 |
| `NVDA 오늘 리포트 이미 존재 - 건너뜀` | cooldown 내 기존 저장 리포트 존재 |
| `NVDA report generation failed (failure_type=readiness_blocked, ...)` | 가격/필수 fact 부족 |
| `NVDA report generation failed (failure_type=quality_failed, ...)` | LLM output이 품질 gate를 통과하지 못함 |
| `NVDA 리포트 생성 완료` | DB commit까지 완료된 경로 |
| 생성 완료 로그 후 404 | 다른 DB 조회, 권한/paywall, ticker mismatch, migration/query 문제 가능 |

## 운영 판단

현재 코드에서 사용자-facing 요청은 리포트를 생성하지 않는다. 따라서 `GET /api/reports/NVDA`가 404라는 것은 "사용자 요청이 생성에 실패했다"가 아니라 "scheduler가 아직 저장하지 않았거나 저장 전에 차단됐다"는 뜻이다.

데모 환경에서 이 상태를 해결하려면 우선 `NVDA` 단일 target으로 scheduler 저장 성공을 확인하고, 시장 live allowlist는 데모용 9개 ticker로 제한한다. 그 외 자산을 mock으로 두는 정책은 `MARKET_LIVE_TICKERS`가 담당하며, 리포트 target 축소는 `REPORT_SCHEDULER_TARGET_TICKERS`가 담당한다.

## Files Inspected

- `.env.example`
- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/app/services/ai_service.py`
- `backend/app/services/market_service.py`
- `backend/app/services/demo_market_data.py`
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/report-backend-generation-failure-analysis-2026-06-08.md`
- `docs/harness/report-backend-generation-remediation-plan-2026-06-08.md`
