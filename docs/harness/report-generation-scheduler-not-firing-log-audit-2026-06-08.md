# 배포 로그 기반 AI 리포트 미생성 정밀 분석 — 스케줄러 잡 미발화 + FMP 402

Date: 2026-06-08
Status: Audit only — 코드/배포 설정 미변경
Feature:
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/deployment-runtime.md`

선행 문서: `docs/harness/report-generation-deployment-failure-remediation-plan-2026-06-07.md` (가설 단계 계획). 이 문서는 그 계획의 가설 중 **#2(sleep/재시작형 런타임에서 in-process scheduler 의존)** 를 실제 배포 로그 증거로 좁힌 분석 기록이다.

## 운영 환경 정정 (2026-06-08, 사용자 확인)

현재 배포 환경은 **Render Standard(상시 가동, idle spin-down 없음) + Supabase 무료 티어(DB) + 그 외 모든 외부 API 무료 티어**다. 이는 본 문서 초안의 전제(sleep/재시작형 런타임)를 일부 정정한다.

- 로그의 `Shutting down` → `Your service is live 🎉`(01:04 → 01:23)는 idle sleep이 아니라 **배포/재시작**이다. Render Standard는 유휴로 죽지 않는다.
- 따라서 **1순위(잡 미발화)의 실제 메커니즘은 "sleep"이 아니라 "배포가 interval 타이머를 0으로 리셋"** 이다. `interval` 최초 발화는 +1주기(6~12h) 후이므로, 배포가 잦으면 매 배포 후 최대 1주기를 기다리게 된다. → `next_run_time` 보정(구현 완료)으로 배포 직후 발화하므로 이 환경에서 특히 효과적이다.
- 선행 계획서의 **Option A(상시 가동 런타임 전환)는 Render Standard로 이미 충족**됐다. Option B(외부 cron)도 필수가 아니다.
- 이 환경에서 **남은 결정적 차단 요인은 무료 티어 provider 데이터 가용성**이다. 특히 `ENABLE_STOOQ_FALLBACK` 기본값이 `False`이고 FMP 무료가 premium 엔드포인트에 402를 반환하므로, FMP 의존 대상(XAU 등 COMMODITY, 지수 INDEX)과 US 주식 history가 무료로는 채워지지 않는다. 상세는 아래 "무료 티어 provider×대상 매트릭스" 참조.

## Objective

Render 배포(`https://project-finance-r9zn.onrender.com`)에서 "항상" 발생하는 `GET /api/reports/{ticker}` 404의 근본 원인을, 사용자가 제공한 런타임 로그와 현재 코드를 대조해 확정한다. 목표 동작(사용자/챗봇이 리포트를 실시간 생성하지 않고, scheduler가 저장한 `AIReport`만 조회)은 그대로 유지한다.

## 분석한 로그 (사용자 제공, 2026-06-08 01:03~01:05 UTC)

핵심 라인만 발췌한다.

```text
2026-06-08 01:03:24 WARNING price_providers | FMP history unavailable (ticker=BRK-B, period=1mo): 402 Payment Required
2026-06-08 01:03:25 WARNING price_providers | FMP history unavailable (ticker=LLY, period=1mo): 402 Payment Required
2026-06-08 01:03:25 WARNING price_providers | FMP history unavailable (ticker=AVGO, period=1mo): 402 Payment Required
...
2026-06-08 01:04:18 INFO app.main | Notification delivery started
2026-06-08 01:04:21 INFO app.main | Notification delivery completed (sent=0, failed=1)
INFO:     Shutting down
INFO:     Waiting for application shutdown.
2026-06-08 01:04:23 INFO apscheduler.scheduler | Scheduler has been shut down
INFO:     Application shutdown complete.
INFO:     Finished server process [64]
...(이후 새 프로세스가 다시 기동, 01:05:18 알림 잡 재실행)...
INFO:     GET /api/reports/NVDA HTTP/1.1 404 Not Found
```

로그에서 확정 가능한 사실:

