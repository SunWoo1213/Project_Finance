# 시장 데이터 provider 무료 멀티소스 교체 계획 (yfinance 탈피)

Date: 2026-06-03
Status: 구현 완료(Implemented) — 구현 기록: `docs/harness/market-data-provider-migration-implementation-2026-06-03.md`
Feature: `docs/harness/features/market-data.md`

## 1. 목적 (Objective)

Render 배포 환경에서 yfinance가 Yahoo Finance로부터 차단되어 시세/뉴스 수집이 실패하는 문제를, 시세·뉴스 데이터 소스를 **무료 멀티소스 API 조합**으로 교체해 해결한다. **프로토타입 동작 복구**가 1차 목표이며, 무료 API의 호출 한도·지연·부분 실패는 provider별 throttle/cache/degrade로 흡수한다.

중요한 전제:
- Render가 `yfinance` 패키지 설치 자체를 거부한 것이 아니라, Yahoo Finance가 Render 데이터센터 IP에서 들어오는 yfinance 요청을 거부한 케이스라면 provider 교체만으로 충분하다.
- 이번 구현에서는 롤백용 잔존 의존성을 두지 않고 `requirements.txt`와 production code path의 `yfinance` import/call을 모두 제거한다.
- 구현 완료 후 `backend/app/main.py`, `backend/app/services/market_service.py`, `backend/app/services/macro_service.py`를 포함한 배포 경로에서 `import yfinance as yf`, `yf.Ticker`, `yf.download` 등 yfinance 사용 흔적이 남지 않았는지 확인한다.

## 2. 배경 / 문제 (현재 동작)

Render 런타임 로그에서 두 종류의 실패가 관측됨.

- `HTTP Error 401: ... "Invalid Crumb"` / `"User is unable to access this feature"` — Yahoo가 **데이터센터(Render) IP 자체를 차단**. crumb/cookie 인증이 IP 단에서 막힘. 코드로 해결 불가(출발지 IP 문제).
- `Too Many Requests. Rate limited.` — 현재 `update_prices_task`는 전체 34개 자산 그룹 호출을 `asyncio.gather`로 한 번에 실행하며, 이 중 약 30개가 yfinance성 가격 호출로 몰릴 수 있어 발생한다(채권 provider 호출은 별도).
- `argument of type 'NoneType' is not a container or iterable` — 위 401로 yfinance 내부 응답이 깨지며 나는 부수 에러.

반면 FRED(미국채)·ECOS(한국채)는 **API 키 기반**이라 200 OK로 정상 동작. 즉 "키 있는 정식 API"는 멀쩡하고 **yfinance만** 차단된다 → provider 교체가 근본 해법.

## 3. 목표 동작 (Target Behavior)

자산군별로 무료 소스를 분담한다. 데이터 신선도는 자산별로 다르며(실시간/준실시간/EOD/T+1 혼재) 프로토타입 범위에서 허용한다. 단, 무료 API라도 rate limit이 있으므로 호출량을 제한한다.

| 자산군 | 대상 티커(내부 표기) | 신규 소스 | 키 | 신선도 |
| --- | --- | --- | --- | --- |
| 미국 주식 | `US_TOP10` 10종(AAPL 등) | **Finnhub** `/quote` (+ `/stock/profile2` 시총), 히스토리는 **1일 단위 daily provider**(Stooq daily CSV 후보 또는 무료 확인된 대체 소스) | `FINNHUB_API_KEY`(기존), Stooq 선택 시 `STOOQ_API_KEY` 후보 | 현재가 실시간, 히스토리 EOD/daily |
| 암호화폐 | `BTC-USD`, `ETH-USD` | **CoinGecko** `/simple/price`, `/market_chart` | `COINGECKO_DEMO_API_KEY` 필수 | 준실시간 |
| 환율 | `KRW=X` | 현재가: **open.er-api.com**. 히스토리: Stooq/대체 소스 확인 후 적용 또는 daily degrade | open.er-api.com open access는 키 없음(단 attribution 필요) 또는 provider별 히스토리 키 | 일별 기준환율(실시간 아님) |
| 미국 지수 | `^GSPC`, `^NDX` | **Stooq** CSV(`^spx`, `^ndx`) 또는 무료 확인된 대체 소스 | Stooq 선택 시 `STOOQ_API_KEY` 후보 | EOD |
| 한국 지수 | `^KS11`(KOSPI), `^KQ11`(KOSDAQ) | **공공데이터포털 지수시세정보** | 신규 키 | 공식상 실시간 갱신 표기, 실제 응답 기준일/시간 보존(EOD/T+1 가능) |
| 한국 주식 | `KR_TOP10` 10종(005930.KS 등) | **공공데이터포털 주식시세정보** | 신규 키 | 공식상 실시간 갱신 표기, 실제 응답 기준일/시간 보존(EOD/T+1 가능) |
| 원자재(금/은) | `XAU`(GC=F), `XAG`(SI=F) | **Stooq** CSV(`xauusd`, `xagusd`) 또는 무료 확인된 대체 소스 | Stooq 선택 시 `STOOQ_API_KEY` 후보 | EOD |
| 미국채/한국채 | `DGS*`, `KTB_*` | **변경 없음**(FRED/ECOS 유지) | 기존 | - |

