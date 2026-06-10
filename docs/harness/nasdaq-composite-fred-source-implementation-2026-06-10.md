# 나스닥 카드 FRED NASDAQ Composite 전환 + USD/KRW 등락 삭제 구현

Date: 2026-06-10

## 목적

메인 대시보드 나스닥 카드를 **Stooq → FRED NASDAQ Composite(`NASDAQCOM`)** 로 전환하고(방식 A: 캐노니컬 티커 `^NDX`→`^IXIC`, 라벨 "Nasdaq Composite"), **USD/KRW 전일 대비 등락 표시·계산을 삭제**한다. 두 변경의 결과로 Stooq가 라이브 기본 경로에서 완전히 빠진다.

계획서: [nasdaq-composite-fred-source-plan-2026-06-10.md](nasdaq-composite-fred-source-plan-2026-06-10.md)

## 배경

Stooq 무료 apikey CSV 경로가 막혀(새 키로도 `^ndq`·`aapl.us`·`^spx`·`usdkrw` 전부 빈 200, `.com`/`.pl` 동일, PoW는 성공) 나스닥/환율 등락이 안 나왔다. 키 재발급으로 해결 불가한 외부 변경이라 provider를 FRED로 전환했다. FRED는 이미 `DGS10` 연동·유효 키가 있고 무료·캡차/PoW 없음. 실측으로 `NASDAQCOM` 정상 수신 확인.

## 변경 파일

### Backend
- [price_providers.py](../../backend/app/services/price_providers.py)
  - `STOOQ_PRIMARY_SYMBOLS`를 빈 집합으로(나스닥 Stooq 1차 제거). `STOOQ_FX_SYMBOLS`도 빈 집합으로(KRW Stooq 제거).
  - `FRED_OBSERVATIONS_URL`, `FRED_INDEX_SYMBOLS = {"^IXIC": "NASDAQCOM"}` 상수, `_fred_key()` 추가.
  - `fetch_fred_history(ticker, period)` 추가: FRED 관측치를 history payload로. 결측치 `"."`는 desc 응답 기준 직전(더 최신) 유효값 carry-forward, 오래된→최신 정렬. 12h 캐시·실패 쿨다운·stale 유지. 키는 응답/로그에 노출 안 함(`redact_secrets`).
  - `_fetch_fred_snapshot(ticker)` 추가: 등락 = FRED 최신 관측일(`points[-1]`) vs 직전 관측일(`points[-2]`) day-over-day. `provider_meta.provider="fred"`, `as_of=최신일`.
  - `fetch_market_snapshot`/`fetch_market_history` INDEX 분기에 `FRED_INDEX_SYMBOLS` 라우팅 추가(Stooq primary보다 우선).
  - `_fetch_fx_snapshot`: Stooq 일별 종가 호출·등락 계산 블록 제거. 현재가(open.er-api live_rate)만, `changePercent=0.0`, `history_prices=[현재가]`, `change_source="none"`.
  - `fetch_market_history`의 `KRW=X` 분기: Stooq 호출 제거, 현재가 1점만.
- [market_service.py](../../backend/app/services/market_service.py): `INDICES`의 `"Nasdaq 100": "^NDX"` → `"Nasdaq Composite": "^IXIC"`.
- [config.py](../../backend/app/core/config.py): `MARKET_LIVE_TICKERS` 기본값 `^NDX` → `^IXIC`.
- [demo_market_data.py](../../backend/app/services/demo_market_data.py): `DEFAULT_LIVE_TICKERS` `^NDX`→`^IXIC`, mock `"^NDX": 19042.11` → `"^IXIC": 25318.45`.
- [chat_tools.py](../../backend/app/services/chat_tools.py): alias `"^NDX"` → `"^IXIC"`(나스닥/nasdaq/composite/종합 키워드 포함). 후보 등록은 `INDICES` 기반이라 자동 반영.
- [chat_grounding.py](../../backend/app/services/chat_grounding.py): USD 단위 지수 집합 `{"^GSPC", "^NDX"}` → `{"^GSPC", "^IXIC"}`.

### Frontend
- [constants.js](../../frontend/src/utils/constants.js): `"^NDX": "Nasdaq 100"` → `"^IXIC": "Nasdaq Composite"`.
- [MarketSnapshot.jsx](../../frontend/src/pages/MarketSnapshot.jsx): `SNAPSHOT_META` 키 `^NDX`→`^IXIC`, 설명 갱신. FX(환율)은 등락 배지 미표시(`showChangeBadge`).
- [Home.jsx](../../frontend/src/pages/Home.jsx): 나스닥 카드 `label/dataKey: 'Nasdaq Composite', ticker: '^IXIC'`. 환율 카드 `hideChange: true`로 등락 배지 미렌더.
- [CategoryView.jsx](../../frontend/src/pages/CategoryView.jsx): `data.symbol === 'KRW=X'`이면 등락 배지 미표시.
- [AssetDetail.jsx](../../frontend/src/pages/AssetDetail.jsx): `KRW=X`이면 등락 배지 미표시.

