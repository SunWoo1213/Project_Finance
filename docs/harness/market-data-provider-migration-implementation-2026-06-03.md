# 시장 데이터 provider 무료 멀티소스 교체 구현

Date: 2026-06-03
Feature: `docs/harness/features/market-data.md`
Plan: `docs/harness/market-data-provider-migration-plan-2026-06-03.md`

## Objective

Render 배포 환경에서 Yahoo Finance/yfinance가 401 `Invalid Crumb` 및 429 rate limit으로 실패하는 문제를 피하기 위해, production code path와 `backend/requirements.txt`에서 yfinance를 제거하고 무료 멀티소스 provider 조합으로 가격, 뉴스, 최신 컨텍스트, 히스토리 경로를 교체했다.

## Files Changed

- `backend/app/services/price_providers.py` 신규: Finnhub, CoinGecko Demo, 공공데이터포털, Stooq daily CSV, open.er-api.com, Naver 뉴스 provider 라우팅과 정규화, cache/cooldown.
- `backend/app/services/market_service.py`: 가격/뉴스/latest-context 수집을 yfinance 대신 `price_providers.py`로 위임. `force_refresh=true`에도 5분 latest-context cooldown 적용.
- `backend/app/services/macro_service.py`: 금/은 commodity snapshot을 provider 모듈로 위임. FRED/ECOS 채권 경로는 유지.
- `backend/app/main.py`: `/api/market/history/{ticker}` 기본 경로를 provider-dated daily history로 교체.
- `backend/app/core/config.py`, `.env.example`: `COINGECKO_DEMO_API_KEY`, `DATA_GO_KR_API_KEY`, `STOOQ_API_KEY` 추가.
- `backend/requirements.txt`: `yfinance` 제거.
- `backend/app/services/external_api_service.py`: CoinGecko helper도 Demo key 없이는 no-key 호출하지 않고 degrade.
- `frontend/src/pages/MarketSnapshot.jsx`: `1d` intraday 문구를 daily provider history 기준 문구로 수정.
- `backend/tests/test_price_providers.py`: provider 날짜 보존, key 미설정 degrade, history cache, latest-context cooldown 테스트 추가.
- `docs/harness/features/market-data.md`, `docs/harness/feature-index.md`, `docs/harness/error-casebook-2026-06-03.md`, `backend/app/services/DEVELOPMENT_DIRECTION.md`: provider ownership, 계약, 리스크, 오류 사례 갱신.

## Behavior Changes

- 미국 주식 snapshot은 `FINNHUB_API_KEY` 기반 Finnhub quote/profile을 사용한다. 미국 주식 daily history는 `STOOQ_API_KEY`가 있을 때 Stooq daily CSV를 사용하고, 키가 없으면 빈 history로 degrade한다.
- 암호화폐 snapshot/history는 `COINGECKO_DEMO_API_KEY`가 있을 때만 CoinGecko Demo API를 호출한다. no-key fallback은 없다.
- 한국 주식/지수는 `DATA_GO_KR_API_KEY` 기반 공공데이터포털 금융위원회 주식시세정보/지수시세정보를 사용한다.
- USD/KRW snapshot은 open.er-api.com open access daily reference FX를 사용한다. 히스토리는 현재 provider 기준 single daily point로 degrade한다.
- 금/은과 미국 지수는 `STOOQ_API_KEY` 기반 daily CSV를 사용한다. 키가 없으면 빈 응답으로 degrade한다.
- 미국 주식 뉴스/이벤트는 Finnhub company-news/earnings calendar, 한국 주식 뉴스는 Naver 뉴스 검색, crypto/FX/general 뉴스는 Finnhub category news를 사용한다.
- `/api/market/history/{ticker}?period=1d`는 더 이상 5분봉 intraday가 아니라 provider가 준 날짜 기반 daily points를 반환한다.
- 사용자-facing 요청과 챗봇 요청은 여전히 저장된 scheduled report만 읽는다. 이 변경은 AI 리포트 생성 트리거를 추가하지 않았다.

## Verification

- `.\backend\.venv\Scripts\python.exe -m py_compile backend\app\services\price_providers.py backend\app\services\market_service.py backend\app\services\macro_service.py backend\app\main.py` 통과.
- `cd backend; .\.venv\Scripts\python.exe -m pytest tests\test_price_providers.py tests\test_macro_service.py` 통과: 11 passed. 단, 기존 `.pytest_cache` 권한 warning 1건은 테스트 결과와 무관하게 남았다.
- `cd frontend; npm.cmd run build` 통과. Vite chunk size warning은 기존 번들 크기 경고이며 build 실패가 아니다.
- `rg "yfinance|yf\." backend\app\main.py backend\app\services backend\requirements.txt .env.example` 결과 production code/requirements에서는 제거됨. 남은 문서 언급은 오류 사례/계획 기록 목적이다.
- Stooq 무키 CSV hard gate: `https://stooq.com/q/d/l/?s=xauusd&i=d` 응답이 `Get your apikey` 안내를 반환함을 확인했다. 구현은 `STOOQ_API_KEY`가 있을 때만 Stooq를 호출한다.

## Follow-up Risks

- Provider key가 없으면 해당 자산군은 의도적으로 빈 snapshot/history/news로 degrade한다. 배포 전 `FINNHUB_API_KEY`, `COINGECKO_DEMO_API_KEY`, `DATA_GO_KR_API_KEY`, 필요 시 `STOOQ_API_KEY`를 backend secret store에 설정해야 한다.
- Stooq는 공식 REST API가 아니라 CSV 다운로드 경로이므로 key 정책, 심볼명, 응답 형식 변경에 취약하다.
- Naver 뉴스는 공식 API가 아니므로 selector 변경/차단/빈 결과가 정상 edge case다.
- 공공데이터포털은 메타데이터상 real-time으로 표기되더라도 실제 데이터는 영업일 다음 날 13시 이후 제공될 수 있다.
- open.er-api.com은 daily reference FX이며 trading-grade realtime 환율이 아니다. UI/문서에서 실시간 FX로 표현하지 않는다.
