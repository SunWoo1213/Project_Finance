# Live ticker allowlist + mock market fallback implementation

Date: 2026-06-08

## Objective

무료 API 기반 데모에서 시장 데이터 provider 호출량을 극단적으로 줄이기 위해 실제 provider 호출 허용 ticker를 `DGS10,XAU,BTC-USD,NVDA,005930.KS`로 제한했다. 허용 목록 밖의 자산은 가격, 뉴스, latest-context, history 모두 로컬 deterministic mock 데이터로 응답한다.

## Files Changed

- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/app/services/demo_market_data.py`
- `backend/app/services/market_service.py`
- `backend/tests/test_price_providers.py`
- `backend/tests/test_market_history_route.py`
- `.env.example`
- `docs/harness/features/market-data.md`
- `docs/harness/feature-index.md`
- `docs/harness/market-live-ticker-mock-fallback-implementation-2026-06-08.md`

## Behavior Changes

- `MARKET_LIVE_TICKERS` 설정을 추가했다. 기본값은 `DGS10,XAU,BTC-USD,NVDA,005930.KS`다.
- `MARKET_LIVE_TICKERS=*`로 설정하면 기존처럼 전체 ticker가 live provider 경로를 탈 수 있다.
- `update_prices_task()` / `update_news_task()`는 allowlist 밖 ticker에 대해 외부 provider를 호출하지 않고 `demo_mock` payload를 채운다.
- `GET /api/market/latest-context/{ticker}`는 allowlist 밖 ticker에 대해 provider 뉴스/이벤트 호출 없이 mock latest-context를 반환하고 캐시에 저장한다.
- `GET /api/market/history/{ticker}`는 allowlist 밖 ticker에 대해 FRED/ECOS/FMP/CoinGecko/data.go.kr/Stooq 등 provider를 호출하지 않고 period별 mock points를 반환한다.
- AI 리포트 생성 정책 자체는 변경하지 않았다. user-facing 요청은 여전히 fresh report generation을 트리거하지 않고 저장된 scheduled report만 읽는다.

## Verification Performed

- `python -m pytest tests/test_price_providers.py tests/test_market_history_route.py`
  - 결과: 39 passed, 1 warning
  - warning: 기존 `langchain_community.tools.DuckDuckGoSearchResults` deprecation warning

## Commands Not Run

- 실제 provider smoke는 API quota 절약 목적의 변경이므로 실행하지 않는다.

## Follow-up Risks

- mock 데이터는 데모 표시용이며 실제 투자 판단용 데이터가 아니다. 사용자 UI에 source/freshness 표시가 필요하면 후속으로 mock 배지를 노출하는 것이 좋다.
- allowlist에 없는 주요 지수와 환율도 mock으로 표시된다. 데모에서 특정 화면의 실데이터가 필요하면 `MARKET_LIVE_TICKERS`에 해당 ticker를 명시하거나 `*`로 전환해야 한다.
- provider 호출량은 줄지만, 허용 5개 ticker의 provider key/무료 플랜 한도 문제는 여전히 남는다.

## Feature Links

- `docs/harness/features/market-data.md`
