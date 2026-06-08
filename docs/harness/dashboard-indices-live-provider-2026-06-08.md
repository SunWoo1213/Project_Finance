# 메인 대시보드 지수 4개 live provider 전환

Date: 2026-06-08

## Objective

API 호출량 절감을 위해 도입한 `MARKET_LIVE_TICKERS` allowlist 때문에 메인 대시보드(Home)에 표시되는 지수·환율 4개가 `demo_mock` 값으로 응답되고 있었다. 데모 화면 첫 인상인 이 4개는 실제 provider 데이터를 보여주도록 allowlist 기본값에 추가한다. 나머지 자산은 그대로 mock으로 유지해 호출량 절감 효과를 보존한다.

## 대상 ticker

메인 대시보드(`frontend/src/pages/Home.jsx`)의 `targetIndices`:

- `^GSPC` (S&P 500) — INDEX → FMP quote/EOD (+ opt-in Stooq `^spx` fallback)
- `^NDX` (Nasdaq 100) — INDEX → FMP quote/EOD (+ opt-in Stooq `^ndx` fallback)
- `KRW=X` (원/달러 환율) — FX → open.er-api.com 일일 기준환율 (+ opt-in Stooq `usdkrw` fallback)
- `^KS11` (KOSPI) — KR INDEX → 공공데이터포털 `getStockMarketIndex`(`코스피`)

KOSDAQ(`^KQ11`)는 대시보드에 표시되지 않으므로 allowlist에 넣지 않고 mock을 유지한다.

## Files Changed

- `backend/app/core/config.py` — `MARKET_LIVE_TICKERS` 기본값에 `^GSPC,^NDX,KRW=X,^KS11` 추가.
- `backend/app/services/demo_market_data.py` — `DEFAULT_LIVE_TICKERS` 기본값을 config와 동일하게 맞춤.
- `docs/harness/features/market-data.md` — allowlist 기본값 설명 갱신, 본 기록 링크 추가.
- `docs/harness/feature-index.md` — market-data 항목 갱신.
- `docs/harness/dashboard-indices-live-provider-2026-06-08.md` — 본 변경 기록.

변경 후 기본값: `DGS10,XAU,BTC-USD,NVDA,005930.KS,^GSPC,^NDX,KRW=X,^KS11`

## Behavior Changes

- `is_live_market_ticker()`가 위 4개 ticker에 대해 `True`를 반환하므로, 가격(`update_prices_task`/`ensure_price_cache_for_ticker`), 뉴스, latest-context, history 경로가 mock 대신 실제 provider를 호출한다.
- 대시보드 macro 카드(S&P 500, Nasdaq 100, 원/달러, KOSPI)가 실데이터(또는 provider 실패 시 stale/0 폴백)로 표시된다.
- allowlist 밖 자산의 mock 동작은 그대로다. KOSDAQ 포함 다른 지수·종목은 여전히 `demo_mock`.
- AI 리포트 생성 정책은 변경하지 않았다. user-facing 요청은 fresh report를 트리거하지 않고 저장된 scheduled report만 읽는다.

## Verification Performed

- 코드 정적 검토: 4개 ticker가 `price_providers.py`의 `STOOQ_SYMBOLS`/`FMP_SYMBOL_CANDIDATES`/`KR_INDEX_NAMES` 및 `fetch_market_snapshot`의 FX/INDEX/KR 분기에서 지원됨을 확인.
- 기존 테스트는 `MARKET_LIVE_TICKERS`를 monkeypatch로 명시 설정하므로 기본값 변경의 영향을 받지 않는다.

## Commands Not Run

- 실제 provider smoke는 무료 플랜 quota 절약을 위해 실행하지 않았다. 배포 환경에서 첫 1회 provider 성공과 키/플랜 점검 필요.
- `python -m pytest`는 본 변경이 기본값 상수만 바꾸고 기존 monkeypatch 테스트에 영향이 없어 생략 가능하나, 회귀 확인이 필요하면 `tests/test_price_providers.py tests/test_market_history_route.py` 실행 권장.

## Follow-up Risks

- 실제 배포의 `.env`에 `MARKET_LIVE_TICKERS`가 명시되어 있으면 코드 기본값이 무시된다. 이 경우 `.env`(및 `.env.example`)의 값에 `^GSPC,^NDX,KRW=X,^KS11`을 직접 추가해야 한다. `.env.example`은 하네스 권한상 직접 편집이 차단되어 본 작업에서 수정하지 못했다.
- 4개 ticker가 다시 live 경로를 타므로 FMP 일일 호출 budget, data.go.kr rate-limit, open.er-api.com 일일 기준환율 한계가 다시 적용된다. 호출량은 5분 가격 스케줄 + warm-up 기준으로 소폭 증가한다.
- `KRW=X`는 open.er-api.com 일일 기준환율이라 `changePercent`가 0일 수 있고(이전 종가 미제공), Stooq fallback은 opt-in이다.

## Feature Links

- `docs/harness/features/market-data.md`
