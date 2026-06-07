# 시장 데이터 무료 플랜 기반 Stooq 대체 계획

Date: 2026-06-07
Status: Plan
Feature:
- `docs/harness/features/market-data.md`

## Objective

Stooq가 Render 배포 환경에서 `ConnectTimeout('')`로 반복 실패하는 문제를 근본적으로 줄이기 위해, Stooq를 primary provider에서 제외하고 무료 플랜/무료 공개 API만으로 시장 데이터 수집 경로를 재구성한다.

이 계획은 유료 API 전환을 전제로 하지 않는다. 모든 provider는 무료 플랜 또는 무료 공개 API 범위에서만 사용하며, 호출량을 줄이기 위해 현재 프로젝트의 cache/warm-up/scheduler 구조를 유지한다.

## Free-Plan Assumptions

- Financial Modeling Prep(FMP) Basic 무료 플랜은 `250 Calls / Day`, `End of Day Historical Data`, `Profile and Reference Data`를 제공하는 것으로 본다. FMP 문서상 crypto/forex는 Starter 이상 항목으로 표시되므로 무료 플랜 설계에서는 crypto/forex primary로 사용하지 않는다.
- Twelve Data Basic 무료 플랜은 `8 API credits/min`, `800/day`이며 real-time forex/crypto market data를 표시하지만, `Internal non-display usage` 문구가 있어 공개 사용자 화면 표시에는 약관 리스크가 있다. 따라서 공개 화면 primary로 바로 도입하지 않고 USD/KRW 보조 후보로만 둔다.
- CoinGecko Demo 무료 플랜은 BTC/ETH 현재가, 시총, 히스토리용으로 유지한다. 월간 호출량과 분당 제한이 있으므로 scheduler/cache 경유만 허용한다.
- 공공데이터포털 금융위원회 API는 한국 주식/KOSPI 데이터용으로 유지한다. T+1 지연과 간헐적 gateway block은 정상 edge case로 취급한다.
- FRED와 한국은행 ECOS는 미국/한국 채권 금리용으로 유지한다.
- 무료 플랜은 SLA/상업적 표시 권한/재배포 권한이 제한될 수 있다. 졸업작품 데모 또는 내부 검증 범위에서는 사용하되, 공개 상용 서비스로 전환할 경우 provider 약관과 표시 라이선스를 재검토한다.

## Target Provider Matrix

| Asset group | Current weak path | Free-plan target path | Notes |
| --- | --- | --- | --- |
| Nasdaq 100, S&P 500 | Stooq daily CSV | FMP Basic EOD quote/history if endpoint coverage allows | Intraday/realtime을 약속하지 않고 EOD/delayed 시장 데이터로 표시한다. |
| USD/KRW | open.er-api.com + Stooq change calculation | open.er-api.com primary, Twelve Data Basic only as optional non-display/internal fallback candidate | 무료 공개 화면에서는 open.er-api.com 기준 일일 reference FX로 표시한다. 등락률은 provider가 없으면 `0` 또는 이전 cache 기반으로 제한한다. |
| KOSPI | data.go.kr | data.go.kr 유지 | `idxNm=코스피` 한글명 매칭 유지. |
| US stocks top10 | Finnhub quote + Stooq optional history | Finnhub quote 유지, FMP Basic EOD history/profile/market cap 보조 | 무료 호출량 때문에 top10은 고정 대표 리스트를 유지하고, 실시간 시총 랭킹 산출은 하지 않는다. |
| KR stocks top10 | data.go.kr | data.go.kr 유지 | `mrktTotAmt` 기반 시총 표시. 무료 플랜 내에서는 실시간 ranking refresh 대신 고정 대표 리스트 또는 낮은 빈도 재계산만 허용한다. |
| US bonds 3M/10Y | FRED | FRED 유지 | `DGS3MO`, `DGS10`. |
| KR bonds 1Y/10Y/30Y | ECOS | ECOS 유지 | `817Y002` + item code 매핑 유지. |
| Gold/Silver | Stooq daily CSV | FMP Basic EOD quote/history if endpoint coverage allows | FMP 무료에서 해당 symbol이 막히면 stale cache 또는 빈 payload로 degrade한다. |
| BTC/ETH | CoinGecko Demo | CoinGecko Demo 유지 | `simple/price`, `market_chart`를 scheduler/cache 경유로만 사용한다. |

## Design Principles