### 뉴스 / 이벤트

| 대상 | 신규 소스 |
| --- | --- |
| 미국 주식 뉴스 | Finnhub `/company-news?symbol=...` |
| 암호화폐/환율/지수/일반 시장 뉴스 | Finnhub `/news?category=crypto\|forex\|general` |
| 이벤트(실적 등) | Finnhub `/calendar/earnings` (`_fetch_latest_context_sync`의 `events` 대체). 무료 범위는 미국 기업/최근 1개월 중심으로 보고, 한국 주식 이벤트는 기본 degrade |
| **한국 주식 뉴스** | **네이버 금융뉴스**(종목별 한국어 뉴스) |

Provider 제약:
- Finnhub `/company-news`는 North American companies 중심이므로 한국 주식 뉴스 대체재로 보지 않는다.
- Finnhub `/quote`는 미국 주식 현재가에는 적합하지만, Finnhub `stock/candle`, `forex/candle`, `forex/rates`는 공식 문서상 premium 권한이 걸릴 수 있다. 따라서 미국 주식/FX 히스토리와 FX 현재가는 Finnhub 무료 범위라고 가정하지 않는다.
- CoinGecko는 암호화폐 가격/히스토리에 적합하며, production 구현은 `COINGECKO_DEMO_API_KEY` 기반 호출을 기본값으로 둔다. no-key fallback은 사용하지 않는다.
- 네이버 금융뉴스는 공식 REST API가 아니라 페이지/검색 결과 기반 수집이 될 수 있으므로 selector 변경, 차단, 빈 결과를 정상 edge case로 취급하고 빈 배열 degrade를 유지한다.
- Stooq는 무료 historical CSV 소스로 후보 가치가 있지만, 2026-06-03 검증 시 단순 CSV URL이 `apikey` 발급 안내를 반환했다. 따라서 "무키 소스"로 확정하지 않고 `STOOQ_API_KEY` 또는 대체 historical provider를 구현 전 확정한다.
- Stooq는 공식 REST API가 아니라 CSV 다운로드 형식이므로 timeout, 빈 CSV, 심볼 변경, API key 요구 변경을 정상 edge case로 취급한다.
- Stooq를 채택하기 전에는 `AAPL`, `^spx`, `^ndx`, `xauusd`, `xagusd`, `USDKRW` 후보 URL을 실제 응답 기준으로 통과/탈락 표로 확정한다. 이 확인이 끝나기 전에는 Stooq 의존 구현을 시작하지 않는다.
- open.er-api.com open access endpoint는 no-key 호출이 가능하지만 1일 1회 업데이트, attribution 필요, rate limit이 있는 **일별 기준환율** 소스다. "실시간 FX"로 표기하거나 trading-grade 환율로 취급하지 않는다.
- 공공데이터포털 금융위원회 주식/지수 시세는 공식 메타데이터상 무료 REST API이며 실시간 갱신으로 표기되지만, 구현에서는 provider가 내려준 실제 기준일/시간을 화면과 응답에 보존한다. 영업일/휴장일/제공 지연이 있으면 EOD/T+1처럼 보일 수 있으므로 고정된 "실시간" 보장으로 홍보하지 않는다.
- **현재가 snapshot과 차트 history는 별도 책임으로 구현한다.** Finnhub `/quote`만으로는 기존 `history_prices`와 `GET /api/market/history/{ticker}`의 `points`를 대체할 수 없다. provider 헬퍼는 snapshot 정규화와 history point 정규화를 분리해야 한다.
- **히스토리 날짜는 신규 provider가 준 실제 날짜를 보존한다.** 현재 `backend/app/main.py`의 `build_points()`처럼 가격 배열 길이만 보고 날짜를 역산하면 휴장일, T+1 지연, 주간봉/일봉 degrade에서 날짜가 틀어질 수 있다. 본 구현 범위에서 yfinance 대체 경로를 우선 수정하고, FRED/ECOS/commodity 경로까지 만지는 경우에는 해당 경로도 provider 날짜 기반으로 정리한다.
- **최소 provider guard는 1차 구현 범위다.** 무료 API 교체만 하고 기존 `asyncio.gather` 폭주 구조를 그대로 두면 yfinance 429가 Finnhub/CoinGecko/공공데이터포털 429로 바뀔 수 있다. provider별 semaphore, 짧은 실패 cooldown, profile/history cache는 구현 범위에 포함한다.
- **사용자 직접 호출 경로도 cache/cooldown 대상이다.** `/api/market/history/{ticker}`와 `/api/market/latest-context/{ticker}?force_refresh=true`는 사용자가 버튼/탭 반복으로 호출할 수 있으므로 scheduler 경로와 별도로 per-ticker/period cache guard를 둔다.