1. **`"AI 리포트 생성 시작"` 라인이 로그 전체에 단 한 번도 없다.** 즉 `generate_daily_reports()`(scheduler 리포트 잡)가 이 가동 구간에서 **한 번도 실행되지 않았다.**
2. **1분 간격 알림 잡만 발화한다.** `run_notification_delivery_job`(interval 1분)은 01:04:18, 01:05:18에 정상 발화. 즉 `ENABLE_SCHEDULER=true`이고 APScheduler 자체는 살아 있다.
3. **프로세스가 수 분 단위로 종료·재기동한다.** 01:04:23에 `Shutting down` → `Scheduler has been shut down` → `Finished server process [64]`. 이후 새 프로세스가 알림 잡을 다시 돌린다. Render의 sleep/재시작형 런타임 특성.
4. **FMP가 history에서 402 Payment Required를 반환한다.** `historical-price-eod/full` 엔드포인트가 현재 FMP 플랜에 포함되지 않아 과거 시세 조회가 실패한다.

## 코드 대조로 좁힌 근본 원인

### 1순위(확정에 가까움): 리포트 스케줄러 잡이 인스턴스 수명보다 늦게 발화하도록 설정됨

`backend/app/main.py` lifespan에서 리포트 잡은 두 개로 등록된다.

- **주기 잡** `generate_daily_reports`: `scheduler.add_job(..., "interval", hours=REPORT_SCHEDULER_INTERVAL_HOURS=6, ...)`.
  - APScheduler `interval` 트리거는 **최초 발화가 등록 시점 +6시간 후**다(`next_run_time` 미지정). 인스턴스가 6시간을 연속 가동하지 못하면 이 잡은 영원히 발화하지 않는다.
- **시작 1회성 잡** `generate_daily_reports_startup`: `scheduler.add_job(..., "date", run_date=datetime.now() + timedelta(seconds=REPORT_SCHEDULER_STARTUP_DELAY_SECONDS=180), ...)`.
  - 실질적으로 리포트를 돌리는 유일한 경로. 그러나 **cold start 후 180초를 연속으로 버텨야** 발화한다.

로그 증거(프로세스가 ~수 분 단위로 종료·재기동, `"AI 리포트 생성 시작"` 부재)와 합치면:

> **인스턴스가 startup 잡의 180초 지연이 끝나기 전에 종료되고, 재기동하면 타이머가 0부터 다시 시작된다. 그 결과 리포트 잡이 단 한 번도 발화하지 못하고, `ai_reports` 테이블이 비어 있어 `GET /api/reports/{ticker}`가 항상 404다.** 1분 간격 알림 잡만 종료 전에 발화하므로 로그에 보인다.

관련 설정 기본값(`backend/app/core/config.py`): `ENABLE_SCHEDULER=True`, `ENABLE_AI_REPORT_GENERATION=True`, `REPORT_SCHEDULER_INTERVAL_HOURS=6`, `REPORT_SCHEDULER_STARTUP_DELAY_SECONDS=180`, `REPORT_SCHEDULER_TARGET_TICKERS="DGS10,XAU,BTC-USD,NVDA,005930.KS"` (NVDA 포함 — 대상 누락은 원인이 아님).

> **구현 상태(2026-06-08)**: 이 1순위를 보정했다 — `generate_daily_reports`(interval) 잡에 `next_run_time`을 부여해 기동 직후(startup delay 후) 1회 발화하도록 하고 중복 startup date 잡을 제거, `REPORT_SCHEDULER_STARTUP_DELAY_SECONDS` 기본값을 180→60초로 단축. 코드/테스트: `docs/harness/report-scheduler-startup-firing-fix-implementation-2026-06-08.md`. 단 인스턴스가 60초보다 먼저 죽으면 여전히 발화 못 함 → 근본 안정화는 Option A/B(인프라) 필요.

### 2순위(데이터 품질 저하, 주식 차단 원인은 아님): FMP 402 Payment Required

`generate_report_for_ticker()` → `_build_report_facts()` → `_grade_report_readiness()` 경로에서 readiness가 `blocked`가 되려면:

- 가격(`price`) 값이 `None/""/0`이거나(`backend/app/services/ai_service.py:451`),
- `blocking_severity == "blocking"`인 필수 팩트가 결측(현재 blocking은 `PRIMARY_FACT_KEYS`=가격뿐, `ai_service.py:454-460`)이거나,
- CRYPTO/COMMODITY에서 필수 팩트 3개 이상 결측(`ai_service.py:467-468`).

NVDA(STOCK_US)는 가격이 `/api/market/prices` 200으로 들어오므로, FMP 402로 `recent_performance`(history)·`market_cap`이 빠져도 이는 `limiting`이지 `blocking`이 아니다 → readiness는 최악이라도 `limited`로 **생성은 진행**된다. 따라서 **FMP 402는 NVDA 주식 리포트의 직접 차단 원인이 아니다.** 다만:

- `XAU`(COMMODITY), `BTC-USD`(CRYPTO) 대상은 필수 데이터가 더 쉽게 3개 이상 결측되어 `blocked` 유발 가능.
- 전반적으로 fact 빈약 → quality gate(`ReportQualityError`) 통과 실패 확률 상승.

즉 FMP 402는 **2순위 악화 요인**이며, 1순위(잡 미발화)가 해소되어도 별도로 점검해야 한다.

### 선행 사례(casebook 사례 14)와의 차이

casebook 사례 14는 NVDA 404의 원인을 fact_checker 부호 비대칭 루프로 보고 "정상 트레이스백 + `AI 리포트 생성 종료` 로그가 있으므로 **무료 배포 프로세스 강제 종료가 아님이 확정**"이라 기록했다. 그러나 **이번 2026-06-08 로그는 정반대 패턴**이다: `AI 리포트 생성 시작/종료`가 아예 없고, `Shutting down`/`Finished server process`만 보인다. 따라서 현재 증상은 사례 14(잡은 돌지만 품질 게이트 실패)와 **다른 실패 모드**이며, "잡이 애초에 발화하지 못함"으로 분류해야 한다.

## 확인 방법 (배포 로그에서 한 줄로 분기)

| 로그에서 보이는 것 | 의미 / 분류 |
| --- | --- |
| `AI report generation scheduler skipped because ENABLE_AI_REPORT_GENERATION=false` | 환경변수로 꺼짐 → 스위치 조치 |
| `"AI 리포트 생성 시작"`이 **아예 없음** + `Shutting down`/`Finished server process` 반복 | (이번 케이스) startup 잡 발화 전 프로세스 종료 → 1순위 |
| `report generation failed (failure_type=readiness_blocked ...)` | 필수 데이터 부족 차단 → FMP/provider 점검 |
| `report generation failed (failure_type=quality_failed ...)` | LLM 품질 게이트 소진 → 사례 14 계열 |

## 권장 조치 (구현 시 별도 승인 필요)

1순위 해소가 우선이다. 아래는 방향만 제시하며, 실제 구현/배포 변경은 사용자 승인 후 진행한다(비용·운영 cadence 변경 포함).

1. **startup 잡이 cold start 직후 확실히 발화하도록 단축**: `REPORT_SCHEDULER_STARTUP_DELAY_SECONDS`를 180 → 20~30초로 낮추거나, 주기 `interval` 잡에 `next_run_time=datetime.now()`를 부여해 기동 직후 1회 발화시킨다. (단독으로는 인스턴스 재시작이 잦으면 여전히 불안정)
2. **상시 가동 런타임으로 전환(권장, 코드 변경 최소)**: Render Standard 등 sleep 없는 호스트. in-process scheduler를 그대로 사용. — 선행 계획서 Option A.
3. **리포트 생성을 웹 lifespan에서 분리(구조적 해법)**: token-protected task endpoint + 외부 cron. 웹 인스턴스 수명에 의존하지 않음. 일반 사용자/챗봇 경로가 아니므로 AGENTS.md 14절 정책 유지. — 선행 계획서 Option B.
4. **FMP 402 대응(2순위)**: FMP 플랜/한도 점검 또는 history 폴백 provider 경로 확인. 주식 외(XAU/BTC-USD) readiness 개선.

