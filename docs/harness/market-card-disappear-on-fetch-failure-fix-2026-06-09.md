# 시세 수집 실패 시 카드 사라짐 방지 (2026-06-09)

## 목적

홈 화면에서 나스닥 100(`^NDX`)과 원/달러 환율(`KRW=X`) **카드 자체가 사라지는** 문제를 해결한다. 가격이 0으로 보이는 게 아니라 카드가 통째로 제거되는 증상이었다.

## 근본 원인

- 프론트 [Home.jsx](../../frontend/src/pages/Home.jsx) 67-68줄은 `macro[dataKey]`가 없으면 `return null` → 카드를 렌더링하지 않는다.
- 백엔드 [_collect_prices_group.collect_one](../../backend/app/services/market_service.py)은 자산 fetch가 `asyncio.TimeoutError`/예외로 실패하면 `results[label]`을 **설정하지 않고 버렸다.** 그러면 `market_cache["prices"]["macro"]`에서 그 라벨이 빠지고, `/api/market/prices` 응답에도 누락되어 프론트가 카드를 제거했다.
- 직전 작업(`docs/harness/stooq-pow-anti-bot-bypass-implementation-2026-06-09.md`)에서 stooq에 PoW 해결 단계가 추가되며 `^NDX` 스냅샷 지연이 늘었다(로컬 측정 약 5.5s). per-asset 타임아웃(`MARKET_PRICE_FETCH_TIMEOUT_SECONDS`)이 짧거나 provider semaphore 큐가 밀리는 느린/부하 환경에서는 이 지연이 타임아웃으로 이어져, 위 "실패 시 라벨 누락" 결함이 카드 삭제로 표면화됐다.

> 참고: 현재 코드(로컬)에서는 `_collect_prices_group("macro", MACRO_ASSETS)`가 약 7.76s에 5개 라벨(S&P 500/Nasdaq 100/USDKRW/KOSPI/KOSDAQ)을 모두 정상 채운다. 즉 데이터 경로 자체는 정상이며, 핵심은 "실패하면 카드가 사라지는" 취약성이다.

## 변경 파일

- `backend/app/services/market_service.py`
  - `_carry_forward_price_payload(group_name, label, ticker)` 헬퍼 추가 — 직전 유효 캐시값(`market_cache["prices"][group][label]`)을 이어 쓰고, 콜드 스타트로 직전 값이 없으면 0 placeholder를 반환.
  - `collect_one`의 `asyncio.TimeoutError`/`Exception` 처리에서 라벨을 버리는 대신 `_carry_forward_price_payload`로 `results[label]`을 항상 설정. 이로써 수집 실패가 카드 삭제로 이어지지 않는다(provider 계층의 스냅샷 stale 유지 철학과 일치).
- `backend/tests/test_market_warmup_timeout.py`
  - 기존 `test_collect_prices_group_times_out_slow_asset_without_blocking_others`를 새 동작에 맞게 갱신: 느린 자산은 timeout 후에도 라벨 유지(직전 캐시 없으면 0 placeholder), 빠른 자산은 라이브 값 유지.
  - `test_collect_prices_group_carries_forward_last_value_on_failure` 추가: 예외 시 직전 캐시값을 이어 쓰는지 검증.
  - 위 두 timeout 테스트와 뉴스 timeout 테스트에 `is_live_market_ticker`를 True로 고정 — 이 환경의 `MARKET_LIVE_TICKERS` 기본 allowlist에서는 임의 티커("FAST"/"SLOW")가 live가 아니라 mock 경로를 타서, timeout 분기가 실행되지 않아 테스트가 환경 의존적으로 실패하던 문제를 제거.

## 동작 변화

- 시세 수집이 타임아웃/예외로 실패해도 해당 카드는 **직전 유효값** 또는 **0 placeholder**로 유지된다(더 이상 사라지지 않음).
- 정상 수집 시 동작은 동일. 라이브 데이터가 들어오면 그대로 갱신된다.

## 검증

- `cd backend && .venv/Scripts/python.exe -m pytest tests/test_market_warmup_timeout.py tests/test_price_providers.py tests/test_market_history_route.py -q` → **60 passed**.
- 라이브 재현(실제 키 사용, 키 미출력): `_collect_prices_group("macro", MACRO_ASSETS)` → 7.76s, `Nasdaq 100`/`USDKRW` 포함 5개 라벨 모두 실가격으로 present.

## 후속 위험 / 미실행

- `npm run build`(프론트)는 실행하지 않음 — Home.jsx는 변경하지 않았고, 카드 삭제의 근본 원인은 백엔드 응답 누락이었다. 다만 `if (!data) return null`은 그대로이므로, 백엔드가 라벨을 항상 채우는 것이 카드 표시의 전제다.
- 0 placeholder가 카드에 잠깐 노출될 수 있다(콜드 스타트에 직전 캐시가 전혀 없고 첫 수집이 실패한 경우). 이는 카드가 사라지는 것보다 낫고, 다음 수집 주기에 라이브 값으로 교체된다.
- 배포 환경(Render 등)에서 stooq `ConnectTimeout`이 반복되면 `^NDX`/`KRW=X`가 placeholder로 고착될 수 있다. 그 경우 `STOOQ_FETCH_TIMEOUT_SECONDS`/`MARKET_PRICE_FETCH_TIMEOUT_SECONDS`와 키 일일 한도를 함께 점검한다.

## 참고

- `docs/harness/stooq-pow-anti-bot-bypass-implementation-2026-06-09.md`
- `docs/harness/market-snapshot-price-fallback-and-stale-retention-implementation-2026-06-08.md`
- `docs/harness/market-data-warmup-provider-throttle-timeout-implementation-2026-06-04.md`