## 4. yfinance 사용처 전수 (교체 대상 5곳)

코드 조사 결과 yfinance는 다음 5곳에서 호출된다. 모두 교체 대상.

1. `backend/app/services/market_service.py:143` `_fetch_price_sync` — 가격(지수/FX/미국주식/한국주식/암호화폐).
2. `backend/app/services/market_service.py:158` `_fetch_news_sync` — `update_news_task`용 종목별 뉴스.
3. `backend/app/services/market_service.py:259` `_fetch_latest_context_sync` — 자산 상세 최신 뉴스 + `ticker.calendar` 이벤트.
4. `backend/app/services/macro_service.py:133` `fetch_commodity_data` — 금/은(`GC=F`/`SI=F`).
5. `backend/app/main.py:450-451` `get_market_history` 기본 경로 — 주식/암호화폐/지수 차트 히스토리(현재 `1d`는 5분봉 intraday). **사용자 작업지시에는 없었으나 조사 중 발견** — 교체하지 않으면 자산 상세 차트가 깨지므로 본 계획에 포함. 신규 구현에서는 `1d`도 1일 단위 daily history로 반환한다.

## 5. 변경 대상 파일

### Backend
- `backend/app/services/market_service.py` — `_fetch_price_sync`, `_fetch_news_sync`, `_fetch_latest_context_sync` 내부 교체, **심볼 매핑 테이블 신설**.
- `backend/app/services/macro_service.py` — `fetch_commodity_data` 교체.
- `backend/app/main.py` — `get_market_history` 기본 경로 교체.
- (신규 제안) `backend/app/services/price_providers.py` — Finnhub/Stooq/CoinGecko/공공데이터포털 fetch 헬퍼와 심볼 매핑을 한 곳에 모음. `market_service.py`의 오케스트레이션(`update_prices_task`, `_collect_prices_group`)은 그대로 두고, 이 모듈만 호출. *services/`DEVELOPMENT_DIRECTION.md`의 `external_api_service.py`(외부 API 추상화 지점) 원칙과 정합. 신규 파일 생성 시 feature 문서 ownership map 갱신 필요.*
- `backend/app/services/external_api_service.py` — 이미 Finnhub news와 CoinGecko simple price helper가 존재한다. 신규 `price_providers.py`를 만들더라도 URL 구성, 응답 정규화, missing-key degrade 패턴은 이 파일을 참고하고 중복 호출 로직은 가능한 한 줄인다.

### Frontend
- `frontend/src/pages/MarketSnapshot.jsx` — `period=1d`가 daily history로 degrade되면 현재 "시간 단위 변화", "1일 장중 데이터" 문구가 사실과 달라진다. 구현에서 intraday를 포기하는 선택을 유지하면 "최근 일별 흐름" 등으로 라벨을 소폭 수정한다.
- `frontend/src/pages/AssetDetail.jsx` — `1일` 탭은 유지할 수 있지만 daily point 기준임을 UX에서 오해하지 않도록 차트 라벨/빈 상태를 확인한다.

### 설정 (config / .env.example)
- `backend/app/core/config.py` — `FINNHUB_API_KEY`, `FMP_API_KEY`는 이미 존재(67-68행). **신규: 공공데이터포털 서비스키** 필드 추가(예: `DATA_GO_KR_API_KEY`). Stooq를 채택하면 `STOOQ_API_KEY`, 암호화폐용 `COINGECKO_DEMO_API_KEY` 추가. 한국 뉴스 소스는 네이버 금융뉴스로 고정하되, 장애 시 빈 배열 degrade를 적용한다.
- `.env.example` — 신규 키 항목과 설명 추가(실제 키 값은 절대 커밋 금지).

### 변경하지 않음 (그대로 유지)
- 자산 그룹 정의, `_normalize_payload`/`_to_frontend_shape`/`_coerce_normalized_payload`, `_normalize_history`.
- API 라우터 계약(`GET /api/market/prices|news|latest-context|history`)의 응답 shape.
- 프론트엔드 대규모 구조. 단, `1d` intraday 포기 때문에 필요한 문구/라벨 수준의 수정은 허용한다.
- 채권(FRED/ECOS) 경로.