첫 성공 기준: 배포 로그에 `AI 리포트 생성 시작` → `NVDA 리포트 생성 완료`가 찍히고 `GET /api/reports/NVDA`가 200.

## Files Inspected (코드 변경 없음)

- `backend/app/main.py` — lifespan scheduler 등록(`generate_daily_reports`, `generate_daily_reports_startup`, 알림 잡), `GET /api/reports/{ticker}` 404 분기
- `backend/app/services/ai_service.py` — `generate_daily_reports()`, `generate_report_for_ticker()`, `_grade_report_readiness()`, `_fact_is_present()`
- `backend/app/core/config.py` — scheduler/리포트 관련 기본값
- `frontend/src/pages/AssetDetail.jsx`, `frontend/src/components/ReportCard.jsx` — 404 → "scheduled_report_not_ready" 표시

## Verification

분석(audit) 단계이므로 build/test를 실행하지 않았다. 코드/설정 변경이 없다. 실제 조치는 선행 계획서(`report-generation-deployment-failure-remediation-plan-2026-06-07.md`)의 Verification Plan을 따른다.

## Risks / Follow-up

- 위 권장 조치 1~4는 모두 scheduler cadence·런타임·비용·운영 트리거 변경을 포함하므로 구현 전 사용자 승인 필요(AGENTS.md 9·14절).
- secret 값(API 키, DB 비밀번호)은 본 문서·로그·응답에 남기지 않는다. FMP 402 자체는 키 노출이 아니라 플랜 권한 문제다.
- 후속 구현 시 `report-generation-deployment-failure-remediation-implementation-*.md`를 생성하고 본 문서를 출처로 링크한다.

---

## 추가 분석 (2차 로그, 2026-06-08 01:23 UTC) — 스케줄러는 정상 기동, 이번엔 provider 전면 실패

1차 로그(01:03~01:05)와 **양상이 다른** 2차 로그가 추가 확인되었다. 이번에는 1순위(잡 미발화)가 재현되지 않고, **시장 데이터 provider가 전면 실패**하는 별개의 실패 모드다.

### 2차 로그 발췌

```text
2026-06-08 01:23:04 INFO apscheduler.scheduler | Added job "...run_daily_reports_job" to job store "default"   (×2: interval + startup)
2026-06-08 01:23:04 INFO apscheduler.scheduler | Scheduler started
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:10000
[lifespan] scheduler started (prices:5m, news:60m, reports: every 12 hours)
[lifespan] initial market cache warm-up started
2026-06-08 01:23:04 WARNING price_providers | Market snapshot provider failed (ticker=AAPL, category=STOCK_US): 502 Bad Gateway (finnhub.io/quote)
2026-06-08 01:23:05 WARNING price_providers | Market snapshot provider failed (ticker=NVDA, category=STOCK_US): 502 Bad Gateway (finnhub.io/quote)
... MSFT, GOOGL, AMZN, META, BRK-B, LLY, AVGO, TSLA 전부 동일 502 ...
2026-06-08 01:23:05 WARNING price_providers | FMP quote unavailable (ticker=^NDX): 402 Payment Required
2026-06-08 01:23:07 WARNING price_providers | FMP history unavailable (ticker=^NDX, period=1mo): 402 Payment Required
==> Your service is live 🎉
```

### 2차 로그에서 확정 가능한 사실

1. **스케줄러가 이번엔 정상 기동했다.** `Scheduler started`, `Application startup complete`, `Your service is live`, `reports: every 12 hours`. 즉 1순위(잡 미발화)는 이 가동 구간에서는 발생하지 않았다(인스턴스가 살아 있음). `REPORT_SCHEDULER_INTERVAL_HOURS`는 6→**12**로 바뀌어 있다.
2. **STOCK_US 전 종목의 가격 조회가 Finnhub 502 Bad Gateway로 실패한다.** AAPL·MSFT·NVDA·GOOGL·AMZN·META·BRK-B·LLY·AVGO·TSLA 모두 동일.
3. **FMP는 402 Payment Required** (quote·history 모두). 즉 FMP 폴백 경로도 막혀 있다.

### 코드 대조 — 왜 이게 리포트 미생성으로 직결되는가

