# STOCK_US 현재가 폴백 + 스냅샷 stale 유지 구현 (provider 장애 시 리포트 readiness blocked 방지)

Date: 2026-06-08
Status: 구현 완료 (코드 변경 + 테스트). 운영/배포 설정 변경 없음.
Feature:
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`

분석 출처: `docs/harness/report-generation-scheduler-not-firing-log-audit-2026-06-08.md` (추가 분석 섹션, 2026-06-08 01:23 로그) / 에러 케이스북 사례 16.

## Objective

2026-06-08 01:23 UTC 로그에서 확인된 실패 모드를 코드로 차단한다: Finnhub `/quote` 502 + FMP 402가 동시에 발생하면 STOCK_US 스냅샷의 현재가가 0으로 캐시되고, `_grade_report_readiness`가 `price_value in (None,"",0)`로 `blocked` → `ReportReadinessError` → 리포트 미저장 → `GET /api/reports/{ticker}` 404로 고착된다.

목표 동작(사용자/챗봇이 리포트를 실시간 생성하지 않음, 저장 리포트만 조회)은 그대로 유지한다. 이번 변경은 **시장 데이터 수집의 회복력**만 높인다.

## Changes

### 1. STOCK_US 현재가(quote) 폴백 — `backend/app/services/price_providers.py` `_fetch_finnhub_stock_snapshot`

- 기존: Finnhub `/quote` 호출을 try/except 없이 첫 줄에서 수행 → 502 시 예외가 dispatcher까지 전파되어 스냅샷 전체가 `DEFAULT_RESPONSE`(가격 0)로 떨어졌다. 함수 내 폴백은 market_cap·history에만 있었고 **현재가 폴백은 없었다.**
- 변경:
  1. Finnhub `/quote` 호출을 try/except로 감싸 502 등 단일 provider 장애를 흡수(로그: `Finnhub quote unavailable (...)`).
  2. **현재가 폴백 1**: Finnhub 현재가가 비면 `_fetch_fmp_quote_snapshot`로 현재가·등락률을 보강. FMP quote의 `marketCap`은 finnhub/FMP profile이 모두 실패했을 때 tertiary 소스로 사용.
  3. **현재가 폴백 2**: quote 계열(Finnhub·FMP)이 모두 비면 history(FMP→Stooq 종가)의 마지막 값으로 현재가를 채우고, 직전 종가와의 비교로 등락률을 계산.
- 기존 성공 경로(Finnhub quote 정상)는 동작 불변. 기존 테스트 `test_finnhub_stock_snapshot_keeps_quote_when_optional_sources_fail` 그대로 통과.

### 2. 스냅샷 stale 유지 — `backend/app/services/price_providers.py` `fetch_market_snapshot`

- 기존: 전 provider 실패 시 `DEFAULT_RESPONSE`(가격 0)를 `_cache_set`으로 그대로 캐시해, 워밍업 직후 1회 장애가 다음 readiness 차단으로 고착됐다.
- 변경:
  1. 함수 진입 시 `_cache_get_stale`로 **직전 유효 스냅샷을 미리 확보**한다. (`_cache_get`은 TTL 만료 항목을 `pop`하므로, 그 이후 stale 조회는 불가능하다 — 검증 단계에서 발견·수정한 핵심 포인트.)
  2. live 결과의 현재가가 0이면: 확보해 둔 stale의 현재가가 유효할 때 그 stale을 다시 캐시에 적고 반환(로그: `Market snapshot stale fallback used (...)`). 다음 TTL 윈도까지 마지막 유효값을 제공하고, 만료되면 live를 재시도한다(실패는 `_get_json` cooldown으로 throttle).
  3. 직전 유효값도 없으면 0을 반환하되 **캐시에 덮어쓰지 않아** 다음 호출이 곧바로 live 재시도하게 둔다.

### 3. 테스트 — `backend/tests/test_price_providers.py`

추가:
- `test_finnhub_stock_snapshot_falls_back_to_fmp_quote_when_finnhub_502`: Finnhub 502 → FMP quote로 현재가·marketCap 보강.
- `test_finnhub_stock_snapshot_falls_back_to_history_last_close`: quote 계열 전멸 → history 마지막 종가로 현재가/등락률.
- `test_market_snapshot_keeps_stale_when_live_returns_no_price`: live 0 → stale 유지·재캐시.
- `test_market_snapshot_does_not_cache_zero_price_without_stale`: stale 없으면 0 반환하되 캐시 미저장.

## Verification

작업 디렉터리 `backend`. 환경에 `PROJECT_NAME`/`API_V1_STR`/`DATABASE_URL`이 없으면 Settings 검증으로 collection이 실패하므로(이번 변경과 무관한 기존 환경 전제), 비밀이 아닌 식별 값만 in-memory로 주입해 실행했다.

```powershell
cd backend
py -m compileall app/services/price_providers.py   # EXIT=0
# 식별용 더미 env 주입(시크릿 아님) 후:
py -m pytest tests/test_price_providers.py tests/test_macro_service.py -q
```

결과: **38 passed** (price_providers 신규 4건 포함, macro_service 회귀 없음). 컴파일 통과.

1차 검증에서 `test_market_snapshot_keeps_stale_when_live_returns_no_price`가 실패해 `_cache_get`의 pop 동작과 stale 폴백 충돌을 발견 → stale을 함수 진입 시점에 미리 확보하도록 수정 후 재검증 통과.

## 실행하지 않은 것 / 사유

- 실제 LLM·외부 provider 호출: 미실행(테스트는 monkeypatch 기반).
- DB 컨테이너: 대상 테스트가 PostgreSQL 불필요(임시 sqlite로 충분).
- 프론트엔드 lint/build: 프론트 변경 없음 → 생략.
- `.env` 열람: 시크릿 규칙으로 미열람.

## 한계 / 후속 위험

- 이 변경은 **데이터 끝단(가격 0)** 차단 지점만 해소한다. 분석 문서의 또 다른 차단 지점인 **스케줄러 잡 미발화(사례 15, sleep/재시작형 런타임)** 는 별개이며 미해결 — 인스턴스가 startup 잡(+지연) 전에 죽으면 리포트는 여전히 생성되지 않는다.
- FMP가 402(플랜 한도)이고 Finnhub가 지속 502이며 Stooq fallback이 off이거나 US 종목 미매핑이면, **직전 유효 스냅샷이 한 번도 없는 콜드 스타트**에서는 폴백할 stale도 없어 여전히 가격 0이 될 수 있다. 즉 최초 1회는 어느 provider든 성공해야 한다. provider 키/플랜 점검은 여전히 필요(분석 문서 권장 조치 4).
- stale 유지는 장애가 길면 오래된 가격으로 리포트를 생성할 수 있다(설계상 의도된 trade-off — "미생성 404"보다 "마지막 유효값 기반 생성"을 택함). 신선도는 리포트 메타데이터의 `data_as_of`/source 상태로 노출된다.

## Documentation

- feature: `docs/harness/features/market-data.md` (Change Records + Open Risks 갱신), `docs/harness/features/asset-detail-ai-community.md` (Change Records).
- index: `docs/harness/feature-index.md` 항목 추가.
- 분석 출처: `docs/harness/report-generation-scheduler-not-firing-log-audit-2026-06-08.md`, 에러 케이스북 사례 16.