주의:
- `update_prices_task`, `_collect_prices_group`, `update_news_task`, `_collect_news_group`의 외형은 유지한다.
- 전체 scheduler 주기 최적화는 이번 검증의 핵심 범위가 아니다. 다만 provider별 최소 동시성 제한, 실패 cooldown, profile/history cache, 429 degrade는 1차 구현에 포함한다.
- 기존 `market_cache`의 public 응답 shape는 유지하되, 필요하면 `market_cache.setdefault("provider_cache", ...)`처럼 내부 provider cache bucket을 추가할 수 있다. 이 bucket은 프론트 계약에 노출하지 않는다.
- `GET /api/market/history/{ticker}`는 응답 shape는 유지하되, 내부에서는 `history_prices` 배열을 다시 날짜로 역산하지 말고 provider 날짜 기반 `points`를 사용한다.
- `GET /api/market/history/{ticker}`는 사용자 직접 호출 엔드포인트이므로 `ticker+period` 단위 cache TTL을 둔다. 캐시가 신선하면 provider를 재호출하지 않는다.
- `period=1d`는 더 이상 5분봉 intraday로 제공하지 않는다. 무료 provider 조합의 안정성을 우선해 1일 단위 daily history로 반환한다.

## 6. 단계별 구현 계획

1. **심볼 매핑 정의**: 내부 티커(Yahoo형) → 소스별 심볼 매핑 테이블 작성.
   - Stooq 후보: `^GSPC→^spx`, `^NDX→^ndx`, `GC=F→xauusd`, `SI=F→xagusd`. 단, `apikey` 필요 여부와 심볼별 CSV 응답을 구현 직전에 확인한다.
   - Finnhub: 미국주식은 그대로(`AAPL`). Forex는 무료 기본 provider로 쓰지 않고, 유료/권한 확인 후에만 `OANDA:*` 계열을 검토한다.
   - CoinGecko: `BTC-USD→bitcoin`, `ETH-USD→ethereum`. `COINGECKO_DEMO_API_KEY` 기반으로 헤더 또는 query key를 붙인다. 키가 없으면 provider 호출을 건너뛰고 crypto degrade로 처리한다.
   - 공공데이터포털: 한국주식은 `.KS` 제거 후 6자리 코드(`005930.KS→005930`), 지수는 KOSPI/KOSDAQ 코드 파라미터.
2. **provider 헬퍼 구현**(`price_providers.py`): snapshot과 history를 분리한다.
   - Snapshot: `{currentPrice, changePercent, history_prices, marketCap}`로 정규화해 기존 cache/frontend shape를 유지한다.
   - History: `{ticker, series_type, unit, points: [{date, value}], legacy}`를 만들 수 있도록 provider 날짜를 보존한 `points`를 반환한다.
   - 실패 시 빈 응답/예외 → 기존 `_coerce_normalized_payload`·`DEFAULT_RESPONSE` 패턴 유지.
3. **provider guard/cache 추가**: provider별 semaphore(초기값 1~2), 실패 cooldown(예: 5분), profile cache(예: 12시간), history cache(예: ticker+period 기준 6~24시간)를 둔다. `market_cache` 내부 bucket 또는 `price_providers.py` 모듈 캐시로 시작하되, 프론트 응답 shape는 바꾸지 않는다.
4. **provider 실패/degrade 방어 추가**: 401/429/timeout/빈 CSV/미지원 심볼은 실패 로그만 남기고 빈 응답/degrade로 흡수한다. 429는 실패 cooldown에 기록해 같은 provider/symbol을 즉시 재시도하지 않는다.
5. **`_fetch_price_sync` 교체**: 카테고리/티커에 따라 provider 헬퍼로 라우팅. 가능하면 async `httpx.AsyncClient` 기반으로 정리하고, 동기 wrapper가 필요할 때만 `asyncio.to_thread`를 사용한다.
6. **Stooq hard gate 확인**: `AAPL`, `^spx`, `^ndx`, `xauusd`, `xagusd`, `USDKRW` 후보를 실제 CSV 응답으로 확인하고, `STOOQ_API_KEY` 필요 여부/심볼별 성공 여부/대체 provider 또는 degrade 결정을 표로 남긴다.
7. **`fetch_commodity_data` 교체**: Stooq xauusd/xagusd를 우선 후보로 두되, `STOOQ_API_KEY`와 실제 CSV 응답이 확인될 때만 사용한다. 미확정이면 무료 대체 소스 또는 빈 응답 degrade를 선택한다.
8. **`get_market_history` 교체**: 기본 경로를 provider별 히스토리로 교체하고 provider 날짜를 보존한다. 이 엔드포인트는 사용자 직접 호출 경로이므로 `ticker+period` 단위 cache TTL을 먼저 확인한 뒤 provider를 호출한다.
   - 미국 주식: 1일 단위 daily history만 제공한다. Stooq daily CSV 후보(`AAPL→aapl.us` 등)를 우선 검증하되, `apikey`가 없거나 작동하지 않는 종목은 빈 응답/degrade 또는 대체 daily provider로 처리한다.
   - 암호화폐: CoinGecko `/market_chart`.
   - 미국 지수/원자재: Stooq daily CSV 후보.
   - 한국 주식/지수: 공공데이터포털 날짜 기반 응답.
   - 환율: open.er-api.com을 일별 기준환율 현재 snapshot 기본 provider로 사용한다. open access attribution 요구를 문서/UI에 반영한다. 히스토리는 Stooq 또는 무료 히스토리 소스 확인 후 적용하고, 미확정이면 현재가만 제공하고 히스토리는 daily degrade/빈 응답 처리한다.
   - `1d` intraday(5분봉)는 포기한다. 모든 자산군의 `period=1d` 응답도 provider 날짜 기반 1일 단위 daily `points`로 맞춘다.
