# 리포트 스케줄러 시장 캐시 miss 보완

Date: 2026-06-04
Feature:
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/market-data.md`

## Objective

Render 런타임에서 startup AI report job이 market warm-up 완료보다 먼저 실행되며 `NVDA 리포트 실패: No cached market data found for ticker: NVDA`가 발생하는 문제를 보완했다.

## Root Cause

시장 데이터 warm-up은 서버 health check를 빠르게 통과시키기 위해 `asyncio.create_task`로 백그라운드 실행된다. 반면 AI report startup job은 scheduler에 `run_date=datetime.now()`로 즉시 등록된다. 배포 시작 직후에는 `market_cache["prices"]`가 아직 비어 있거나 일부 자산군만 채워진 상태일 수 있어, `generate_report_for_ticker()`가 `NVDA` 같은 scheduled target의 가격 payload를 찾지 못했다.

## Files Changed

- `backend/app/services/market_service.py`
  - `ensure_price_cache_for_ticker()` 추가.
  - scheduled report 대상 ticker가 캐시에 없을 때 해당 ticker만 `fetch_asset_data()`로 보강하고 `market_cache["prices"]`에 같은 frontend shape로 저장한다.
- `backend/app/services/ai_service.py`
  - `generate_report_for_ticker()`가 가격 캐시 miss를 만나면 ticker-level cache fill을 한 번 시도한 뒤 다시 조회한다.
- `backend/tests/test_ai_report_quality_gate.py`
  - 캐시가 비어 있어도 리포트 생성 전에 ticker-level cache fill이 호출되고, 채워진 payload가 graph state로 전달되는지 테스트 추가.

## Behavior Changes

- Scheduled report generation이 market warm-up과 race condition에 걸려도 즉시 `No cached market data`로 실패하지 않고, 대상 ticker 하나만 캐시 보강을 시도한다.
- 이 보강은 백엔드 scheduled/background report generation 경로에서만 일어난다.
- 사용자-facing report page, chatbot request, notification job은 여전히 새 AI report generation을 트리거하지 않는다.
- provider key가 없거나 provider가 실패해 0/empty payload만 들어오면 기존 readiness gate가 보고서를 `blocked`로 막을 수 있다. 이 경우 LLM 호출 없이 데이터 부족으로 처리된다.

## Verification

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests\test_ai_report_quality_gate.py tests\test_ai_report_generation_switch.py tests\test_price_providers.py
```

Result: 37 passed.

Note: 기존 `backend/.pytest_cache` 권한 문제로 `PytestCacheWarning` 1건이 남았다. 테스트 결과에는 영향이 없었다.

## Follow-up Risks

- `NVDA` report가 실제로 생성되려면 Render backend 환경에 `FINNHUB_API_KEY`가 설정되어 있어야 한다. 없으면 US stock snapshot은 빈 payload로 degrade되고 readiness가 막을 수 있다.
- `XAU` 등 Stooq 의존 ticker는 `STOOQ_API_KEY`가 없으면 빈 history/snapshot으로 degrade될 수 있다.
- startup report job은 여전히 즉시 예약된다. 이번 보완은 race를 흡수하지만, Render cold start 중 provider latency가 길면 첫 run에서 일부 target은 `blocked` 또는 provider failure로 남을 수 있다. 다음 scheduler run에서 다시 시도된다.
