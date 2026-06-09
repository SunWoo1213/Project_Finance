# 메인 대시보드 지수 데모 live allowlist 구현

Date: 2026-06-09

## Objective

메인 대시보드의 주요 지수·환율 4개(S&P 500, Nasdaq 100, 원/달러 환율, KOSPI)를 기존 시장 데이터 API의 live provider 경로로 전환하되, 현재 목적이 프로덕션 전체 실시간화가 아니라 데모임을 유지한다. 따라서 전체 자산을 live로 열지 않고 대표 리포트/데모 대상 5개와 홈 카드 4개만 allowlist에 둔다.

## Files Changed

- `backend/app/core/config.py`
- `backend/tests/test_price_providers.py`
- `.env.example`
- `docs/harness/features/market-data.md`
- `docs/harness/feature-index.md`
- `docs/harness/dashboard-indices-demo-live-allowlist-implementation-2026-06-09.md`

## Behavior Changes

- `Settings.MARKET_LIVE_TICKERS` 기본값을 아래 데모 allowlist로 갱신했다.

```text
DGS10,XAU,BTC-USD,NVDA,005930.KS,^GSPC,^NDX,KRW=X,^KS11
```

- 홈 대시보드 카드 4개는 기존 `GET /api/market/prices` -> `macro` cache 흐름을 그대로 사용한다.
- `^GSPC`, `^NDX`, `KRW=X`, `^KS11`는 기본 설정에서 `demo_mock` 대신 live provider 경로를 탄다.
- allowlist 밖 자산(`AAPL`, `^KQ11` 등)은 계속 `demo_mock` 경로를 사용한다.
- `.env.example`은 데모 기본값이 “대표 5개 + 홈 4개만 live”임을 명시하도록 갱신했다.
- AI 리포트 생성 정책은 변경하지 않았다. 사용자 화면/챗봇 요청은 fresh report generation을 트리거하지 않는다.

## Verification Performed

- `cd backend`
- `.\\.venv\\Scripts\\python.exe -m pytest tests/test_price_providers.py tests/test_market_history_route.py`
  - 결과: 40 passed, 1 warning
  - warning: `.pytest_cache` 경로 생성 권한 문제(`PytestCacheWarning: could not create cache path ... Access is denied`). 테스트 결과에는 영향 없음.

## Commands Not Run

- `pytest tests/test_price_providers.py tests/test_market_history_route.py`
  - 실패: `pytest`가 PATH에 없어 실행되지 않음.
- `python -m pytest tests/test_price_providers.py tests/test_market_history_route.py`
  - 실패: 시스템 `python`이 PATH에 없어 실행되지 않음.
- 실제 provider smoke는 API quota와 키 상태에 영향을 주므로 실행하지 않는다.
- `.env`는 시크릿 보호 규칙에 따라 열람하지 않았다.
- 프론트 코드는 변경하지 않았으므로 `npm run build`는 필수 검증에서 제외한다. 단, 배포 전 전체 smoke가 필요하면 실행할 수 있다.

## Follow-up Risks

- 실제 배포 환경에 `MARKET_LIVE_TICKERS`가 명시되어 있으면 코드 기본값이 무시된다. 배포 secret store의 값에도 홈 4개를 추가해야 한다.
- `^GSPC`, `^NDX`는 FMP key/플랜/quota 영향을 받는다. FMP가 실패하면 Stooq fallback은 `ENABLE_STOOQ_FALLBACK=true`와 `STOOQ_API_KEY`를 별도 승인 후 설정해야 한다.
- `KRW=X`는 open.er-api.com 일일 기준환율이라 기본 등락률이 `0.0`일 수 있다.
- `^KS11`은 data.go.kr 지연/차단 가능성이 있어, 과도한 refresh 주기 단축은 피해야 한다.

## Feature Links

- `docs/harness/features/market-data.md`
- `docs/harness/feature-index.md`
- `docs/harness/dashboard-indices-realtime-api-plan-2026-06-09.md`