9. **뉴스 교체**: `_fetch_news_sync`·`_fetch_latest_context_sync`를 Finnhub 뉴스/이벤트와 네이버 금융뉴스로 교체한다. 미국 주식 뉴스/이벤트는 Finnhub를 사용하고, 한국 주식 뉴스는 네이버 금융뉴스를 사용한다. Finnhub earnings calendar는 미국 기업/최근 1개월 범위로 제한될 수 있음을 반영하고, 한국 이벤트는 기본 빈 배열로 둔다. 네이버 금융뉴스 수집 실패 시에도 cache shape는 `{"symbol": ticker, "items": []}`로 유지해 프론트가 label 누락으로 흔들리지 않게 한다.
10. **latest-context 강제 새로고침 방어**: 현재 `AssetDetail.jsx`의 새로고침 버튼은 `force_refresh=true`로 TTL을 우회할 수 있다. 무료 provider 전환 후에는 `force_refresh`에도 최소 cooldown을 적용하거나, 최근 요청 시 cached payload를 반환해 사용자가 Finnhub를 반복 호출하지 못하게 한다.
11. **프론트 라벨 정합성 보정**: `/market/:ticker`의 "시간 단위 변화", "1일 장중 데이터" 문구와 `1d` 차트 빈 상태를 daily history 정책에 맞게 소폭 수정한다.
12. **설정/문서**: config·`.env.example`에 신규 키와 provider cadence/cache 정책 추가, feature 문서·index·error-casebook 갱신(§11).
13. **yfinance 완전 제거**: 같은 구현에서 `requirements.txt`와 모든 `import yfinance as yf`/`yf.Ticker`/`yf.download` 호출을 제거한다. production 실행 경로뿐 아니라 의존성 목록에도 yfinance가 남지 않게 한다. `_resolve_yfinance_news_symbol`, `_parse_yfinance_news_item`, `"source": "yfinance"`처럼 yfinance 전용 helper명과 응답 source 문자열도 신규 provider 이름/중립 명칭으로 함께 정리한다.

## 7. 환경변수 / 키 준비 (사용자 작업)

- `FINNHUB_API_KEY` — finnhub.io 무료 가입 후 발급(미설정 시 미국주식/뉴스 실패).
- 공공데이터포털 서비스키 — data.go.kr에서 "주식시세정보"·"지수시세정보" 활용신청 후 발급(미설정 시 한국 주식/지수 실패).
- `COINGECKO_DEMO_API_KEY` — 필수. CoinGecko Demo API key 기반으로 암호화폐 현재가/히스토리를 호출한다. 없으면 no-key fallback 없이 crypto degrade.
- `STOOQ_API_KEY` — Stooq CSV를 채택하는 경우 필요할 수 있음. 2026-06-03 검증 기준 단순 CSV URL은 `apikey` 안내를 반환했으므로 무키 provider로 간주하지 않는다.
- open.er-api.com — 환율 현재가 기본 provider. open access는 키가 없지만 attribution 필요, 1일 1회 업데이트, rate limit이 있으므로 구현 시 attribution 처리와 24시간 캐시를 함께 둔다.

운영 정책값 후보:
- `MARKET_PRICES_REFRESH_MINUTES`: Render smoke에서는 30분 이상 권장. 지수/한국주식 중심 프로토타입이면 720분(12시간)도 가능.
- `MARKET_NEWS_REFRESH_MINUTES`: 60분 이상 유지.
- provider profile cache TTL: 신규 코드 상수 또는 env로 12시간 이상 권장.
- provider history cache TTL: `ticker+period` 기준 6~24시간 권장. 특히 Stooq/공공데이터포털/open.er-api.com처럼 일별 데이터인 provider는 12~24시간 캐시를 기본으로 둔다.
- provider failed-call cooldown: 429/401/timeout/빈 응답 반복에 대해 5분 이상 권장.
- provider별 동시성: Finnhub/CoinGecko/공공데이터포털/Stooq 각각 1~2개 동시 호출부터 시작.

주의: 전체 scheduler 주기 조정은 구현 승인 전 필수 결정사항이 아니라 배포 안정화 후보로 둔다. 단, provider별 최소 동시성 제한/cache/cooldown은 무료 API 장애를 막기 위한 1차 구현 범위다.

