# 시장 데이터 provider 응답 형식 점검 및 보완 계획

Date: 2026-06-03
Status: 계획 수립(Planned)
Feature: `docs/harness/features/market-data.md`
Related:
- `docs/harness/market-data-provider-migration-plan-2026-06-03.md`
- `docs/harness/market-data-provider-migration-implementation-2026-06-03.md`

## 1. 목적

yfinance 제거 후 Finnhub, CoinGecko Demo, 공공데이터포털, Stooq, open.er-api.com, Naver 뉴스로 교체된 현재 구현이 프론트엔드와 백엔드의 기존 시장 데이터 계약을 유지하는지 확인하고, provider별 원본 응답 형식 차이 때문에 남을 수 있는 보완 작업을 계획한다.

중요: 이 점검은 시장 데이터 수집/정규화 경로만 다룬다. 사용자-facing 요청과 챗봇 요청은 계속 저장된 scheduled AI report를 읽어야 하며, 이번 계획은 새 AI 리포트 생성을 트리거하는 경로를 추가하지 않는다.

## 2. 확인한 파일

- `backend/app/services/price_providers.py`
- `backend/app/services/market_service.py`
- `backend/app/services/macro_service.py`
- `backend/app/main.py`
- `backend/app/core/config.py`
- `backend/app/services/external_api_service.py`
- `frontend/src/pages/MarketSnapshot.jsx`
- `frontend/src/pages/AssetDetail.jsx`
- `frontend/src/pages/CategoryView.jsx`
- `frontend/src/utils/apiClient.js`
- `backend/tests/test_price_providers.py`
- `backend/tests/test_market_history_route.py`
- `backend/tests/test_macro_service.py`
- `docs/harness/features/market-data.md`

`.env`는 시크릿 보호 규칙에 따라 읽지 않았다. 설정값은 변수명과 코드 경로만 확인했다.

## 3. 현재 정합성 확인 결과

대체로 새 API/provider 응답은 내부 표준 형식으로 감싸져 있다.

- 가격 snapshot은 `fetch_market_snapshot()`에서 자산군별 provider로 라우팅된 뒤 `currentPrice`, `changePercent`, `history_prices`, `marketCap` 형태로 정규화된다.
- `market_service._to_frontend_shape()`는 기존 프론트 호환 키인 `price`, `change_pct`와 신규/정규화 키인 `currentPrice`, `changePercent`를 함께 내려준다.
- `/api/market/history/{ticker}`의 일반 가격 경로는 `fetch_market_history()`가 반환한 `points: [{ date, value }]`와 `legacy`를 그대로 전달한다.
- `MarketSnapshot.jsx`와 `AssetDetail.jsx`는 `points`를 우선 사용하고, 없으면 `legacy`를 fallback으로 사용한다.
- 시장 API 호출은 프론트에서 공통 `apiClient`를 사용한다. 페이지 단위 `localhost:8000` 하드코딩은 확인되지 않았다.
- production code/requirements 범위에서 `yfinance` 호출 흔적은 제거되어 있다. 남은 `backend/app/api/DEVELOPMENT_DIRECTION.md`의 `yfinance` 언급은 "라우터에서 직접 호출하지 말아야 할 외부 API 예시" 문맥이다.
- 최신 컨텍스트는 `force_refresh=true`에도 5분 cooldown을 적용한다.

## 4. 검증한 명령

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_price_providers.py tests\test_market_history_route.py tests\test_macro_service.py
```

결과: 13 passed. 단, 기존 `backend/.pytest_cache` 권한 문제로 `PytestCacheWarning` 1건이 남았다. 테스트 성공에는 영향이 없었다.

```powershell
rg -n 'yfinance|yf\.' backend\app backend\requirements.txt .env.example
```

결과: production code path, requirements, `.env.example`에서는 제거됨. 문서성 언급 1건만 남음.

```powershell
rg -n 'apiClient|/api/market|localhost:8000|127\.0\.0\.1:8000' frontend\src
```

결과: 시장 데이터 화면은 `apiClient`를 사용한다. `frontend/src/utils/apiClient.js`의 `http://localhost:8000` fallback은 로컬 개발용 중앙 설정이다.

## 5. 발견한 보완점

### P1. open.er-api.com 환율 히스토리 날짜 파싱 보완

