# 시장 가격 데이터 일일 API 갱신 계획

Date: 2026-06-09
Status: Plan only - 코드/배포 설정 미변경

## Objective

데모 목적의 시장 데이터 운영에서 가격 API 호출을 자주 하지 않고, 하루 1회 수준으로 제한한다. 메인 대시보드 지수 4개는 live provider 경로를 유지하되, 전체 서비스는 프로덕션 실시간 시세가 아니라 지연/캐시 기반 데모 데이터로 동작하도록 한다.

핵심 목표:

- `GET /api/market/prices`는 외부 provider를 직접 호출하지 않고 기존 `market_cache["prices"]`만 반환한다.
- 가격 캐시 갱신 job이 하루 1회 수준으로 외부 API를 호출한다.
- allowlist 밖 자산은 계속 `demo_mock`을 사용한다.
- 일반 사용자 화면, 자산 상세 진입, 챗봇 요청은 fresh AI report generation을 트리거하지 않는다.

## Current Code Facts

- 가격 갱신 주기는 이미 환경변수 `MARKET_PRICES_REFRESH_MINUTES`로 분리되어 있다.
  - 현재 코드 기본값: `5`
  - 위치: `backend/app/core/config.py`
- `backend/app/main.py`는 `ENABLE_SCHEDULER=true`일 때 `update_prices_task`를 interval job으로 등록한다.
  - `minutes=settings.MARKET_PRICES_REFRESH_MINUTES`
- `ENABLE_MARKET_WARMUP=true`이면 backend startup 직후 `update_prices_task()`와 `update_news_task()`를 백그라운드로 한 번 실행한다.
- `GET /api/market/prices`는 provider를 호출하지 않고 인메모리 `market_cache["prices"]`만 반환한다.
- `MARKET_LIVE_TICKERS` allowlist 밖 ticker는 `demo_mock` 값으로 응답하므로 외부 provider 호출량을 만들지 않는다.
- 현재 데모 allowlist는 대표 5개 + 홈 대시보드 4개만 live로 두는 방향이다.

## Important Semantics

`MARKET_PRICES_REFRESH_MINUTES=1440`만 설정하면 scheduler 기준 가격 갱신은 24시간 간격이 된다. 하지만 다음 케이스는 별도 호출을 만들 수 있다.

- `ENABLE_MARKET_WARMUP=true`: 서버 시작마다 가격 warm-up이 한 번 실행된다.
- 서버가 자주 재시작되는 무료/슬립 런타임: startup warm-up 때문에 하루 1회보다 많이 호출될 수 있다.
- `GET /api/market/history/{ticker}` 또는 `GET /api/market/latest-context/{ticker}`는 allowlist 안 ticker에서 별도 provider 경로를 탈 수 있다.

따라서 “대략 하루마다 갱신”과 “강하게 하루 1회 이하로 제한”은 운영안이 다르다.

## Recommended Demo Plan

### Phase 1. 환경변수만으로 일일 가격 갱신 적용

데모 안정성과 즉시 표시를 우선하면 아래 설정을 적용한다.

```dotenv
ENABLE_MARKET_WARMUP=true
ENABLE_SCHEDULER=true

MARKET_PRICES_REFRESH_MINUTES=1440
MARKET_NEWS_REFRESH_MINUTES=1440
MARKET_LATEST_CONTEXT_TTL_MINUTES=1440

MARKET_LIVE_TICKERS=DGS10,XAU,BTC-USD,NVDA,005930.KS,^GSPC,^NDX,KRW=X,^KS11
ENABLE_AI_REPORT_GENERATION=false
ENABLE_NOTIFICATION_SCHEDULER=false
ENABLE_LLM_CHATBOT=false
```

동작:

- 서버 시작 시 데모 화면을 채우기 위해 한 번 warm-up한다.
- 이후 가격/뉴스/latest-context는 하루 단위로 재사용한다.
- provider 호출량은 매우 줄지만, 서버 재시작이 잦으면 startup warm-up 호출이 추가된다.

적합한 경우:

- 로컬 또는 장시간 살아있는 데모 backend.
- 발표 전 backend를 한 번 켜두고 화면 데이터가 채워진 상태로 시연하는 경우.

### Phase 2. Startup 호출까지 줄이는 최소 호출 프로파일

무료 배포에서 cold start가 잦아 startup warm-up이 호출량을 만든다면 아래 설정을 적용한다.

```dotenv
ENABLE_MARKET_WARMUP=false
ENABLE_SCHEDULER=true

MARKET_PRICES_REFRESH_MINUTES=1440
MARKET_NEWS_REFRESH_MINUTES=1440
MARKET_LATEST_CONTEXT_TTL_MINUTES=1440

MARKET_LIVE_TICKERS=DGS10,XAU,BTC-USD,NVDA,005930.KS,^GSPC,^NDX,KRW=X,^KS11
ENABLE_AI_REPORT_GENERATION=false
ENABLE_NOTIFICATION_SCHEDULER=false
ENABLE_LLM_CHATBOT=false
```

주의:

- 현재 price scheduler는 interval job이라, warm-up을 끄면 프로세스 시작 직후 바로 가격 캐시가 채워지지 않을 수 있다.
- 인메모리 `market_cache`만 사용하는 구조에서는 재시작 후 첫 scheduler 실행 전까지 `/api/market/prices`가 비거나 부족할 수 있다.
- 이 프로파일을 안정적으로 쓰려면 “시연 전 캐시 채우기” 절차나 캐시 영속화가 필요하다.

### Phase 3. 하루 1회 보장을 강화하는 코드 개선

정말로 “하루마다 한 번만 API를 가져오는” 정책을 코드로 보장하려면 환경변수만으로는 부족하다. 다음 중 하나를 추가한다.