## 8. 동작 차이 / degrade 포인트 (주의)

- **신선도**: 미국주식은 provider 권한 범위에서 실시간/준실시간, 암호화폐는 준실시간, open.er-api.com 환율은 **일별 기준환율**, 미국 지수와 원자재는 EOD. 공공데이터포털 한국 지수/주식은 공식상 실시간 갱신으로 표기되더라도 실제 응답의 기준일/시간을 보존하고, 영업일/휴장일/제공 지연 때문에 EOD/T+1처럼 보일 수 있음을 UI/문서에서 과장하지 않는다.
- **무료 API 호출 한도**: 호출 한도는 무시하지 않는다. Render 배포에서는 scheduler 주기, provider별 semaphore, profile TTL cache, 429 degrade를 함께 적용해야 한다.
- **히스토리 사용자 호출 한도**: `/api/market/history/{ticker}`는 `AssetDetail.jsx` 기간 탭과 `MarketSnapshot.jsx` 진입에서 직접 호출된다. `ticker+period` cache/cooldown 없이 provider를 붙이면 사용자가 무료 API를 반복 호출할 수 있으므로, history 경로도 scheduler와 독립적으로 guard한다.
- **latest-context 사용자 새로고침**: `force_refresh=true`가 TTL을 완전히 우회하면 사용자가 무료 뉴스 provider를 직접 반복 호출할 수 있다. force refresh에도 cooldown/cache guard를 적용한다.
- **Finnhub 이벤트 범위**: Finnhub `/calendar/earnings`는 미국 기업/최근 1개월 범위 중심으로 보고, 한국 주식 이벤트 provider로 사용하지 않는다. 한국 이벤트는 별도 소스가 정해지기 전까지 빈 배열 degrade를 기본값으로 둔다.
- **시가총액**: Finnhub `/stock/profile2`로 미국주식 시총은 가능하나, 그 외 자산은 미제공 → `marketCap=0`. 시총 표시 화면이 있으면 빈값 처리.
- **차트 히스토리**: `/quote`류 현재가 API만 붙이면 `/api/market/history/{ticker}`가 대체되지 않는다. 미국 주식/FX는 별도 히스토리 소스 검증이 필요하다.
- **Stooq key 요구**: Stooq CSV는 무료 후보지만 현재 단순 다운로드 URL이 `apikey` 요구 안내를 반환한다. 키 확보 없이 Stooq 의존 구현을 시작하면 history/commodity/index가 한꺼번에 빈 응답으로 떨어질 수 있다.
- **CoinGecko key 정책**: CoinGecko는 Demo API key 사용을 공식 흐름으로 안내한다. production 기본 경로는 `COINGECKO_DEMO_API_KEY` 기반이며, 키가 없으면 암호화폐 provider를 호출하지 않고 degrade한다.
- **Finnhub FX/candle 권한**: Finnhub stock/forex candle과 forex rates는 premium 권한이 필요할 수 있으므로 무료 구현의 기본 provider로 두지 않는다.
- **`1d` intraday 차트**: Stooq는 일별 CSV이고, 공공데이터포털도 이 계획에서는 실시간 intraday chart provider로 쓰지 않는다. 무료 provider 조합의 안정성이 우선이므로 `1d` 5분봉은 제공하지 않고, `period=1d`도 provider 기준일/시간이 보존된 daily 성격의 `points`로 반환한다. 프론트 차트 라벨/UX 영향 확인 필요.
- **MarketSnapshot 문구 정합성**: 현재 `/market/:ticker` 화면은 "시간 단위 변화", "1일 장중 데이터"를 표시한다. daily degrade를 선택하면 구현 단계에서 해당 문구를 "최근 일별 흐름" 계열로 수정한다.
- **히스토리 날짜**: 신규 provider가 반환한 날짜를 보존한다. 임의 날짜 역산은 휴장일과 지연 데이터에서 부정확하다. FRED/ECOS/commodity 기존 경로까지 변경할지는 구현 범위에서 별도 결정한다.
- **한국 주식 뉴스**: 네이버 금융뉴스를 기본 source로 사용한다. 비공식 수집 특성상 selector 변경/차단/빈 결과가 생길 수 있으므로 실패 시 종목별 `items: []` shape를 유지한다.
- **단일 소스 의존**: Stooq/공공데이터포털이 죽으면 해당 자산군 일괄 실패 → 기존 빈 응답 fallback으로 흡수.

## 9. 확정 결정 (2026-06-03)

**한국 주식 뉴스 소스** — 네이버 금융뉴스를 사용한다. 종목별 한국어 뉴스 커버리지를 우선한다. 비공식 수집 경로가 될 수 있으므로 selector 변경/차단/빈 결과는 provider 실패로 기록하고 빈 배열 degrade로 흡수한다.