### Test
- [test_price_providers.py](../../backend/tests/test_price_providers.py): `^NDX` Stooq primary 테스트 3개 제거, FRED `^IXIC` 테스트 추가(history 라우팅·series_id·정렬·as_of / 스냅샷 최신일 vs 직전일 등락 / 결측 carry-forward / 키 없을 때 degrade). `KRW=X` 등락=0·Stooq 미호출 테스트 추가. Stooq 기반 USD/KRW 등락 검증 테스트 3개(`test_fx_snapshot_change_percent_from_stooq_close` 등) 삭제. live-ticker 테스트 `^NDX`→`^IXIC`.
- [test_market_warmup_timeout.py](../../backend/tests/test_market_warmup_timeout.py): carry-forward 픽스처 `^NDX`/"Nasdaq 100" → `^IXIC`/"Nasdaq Composite".
- [test_chat_service.py](../../backend/tests/test_chat_service.py): 나스닥 라우팅 URL `/market/%5ENDX` → `/market/%5EIXIC`.

## 동작 변화

- 나스닥 카드: 라벨 "Nasdaq Composite", 데이터는 FRED `NASDAQCOM`. 현재가=FRED 최신 관측일, 등락=최신일 vs 직전일(EOD·1~2영업일 지연). history=FRED 관측치.
- USD/KRW: 현재가(open.er-api)만 표시, **등락 배지 미표시**. 백엔드 `changePercent=0`.
- Stooq: 라이브 기본 경로에서 호출 안 됨. fallback 코드(`ENABLE_STOOQ_FALLBACK`, 기본 false)는 휴면으로 잔존. `STOOQ_API_KEY` 수동 교체 불필요.
- 잔존 `^NDX` 참조(`STOOQ_SYMBOLS`, `FMP_SYMBOL_CANDIDATES`, history의 `{"^GSPC","^NDX"}`)는 카드에서 빠져 dead path지만 동작에 영향 없어 최소 변경으로 둠.

## 검증 결과

- `cd backend; python -m pytest tests/test_price_providers.py tests/test_market_warmup_timeout.py tests/test_chat_service.py` → **71 passed**.
  - 테스트 수집용 임시 env(`PROJECT_NAME`, `API_V1_STR`, `DATABASE_URL=sqlite+aiosqlite:///./test.db`)만 주입. 시크릿 비노출.
- 전체 `pytest` → 215 passed, **4 failed**. 4건(`test_payment_service`/`test_subscription_api` 결제 provider, `test_ai_report_quality_gate` external provider 키)은 **본 변경과 무관**. 변경을 `git stash`로 되돌려도 동일하게 실패함을 확인 → 로컬 `.env`에 실제 provider 키가 있어 "키 없음/미설정"을 기대하는 테스트가 깨지는 기존 환경 이슈.
- `cd frontend; npm run lint` → 통과(에러 없음). `npm run build` → 성공(vite build ✓). chunk size 경고는 기존 사항.

## 미실행 명령과 이유

- 라이브 smoke(`GET /api/market/prices` 실 FRED 키로 `^IXIC` 값 확인)는 배포 후 단계로 남김. 로컬 실측으로 `NASDAQCOM` 정상 수신은 이미 확인.
- 전체 `pytest`의 4개 실패는 위 사유로 미수정(시크릿/결제 키 환경 의존, 본 작업 범위 밖).

## 후속 위험

- FRED는 EOD·1~2영업일 지연. "현재가"는 최신 거래일 종가이며 실시간이 아니다. 등락도 최신 관측일 기준.
- FRED 키 만료/한도 시 빈 응답 → 카드 carry-forward(직전 유효값) 또는 콜드 스타트에서 0. `FRED_API_KEY` 관리 필요.
- `^IXIC`로 캐노니컬 변경: 기존 `^NDX` 딥링크/즐겨찾기가 있으면 더 이상 나스닥 카드와 연결되지 않음(나스닥은 스케줄 리포트 대상 아님이라 리포트 영향 없음).
- 배포 시 Render 환경변수 `MARKET_LIVE_TICKERS`를 쓰는 경우 `^NDX`→`^IXIC`로 갱신 필요(기본값은 코드에서 갱신됨).

## Feature Links

- [docs/harness/features/market-data.md](features/market-data.md)
- [docs/harness/feature-index.md](feature-index.md)
- [docs/harness/nasdaq-composite-fred-source-plan-2026-06-10.md](nasdaq-composite-fred-source-plan-2026-06-10.md)
- [docs/harness/nasdaq-fx-stooq-key-resilience-plan-2026-06-10.md](nasdaq-fx-stooq-key-resilience-plan-2026-06-10.md)