1. `update_prices_task()` 실행 시 `market_cache["last_updated"]["prices"]`를 보고 24시간 미만이면 provider 수집을 skip한다.
2. `MARKET_PRICES_MIN_REFRESH_HOURS=24` 같은 guard 설정을 추가해 scheduler, warm-up, 수동 내부 호출 모두 같은 최소 간격을 따른다.
3. `market_cache`를 인메모리가 아니라 DB 또는 Redis에 저장해 재시작 후에도 마지막 갱신 시각과 payload를 유지한다.
4. 데모 전용으로 token-protected admin endpoint 또는 scheduled external cron을 두고, backend scheduler는 끈다.

권장 우선순위:

- 단기 데모: Phase 1 환경변수 적용.
- cold start가 잦은 무료 배포: Phase 2 + 발표 전 warm-up 절차.
- 장기 데모 안정화: Phase 3의 DB/Redis 기반 price snapshot cache.

## Implementation Plan If Code Change Is Approved

### Step 1. 설정 문서 갱신

- `.env.example`
  - 데모 권장값으로 `MARKET_PRICES_REFRESH_MINUTES=1440` 주석 추가.
  - 기본값 자체를 바꿀지, 배포 환경변수만 바꿀지 결정 필요.
- `docs/harness/features/market-data.md`
  - 데모에서는 가격 갱신을 일일 캐시로 운영할 수 있음을 명시.

### Step 2. 선택적 코드 guard 추가

새 설정 예시:

```python
MARKET_PRICES_MIN_REFRESH_HOURS: int = 24
```

예상 로직:

- `update_prices_task(force: bool = False)` 형태로 확장한다.
- `force=false`이고 마지막 `prices` 갱신이 24시간 미만이면 provider 호출 없이 skip한다.
- startup warm-up도 기본적으로 guard를 따르게 한다.
- 필요한 경우 로컬 개발에서만 `force=true` 또는 `MARKET_PRICES_MIN_REFRESH_HOURS=0`을 허용한다.

### Step 3. 테스트

- 24시간 미만이면 `_collect_prices_group()`이 호출되지 않는지 테스트한다.
- 24시간 이상 지났으면 기존처럼 provider/mock 수집이 실행되는지 테스트한다.
- `force=true` 또는 guard 비활성 값이 의도대로 동작하는지 테스트한다.
- `last_updated` 값이 없으면 최초 1회는 수집되는지 테스트한다.

### Step 4. 운영 절차

- 배포 환경변수 변경 후 backend를 재시작한다.
- 로그에서 `prices:1440m`를 확인한다.
- `/api/market/prices`의 `macro` 그룹이 홈 카드 4개를 반환하는지 확인한다.
- provider key가 없는 환경에서는 `0`/빈 payload/fallback 가능성을 데모 리스크로 기록한다.

## Files Expected To Change If Implemented

환경변수 운영만 적용하면 저장소 코드 변경은 필요 없다. 코드 guard까지 구현하면 다음 파일이 바뀔 수 있다.

- `backend/app/core/config.py`
- `backend/app/services/market_service.py`
- `backend/app/main.py` (startup warm-up force/guard 정책을 명확히 할 경우)
- `backend/tests/test_market_warmup_timeout.py` 또는 신규 `backend/tests/test_market_refresh_cadence.py`
- `.env.example`
- `docs/harness/features/market-data.md`
- `docs/harness/feature-index.md`
- 구현 기록: `docs/harness/market-data-daily-price-refresh-implementation-YYYY-MM-DD.md`

## Verification Plan

환경변수만 바꾸는 경우:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_price_providers.py tests/test_market_history_route.py
```

코드 guard를 구현하는 경우:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_market_refresh_cadence.py tests/test_price_providers.py tests/test_market_history_route.py
```

프론트 코드는 변경하지 않으므로 기본적으로 `npm run build`는 필수는 아니다. 홈 UI fallback까지 바꾸면 다음을 실행한다.

```powershell
cd frontend
npm run build
```

## Commands Not Run

- 본 작업은 계획서 작성만 수행했으므로 테스트와 빌드는 실행하지 않았다.
- `.env`는 시크릿 보호 규칙에 따라 열람하지 않았다.
- 실제 provider smoke는 API quota와 키 상태에 영향을 줄 수 있어 실행하지 않았다.

## User-Facing Report Generation Impact

가격 갱신 주기를 하루 단위로 늘려도 AI 리포트 생성 정책은 바뀌지 않는다. 사용자 화면과 챗봇은 계속 저장된 scheduled report만 읽어야 하며, `POST /api/ai/generate/{ticker}`의 일반 사용자 403 정책은 유지한다.

## Risks And Follow-Up

- 하루 1회 갱신은 데모 안정성에는 좋지만, 화면의 수치가 최신 실시간 시세처럼 보이면 오해가 생길 수 있다. UI 또는 발표 설명에서 “데모용 지연/캐시 데이터”임을 명확히 하는 것이 좋다.
- `ENABLE_MARKET_WARMUP=true`는 재시작마다 API 호출을 만든다. 엄격한 일일 호출 제한이 필요하면 warm-up guard 또는 영속 cache가 필요하다.
- 인메모리 cache는 재시작 시 사라진다. 하루 1회 정책과 즉시 표시를 동시에 만족하려면 DB/Redis snapshot 저장이 가장 안정적이다.
- Render Free 같은 sleep 환경에서는 in-process APScheduler가 정확히 하루마다 실행된다는 보장이 약하다. 안정적인 데모에는 persistent backend 또는 external cron이 더 적합하다.

## Feature Links

- `docs/harness/features/market-data.md`
- `docs/harness/feature-index.md`
- `docs/harness/demo-free-tier-data-cadence-plan-2026-06-08.md`