**yfinance 의존성 처리** — `requirements.txt`와 production code path에서 yfinance를 모두 제거한다. `import yfinance as yf`, `yf.Ticker`, `yf.download` 호출은 남기지 않는다. yfinance 전용 helper명(`_resolve_yfinance_news_symbol`, `_parse_yfinance_news_item`)과 응답 source 문자열(`"yfinance"`, `"yfinance calendar"`)도 남기지 않는다.

**미국 주식 히스토리 정책** — 1일 단위 daily history로 제공한다. `period=1d`도 5분봉 intraday가 아니라 provider 날짜 기반 daily `points`를 반환한다. 구체 provider는 Stooq daily CSV 후보를 우선 검증하되, 키 요구/응답 실패 시 무료 확인된 대체 daily provider 또는 빈 응답 degrade로 처리한다.

**암호화폐 CoinGecko 인증 정책** — `COINGECKO_DEMO_API_KEY` 기반으로 호출한다. no-key fallback은 production 기본 경로에서 제외한다.

**환율 현재가 소스** — open.er-api.com을 기본값으로 사용한다. 일별 기준환율 source이며 실시간 FX로 표기하지 않는다. attribution 요구와 24시간 cache를 구현/문서에 반영한다.

**호출 주기 정책** — 전체 scheduler 주기(`MARKET_PRICES_REFRESH_MINUTES`, `MARKET_NEWS_REFRESH_MINUTES`) 조정은 이번 구현 전 필수 확정 사항에서 제외하고 배포 안정화 단계에서 재검토한다. 단, provider별 semaphore, cache, failed-call cooldown처럼 개별 provider 재호출을 줄이는 guard는 1차 구현 범위에 포함한다.

**최소 provider guard 정책** — 다음 기본값으로 진행하고, 구현 후 배포 안정화에서 조정한다.
1. provider별 동시성은 1~2개로 제한한다.
2. 401/429/timeout/빈 응답은 5분 이상 failed-call cooldown에 기록한다.
3. profile/current snapshot 보조 데이터는 12시간 이상 TTL cache를 둔다.
4. `/api/market/history/{ticker}`는 `ticker+period` 단위 6~24시간 TTL cache를 둔다.

## 10. 위험과 Risky Change 여부 (AGENTS.md §9)

- **유료 API 도입 아님(현재 계획 기준)** — Finnhub FX/candle premium 경로는 기본 구현에서 제외한다. 만약 해당 paid endpoint를 쓰기로 바꾸면 AGENTS.md §9의 "paid APIs" 승인 대상이 된다.
- **DB 스키마/인증/리포트 생성/스케줄러 비용 변경 없음** — Risky Change 항목 아님. 단, 외부 provider/네트워크 연동을 다수 신설하므로 §9 "network-heavy workflows" 관점에서 사전 공유.
- **무료 API도 rate limit/key 정책이 있음** — Finnhub, CoinGecko, 공공데이터포털, Stooq 모두 429/일일 호출량/계정별 한도/키 요구 변경에 걸릴 수 있으므로, 기존 동시 호출 구조를 그대로 두면 Render에서 다른 형태의 장애가 생길 수 있다.
- **사용자 직접 호출 경로도 rate limit 위험이 있음** — `/api/market/history/{ticker}`와 latest-context 새로고침은 scheduler가 아니어도 브라우저에서 반복 호출될 수 있다. 구현은 public 응답 shape를 유지하면서 내부 cache/cooldown으로 provider 재호출을 제한한다.
- AI 리포트 생성 동작은 **불변** — 사용자/챗봇 요청이 리포트를 실시간 생성하지 않는다는 규칙(AGENTS.md §14) 그대로. 본 변경은 시세/뉴스 provider 한정.
- 데이터 신선도 저하(EOD/T+1)와 일부 화면 degrade는 프로토타입 전제에서 수용.
- 결론: **표준 Risky Change 승인 대상은 아님.** §9의 provider 선택은 확정되었으며, 남은 구현 리스크는 신규 키 발급 의존, 네이버 금융뉴스 비공식 수집 안정성, Stooq/대체 daily history provider 검증, §8 degrade 수용 여부다.

## 11. 검증 계획 (AGENTS.md §6)

