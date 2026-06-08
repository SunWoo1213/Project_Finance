# 데모 환경 무료 티어 데이터 수집 주기 완화 계획

Date: 2026-06-08
Status: Plan only - 코드/배포 설정 미변경
Feature:
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/deployment-runtime.md`

## Objective

무료 티어 API 호출 제한에 자주 걸리는 문제를 줄이기 위해, 실제 상용 서비스가 아니라 졸업작품/시연용 데모 환경에 맞춰 외부 시장 데이터와 AI 리포트 생성 주기를 길게 가져가는 운영 계획을 정리한다.

핵심 목표는 다음과 같다.

- 사용자 화면은 캐시된 시장 데이터와 저장된 리포트를 읽는다.
- 주기 작업은 데모에 필요한 최소 빈도로만 외부 provider를 호출한다.
- 일반 사용자 요청, asset detail 진입, 챗봇 질문은 fresh AI 리포트 생성을 트리거하지 않는다.
- 무료 티어 제한을 피하기 위해 실시간성보다 안정적인 데모 표시를 우선한다.

## Current Code Facts

- `backend/app/core/config.py`는 이미 시장 데이터 주기를 환경 변수로 분리한다.
  - `MARKET_PRICES_REFRESH_MINUTES` 기본값: `5`
  - `MARKET_NEWS_REFRESH_MINUTES` 기본값: `60`
  - `MARKET_LATEST_CONTEXT_TTL_MINUTES` 기본값: `10`
- `backend/app/main.py`는 `ENABLE_SCHEDULER=true`일 때 APScheduler에 가격/뉴스 job을 등록한다.
- `ENABLE_MARKET_WARMUP=true`이면 startup 직후 가격/뉴스 warm-up을 백그라운드로 실행한다.
- AI 리포트 생성은 `ENABLE_SCHEDULER=true`와 `ENABLE_AI_REPORT_GENERATION=true`가 모두 켜져야 등록된다.
- 기본 AI 리포트 주기는 `REPORT_SCHEDULER_INTERVAL_HOURS=6`, 대상은 대표 ticker 5개이다.
- `POST /api/ai/generate/{ticker}`는 일반 사용자에게 HTTP 403을 반환한다.
- `GET /api/reports/{ticker}`는 저장된 최신 `AIReport`만 반환한다.
- 챗봇은 저장된 리포트와 캐시된 시장 데이터만 읽어야 하며, 리포트 생성 도구를 호출하지 않는다.

## Recommended Demo Runtime Profile

첫 번째 구현은 코드 변경 없이 배포 환경 변수만 조정하는 방식으로 진행한다. 기본값은 개발/로컬 빠른 확인용으로 유지하고, 데모 배포 환경에서만 긴 주기를 적용한다.

```dotenv
ENABLE_MARKET_WARMUP=true
ENABLE_SCHEDULER=true
ENABLE_AI_REPORT_GENERATION=false

MARKET_PRICES_REFRESH_MINUTES=360
MARKET_NEWS_REFRESH_MINUTES=720
MARKET_LATEST_CONTEXT_TTL_MINUTES=360

FMP_DAILY_CALL_BUDGET=50
ENABLE_STOOQ_FALLBACK=false

ENABLE_NOTIFICATION_SCHEDULER=false
ENABLE_LLM_CHATBOT=false
```

의도:

- 가격 캐시는 6시간마다 갱신한다.
- 뉴스 캐시는 12시간마다 갱신한다.
- ticker별 latest-context는 6시간 TTL로 재사용한다.
- AI 리포트 자동 생성은 데모 기본값에서 꺼 둔다. 이미 저장된 리포트를 보여주는 방식으로 시연한다.
- Stooq fallback은 Render timeout이 반복된 이력이 있으므로 데모 기본값에서 끈다.
- 알림 scheduler와 LLM 챗봇은 데모 핵심 시나리오가 아니면 꺼서 provider/API 호출을 줄인다.

주의: `ENABLE_MARKET_WARMUP=true`는 서버 시작 시 한 번 외부 provider를 호출한다. Render Free처럼 cold start가 잦은 환경에서는 startup마다 호출이 반복될 수 있으므로, 제한이 계속 걸리면 아래 최소 호출 프로파일로 전환한다.

## Minimal-Call Demo Profile

free-tier 제한이 계속 발생하거나 cold start가 잦은 배포에서는 다음 프로파일을 사용한다.

```dotenv
ENABLE_MARKET_WARMUP=false
ENABLE_SCHEDULER=true
ENABLE_AI_REPORT_GENERATION=false

