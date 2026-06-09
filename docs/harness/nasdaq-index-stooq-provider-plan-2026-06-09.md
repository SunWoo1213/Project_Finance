# 나스닥 지수(^NDX) Stooq provider 전환 계획

Date: 2026-06-09

## Objective

메인 대시보드 및 시장 데이터에서 **나스닥 지수(`^NDX`, Nasdaq 100)**가 값을 가져오지 못하는 문제를 해결한다. FMP free/stable 플랜이 지수 심볼을 제공하지 못해 `^NDX`가 빈/0 값으로 degrade되는 상황에서, 사용자가 삽입한 `STOOQ_API_KEY`를 실제로 활용해 `^NDX`(필요 시 `^GSPC` 포함) 가격·등락률·history를 가져올 수 있도록 provider 경로와 게이트 설정을 정비한다.

이 계획은 새 외부 API를 추가하지 않는다. 이미 코드에 존재하는 Stooq 경로(`fetch_stooq_history` / `_fetch_stooq_snapshot`)와 `STOOQ_SYMBOLS["^NDX"] = "^ndx"` 매핑을 재사용한다.

## Current Behavior (코드 점검 결과)

### 지수 라우팅
- `^NDX`는 `INDICES`에 `"Nasdaq 100": "^NDX"`로 정의되고 `MACRO_ASSETS`에서 `INDEX` 카테고리로 분류된다.
  - `backend/app/services/market_service.py:29`
  - `backend/app/services/market_service.py:175`
- 스냅샷은 `fetch_market_snapshot()`에서 카테고리로 분기한다. `^NDX`는 `KR_INDEX_NAMES`에 없으므로 `INDEX` → `_fetch_fmp_snapshot()`로 라우팅된다.
  - `backend/app/services/price_providers.py:1095-1098`
- history도 `fetch_market_history()`에서 `^NDX ∈ {"^GSPC","^NDX"}` 조건으로 FMP를 먼저 호출하고, **`ENABLE_STOOQ_FALLBACK`가 true일 때만** Stooq로 폴백한다.
  - `backend/app/services/price_providers.py:1133-1136`

### FMP가 지수를 못 가져오는 지점
- `_fetch_fmp_snapshot()`는 FMP quote/EOD history를 시도하고, 결과가 비면 **`settings.ENABLE_STOOQ_FALLBACK`가 true인 경우에만** `_fetch_stooq_snapshot()`로 폴백한다.
  - `backend/app/services/price_providers.py:571-579`
- FMP `stable` 플랜은 `^NDX` 같은 지수 심볼을 quote/`historical-price-eod/full`에서 정상 반환하지 못해 `currentPrice=0` + 빈 history로 degrade된다(이미 기존 문서들이 "FMP 지수 quota/플랜 제약"으로 기록).

### Stooq 경로가 막혀 있는 지점 (핵심 원인)
- Stooq 심볼 매핑은 이미 존재한다: `STOOQ_SYMBOLS["^NDX"] = "^ndx"` (Stooq의 Nasdaq 100 심볼), `"^GSPC" = "^spx"`.
  - `backend/app/services/price_providers.py:51-69`
- `STOOQ_API_KEY` 설정 필드와 `_stooq_key()` 헬퍼도 이미 존재한다.
  - `backend/app/core/config.py:71`
  - `backend/app/services/price_providers.py:274-275`
- 그러나 `fetch_stooq_history()`는 세 게이트를 모두 통과해야 호출된다: `stooq_symbol` 존재, `key` 존재, **`settings.ENABLE_STOOQ_FALLBACK`**.
  - `backend/app/services/price_providers.py:811`
- `_fetch_fmp_snapshot()`의 Stooq 폴백도 `settings.ENABLE_STOOQ_FALLBACK` 조건이다.
  - `backend/app/services/price_providers.py:571`
- **`ENABLE_STOOQ_FALLBACK`의 기본값은 `False`.**
  - `backend/app/core/config.py:117`

### 결론
사용자가 `STOOQ_API_KEY`를 넣었더라도 **`ENABLE_STOOQ_FALLBACK`가 켜지지 않으면 Stooq는 단 한 번도 호출되지 않는다.** `^NDX`는 FMP에서 실패 → Stooq 폴백 차단 → 빈/0 값으로 굳는다. (`fetch_market_snapshot`의 stale 유지 로직 때문에 직전 유효값이 없으면 0이 그대로 남는다.)

부차적 사실: live/mock 게이트(`MARKET_LIVE_TICKERS`)에는 `^NDX`가 이미 포함되어 있어 mock 차단 문제는 아니다.
  - `backend/app/core/config.py:97`

## Target Behavior

1. `^NDX`(및 `^GSPC`)가 Stooq를 통해 실제 종가·등락률·history를 반환한다.
2. `STOOQ_API_KEY`가 설정된 환경에서 Stooq가 실제로 호출된다.
3. FMP가 지수에서 계속 실패해도 사용자/대시보드는 빈 값 대신 Stooq daily 값을 본다.
4. AI 리포트 생성 정책은 변경하지 않는다. 사용자/대시보드/챗봇 요청은 fresh report를 트리거하지 않는다.
5. Stooq를 광범위하게 강제로 켜지 않는다. 무료 provider 호출량/타임아웃 가드레일(`STOOQ_FETCH_TIMEOUT_SECONDS`, failed-call cooldown)을 유지한다.