- 백엔드 서비스 단위: 교체한 provider 경로별 정규화 결과를 좁은 테스트로 확인(가능하면 HTTP는 mock). 실제 LLM 호출 없음.
- History 단위: 신규 provider가 준 날짜가 `points[].date`에 보존되는지 확인. 신규 경로에서는 `history_prices` 배열을 임의 날짜로 역산하지 않는다.
- History cache 단위: 같은 `ticker+period`를 연속 호출하면 provider 함수가 재호출되지 않고 cached payload가 반환되는지 확인.
- News degrade 단위: 네이버 금융뉴스 수집 실패/빈 결과에도 label별 `{"symbol": ticker, "items": []}` shape가 유지되는지 확인.
- yfinance 제거 검증: `backend/app/services/market_service.py`, `backend/app/services/macro_service.py`, `backend/app/main.py` production 경로에서 `import yfinance`, `yf.Ticker`, `yf.download` 호출이 남지 않았는지 확인하고, `requirements.txt`에서도 `yfinance` 제거를 확인한다. 또한 yfinance 전용 helper명과 `"source": "yfinance"` 계열 문자열이 신규 provider 경로에 남지 않았는지 `rg "yfinance|yf\\." backend`로 확인한다.
- 로컬 스모크: `ENABLE_MARKET_WARMUP=false`, `ENABLE_SCHEDULER=false`로 기동 후 `update_prices_task()` 1회 수동 실행 → 캐시 채워지는지, 401/RateLimit 로그 사라지는지 확인.
- 엔드포인트: `GET /api/market/prices`, `/news`, `/latest-context/{ticker}`, `/history/{ticker}?period=1d|1mo|1y|5y` 응답 shape 유지 확인. `1d`는 intraday가 아닌 1일 단위 daily history로 반환되는지 확인.
- `latest-context` 검증: 같은 ticker에 대해 `force_refresh=true`를 반복 호출해도 provider cooldown/cache guard가 작동하고 응답 shape가 유지되는지 확인.
- Provider guard 검증: Finnhub/CoinGecko/Stooq/공공데이터포털 mock 응답에서 429/timeout/빈 응답 발생 시 failed-call cooldown이 기록되고 즉시 재시도가 차단되는지 확인.
- Stooq hard gate 검증: 구현 전 또는 구현 초기에 후보 심볼(`AAPL`, `^spx`, `^ndx`, `xauusd`, `xagusd`, `USDKRW`)별 실제 CSV 응답/키 요구/대체 결정 결과를 기록한다.
- 프론트 영향: `MarketSnapshot.jsx`의 intraday 문구가 daily history 정책과 맞는지 확인하고 `cd frontend; npm run build`.
- DB 불필요(시장 캐시는 인메모리). 키 미설정/네트워크 차단 시 해당 자산군 빈 응답으로 떨어지는지 확인. 특히 `FINNHUB_API_KEY`, `DATA_GO_KR_API_KEY`, `COINGECKO_DEMO_API_KEY`, `STOOQ_API_KEY` 미설정 degrade를 각각 확인한다.

## 12. 갱신할 문서

- `docs/harness/features/market-data.md` — `Data Flow`(provider 라우팅), `Contracts`(신규 키, `1d` daily history 정책, latest-context/history cooldown), `Open Risks`(EOD/1d daily degrade, open.er-api.com attribution, provider별 rate limit), `Change Records`에 계획/구현 기록 링크 추가. Ownership Map에 `price_providers.py` 신규 시 추가.
- `docs/harness/feature-index.md` — 본 계획서 및 후속 구현 기록 항목 추가. market-data 행 Primary backend files에 신규 파일 반영.
- `docs/harness/error-casebook-2026-06-03.md` — yfinance Render IP 차단(401 Invalid Crumb) 사례 누적.
- `backend/app/services/DEVELOPMENT_DIRECTION.md` — provider 책임 변경(yfinance→멀티소스) 반영. 폴더 소유권 변화 시 갱신.
- `.env.example` — 신규 키 항목과 기존 yfinance 중심 rate-limit 설명 수정.

## 13. 다음 단계

1. 사용자가 §9 확정 결정에 따라 `/harness-implement` 진행을 승인한다.
2. Finnhub·공공데이터포털·CoinGecko Demo key를 준비한다. Stooq key는 daily history provider 검증 결과에 따라 필요 시 발급한다(§7).
3. `/harness-implement`로 구현 → `/harness-verify`로 검증 → 문서 동기화.

## References Checked

- Finnhub quote/profile/news: `https://finnhub.io/docs/api/quote`, `https://finnhub.io/docs/api/company-news`
- Finnhub forex/candle 권한 확인: `https://finnhub.io/docs/api/forex-symbols`, `https://finnhub.io/docs/api/quote`
- CoinGecko endpoint overview/API key: `https://docs.coingecko.com/reference/endpoint-overview`, `https://docs.coingecko.com/docs/setting-up-your-api-key`
- 공공데이터포털 금융위원회 주식시세정보: `https://www.data.go.kr/data/15094808/openapi.do`
- 공공데이터포털 금융위원회 지수시세정보: `https://www.data.go.kr/data/15094807/openapi.do`
- Stooq historical CSV data/API key probe: `https://stooq.com/db/h/`, `https://stooq.com/q/d/l/?s=xauusd&i=d`
- ExchangeRate-API open access 환율: `https://www.exchangerate-api.com/docs/free`, `https://open.er-api.com/v6/latest/USD`