`fetch_market_snapshot()` dispatcher는 STOCK_US를 `_fetch_finnhub_stock_snapshot()`로 보낸다(`backend/app/services/price_providers.py:1051-1052`). 그런데 그 함수 내부에서 **현재가(quote) 호출에는 폴백이 없다**:

- `_get_json("finnhub", ".../quote", ...)`가 첫 호출이고 502 시 즉시 예외를 던진다(`price_providers.py:609-613`).
- 함수 내 `try/except`는 **market_cap(profile)·history 폴백에만** 걸려 있고(`:619-656`), **현재가 자체의 폴백은 없다.**
- 따라서 502 예외는 dispatcher의 `except Exception`까지 전파되어 `DEFAULT_RESPONSE`(가격 0/빈값)를 그대로 캐시한다(`price_providers.py:1067-1071`).

그 결과 워밍업은 US 주식 가격을 **0(빈값)으로 캐시**한다. 이후 리포트 잡이 NVDA를 처리할 때:

- `generate_report_for_ticker()`의 `price_payload`는 존재하더라도 가격이 0/None,
- `_grade_report_readiness()`에서 `price_value in (None, "", 0)` → `blocking_reasons` 추가 → **`status="blocked"`** (`backend/app/services/ai_service.py:451-452`),
- → `ReportReadinessError` 발생, **LLM 호출 없이 미저장** → `ai_reports` 비어 있음 → `GET /api/reports/NVDA` 404.

> **2차 로그의 근본 원인: 상위 provider 장애/한도(Finnhub 502 + FMP 402)가 동시에 발생한 상태에서, STOCK_US 경로에 "현재가" 폴백이 없어 가격이 0으로 캐시되고, readiness가 `blocked`가 되어 리포트가 저장되지 않는다.** Stooq 폴백은 opt-in(`ENABLE_STOOQ_FALLBACK`)이며 이 경로에서 **history만** 보강할 뿐 live quote는 대체하지 못한다(`price_providers.py:647-656`).

### 두 로그의 관계 정리

| 구분 | 1차 로그(01:03~05) | 2차 로그(01:23) |
| --- | --- | --- |
| 스케줄러 상태 | 발화 전 프로세스 종료(`Finished server process`), `AI 리포트 생성 시작` 부재 | 정상 기동(`Scheduler started`, `service is live`) |
| 리포트 잡 주기 | 6h | 12h |
| 주 차단 지점 | **잡 미발화**(1순위) | **provider 전면 실패 → 가격 0 → readiness blocked**(신규) |
| 공통 | `GET /api/reports/{ticker}` 404, 저장 행 0 | 동일 |

즉 **두 개의 독립적 차단 지점**이 존재한다. 잡 발화 문제(1순위)를 고쳐도, provider 장애 구간에 잡이 돌면 2차 로그처럼 readiness blocked로 여전히 0건이 된다. 둘 다 해소해야 한다.

> **구현 상태(2026-06-08)**: 아래 권장 조치 1·3을 구현했다 — STOCK_US 현재가 폴백(Finnhub→FMP→Stooq 종가) + 전 provider 실패 시 가격 0을 캐시하지 않고 직전 유효 스냅샷(stale) 유지. 코드/테스트: `docs/harness/market-snapshot-price-fallback-and-stale-retention-implementation-2026-06-08.md`. 권장 조치 2(502 재시도)·4(FMP 플랜)와 1순위(스케줄러 잡 미발화)는 미해결로 남아 있다.

### 2차 로그에 대한 권장 조치 (구현 시 승인 필요)

1. **STOCK_US 현재가 폴백 추가**: Finnhub quote 실패 시 FMP quote → (가능하면) Stooq 일별 종가의 마지막 값으로 `currentPrice`를 채우는 폴백을 `_fetch_finnhub_stock_snapshot`에 추가. 단 FMP가 402로 막혀 있으면 실효가 제한되므로 provider 키/플랜 점검과 병행.
2. **provider 헬스 확인**: Finnhub 502가 일시적 게이트웨이 장애인지(재시도로 회복) 지속적인지(토큰/플랜/레이트리밋) 구분. 일시적이면 워밍업·스냅샷에 짧은 재시도/백오프 추가 검토.
3. **가격 0을 캐시하지 않기**: 전 provider 실패 시 `DEFAULT_RESPONSE`(가격 0)를 캐시에 덮어쓰지 말고 직전 유효 캐시를 유지(stale 허용)하도록 검토 — 워밍업 직후 1회 장애가 6/12시간 readiness 차단으로 굳는 것을 방지.
4. FMP 402(플랜 한도)는 1차 분석의 2순위 조치와 동일하게 점검.