현재 `fetch_market_history("KRW=X")`는 `provider_meta.as_of`를 문자열 앞 10자로 잘라 날짜로 사용한다. open.er-api.com의 `time_last_update_utc`는 `"Wed, 03 Jun 2026 00:00:01 +0000"` 같은 RFC 스타일 문자열일 수 있어, 단순 `[:10]`은 `"Wed, 03 J"`처럼 날짜가 아닌 값을 만들 수 있다.

계획:
- `email.utils.parsedate_to_datetime` 또는 명시적 parser로 RFC 날짜를 ISO `YYYY-MM-DD`로 변환한다.
- 변환 실패 시에만 UTC 오늘 날짜로 fallback한다.
- 테스트: open.er-api.com 샘플 응답의 `time_last_update_utc`가 `points[0].date == "2026-06-03"`으로 보존되는지 추가한다.

### P1. 공공데이터포털 `serviceKey` 인코딩 정책 검증

공공데이터포털 serviceKey는 대시보드에서 URL-encoded 값으로 제공되는 경우가 많다. 현재 `_data_go_params()`는 `serviceKey`를 `httpx` params에 그대로 넣기 때문에, 사용자가 encoded key를 환경변수에 넣으면 `%`가 다시 인코딩되어 인증 실패가 날 수 있다.

계획:
- `DATA_GO_KR_API_KEY`는 decoded key를 권장할지, encoded key도 받아서 `unquote()`로 정규화할지 정책을 확정한다.
- 코드에서는 secret 값을 출력하지 않고, key 존재 여부와 요청 실패 상태만 로그에 남긴다.
- `.env.example`에 "대시보드의 encoded/decoded key 중 어떤 형식을 넣어야 하는지"를 명확히 적는다.
- 테스트: encoded key 입력 시 요청 params가 의도한 serviceKey 형태로 구성되는지 mock으로 검증한다.

### P1. 공공데이터포털 history row 정렬 후 기간 절단

`fetch_data_go_stock_history()`와 `fetch_data_go_index_history()`는 provider row를 point로 만든 뒤 `points[-_period_to_days(period):]`를 먼저 적용하고, 이후 `_history_payload()`에서 정렬한다. provider가 최신순 또는 비정렬로 내려오면 기간 절단 대상이 틀어질 수 있다.

계획:
- `_normalize_points(points, limit=...)` 또는 `_history_payload(..., limit=...)`를 사용해 "정렬 후 limit" 순서로 통일한다.
- 한국 주식/지수 모두 같은 helper를 쓰게 한다.
- 테스트: 날짜가 최신순/섞인 순서로 들어와도 최근 N개가 오름차순으로 반환되는지 추가한다.

### P2. `period=1d` 의미와 point 수 정책 확정

문서는 "`1d`도 intraday가 아닌 provider-dated daily points"라고 설명하지만, `price_providers._period_to_days("1d")`는 현재 30일을 반환한다. `main.py`의 채권 경로는 `1d`를 7일로 본다. 기능은 깨지지 않지만 화면/문서/테스트에서 "1d"가 몇 개의 일별 point를 의미하는지 일관성이 약하다.

계획:
- 정책 후보 중 하나로 확정한다.
  - 후보 A: `1d` 탭을 "최근 일별"로 유지하고 30개 daily point를 반환한다.
  - 후보 B: `1d`는 최근 1~7개 daily point만 반환하고, 30개 daily point는 `1mo`로만 제공한다.
- 선택한 정책을 `docs/harness/features/market-data.md`, `MarketSnapshot.jsx`, `AssetDetail.jsx` 라벨에 반영한다.
- 테스트: `fetch_market_history(ticker, "1d")`가 정책에 맞는 limit을 적용하는지 추가한다.

### P2. US bond 히스토리도 provider 날짜 보존으로 정리

`main.py`의 US bond 경로는 `fetch_us_bond_data()`가 반환한 `history_prices` 배열을 현재 날짜 기준으로 역산해 `points`를 만든다. 이번 yfinance 대체 provider 경로에는 직접 영향을 주지 않지만, market history API 전체 관점에서는 "provider 날짜 보존" 원칙과 맞지 않는다.

계획:
- `macro_service.fetch_us_bond_data()` 또는 별도 `fetch_us_bond_history()`가 FRED observation 날짜를 보존하도록 확장한다.
- `/api/market/history/DGS10`은 역산 대신 provider 날짜 기반 `points`를 반환하게 한다.
- 기존 bond 테스트에 날짜 보존 assertion을 추가한다.