## Implementation Plan

두 가지 경로를 제시한다. **권장은 1단계(설정만)** 이며, FMP 비용/cooldown 낭비까지 없애려면 2단계(코드)를 옵션으로 더한다.

### 1단계 — 설정만으로 Stooq 폴백 활성화 (권장, 코드 변경 없음)

배포/로컬 backend 환경변수에 다음을 설정한다(하네스는 `.env`를 직접 열거나 출력하지 않는다. 배포 담당자가 설정):

```text
ENABLE_STOOQ_FALLBACK=true
STOOQ_API_KEY=<사용자 발급 키>
```

- 효과: FMP가 `^NDX`에서 빈 값을 반환하면 `_fetch_fmp_snapshot()`가 `_fetch_stooq_snapshot()`로 폴백하고, history도 Stooq로 폴백한다.
- 장점: 코드 변경 없음, 기존 동작과 호환, 즉시 적용 가능.
- 한계/주의:
  - Stooq는 **FMP 시도 후 폴백**이므로, 매 갱신 사이클마다 FMP 호출이 먼저 일어나 `FMP_DAILY_CALL_BUDGET`를 소모하고 30분 cooldown을 거친다. 지수처럼 FMP가 항상 실패하는 대상에는 비효율적이다.
  - `ENABLE_STOOQ_FALLBACK=true`는 `^NDX`뿐 아니라 STOCK_US 종가 폴백, `KRW=X` 등락률 폴백 등 **다른 Stooq 경로도 전역적으로 켠다**. 기존 문서가 경고한 Stooq `ConnectTimeout('')` 반복 위험이 있어, 켠 뒤 로그 관찰이 필요하다.

### 2단계 — US 지수를 Stooq primary로 라우팅 (옵션, 코드 변경)

FMP가 지수를 구조적으로 못 주는 점을 반영해, `^GSPC`/`^NDX`는 Stooq를 1차로 시도하고 FMP를 보조로 둔다. FMP 예산/cooldown 낭비를 없애고, FMP 실패에 의존하지 않는 안정적 경로를 만든다.

대상 파일: `backend/app/services/price_providers.py` (backend 단일 파일)

- (a) 스냅샷 라우팅: `fetch_market_snapshot()`의 `INDEX` 분기에서, KR 지수가 아닌 US 지수(`^GSPC`, `^NDX`)는 Stooq를 먼저 시도하는 전용 경로로 분기한다.
  - 현재 `backend/app/services/price_providers.py:1097-1098`의 `elif category == "INDEX": payload = await _fetch_fmp_snapshot(normalized)`를 US 지수 전용 헬퍼(예: `_fetch_index_snapshot`)로 교체한다.
  - 새 헬퍼는 `ENABLE_STOOQ_FALLBACK`가 true이고 `STOOQ_API_KEY`가 있으면 Stooq를 먼저 호출하고, Stooq가 비면 FMP로 폴백한다(또는 그 반대 순서를 유지하되 FMP가 빈 값일 때 budget을 쓰지 않도록 한다).
- (b) history 라우팅: `fetch_market_history()`의 `^GSPC/^NDX` 분기에서도 동일하게 Stooq 우선 시도 후 FMP 보조로 순서를 조정한다.
  - `backend/app/services/price_providers.py:1133-1136`
- (c) 게이트 일관화: US 지수의 Stooq 사용을 `ENABLE_STOOQ_FALLBACK`에 계속 묶을지, 아니면 지수에 한해 `STOOQ_API_KEY` 존재만으로 허용할지 결정한다. **현재 가드레일을 흔들지 않으려면 `ENABLE_STOOQ_FALLBACK` 게이트를 유지**하고 1단계 설정을 전제로 하는 것이 안전하다.
- (d) `provider_meta` 보존: Stooq로 채운 지수 응답에 `provider="stooq"` 메타를 남겨 진단 가능하게 한다(기존 `_fetch_fmp_snapshot` 폴백 메타 패턴 재사용).

> 2단계는 provider 우선순위라는 동작 변경이므로 1단계로 먼저 검증한 뒤 필요할 때만 진행하길 권장한다.

### Stooq 심볼 검증
- `^NDX` → `^ndx`(Nasdaq 100) 매핑이 Stooq에서 유효한지 구현/검증 단계에서 1회 실데이터로 확인한다. 사용자의 의도가 Nasdaq Composite(`^IXIC`)라면 Stooq 심볼은 `^ndq`로 달라지므로, 표시명("Nasdaq 100")과 실제 원하는 지수를 먼저 확정한다.

## 변경 대상 파일

