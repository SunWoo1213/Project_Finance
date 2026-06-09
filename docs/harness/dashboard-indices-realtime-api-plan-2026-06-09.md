# 메인 대시보드 지수 실시간 API 전환 계획

Date: 2026-06-09

## Objective

메인 대시보드(`/`)의 주요 지수·환율 카드 4개(S&P 500, Nasdaq 100, 원/달러 환율, KOSPI)가 deterministic `demo_mock` 값이 아니라 기존 시장 데이터 API와 provider 캐시를 통해 실제 데이터로 표시되도록 전환한다.

이 계획은 새 외부 API를 프론트에서 직접 호출하지 않고, 현재 프로젝트의 표준 흐름인 `frontend -> FastAPI /api/market/prices -> market_cache -> provider service` 구조를 재사용한다.

## Current Code Findings

- 프론트 홈 화면은 이미 `apiClient`로 `GET /api/market/prices`와 `GET /api/market/news`를 호출한다.
  - `frontend/src/pages/Home.jsx:17`
  - `frontend/src/pages/Home.jsx:25`
- 홈 카드 4개는 `priceResult.value.data.macro`에서 아래 key를 읽는다.
  - `S&P 500` -> `^GSPC`
  - `Nasdaq 100` -> `^NDX`
  - `USDKRW` -> `KRW=X`
  - `KOSPI` -> `^KS11`
  - `frontend/src/pages/Home.jsx:51`
- 백엔드 공개 가격 API는 별도 DB 조회 없이 인메모리 `market_cache["prices"]`를 그대로 반환한다.
  - `backend/app/main.py:370`
- `update_prices_task()`는 `macro` 그룹을 포함한 전체 가격 캐시를 갱신한다.
  - `backend/app/services/market_service.py:393`
  - `backend/app/services/market_service.py:395`
- `MACRO_ASSETS`는 `INDICES`와 `FX`로 구성되어 홈 카드 4개를 모두 포함한다.
  - `backend/app/services/market_service.py:174`
- 실제 provider 호출 여부는 `is_live_market_ticker()`가 `settings.MARKET_LIVE_TICKERS` allowlist로 결정한다.
  - `backend/app/services/demo_market_data.py:34`
  - `backend/app/services/demo_market_data.py:40`
- 현재 실제 코드 기준 `Settings.MARKET_LIVE_TICKERS` 기본값은 `DGS10,XAU,BTC-USD,NVDA,005930.KS`로, 홈 카드 4개가 빠져 있다.
  - `backend/app/core/config.py:97`
- `.env.example`도 같은 5개 기본값을 안내한다.
  - `.env.example:243`
- 반면 `docs/harness/dashboard-indices-live-provider-2026-06-08.md`는 이미 홈 4개를 allowlist에 추가했다고 기록한다. 현재 코드와 문서가 충돌하므로, 후속 구현 시 현재 코드를 기준으로 다시 정합화해야 한다.
- `demo_market_data.py`의 `DEFAULT_LIVE_TICKERS`에는 홈 4개가 포함되어 있지만, `settings.MARKET_LIVE_TICKERS`의 기본 문자열이 비어 있지 않으므로 일반 실행에서는 이 fallback 기본값이 우선되지 않는다.
  - `backend/app/services/demo_market_data.py:8`

## Existing Provider Paths

| Dashboard item | Ticker | Backend category | Provider path | Required runtime config |
| --- | --- | --- | --- | --- |
| S&P 500 | `^GSPC` | `INDEX` | `fetch_market_snapshot()` -> `_fetch_fmp_snapshot()` | `FMP_API_KEY`; optional `ENABLE_STOOQ_FALLBACK=true` + `STOOQ_API_KEY` |
| Nasdaq 100 | `^NDX` | `INDEX` | `fetch_market_snapshot()` -> `_fetch_fmp_snapshot()` | `FMP_API_KEY`; optional `ENABLE_STOOQ_FALLBACK=true` + `STOOQ_API_KEY` |
| 원/달러 환율 | `KRW=X` | `FX` | `fetch_market_snapshot()` -> `_fetch_fx_snapshot()` -> open.er-api.com | no key for open.er-api.com; optional Stooq fallback for change/history |
| KOSPI | `^KS11` | `INDEX` | `fetch_market_snapshot()` -> data.go.kr index path via `KR_INDEX_NAMES` | `DATA_GO_KR_API_KEY` |

