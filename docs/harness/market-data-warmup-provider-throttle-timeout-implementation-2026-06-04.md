# 시장 데이터 워밍업 비차단화 + per-asset 타임아웃 상향 구현 (A+C)

Date: 2026-06-04
Status: 구현 완료(Implemented)
Feature: `docs/harness/features/market-data.md`
Plan: `docs/harness/market-data-warmup-provider-throttle-timeout-plan-2026-06-03.md`
Related:
- `docs/harness/market-data-provider-migration-implementation-2026-06-03.md`
- `docs/harness/error-casebook-2026-06-03.md` (사례 10)

## 1. 목적

배포 로그에서 워밍업/스케줄러가 다수 종목을 빈 `failed:`(=`asyncio.TimeoutError`)로 떨어뜨리던 문제를 해결한다. 원인은 provider별 `asyncio.Semaphore(1)` 직렬화와 per-asset 타임아웃(가격 15s/뉴스 8s)의 충돌이다. 계획서의 **A(타임아웃 상향) + C(워밍업 비차단화)** 만 구현하고, **provider 동시성(Semaphore)은 변경하지 않는다**(rate limit/IP 차단 위험 회피).

## 2. 변경 파일과 동작 변화

### `backend/app/core/config.py`
- 신규 설정 추가:
  - `MARKET_PRICE_FETCH_TIMEOUT_SECONDS: int = 30`
  - `MARKET_NEWS_FETCH_TIMEOUT_SECONDS: int = 20`
- 신규 validator `enforce_minimum_fetch_timeout`로 두 값을 **최소 5초**로 보정(0/음수로 인한 대량 즉시 실패 방지). 기존 `enforce_minimum_minutes`와 동일한 패턴.

### `backend/app/services/market_service.py`
- `_collect_prices_group.collect_one()`: `asyncio.wait_for(..., timeout=15)` → `timeout=settings.MARKET_PRICE_FETCH_TIMEOUT_SECONDS`. 타임아웃 로그 메시지도 설정값을 출력(`timeout after {N}s`).
- `_collect_news_group.collect_one()`: `asyncio.wait_for(..., timeout=8)` → `timeout=settings.MARKET_NEWS_FETCH_TIMEOUT_SECONDS`. 로그 메시지 동일하게 설정값 출력.
- 설정값은 호출 시점에 읽으므로 재시작 시 반영(프로세스 시작 시 로드되는 pydantic Settings 특성).

### `backend/app/main.py`
- `import asyncio` 추가.
- `lifespan()` 워밍업을 **비차단(background task)** 으로 전환: 기존 `await update_prices_task()` / `await update_news_task()`를 내부 코루틴 `run_market_warmup()`으로 감싸 `asyncio.create_task(...)`로 실행. 서버가 즉시 port를 바인딩/헬스체크를 통과하고, in-memory 캐시는 직후 background에서 채워진다.
- 워밍업 시작/완료/실패 로그를 유지하고, 실패는 `print(f"... failed: {exc!r}")`로 흡수해 기동을 막지 않는다.
- 종료(`finally`)에서 미완료 warmup task를 `cancel()` 후 await하여 정리. `app.state.warmup_task`에 보관.

동작 요약:
- (이전 턴 선반영) 빈 `failed:`가 `failed: timeout after Ns` / `{exc!r}`로 구분 출력됨.
- 직렬 provider 큐가 더 길어진 타임아웃(30s/20s) 안에 드레인되어, 큐 뒤쪽 종목도 대부분 정상 수집된다.
- 워밍업이 startup을 막지 않으므로 Render "No open ports detected" 포트 스캔 지연 위험이 사라진다.

## 3. 검증 결과

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests\test_market_warmup_timeout.py tests\test_price_providers.py -q
```
결과: **9 passed** (신규 4 + 기존 5).

신규 테스트(`backend/tests/test_market_warmup_timeout.py`):
- `test_fetch_timeout_settings_enforce_minimum`: 1/0초 입력이 각각 5초로 보정.
- `test_fetch_timeout_settings_accept_configured_values`: 45/25초 입력 보존.
- `test_collect_prices_group_times_out_slow_asset_without_blocking_others`: 느린 자산은 설정 타임아웃 후 결과에서 누락되고, 같은 그룹의 빠른 자산은 정상 수집.
- `test_collect_news_group_times_out_slow_symbol`: 뉴스 그룹도 동일.

```powershell
.\.venv\Scripts\python.exe -W error::SyntaxWarning -m py_compile app\main.py app\services\market_service.py app\core\config.py
```
결과: clean(경고 없음).

## 4. 실행하지 않은 명령과 이유

- `.env.example` 갱신: 하네스 권한 규칙이 `.env*` 매칭으로 `.env.example` 읽기/편집을 차단해 수정하지 못했다(시크릿 보호 정책과 동일 경로). 신규 env는 본 문서와 feature 문서 `Contracts`에 명시했다. 필요 시 사용자가 직접 다음 두 줄을 추가하면 된다: `MARKET_PRICE_FETCH_TIMEOUT_SECONDS=30`, `MARKET_NEWS_FETCH_TIMEOUT_SECONDS=20`.
- `npm run lint`/`npm run build`: 프론트엔드 변경이 없어 실행하지 않음.
- 실제 provider key가 있는 배포/스테이징 워밍업 smoke: 로컬에서 외부 key/네트워크 없이 재현 불가. 다음 배포 로그에서 `failed:` 줄 수 감소와 `timeout after 30s` 표기로 확인 예정.

## 5. 남은 위험과 후속

- 종목 수가 더 늘면 30s/20s 안에도 직렬 큐가 안 빠질 수 있다. 그때는 계획서의 후보 B(공식 API 한정 동시성 상향) 또는 후보 E(스냅샷에서 history 호출 분리)를 별도 승인 후 진행한다.
- 비차단 워밍업으로 기동 직후 짧게 `/api/market/prices`가 빈 그룹을 반환할 수 있다. 엔드포인트는 빈 캐시를 정상 degrade하도록 이미 설계되어 있다.
- 타임아웃은 env로 조정 가능(최소 5s). 기본 미설정 시 30s/20s가 적용된다(이전 15s/8s보다 길어짐).

## 6. 영향받은 문서

- `docs/harness/features/market-data.md` — Data Flow, Contracts, Open Risks, Change Records 갱신.
- `docs/harness/feature-index.md` — market-data 행에 본 구현/계획 기록 링크 추가.
- `docs/harness/error-casebook-2026-06-03.md` — 사례 10(빈 `failed:` = 직렬화+타임아웃 충돌) 추가.