---

## 무료 티어 provider×대상 매트릭스 (Render Standard + 전 API 무료 기준)

스케줄 기본 대상 `REPORT_SCHEDULER_TARGET_TICKERS="DGS10,XAU,BTC-USD,NVDA,005930.KS"`가 무료 티어에서 가격을 채우려면 다음 provider/키가 필요하다. dispatcher 분기는 `backend/app/services/price_providers.py:fetch_market_snapshot` 기준.

| 대상 | 분류/경로 | 무료 provider | 필요 env | 무료 티어 상태 |
| --- | --- | --- | --- | --- |
| `DGS10` | US_BOND → `fetch_us_bond_data` | FRED | `FRED_API_KEY` | ✅ 무료로 동작 |
| `NVDA` | STOCK_US → `_fetch_finnhub_stock_snapshot` | Finnhub(quote), history는 Stooq | `FINNHUB_API_KEY` + (`STOOQ_API_KEY`, `ENABLE_STOOQ_FALLBACK=true`) | ⚠️ quote는 무료 OK(502는 일시적). **history는 FMP 402 → Stooq 필요** |
| `XAU` | COMMODITY → `_fetch_fmp_snapshot` | FMP(402) → **Stooq**(`xauusd`) | `STOOQ_API_KEY` + `ENABLE_STOOQ_FALLBACK=true` | ❌ Stooq 미활성 시 가격 0 → readiness blocked |
| `BTC-USD` | CRYPTO → `_fetch_coingecko_snapshot` | CoinGecko demo | `COINGECKO_DEMO_API_KEY` | ⚠️ 키 없으면 빈 응답 |
| `005930.KS` | STOCK_KR → `_fetch_data_go_snapshot` | data.go.kr | `DATA_GO_KR_API_KEY` | ✅ 키 있으면 무료 동작 |

핵심: **`ENABLE_STOOQ_FALLBACK` 기본값이 `False`**라서, 무료 티어에서 FMP가 402인 XAU(및 지수 INDEX 대상)와 US 주식 history가 폴백을 못 탄다. Stooq는 `STOOQ_SYMBOLS`로 US 주식·지수(^GSPC/^NDX)·금속(XAU/XAG)·USDKRW를 커버하므로, 활성화하면 이들 대상의 무료 데이터 공백이 메워진다(라이선스상 fallback-only opt-in이라 기본값은 off 유지 — 운영자가 env로 켠다).

### 이 환경에서의 우선 조치 (코드 아닌 env/운영)

1. `ENABLE_STOOQ_FALLBACK=true` + `STOOQ_API_KEY` 설정 → XAU·지수·US 주식 history 무료 충당. **단일 최고 레버리지.**
2. 대상별 키 확인: `FRED_API_KEY`(DGS10), `FINNHUB_API_KEY`(NVDA), `COINGECKO_DEMO_API_KEY`(BTC-USD), `DATA_GO_KR_API_KEY`(005930.KS).
3. `FMP_DAILY_CALL_BUDGET`(기본 180)로 FMP 무료 250/day 초과 방지 — 이미 가드됨.
4. Supabase 무료: asyncpg는 pooler URL(6543)·작은 pool 권장(연결 한도). 리포트 미생성과 직접 관련은 적음.
5. 그래도 무료로 가격이 안 되는 대상(키 부재/미지원)은 `REPORT_SCHEDULER_TARGET_TICKERS`에서 빼 readiness blocked 반복 실패를 줄인다.

(secret 값은 문서/로그/응답에 남기지 않는다. 위는 변수명·동작만 기술.)
