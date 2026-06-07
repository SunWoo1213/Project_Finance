# Stooq timeout fallback 보완

Date: 2026-06-07
Status: Implemented
Feature:
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/deployment-runtime.md`

## Objective

Render 배포 로그에서 `^GSPC`, `^NDX`, `XAU`, `XAG` Stooq snapshot 호출이 `ConnectTimeout('')`로 반복되고, 이 영향으로 미국 지수/원자재/환율 데이터가 비거나 기본값으로 degrade되는 문제를 완화한다.

## Root Cause

현재 구현에서 미국 지수, 원자재, 미국 주식 history, USD/KRW history는 Stooq daily CSV를 사용한다. Stooq 호출 timeout은 `12`초로 고정되어 있었고, provider는 rate-limit 위험을 줄이기 위해 직렬화되어 있었다. 따라서 Render에서 Stooq 접속이 느려지면 지수/원자재 요청이 순차적으로 timeout되고, USD/KRW도 open.er-api.com 현재 환율을 가져온 뒤 Stooq 등락률 계산에서 예외가 전파되어 전체 snapshot이 기본값으로 떨어질 수 있었다.

## Files Changed

- `backend/app/core/config.py`
  - `STOOQ_FETCH_TIMEOUT_SECONDS` 설정을 추가했다. 기본값은 `12`초이며 최소 `5`초로 보정된다.
- `backend/app/services/price_providers.py`
  - `fetch_stooq_history()`가 Stooq timeout/error 시 기존 stale history cache가 있으면 TTL이 지났더라도 재사용한다.
  - stale cache가 없으면 예외를 전파하지 않고 빈 history payload로 degrade한다.
  - `_fetch_fx_snapshot()`이 Stooq history 실패 시 open.er-api.com 현재 환율을 유지하고 `changePercent=0`, `change_source=none`으로 degrade한다.
- `backend/tests/test_price_providers.py`
  - Stooq timeout 설정 반영, stale cache fallback, USD/KRW open-rate fallback 테스트를 추가했다.
- `.env.example`
- `ENVIRONMENT_VARIABLE_SETUP.md`
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/feature-index.md`

## Behavior Changes

- Stooq가 일시 timeout되어도 이전 성공 history cache가 있으면 미국 지수/원자재/미국 주식 history/USD-KRW history 화면이 stale 값으로 유지될 수 있다.
- Stooq가 처음부터 실패하고 캐시도 없으면 미국 지수/원자재는 여전히 빈/default snapshot으로 degrade된다.
- USD/KRW는 Stooq가 실패해도 open.er-api.com 현재 환율을 표시할 수 있다. 이 경우 등락률은 `0`이고 `provider_meta.change_source=none`이다.
- Stooq 단일 호출 timeout은 배포 환경변수 `STOOQ_FETCH_TIMEOUT_SECONDS`로 조정할 수 있다. Render에서 `ConnectTimeout('')`가 반복되면 `20` 또는 `30`으로 올려 재배포한다.
- 사용자 화면과 챗봇 요청은 여전히 저장된 scheduled report만 읽는다. 이 변경은 사용자-facing fresh report 생성을 추가하지 않는다.
- scheduler 주기, report coverage, cooldown, LLM 호출량은 변경하지 않았다.

## Verification

구현 후 실행한 검증:

```powershell
cd backend
..\backend\.venv\Scripts\python.exe -m pytest tests\test_price_providers.py
cd ..
.\backend\.venv\Scripts\python.exe -m compileall backend\app
cd backend
..\backend\.venv\Scripts\python.exe -m pytest tests\test_market_warmup_timeout.py
```

결과:

- `tests\test_price_providers.py`: 16 passed.
- `tests\test_market_warmup_timeout.py`: 7 passed.
- `compileall backend\app`: passed.
- pytest가 `.pytest_cache` 쓰기 권한 경고를 출력했지만, 테스트 수집과 assertion은 모두 통과했다.

## Follow-Up Risks

- Stooq가 배포 region에서 계속 timeout되면 미국 지수/원자재 최초 warm-up은 여전히 실패할 수 있다. 이 경우 `STOOQ_FETCH_TIMEOUT_SECONDS=20~30`으로 완화하고, 그래도 실패하면 별도 지수/원자재 provider 도입을 검토해야 한다.
- Stale cache fallback은 이전에 한 번이라도 성공한 값이 있어야 동작한다.
- 미국 주식 현재가는 Finnhub quote에 의존한다. `FINNHUB_API_KEY` 부재 또는 quote timeout은 이 변경으로 해결되지 않는다.