1. **무료 플랜 호출량 우선**
   - Market warm-up과 scheduler만 외부 provider를 호출한다.
   - 사용자 요청, 챗봇, asset detail 클릭은 cache/stored report를 읽는다.
   - FMP Basic `250/day` 기준으로 미국 지수 2개, 원자재 2개, 미국 주식 10개를 매 5분 갱신하면 즉시 한도를 초과한다. FMP 대상은 별도 느린 cadence 또는 12시간 TTL을 둔다.

2. **Stooq primary 제거**
   - `fetch_stooq_history()`는 구현 직후 바로 삭제하지 않고 compatibility fallback으로 남긴다.
   - 새 FMP path가 성공하면 미국 지수/원자재/미국 주식 history는 FMP를 먼저 사용한다.
   - Stooq는 `ENABLE_STOOQ_FALLBACK=true` 같은 opt-in fallback으로 격하하거나, 무료 플랜 안정화 후 제거한다.

3. **데이터 신선도 표현 정직화**
   - FMP Basic 기반 데이터는 EOD/delayed로 표시한다.
   - `provider_meta`에 `provider`, `as_of`, `freshness`, `license_scope`, `change_source`를 넣어 frontend와 report fact builder가 과장하지 않게 한다.
   - USD/KRW는 open.er-api.com daily reference로 명시하고 trading-grade realtime FX로 표현하지 않는다.

4. **무료 약관 리스크 격리**
   - Twelve Data Basic은 `Internal non-display usage` 문구가 있으므로 공개 사용자 화면 primary로 사용하지 않는다.
   - FMP도 data display/redistribution에는 별도 licensing agreement가 필요할 수 있으므로, 무료 플랜은 졸업작품 데모/개발 검증 범위로 문서화한다.

## Implementation Plan

### Phase 1. Configuration and provider scaffolding

- `backend/app/core/config.py`
  - `FMP_API_KEY`가 이미 있으면 재사용하고, 없으면 추가한다.
  - `FMP_FETCH_TIMEOUT_SECONDS`, `FMP_DAILY_CALL_BUDGET`, `ENABLE_STOOQ_FALLBACK`를 추가한다.
- `.env.example`, `ENVIRONMENT_VARIABLE_SETUP.md`
  - FMP Basic 무료 플랜 전제와 `250/day` 한도, EOD/delayed 성격, display licensing 주의사항을 기록한다.
- `backend/app/services/price_providers.py`
  - `FMP_BASE_URL`와 `_fmp_key()`, `_fetch_fmp_json()`, provider semaphore/cooldown/cache key를 추가한다.
  - FMP 예외 로그는 `redact_secrets()`를 통과시켜 API key가 URL에 노출되지 않게 한다.

### Phase 2. FMP EOD path for Stooq-backed assets

- 미국 지수
  - `^GSPC`, `^NDX`를 FMP symbol로 매핑한다.
  - 현재가/등락률은 FMP 무료 endpoint가 제공하는 EOD quote 또는 latest historical close에서 계산한다.
- 원자재
  - `XAU`, `XAG`를 FMP에서 허용되는 gold/silver symbol로 매핑한다.
  - symbol coverage가 무료 플랜에서 실패하면 빈 payload 또는 stale cache로 degrade한다.
- 미국 주식 history/profile
  - Finnhub quote는 유지한다.
  - Stooq history 대신 FMP EOD historical path를 먼저 시도한다.
  - market cap/profile은 FMP Basic 또는 기존 Finnhub profile 중 더 안정적인 값을 사용하되, 실패해도 quote를 버리지 않는다.

### Phase 3. FX, crypto, KR, bond paths keep their free providers

- USD/KRW
  - open.er-api.com을 primary로 유지한다.
  - Stooq 기반 change calculation은 제거하거나 opt-in fallback으로 격하한다.
  - 등락률을 계산할 reliable free public source가 없으면 `changePercent=0`, `provider_meta.change_source=none`으로 둔다.
- BTC/ETH
  - CoinGecko Demo를 유지한다.
  - `COINGECKO_DEMO_API_KEY`가 없으면 현재처럼 빈 응답으로 degrade한다.
- 한국 주식/KOSPI
  - data.go.kr를 유지한다.
  - top10은 무료 API 한도와 응답 지연을 고려해 고정 대표 리스트를 유지한다. 시총 기반 자동 top10 재계산은 낮은 빈도 batch 또는 후속 계획으로 분리한다.
