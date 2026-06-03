# 환율(USD/KRW) 등락폭 MOCK(0) 제거 — stooq 일별 종가 기반 계산

날짜: 2026-06-04

## 목적

USD/KRW(`KRW=X`) 스냅샷의 `changePercent`가 `0.0`으로 하드코딩(MOCK)되어 있어 화면에 항상 "등락 0%"로 표시되던 문제를 해결한다. 환율 데이터 소스인 open.er-api.com이 현재 환율만 제공하고 전일 종가를 주지 않아 등락폭을 계산할 수 없던 것이 원인이다.

## 원인

`backend/app/services/price_providers.py`의 `_fetch_fx_snapshot`은 open.er-api.com(`https://open.er-api.com/v6/latest/USD`)에서 현재 KRW 환율만 받아 사용했다. 전일 종가가 없으므로 `changePercent`를 `0.0`으로 고정했고, history도 현재가 단일 포인트만 만들었다.

반면 미국주식 스냅샷(`_fetch_finnhub_stock_snapshot`)은 "실시간 현재가 + 전일 종가 + stooq 과거 종가" 패턴으로 등락폭을 계산한다. FX도 동일 패턴으로 맞췄다.

## 변경 파일

- `backend/app/services/price_providers.py`
  - `STOOQ_SYMBOLS`에 `"KRW=X": "usdkrw"` 매핑 추가.
  - `_fetch_fx_snapshot`: open.er-api.com 현재 환율을 `currentPrice`로 두고, `fetch_stooq_history("KRW=X", "1mo")`의 일별 USD/KRW 종가 중 최신 종가를 전일 종가로 삼아 `changePercent`를 계산한다. `history_prices`도 stooq 종가로 채운다. stooq 키가 없거나(=`STOOQ_API_KEY` 미설정) 데이터가 없으면 기존처럼 등락 0 + 현재가 단일 포인트로 폴백한다. `provider_meta.change_source`(`"stooq"` 또는 `"none"`)로 등락 계산 출처를 표시한다.
  - `fetch_market_history`의 `KRW=X` 분기: stooq 일별 종가로 실제 시계열을 만들고, stooq 데이터가 없을 때만 open.er-api 현재가 단일 포인트로 폴백한다. 단위는 그대로 `KRW`.
- `backend/tests/test_price_providers.py`
  - `test_fx_snapshot_change_percent_from_stooq_close`: stooq 최신 종가 대비 현재 환율로 등락폭이 0이 아니게 계산되는지 검증.
  - `test_fx_snapshot_falls_back_when_stooq_empty`: stooq 데이터가 없으면 등락 0 + `change_source="none"`로 폴백하는지 검증.

## 동작 변화

- `STOOQ_API_KEY`가 설정되어 있고 stooq에 USD/KRW 일별 종가가 있으면, USD/KRW 스냅샷의 `changePercent`가 실제 값으로 계산된다(더 이상 0 고정 아님).
- USD/KRW history(`GET /api/market/history/KRW=X`)가 단일 포인트가 아니라 stooq 일별 종가 시계열을 반환한다.
- `STOOQ_API_KEY`가 없거나 stooq 응답이 비면 기존과 동일하게 동작한다(등락 0, 현재가 단일 포인트). 가용성 회귀 없음.

## 검증

- `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_price_providers.py -q` → 12 passed (신규 2건 포함).

## 미실행 / 후속 위험

- `npm run build`/`npm run lint`은 프론트엔드 변경이 없어 실행하지 않음(백엔드 제공 데이터 형식은 동일 키 유지).
- 실제 stooq `usdkrw` 일별 종가의 신선도는 stooq 무료 데이터에 의존한다. open.er-api 현재가와 stooq 최신 종가의 기준 시점이 달라 등락폭은 "마지막 일별 종가 대비 현재 환율" 의미이며, 거래소 실시간 등락과 미세하게 다를 수 있다(finnhub 주식 스냅샷과 동일한 한계).
- `STOOQ_API_KEY` 미설정 배포에서는 여전히 등락 0으로 표시된다.