| 구분 | 파일 | 변경 |
| --- | --- | --- |
| 설정(런타임 env) | 배포/로컬 `.env` (하네스가 직접 수정 안 함) | `ENABLE_STOOQ_FALLBACK=true`, `STOOQ_API_KEY=...` |
| 설정(기본값) | `backend/app/core/config.py` | (옵션) `ENABLE_STOOQ_FALLBACK` 기본값 논의 — 기본 true 전환은 전역 영향이라 비권장 |
| 문서 안내 | `.env.example` | Stooq 활성화 방법/주의 주석 보강 (시크릿 값은 넣지 않음) |
| backend (2단계 옵션) | `backend/app/services/price_providers.py` | US 지수 Stooq-primary 라우팅 헬퍼 추가, snapshot/history 분기 조정 |
| test | `backend/tests/test_price_providers.py` | 지수 Stooq 분기 단위 테스트 추가 |
| 문서 | `docs/harness/features/market-data.md`, `docs/harness/feature-index.md` | 변경 기록 링크 및 지수 provider 설명 갱신 |

## 위험과 Risky Change 여부 (AGENTS.md 섹션 9)

- **provider 동작/우선순위 변경(2단계)**: 시장 데이터 가져오는 경로의 동작 변경이다. DB 스키마·인증·리포트 비용과는 무관하나, provider 호출 패턴이 바뀌므로 구현 전 사용자 확인이 바람직하다.
- **`ENABLE_STOOQ_FALLBACK` 전역 활성화**: 이 플래그는 지수뿐 아니라 STOCK_US 종가 폴백, `KRW=X` 등락률 등 **여러 경로를 동시에 켠다**. 기존 문서들이 Stooq `ConnectTimeout` 반복과 타임아웃 위험을 경고했으므로(`docs/harness/stooq-timeout-fallback-2026-06-07.md`, `render-standard-market-provider-timeout-remediation-2026-06-07.md`), 켠 뒤 로그/타임아웃을 관찰해야 한다. → **사용자 승인 필요 항목**.
- **`ENABLE_STOOQ_FALLBACK` 기본값을 true로 바꾸는 것은 권장하지 않는다.** 데모 가드레일(무료 provider 호출 통제)을 흔든다. 환경변수로만 켜는 것이 안전하다.
- 비용: Stooq는 무료 daily CSV이며 새 유료 API가 아니다. 단, 네트워크 호출이 늘어날 수 있어 cooldown/timeout 가드레일을 유지한다.
- AI 리포트: 본 변경은 리포트 스케줄·cooldown·생성 트리거를 건드리지 않는다(섹션 14 무관). 사용자/챗봇은 저장된 리포트만 읽는다.

## 검증 계획 (AGENTS.md 섹션 6, 최소 집합)

1. 정적 확인
   - `rg -n "ENABLE_STOOQ_FALLBACK|STOOQ_SYMBOLS|_fetch_fmp_snapshot|fetch_stooq_history" backend/app/services/price_providers.py backend/app/core/config.py`
2. 백엔드 단위 테스트
   - `cd backend`
   - `pytest tests/test_price_providers.py`
   - 2단계 진행 시: 지수 Stooq 분기(키 있음/없음, `ENABLE_STOOQ_FALLBACK` on/off) 테스트를 추가하고 함께 실행. 실 LLM·실 provider 네트워크 호출은 mock으로 대체(AGENTS.md 섹션 4).
3. 로컬 smoke (실키 필요, quota 소모 인지)
   - `ENABLE_STOOQ_FALLBACK=true`, `STOOQ_API_KEY=...` 설정 후 backend 기동
   - `GET /api/market/prices`의 `macro` 그룹에서 `^NDX`의 `currentPrice`가 0이 아닌지 확인
   - 또는 backend 셸에서 `fetch_market_snapshot("^NDX", "INDEX")`를 직접 호출해 Stooq 값 확인
   - frontend `/`에서 Nasdaq 100 카드가 표시되는지 확인
4. 미실행 명령
   - 본 단계는 계획서 작성만 수행 — 테스트/빌드/실 provider 호출 미실행
   - `.env`는 시크릿 보호 규칙에 따라 열람하지 않음

## 갱신할 문서

- `docs/harness/features/market-data.md`
  - US 지수 provider 설명에 "FMP는 free 플랜에서 지수를 제공하지 못하며, `ENABLE_STOOQ_FALLBACK=true` + `STOOQ_API_KEY`로 Stooq daily 값을 사용"을 명시. 2단계 진행 시 Stooq-primary 라우팅을 반영.
  - 구현 기록 링크를 `Change Records`에 추가.
- `docs/harness/feature-index.md`
  - Market data 변경 기록에 본 계획 및 후속 구현 기록을 연결.
- (참고) `docs/harness/dashboard-indices-realtime-api-plan-2026-06-09.md`가 이미 "`^NDX`는 FMP, Stooq 폴백은 opt-in"을 기록함 — 본 계획은 그 opt-in을 실제로 켜고(필요 시 라우팅을 강화) 나스닥을 가져오는 후속에 해당.

## Feature Links

- `docs/harness/features/market-data.md`
- `docs/harness/feature-index.md`
- `docs/harness/dashboard-indices-realtime-api-plan-2026-06-09.md`
- `docs/harness/market-data-free-plan-stooq-replacement-plan-2026-06-07.md`
- `docs/harness/stooq-timeout-fallback-2026-06-07.md`