- 채권
  - FRED/ECOS 유지. 이번 변경 대상에서 제외한다.

### Phase 4. Cache and scheduler tuning

- FMP 대상 asset은 별도 TTL을 길게 둔다.
  - 추천: snapshot/history cache 12시간, failed-call cooldown 30분.
  - market price scheduler가 5분마다 돌더라도 FMP cache hit이면 외부 호출하지 않게 한다.
- FMP 호출량 budget guard를 둔다.
  - process-local daily counter로 `FMP_DAILY_CALL_BUDGET` 초과 시 provider call을 skip한다.
  - 기본값은 180 이하로 둬 FMP 무료 `250/day`에 여유를 남긴다.
- provider concurrency는 `Semaphore(1)`을 유지한다.

### Phase 5. Tests

- `backend/tests/test_price_providers.py`
  - FMP key 없음 degrade.
  - FMP quote/history success normalization.
  - FMP daily budget exceeded skip.
  - FMP failure does not discard Finnhub quote.
  - Stooq fallback disabled by default.
  - USD/KRW keeps open.er-api.com value without Stooq.
- `backend/tests/test_market_warmup_timeout.py`
  - FMP 대상이 per-asset timeout 안에서 skip/degrade되는지 확인한다.
- Optional compile check
  - `.\backend\.venv\Scripts\python.exe -m compileall backend\app`

## Files Expected To Change

- `backend/app/core/config.py`
- `backend/app/services/price_providers.py`
- `backend/tests/test_price_providers.py`
- `.env.example`
- `ENVIRONMENT_VARIABLE_SETUP.md`
- `docs/harness/features/market-data.md`
- `docs/harness/feature-index.md`
- 구현 시 별도 implementation record: `docs/harness/market-data-free-plan-stooq-replacement-implementation-2026-06-07.md`

## Verification Plan

```powershell
cd backend
..\backend\.venv\Scripts\python.exe -m pytest tests\test_price_providers.py
..\backend\.venv\Scripts\python.exe -m pytest tests\test_market_warmup_timeout.py
cd ..
.\backend\.venv\Scripts\python.exe -m compileall backend\app
```

Frontend 표시 문구나 provider metadata UI를 바꾸는 경우:

```powershell
cd frontend
npm run build
```

## Non-Goals

- 유료 API 플랜 도입.
- 사용자 요청 또는 챗봇 요청에서 fresh external provider call 실행.
- AI 리포트 fresh generation trigger 추가.
- 미국/한국 top10을 매 요청마다 실시간 시총 순위로 재계산.
- Intraday/realtime 차트 복구.

## User-Facing Report Generation Impact

없음. 이 변경은 market cache provider 교체 계획이며, 사용자-facing 요청과 챗봇 요청은 계속 저장된 scheduled report만 읽는다. ordinary user request가 새 리포트 생성을 트리거하지 않는다.

## Risks And Follow-Up

- FMP Basic 무료 플랜은 EOD 중심이므로 미국 지수/원자재/미국 주식 history는 실시간이 아니다.
- FMP 무료 symbol coverage가 제한될 수 있다. 특히 지수/원자재 symbol은 실제 endpoint probing 후 매핑을 확정해야 한다.
- FMP/Twelve Data 무료 플랜은 display/redistribution 약관 제약이 있을 수 있다. 공개 배포 범위가 커지면 라이선스 확인이 필요하다.
- process-local daily budget counter는 서버 재시작 시 초기화된다. 무료 한도 초과를 더 엄격히 막으려면 DB/Redis 기반 provider usage ledger가 필요하다.
- Stooq fallback을 완전히 제거하면 FMP 무료 coverage 실패 시 미국 지수/원자재 최초 warm-up이 빈 값으로 degrade될 수 있다. 구현 초기는 opt-in fallback 또는 stale cache를 함께 유지한다.

## References Checked

- FMP Pricing: `https://site.financialmodelingprep.com/developer/docs/pricing`
- Twelve Data Pricing: `https://twelvedata.com/pricing`
- CoinGecko Pricing: `https://www.coingecko.com/en/api/pricing`
- Finnhub API quote docs: `https://api.finnhub.io/docs/api/quote`
- FRED API observations: `https://fred.stlouisfed.org/docs/api/fred/series_observations.html`
- 공공데이터포털 금융위원회 주식시세정보: `https://www.data.go.kr/data/15094808/openapi.do`
