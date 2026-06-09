# 원달러(USD/KRW, `KRW=X`) 변동성(`changePercent`) 미표시 해결 — 구현 기록

날짜: 2026-06-09
관련 계획: [krw-fx-change-percent-not-captured-plan-2026-06-09.md](krw-fx-change-percent-not-captured-plan-2026-06-09.md)
게이팅 결정: **A안 — `STOOQ_API_KEY`가 있으면 활성**(사용자 승인 완료)

## 목적

USD/KRW 스냅샷의 `changePercent`가 기본 배포에서 항상 0(변동 없음)으로 표시되던 문제를 해결한다. 등락 계산이 실제 일별 변동을 반영하도록 데이터 소스 게이팅과 계산 로직을 교정한다.

## 원인 (요약)

- `changePercent`는 stooq 일별 종가에만 의존하는데, stooq 호출이 `ENABLE_STOOQ_FALLBACK`(기본 `false`)에 묶여 있었다.
- `KRW=X`는 `STOOQ_PRIMARY_SYMBOLS`(`^NDX`만 포함)에 없어 key-only 우회 대상도 아니었다.
- 결과: 기본 배포에서 stooq history가 비어 `prev_close=0` → `changePercent`가 항상 0으로 고정.
- 부가 결함: open.er-api 응답이 비면 `current_price`를 `history_prices[-1]`로 채우는데 `prev_close`도 같은 값이라 자기 비교로 등락이 정확히 0이 됨.

## 변경 파일

### Backend (코드)
- [backend/app/services/price_providers.py](../../backend/app/services/price_providers.py)
  - `STOOQ_FX_SYMBOLS = {"KRW=X"}` 상수 추가. FX 등락을 stooq 일별 종가로 계산하기 위한 key-only 게이팅 집합. 지수 primary(`STOOQ_PRIMARY_SYMBOLS`) 의미와 분리.
  - `fetch_stooq_history`의 `force_stooq` 판정에 `STOOQ_FX_SYMBOLS` 포함 → `STOOQ_API_KEY`만 있으면 `ENABLE_STOOQ_FALLBACK`과 무관하게 `KRW=X` 일별 종가 조회.
  - `_fetch_fx_snapshot`:
    - stooq 호출 게이트를 `settings.ENABLE_STOOQ_FALLBACK or _stooq_key()`로 변경(A안).
    - 현재가는 open.er-api live rate 우선, 없으면 stooq 최신 종가로 채움.
    - 전일 종가 산정: live rate가 있으면 stooq 최신 종가(`[-1]`)와 비교(live vs last close), live rate가 없어 현재가를 `[-1]`로 채웠으면 직전 종가(`[-2]`)와 비교해 day-over-day 계산. 자기 비교로 0이 되는 경로 제거.
  - `fetch_market_history`의 `KRW=X` 분기 게이트도 동일하게 `settings.ENABLE_STOOQ_FALLBACK or _stooq_key()`로 일치시킴.

### Backend (테스트)
- [backend/tests/test_price_providers.py](../../backend/tests/test_price_providers.py)
  - `test_fx_snapshot_uses_stooq_when_key_present_without_global_optin` (신규): `STOOQ_API_KEY` 있고 `ENABLE_STOOQ_FALLBACK=False`여도 stooq를 호출하고 등락이 0이 아니게 계산되는지(live vs last close) 검증.
  - `test_fx_snapshot_avoids_self_comparison_when_open_rate_missing` (신규): er-api 빈 응답 시 현재가를 stooq `[-1]`로 채우고 전일 종가를 `[-2]`로 잡아 등락이 0으로 고착되지 않는지 검증.
  - `test_fx_snapshot_keeps_open_rate_without_stooq_fallback` (갱신): 새 게이팅에서 hermetic하도록 `STOOQ_API_KEY=None` 명시.
  - `test_fx_history_fallback_normalizes_open_er_api_rfc_date` (갱신): 동일하게 `STOOQ_API_KEY=None` 명시.

### 설정 / Frontend / DB
- 설정 변경 없음(신규 환경변수 없이 기존 `STOOQ_API_KEY` 존재를 게이트로 사용).
- 프론트 변경 없음. 응답 키(`currentPrice`, `changePercent`, `history_prices`, `provider_meta`) 형식 유지.
- DB 스키마 변경 없음.

## 동작 변화

- `STOOQ_API_KEY`가 설정된 배포: `ENABLE_STOOQ_FALLBACK` 값과 무관하게 USD/KRW의 일별 등락이 계산되어 표시된다(더 이상 0 고정 아님). `provider_meta.change_source="stooq_fallback"`.
- open.er-api 현재가가 비어도 stooq 최신/직전 종가로 day-over-day 등락을 계산해 자기 비교로 0이 되지 않는다.
- `STOOQ_API_KEY`가 없고 `ENABLE_STOOQ_FALLBACK`도 꺼진 배포: 기존과 동일하게 `changePercent=0`, 현재가 단일 포인트, `change_source="none"`로 안전 폴백(가용성 회귀 없음).
- AI 리포트 스케줄러/쿨다운/수동 생성/챗봇 리포트 경로는 건드리지 않았다. 사용자/챗봇 요청이 실시간 리포트 생성을 유발하지 않는다(AGENTS.md 섹션 14 정책 유지).

## 검증

- `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_price_providers.py -q` → **40 passed** (신규 2건 포함, 갱신 2건 포함).
- 로컬에 venv가 없어 `py -m venv .venv` 후 `requirements.txt` 설치 뒤 실행함.

## 미실행 명령과 이유

- `npm run lint` / `npm run build`: 프론트엔드 변경이 없어 실행하지 않음(백엔드 제공 데이터 형식 동일 키 유지).
- 실제 open.er-api / stooq 네트워크 호출: 테스트에서 mock 처리(AGENTS.md 섹션 4 — 일반 테스트에서 외부/실 호출 회피).

## 후속 위험

- `STOOQ_API_KEY` 설정 배포에서 FX 스냅샷 갱신마다 stooq daily CSV 호출이 1건 추가된다. `FX_CACHE_TTL_SECONDS=24h` + 스케줄러 주기로 호출량은 낮지만, [market-data.md Open Risks](features/market-data.md)의 "Stooq `ConnectTimeout` 반복 배포에서는 광범위하게 켜지 말 것" 주의는 여전히 유효하다. FX 한정 경로이므로 영향 범위는 제한적.
- 등락 의미는 "live er-api 환율 vs stooq 마지막 일별 종가"(또는 er-api 부재 시 stooq day-over-day)이며, 기준 시점이 달라 거래소 실시간 등락과 미세하게 다를 수 있다(finnhub 주식 스냅샷과 동일한 한계).
- stooq `usdkrw` 일별 종가의 신선도/지연은 stooq 무료 데이터에 의존한다.

## 영향받은 feature 문서

- [docs/harness/features/market-data.md](features/market-data.md) — USD/KRW 동작 설명·`STOOQ_FX_SYMBOLS`·Stooq 계약 라인 갱신, `Change Records`에 본 기록 링크 추가.
- [docs/harness/feature-index.md](feature-index.md) — market-data 항목 유지(범위 변동 없음).