Important constraints:

- `KRW=X`의 기본 open.er-api.com 경로는 일일 기준환율 성격이며, 이전 종가가 없으면 `changePercent=0.0`이 정상적으로 나올 수 있다.
- `^GSPC`, `^NDX`는 FMP free/basic 플랜과 quota 영향을 받는다. FMP 실패 시 Stooq fallback은 opt-in이다.
- `^KS11`은 공공데이터포털 `getStockMarketIndex`를 사용하며, data.go.kr 응답 지연과 gateway block 가능성을 고려해야 한다.
- 이 전환은 AI 리포트 생성 정책을 바꾸지 않는다. 사용자 요청, 홈 진입, 챗봇 요청은 fresh report generation을 트리거하지 않는다.

## Target Behavior

1. 백엔드 기본 설정과 문서의 `MARKET_LIVE_TICKERS`에 `^GSPC,^NDX,KRW=X,^KS11`를 포함한다.
2. 메인 대시보드 홈 카드는 기존 `/api/market/prices` 응답의 `macro` 그룹을 계속 사용한다.
3. allowlist 안의 홈 4개 ticker는 가격 warm-up, scheduler refresh, history, latest-context에서 mock 대신 live provider 경로를 탄다.
4. allowlist 밖의 자산은 기존처럼 `demo_mock` fallback을 유지해 무료 provider 호출량을 통제한다.
5. provider 실패 시 현재의 빈 값, stale snapshot, `0` fallback 정책을 유지하되, 검증 단계에서 카드가 조용히 사라지지 않는지 확인한다.

## Implementation Plan

### 1. Allowlist 기본값 정합화

- `backend/app/core/config.py`
  - `MARKET_LIVE_TICKERS` 기본값을 다음으로 변경한다.

```text
DGS10,XAU,BTC-USD,NVDA,005930.KS,^GSPC,^NDX,KRW=X,^KS11
```

- `backend/app/services/demo_market_data.py`
  - `DEFAULT_LIVE_TICKERS`가 위 값과 동일한지 확인한다. 현재는 이미 동일한 방향이므로, 필요 시 중복 상수를 줄이는 follow-up을 검토한다.
- `.env.example`
  - `MARKET_LIVE_TICKERS` 주석을 "무료 API 데모 기본값은 대표 5개 + 홈 대시보드 4개 live"로 갱신한다.
  - 예시 값도 동일하게 갱신한다.
- 운영/배포 환경
  - 실제 `.env`, Render, Railway, Fly.io, 또는 기타 backend secret store에 `MARKET_LIVE_TICKERS`가 명시되어 있으면 코드 기본값이 무시된다.
  - 하네스는 `.env`를 열지 말고, 배포 담당자가 아래 값을 설정하도록 안내한다.

```text
MARKET_LIVE_TICKERS=DGS10,XAU,BTC-USD,NVDA,005930.KS,^GSPC,^NDX,KRW=X,^KS11
```

### 2. Home 데이터 흐름 유지

- `frontend/src/pages/Home.jsx`는 새 provider를 직접 호출하지 않는다.
- 현재 `apiClient.get('/api/market/prices')` 흐름을 유지한다.
- 필요 시 빈 macro payload일 때 카드 전체가 사라지는 현상을 줄이기 위해 다음 UI 보강을 별도 범위로 검토한다.
  - `marketData[dataKey]`가 없으면 카드 자리에는 "데이터 대기 중" 상태를 표시.
  - `provider_meta.provider === "demo_mock"` 같은 진단 정보가 필요하면 백엔드 payload가 `provider_meta`를 보존하도록 후속 변경.

### 3. Provider 및 fallback 정책 확인

- `^GSPC`, `^NDX`
  - FMP key가 없거나 quota가 소진되면 현재 구조상 빈/0 payload가 될 수 있다.
  - 운영에서 무료 fallback이 필요하면 `ENABLE_STOOQ_FALLBACK=true`와 `STOOQ_API_KEY`를 별도 승인 후 설정한다.
- `KRW=X`
  - open.er-api.com 기본 경로는 key 없이 동작한다.
  - 등락률이 중요하면 Stooq fallback을 opt-in으로 켜야 한다.