### P2. provider 응답 메타데이터 표준화

일부 snapshot에는 `provider_meta`가 있지만 `market_service._coerce_normalized_payload()`와 `_to_frontend_shape()`를 지나면 public price cache에는 보존되지 않는다. 현재 프론트 계약에는 필수는 아니지만, daily/EOD/T+1 데이터임을 화면에서 정확히 보여주려면 `as_of`, `provider`, `freshness` 같은 중립 메타가 필요할 수 있다.

계획:
- public 응답에 메타를 추가할지, 내부 cache/debug endpoint에만 둘지 결정한다.
- public에 추가할 경우 기존 프론트가 무시할 수 있는 optional field로만 추가한다.
- open.er-api.com attribution, 공공데이터포털 기준일, Stooq EOD 성격을 노출할 UI 위치를 정한다.

### P3. provider별 failure/cooldown 테스트 확대

현재 테스트는 Stooq parser, CoinGecko key 미설정, history cache, latest-context cooldown을 확인한다. Finnhub 429/timeout, Stooq key 미설정, 공공데이터포털 빈 응답, Naver selector 실패에 대한 단위 테스트는 아직 부족하다.

계획:
- `_get_json()`/`_get_text()` 실패 후 동일 request key가 TTL 안에서 재호출되지 않는지 검증한다.
- key 미설정 provider가 네트워크를 호출하지 않고 빈 응답으로 degrade하는지 자산군별로 검증한다.
- Naver HTML이 바뀌거나 빈 문자열이어도 `items: []`로 유지되는지 검증한다.

### P3. Stooq 의존 범위 재검증

Stooq는 key 기반 CSV 후보로 구현되어 있지만 공식 REST API가 아니며, 심볼명과 key 정책 변경에 취약하다. 미국 주식/미국 지수/원자재 daily history가 Stooq에 묶여 있으므로 배포 전 실제 key로 smoke가 필요하다.

계획:
- 실제 key가 준비된 환경에서 `AAPL`, `^spx`, `^ndx`, `xauusd`, `xagusd` 응답 shape를 확인한다.
- 실패 심볼은 symbol map 보정 또는 빈 history degrade를 명확히 기록한다.
- 실패 사례가 확인되면 `docs/harness/error-casebook-2026-06-03.md`에 추가한다.

## 6. 단계별 실행 계획

1. 환율 날짜 parser와 공공데이터포털 key 정규화 테스트를 먼저 추가한다.
2. 공공데이터포털 history 정렬/limit helper를 고친다.
3. `period=1d` 정책을 확정하고 백엔드 limit, 프론트 라벨, feature 문서를 맞춘다.
4. US bond 날짜 보존은 별도 작은 변경으로 분리한다. 채권 경로는 기존 FRED/ECOS 안정성에 영향을 줄 수 있으므로 테스트를 먼저 확장한다.
5. provider failure/cooldown 테스트를 확대한다.
6. 실제 provider key가 있는 배포/스테이징 환경에서 `/api/market/prices`, `/api/market/history/{ticker}`, `/api/market/latest-context/{ticker}` smoke 결과를 기록한다.

## 7. 권장 검증

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests\test_price_providers.py tests\test_market_history_route.py tests\test_macro_service.py
```

```powershell
cd frontend
npm run build
```

실제 provider key가 있는 환경에서 수동 smoke:

- `GET /api/market/prices`
- `GET /api/market/history/AAPL?period=1d`
- `GET /api/market/history/KRW%3DX?period=1d`
- `GET /api/market/history/005930.KS?period=1mo`
- `GET /api/market/latest-context/AAPL?force_refresh=true` 반복 호출

## 8. 남은 리스크

- 무료 provider는 key 정책, rate limit, 응답 shape가 바뀔 수 있다.
- 공공데이터포털과 Stooq는 실제 key/실제 응답으로 배포 전 검증해야 한다.
- Naver 뉴스는 공식 API가 아니므로 selector 변경/차단 가능성이 있다.
- open.er-api.com은 daily reference FX이며 실시간 환율이 아니다.
- `period=1d` daily degrade는 사용자에게 intraday처럼 보이지 않도록 UI 문구를 계속 점검해야 한다.
