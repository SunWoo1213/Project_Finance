# 시장 데이터 무료 플랜 기반 Stooq 대체 구현

Date: 2026-06-07
Status: Implemented
Feature:
- `docs/harness/features/market-data.md`
Plan:
- `docs/harness/market-data-free-plan-stooq-replacement-plan-2026-06-07.md`

## Objective

Render 배포 환경에서 반복되던 Stooq `ConnectTimeout('')` 리스크를 줄이기 위해 Stooq를 기본 provider에서 제외하고, FMP Basic 무료 플랜과 기존 무료 provider 중심으로 미국 지수/원자재/미국 주식 history 경로를 재구성했다.

## Files Changed

- `backend/app/core/config.py`
- `backend/app/services/price_providers.py`
- `backend/tests/test_price_providers.py`
- `backend/tests/test_market_warmup_timeout.py`
- `.env.example`
- `ENVIRONMENT_VARIABLE_SETUP.md`
- `docs/harness/features/market-data.md`
- `docs/harness/feature-index.md`
- `docs/harness/market-data-free-plan-stooq-replacement-implementation-2026-06-07.md`

## Behavior Changes

- `FMP_FETCH_TIMEOUT_SECONDS`, `FMP_DAILY_CALL_BUDGET`, `ENABLE_STOOQ_FALLBACK` 설정을 추가했다.
- FMP 호출은 `https://financialmodelingprep.com/stable`의 `quote`, `historical-price-eod/full`, `profile` 경로를 사용한다.
- FMP 대상 데이터는 12시간 내부 cache, 30분 failed-call cooldown, provider `Semaphore(1)`, process-local daily budget guard를 거친다.
- 미국 지수와 원자재 snapshot/history는 FMP quote/EOD history를 먼저 사용한다.
- 미국 주식 snapshot은 Finnhub quote를 primary로 유지하고, FMP profile/history를 optional support로 사용한다. Finnhub/FMP/Stooq optional source 실패는 성공한 quote를 버리지 않는다.
- Stooq는 기본 비활성이다. `ENABLE_STOOQ_FALLBACK=true`일 때만 compatibility fallback으로 호출한다.
- USD/KRW는 기본적으로 open.er-api.com daily reference rate만 사용한다. reliable free public previous close가 없으면 `changePercent=0`, `provider_meta.change_source=none`으로 둔다. Stooq FX change/history는 opt-in fallback에서만 사용한다.
- FMP 기반 응답에는 `provider_meta.provider`, `freshness`, `license_scope`, `change_source`를 포함해 EOD/delayed/free-plan 성격을 숨기지 않게 했다.
- 사용자-facing 요청과 챗봇 요청은 새 리포트 생성을 트리거하지 않는다. 이 변경은 market provider/cache 경로 변경이며 report generation cadence나 coverage를 늘리지 않았다.

## Verification Performed

```powershell
cd backend
..\backend\.venv\Scripts\python.exe -m pytest tests\test_price_providers.py
..\backend\.venv\Scripts\python.exe -m pytest tests\test_market_warmup_timeout.py
cd ..
.\backend\.venv\Scripts\python.exe -m compileall backend\app
```

Result:
- `tests\test_price_providers.py`: 22 passed
- `tests\test_market_warmup_timeout.py`: 10 passed
- `compileall backend\app`: passed

Note:
- 초반 검증에서 pytest cache dir 생성 권한 경고가 있어 생성된 `pytest-cache-files-*` 임시 디렉터리를 workspace 내부 경로 검증 후 정리했다. 최종 검증은 `-p no:cacheprovider`로 cache provider를 끄고 경고 없이 통과했다.

## Follow-Up Risks

- FMP Basic 무료 플랜의 실제 symbol coverage는 계정/plan 정책에 따라 달라질 수 있다. `^GSPC`, `^NDX`, `GCUSD`, `SIUSD`가 막히면 빈 payload 또는 stale cache로 degrade한다.
- `FMP_DAILY_CALL_BUDGET` counter는 process-local이므로 서버 재시작 시 초기화된다. 무료 한도를 더 엄격히 관리하려면 DB/Redis 기반 usage ledger가 필요하다.
- FMP/Twelve Data/CoinGecko 등 무료 플랜은 공개 상용 표시/재배포 license가 제한될 수 있다. 졸업작품 데모 범위를 넘어가면 provider 약관을 재검토해야 한다.
- `ENABLE_STOOQ_FALLBACK=true`는 Render의 Stooq timeout 리스크를 되살릴 수 있으므로 운영 기본값은 false로 유지한다.
