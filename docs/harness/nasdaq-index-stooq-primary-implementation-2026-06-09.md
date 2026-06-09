# 나스닥 지수(^NDX) Stooq primary 구현

Date: 2026-06-09

## Objective

FMP free/stable 플랜이 지수 심볼을 제공하지 못해 나스닥 지수(`^NDX`, Nasdaq 100)가 빈/0 값으로 degrade되던 문제를 해결한다. 사용자가 삽입한 `STOOQ_API_KEY`를 활용해 **`^NDX`만** Stooq에서 가져오도록 한다. 전역 opt-in 플래그(`ENABLE_STOOQ_FALLBACK`)는 켜지 않으며, 다른 Stooq 경로(STOCK_US 종가 폴백, `KRW=X` 등락률 등)에는 영향을 주지 않는다.

관련 계획: `docs/harness/nasdaq-index-stooq-provider-plan-2026-06-09.md` (이 구현은 계획의 "2단계 — US 지수 Stooq primary"를 `^NDX` 단일 ticker로 좁혀 적용).

## Files Changed

- `backend/app/services/price_providers.py`
- `backend/tests/test_price_providers.py`
- `docs/harness/features/market-data.md` (feature 문서 갱신)
- `docs/harness/feature-index.md` (색인 갱신)

## Behavior Changes

### 1. `STOOQ_PRIMARY_SYMBOLS` 도입
- `STOOQ_PRIMARY_SYMBOLS = {"^NDX"}` 상수 추가.
- 이 집합의 ticker는 `ENABLE_STOOQ_FALLBACK`가 `False`여도 `STOOQ_API_KEY`만 있으면 Stooq를 사용한다.

### 2. `fetch_stooq_history` 게이트 완화 (scoped)
- 기존: `if not stooq_symbol or not key or not settings.ENABLE_STOOQ_FALLBACK: return 빈 history`.
- 변경: `force_stooq = ticker in STOOQ_PRIMARY_SYMBOLS`를 추가해, force 대상은 전역 플래그 없이도 통과한다. 심볼 매핑(`STOOQ_SYMBOLS`)과 `STOOQ_API_KEY`는 여전히 필수다.
- 따라서 `^NDX` 외 다른 ticker의 Stooq 동작은 기존과 완전히 동일하다(여전히 `ENABLE_STOOQ_FALLBACK` 필요).

### 3. 스냅샷 라우팅 (`fetch_market_snapshot`)
- `INDEX` 분기에서 KR 지수 다음, 일반 FMP 분기 앞에 `^NDX`(STOOQ_PRIMARY_SYMBOLS) 전용 분기를 추가.
- `_fetch_stooq_snapshot(normalized)`로 Stooq daily 종가/등락률을 가져오고, 값이 있으면 `provider_meta`(`provider="stooq"`, `symbol="^ndx"`, `freshness="daily_csv_primary"`)를 부여한다.
- FMP는 `^NDX`에 대해 더 이상 호출되지 않으므로 `FMP_DAILY_CALL_BUDGET`와 30분 cooldown을 낭비하지 않는다.

### 4. history 라우팅 (`fetch_market_history`)
- `^NDX`(STOOQ_PRIMARY_SYMBOLS)는 FMP/`{"^GSPC","^NDX"}` 분기보다 먼저 Stooq를 1차로 호출한다.
- `^GSPC`는 기존 동작(FMP 우선, opt-in 시 Stooq 폴백) 그대로 유지.

### 영향 범위 요약
- 변경: `^NDX` 스냅샷·history가 Stooq를 1차 소스로 사용(전역 플래그 불필요).
- 불변: `^GSPC`, STOCK_US 종가 폴백, `KRW=X` 등락률, 기타 Stooq 경로는 여전히 `ENABLE_STOOQ_FALLBACK` opt-in에 묶여 있다.
- AI 리포트 생성 정책 변경 없음. 사용자/대시보드/챗봇 요청은 fresh report를 트리거하지 않는다.

## Runtime Requirement

`^NDX`가 실제 값을 가져오려면 backend 환경에 `STOOQ_API_KEY`가 설정되어 있어야 한다. `ENABLE_STOOQ_FALLBACK`는 켤 필요가 없다(기본 `false` 유지 권장). 하네스는 `.env`를 열거나 출력하지 않으며, 키 설정은 배포 담당자가 수행한다.

## Stooq 심볼

- `STOOQ_SYMBOLS["^NDX"] = "^ndx"` (Stooq의 Nasdaq 100). 사용자 확인 결과 대상 지수는 Nasdaq 100이며, 이는 표시명("Nasdaq 100")과 일치한다. (Nasdaq Composite를 원했다면 `^ndq`로 매핑이 달라지나, 본 작업 범위는 Nasdaq 100이다.)

## Verification

- 실행: `& .\.venv\Scripts\python.exe -m pytest tests/test_price_providers.py -q` (backend 디렉터리)
- 결과: **38 passed** (신규 3개 포함).
  - `test_ndx_history_uses_stooq_without_global_optin`: `ENABLE_STOOQ_FALLBACK=False`에서도 `^NDX` history가 Stooq(`s="^ndx"`)를 호출하고 FMP는 호출되지 않음을 확인.
  - `test_ndx_snapshot_uses_stooq_without_global_optin`: `^NDX` 스냅샷이 Stooq 종가/메타를 반환하고 FMP 스냅샷이 호출되지 않음을 확인.
  - `test_ndx_stooq_requires_key`: `STOOQ_API_KEY`가 없으면 `^NDX`도 Stooq를 호출하지 않고 빈 history로 degrade함을 확인.

## Commands Not Run

- 실 Stooq 네트워크 smoke(실키 필요)는 quota/네트워크 영향이 있어 실행하지 않았다. 단위 테스트는 `_get_text`를 mock으로 대체했다.
- 프론트 빌드(`npm run build`)는 프론트 코드 변경이 없어 실행하지 않았다(홈은 기존 `/api/market/prices` macro 그룹을 그대로 사용).
- `.env`는 시크릿 보호 규칙에 따라 열람하지 않았다.

## Follow-up Risks

- Stooq daily CSV는 EOD/지연 데이터이며 `ConnectTimeout('')`/`Get your apikey` 응답 가능성이 있다. 실패 시 `_history_payload` 빈 값 + `_mark_failed_call` cooldown으로 degrade하고, `fetch_market_snapshot`의 stale 유지 로직이 직전 유효값을 보존한다. 콜드 스타트에서 첫 성공 이전·Stooq 장애가 겹치면 `^NDX`가 일시적으로 0/빈 값일 수 있다.
- `STOOQ_API_KEY` 미설정 환경에서는 `^NDX`가 빈 값으로 degrade된다(의도된 동작).
- Stooq 심볼 `^ndx` 유효성은 실데이터 smoke로 1회 확인 권장.
- 외부 provider 응답 형식/심볼 정책은 코드 변경 없이 바뀔 수 있다.

## Feature Links

- `docs/harness/features/market-data.md`
- `docs/harness/feature-index.md`
- `docs/harness/nasdaq-index-stooq-provider-plan-2026-06-09.md`