MARKET_PRICES_REFRESH_MINUTES=720
MARKET_NEWS_REFRESH_MINUTES=1440
MARKET_LATEST_CONTEXT_TTL_MINUTES=720

FMP_DAILY_CALL_BUDGET=30
ENABLE_STOOQ_FALLBACK=false
ENABLE_NOTIFICATION_SCHEDULER=false
ENABLE_LLM_CHATBOT=false
```

trade-off:

- startup provider 호출은 줄어든다.
- 첫 scheduler 실행 전에는 in-memory market cache가 비어 있거나 이전 기본 payload에 가까울 수 있다.
- 시연 직전 backend를 켜고 첫 scheduler 실행을 기다리거나, 운영자가 별도 점검 시간에 warm-up이 끝난 상태를 확인해야 한다.

## Optional Stored-Report Demo Profile

데모에서 AI 리포트까지 보여줘야 하지만 OpenAI/API 비용을 줄이고 싶다면, report scheduler를 매우 좁게 켠다.

```dotenv
ENABLE_SCHEDULER=true
ENABLE_AI_REPORT_GENERATION=true
REPORT_SCHEDULER_TARGET_TICKERS=NVDA
REPORT_SCHEDULER_MAX_REPORTS_PER_RUN=1
REPORT_SCHEDULER_INTERVAL_HOURS=24
REPORT_SCHEDULER_ASSET_COOLDOWN_HOURS=24
REPORT_SCHEDULER_STARTUP_DELAY_SECONDS=300
ENABLE_LLM_REPORT_CRITICS=false
```

이 프로파일은 OpenAI와 market provider 비용이 발생할 수 있으므로 적용 전에 사용자 확인이 필요하다. 데모용으로는 사전에 한 번 저장된 `AIReport`를 만든 뒤 `ENABLE_AI_REPORT_GENERATION=false`로 되돌리는 흐름이 더 안전하다.

## Implementation Plan

### Phase 1. 운영 설정만 조정

- 배포 환경 변수에 `Recommended Demo Runtime Profile` 값을 적용한다.
- `.env` 값은 출력하거나 문서에 실제 값을 기록하지 않는다.
- 배포 후 로그에서 다음을 확인한다.
  - `[lifespan] scheduler started`
  - `prices:360m`
  - `news:720m`
  - `reports: disabled by ENABLE_AI_REPORT_GENERATION`
- `/health`와 `/db-check`로 앱/DB 상태를 분리 확인한다.

### Phase 2. 데모 전 캐시 상태 점검

- `/api/market/prices`가 주요 카드 데이터(S&P 500, Nasdaq 100, USD/KRW, KOSPI 등)를 반환하는지 확인한다.
- `/api/market/news`가 빈 값이어도 화면이 깨지지 않는지 확인한다.
- `/api/market/latest-context/{ticker}`는 데모 ticker 몇 개만 직접 확인한다. `force_refresh=true`는 무료 provider 호출을 늘릴 수 있으므로 데모 운영 중에는 사용하지 않는다.
- 저장 리포트 시연이 필요하면 `/api/reports/NVDA`가 200인지 확인한다. 404이면 화면은 pending 상태를 보여야 하며, 사용자 요청으로 생성하지 않는다.

### Phase 3. 필요 시 코드 기반 데모 프로파일 추가

환경 변수 운영만으로 충분하지 않으면 `backend/app/core/config.py`에 `RUNTIME_PROFILE` 또는 `DATA_CADENCE_PROFILE` 같은 명시적 profile 변수를 추가한다.

예상 동작:

- `DATA_CADENCE_PROFILE=development`: 기존 기본값 유지.
- `DATA_CADENCE_PROFILE=demo`: prices 360분, news 720분, latest-context 360분, report 24시간/1개 target 권장.
- 개별 env가 지정되면 profile 기본값보다 개별 env를 우선한다.

이 단계는 코드 변경이므로 구현 시 별도 implementation record를 작성하고, `backend/tests/`에 설정 우선순위 테스트를 추가한다.

### Phase 4. 문서와 배포 가이드 정리

구현 또는 운영 적용 후 다음 문서를 갱신한다.

- `docs/harness/features/market-data.md`: 데모 cadence와 provider 호출 제한 정책.
- `docs/harness/features/deployment-runtime.md`: hosted demo profile env 목록.
- `docs/harness/features/asset-detail-ai-community.md`: 리포트는 저장본 조회만 한다는 규칙 재확인.
- `docs/harness/feature-index.md`: 구현/운영 변경 기록 링크 추가.
- `ENVIRONMENT_VARIABLE_SETUP.md`: 실제 값 없이 변수명과 데모 권장 범위만 추가.

## Files Expected To Change If Implemented

환경 변수만 바꾸는 Phase 1은 저장소 파일 변경이 없다. 코드 기반 profile을 추가하면 다음 파일이 바뀔 수 있다.

- `backend/app/core/config.py`
- `backend/tests/test_database_config.py` 또는 신규 `backend/tests/test_runtime_profile_config.py`
- `ENVIRONMENT_VARIABLE_SETUP.md`
- `docs/harness/features/market-data.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/feature-index.md`
- 별도 구현 기록: `docs/harness/demo-free-tier-data-cadence-implementation-YYYY-MM-DD.md`

## Verification Plan

계획서 작성 단계에서는 코드 변경이 없으므로 build/test는 필수로 실행하지 않는다. 운영 적용 또는 구현 단계에서는 다음을 확인한다.

```powershell
cd backend
python -m pytest tests/test_database_config.py tests/test_market_warmup_timeout.py tests/test_price_providers.py
```

profile 설정 코드를 추가하면 다음 케이스를 테스트한다.

- demo profile 기본값이 prices/news/latest-context/report 주기를 길게 설정하는지.
- 개별 env가 profile 기본값을 override하는지.
- 0 또는 음수 cadence가 기존 validator처럼 최소 1로 보정되는지.
- `ENABLE_AI_REPORT_GENERATION=false`일 때 report scheduler가 등록되지 않는지.

프론트엔드 표시 변경이 없으면 frontend build는 생략 가능하다. UI fallback을 바꾸면 다음을 실행한다.

```powershell
cd frontend
npm run lint
npm run build
```

## User-Facing Report Generation Impact

데모 cadence 조정은 사용자 요청 기반 AI 리포트 생성을 추가하지 않는다. 사용자 화면과 챗봇은 계속 저장된 scheduled report만 읽는다. `ENABLE_AI_REPORT_GENERATION=true`를 켜는 선택지는 backend scheduler 또는 운영 task에만 적용되어야 하며, `POST /api/ai/generate/{ticker}`의 일반 사용자 403 정책은 유지한다.

## Risks And Follow-Up

- 주기를 길게 늘리면 데모 화면의 시장 데이터가 최신이 아닐 수 있다. 화면 문구나 발표 설명에서 “데모용 지연/캐시 데이터”임을 명확히 설명하는 것이 안전하다.
- `ENABLE_MARKET_WARMUP=true`는 startup 호출량을 만든다. cold start가 잦은 무료 배포에서는 오히려 호출 제한을 악화시킬 수 있다.
- `ENABLE_AI_REPORT_GENERATION=true`는 OpenAI와 provider 호출 비용을 만든다. target, max reports, cooldown을 줄이지 않고 켜면 무료 티어와 비용 제한을 다시 초과할 수 있다.
- process-local provider budget은 서버 재시작 시 초기화된다. 엄격한 일일 한도를 보장하려면 DB/Redis 기반 usage ledger가 필요하지만 데모 계획의 범위 밖이다.
- Render Free 같은 sleep 환경에서는 in-process scheduler가 안정적인 주기 실행을 보장하지 않는다. 데모 안정성이 더 중요하면 persistent backend 또는 token-protected external cron/task endpoint를 별도 계획으로 검토한다.