- `^KS11`
  - `DATA_GO_KR_API_KEY`가 필요하다.
  - data.go.kr 지연이 반복되면 `DATA_GO_KR_FETCH_TIMEOUT_SECONDS`, `DATA_GO_KR_MAX_CONCURRENCY`, `MARKET_PRICE_FETCH_TIMEOUT_SECONDS`를 기존 가드레일 안에서 조정한다.

### 4. 테스트 추가 또는 갱신

- `backend/tests/`에서 allowlist 기본값 또는 live/mock 분기 테스트를 추가한다.
  - `settings.MARKET_LIVE_TICKERS` 기본값에 홈 4개가 포함되는지 확인.
  - `is_live_market_ticker("^GSPC")`, `is_live_market_ticker("^NDX")`, `is_live_market_ticker("KRW=X")`, `is_live_market_ticker("^KS11")`가 true인지 확인.
  - allowlist 밖 ticker는 계속 false/mock인지 확인.
- 실제 provider smoke는 quota를 소모하므로 기본 자동 테스트에는 넣지 않는다.

### 5. 문서 정합화

- `docs/harness/features/market-data.md`
  - `MARKET_LIVE_TICKERS` 기본값 설명을 대표 5개 + 홈 4개로 갱신한다.
  - 본 계획 또는 후속 구현 기록을 `Change Records`에 추가한다.
- `docs/harness/feature-index.md`
  - Market data change records에 후속 구현 기록을 연결한다.
- 기존 `docs/harness/dashboard-indices-live-provider-2026-06-08.md`
  - 현재 코드와 어긋난 부분이 있음을 후속 구현 기록에서 명시한다. 기존 기록을 삭제하지 않는다.

## Verification Plan

1. 정적 확인
   - `rg -n "MARKET_LIVE_TICKERS|DEFAULT_LIVE_TICKERS" backend/app/core/config.py backend/app/services/demo_market_data.py .env.example`
   - `rg -n "targetIndices|priceResult.value.data.macro" frontend/src/pages/Home.jsx`
2. 백엔드 단위 테스트
   - `cd backend`
   - `pytest tests/test_price_providers.py tests/test_market_history_route.py`
   - allowlist 기본값 테스트를 추가했다면 해당 테스트 파일도 함께 실행.
3. 프론트 빌드
   - `cd frontend`
   - `npm run build`
4. 로컬 smoke
   - backend 실행 후 `GET /api/market/prices`의 `macro` 그룹에서 4개 key가 존재하는지 확인.
   - provider key가 없는 환경에서는 실패/0/fallback 가능성을 결과와 함께 기록.
   - frontend dev server에서 `/`를 열어 카드 4개가 표시되는지 확인.
5. 배포 smoke
   - backend 환경변수의 `MARKET_LIVE_TICKERS` 실제 값을 확인한다. 값 자체에 secret은 없지만 `.env` 내용은 출력하지 않는다.
   - frontend `VITE_API_BASE_URL`이 배포 backend origin을 가리키는지 확인하고 재배포한다.
   - 배포 `/api/market/prices`와 `/` 홈 카드 표시를 확인한다.

## Commands Not Run

- 본 작업은 계획서 작성만 수행했으므로 테스트와 빌드는 실행하지 않았다.
- `.env`는 시크릿 보호 규칙에 따라 열람하지 않았다.
- 실제 provider smoke는 API quota와 키 상태에 영향을 줄 수 있어 구현 단계 검증으로 남긴다.

## Follow-up Risks

- 배포 환경에 `MARKET_LIVE_TICKERS`가 이미 설정되어 있으면 코드 기본값 변경만으로는 홈 4개가 live로 전환되지 않는다.
- FMP 무료 플랜이 지수 quote/history에 제한을 걸면 `^GSPC`, `^NDX`는 `0` 또는 빈 history로 degrade될 수 있다.
- KOSPI data.go.kr 경로는 느리거나 gateway block이 날 수 있다. retry를 공격적으로 늘리면 rate-limit 위험이 커진다.
- `KRW=X`는 기본적으로 등락률이 0일 수 있다. "실시간 환율 등락률"까지 요구하면 별도 provider 선택과 비용/라이선스 검토가 필요하다.
- 현재 `market_cache`는 인메모리라 프로세스 재시작 직후에는 warm-up 완료 전 홈 카드가 비거나 일부만 표시될 수 있다.

## Feature Links

- `docs/harness/features/market-data.md`
- `docs/harness/feature-index.md`
- `docs/harness/dashboard-indices-live-provider-2026-06-08.md`
