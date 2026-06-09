# 원달러(USD/KRW, `KRW=X`) 변동성(`changePercent`) 미표시 원인 해결 계획

날짜: 2026-06-09
상태: 계획(plan) — 구현 전

## 목적(Objective)

USD/KRW(`KRW=X`) 스냅샷의 `changePercent`가 화면에서 항상 0(변동 없음)으로 표시되는 문제를 해결한다. 환율 등락폭이 실제 일별 변동을 반영하도록 계산 경로를 수정하고, 운영 배포의 기본 설정에서도(현 `ENABLE_STOOQ_FALLBACK=false`) 변동성이 잡히도록 데이터 소스 게이팅을 정리한다.

## 현재 동작 / 목표 동작

### 현재 동작 (코드 기준)

- 현재가 소스는 open.er-api.com(`EXCHANGE_RATE_OPEN_URL`)이며 현재 환율만 제공하고 전일 종가를 주지 않는다.
- [_fetch_fx_snapshot](../../backend/app/services/price_providers.py#L740-L789)의 `changePercent`는 **stooq 일별 종가에만** 의존한다. stooq history는 `if settings.ENABLE_STOOQ_FALLBACK:` 안에서만 호출된다.
- [config.py:117](../../backend/app/core/config.py#L117) `ENABLE_STOOQ_FALLBACK: bool = False`(기본 꺼짐).
- `KRW=X`는 [STOOQ_PRIMARY_SYMBOLS](../../backend/app/services/price_providers.py#L74)(현재 `^NDX`만 포함)에 없어, [fetch_stooq_history:818](../../backend/app/services/price_providers.py#L818)의 `force_stooq` 우회 대상도 아니다.
- 결과: 기본 배포에서 stooq history가 비어 `history_prices=[]` → `prev_close=0.0` → `changePercent`가 **항상 0.0**으로 고정된다. ([market-data.md:47](features/market-data.md) 및 [fx-change-percent-from-stooq-2026-06-04.md:39](fx-change-percent-from-stooq-2026-06-04.md)에 알려진 한계로 명시됨.)

플래그를 켜도 남는 2차 로직 문제:

1. **자기 자신과 비교** — [line 762-770](../../backend/app/services/price_providers.py#L762-L770): er-api가 비면 `current_price = history_prices[-1]`로 채우는데 `prev_close`도 `history_prices[-1]`이라 두 값이 같아져 `changePercent`가 정확히 0이 된다.
2. **전일 종가로 최신 종가 사용** — `prev_close = history_prices[-1]`(가장 최근 종가). stooq 최신 종가가 당일치를 포함하면 live 환율과 거의 같아 등락이 ~0으로 수렴한다. 진짜 "전일 대비"라면 직전 거래일 종가가 기준이어야 한다.
3. **24시간 캐시** — [FX_CACHE_TTL_SECONDS = 24*60*60](../../backend/app/services/price_providers.py#L36) + er-api 무료 티어 일 1회 갱신이라 장중 값이 거의 움직이지 않는다(설계상 daily reference이므로 일별 등락만 의미 있음).

### 목표 동작

- `STOOQ_API_KEY`가 설정된 배포에서는 `ENABLE_STOOQ_FALLBACK` 값과 무관하게 USD/KRW의 일별 등락이 계산되어 표시된다(게이팅 방식은 아래 "결정 필요" 참고).
- 등락폭은 stooq usdkrw 일별 종가의 **직전 거래일 종가 대비** 값으로 계산한다(자기 비교로 0이 되는 경로 제거).
- `STOOQ_API_KEY`가 없거나 stooq 데이터가 비면 기존처럼 `changePercent=0` + `change_source="none"`으로 안전 폴백(가용성 회귀 없음).
- history 엔드포인트(`GET /api/market/history/KRW=X`)도 동일 게이팅으로 stooq 시계열을 채운다(스냅샷과 일관).

## 변경 대상 파일

### Backend (코드)
- [backend/app/services/price_providers.py](../../backend/app/services/price_providers.py)
  - FX용 stooq 게이팅 도입(아래 결정에 따라 `STOOQ_API_KEY` 존재 게이트 또는 신규 플래그).
  - `_fetch_fx_snapshot`의 `changePercent` 계산을 일별 종가 day-over-day 기반으로 교정, 자기 비교 경로 제거, `provider_meta.change_source` 갱신.
  - `fetch_market_history`의 `KRW=X` 분기 게이팅을 스냅샷과 일치시킴.

### Backend (테스트)
- [backend/tests/test_price_providers.py](../../backend/tests/test_price_providers.py)
  - 기존 `test_fx_snapshot_change_percent_from_stooq_close`, `test_fx_snapshot_falls_back_when_stooq_empty`를 새 동작에 맞게 갱신/추가.

### 설정 (선택)
- [backend/app/core/config.py](../../backend/app/core/config.py)
  - 신규 게이팅 플래그 도입을 택할 경우에만 추가(예: `ENABLE_FX_STOOQ_CHANGE`).

### Frontend / DB
- 변경 없음. 백엔드 응답 키(`currentPrice`, `changePercent`, `history_prices`, `provider_meta`) 형식 유지 → 프론트 수정 불필요.

## 단계별 구현 계획

1. **게이팅 정리**: `KRW=X`의 stooq 일별 종가 조회를 `ENABLE_STOOQ_FALLBACK` 강제 의존에서 분리한다. 권장안은 `^NDX`의 `STOOQ_PRIMARY_SYMBOLS` 패턴을 참고해 **`STOOQ_API_KEY`가 있으면 FX 등락 계산용 stooq를 호출**하도록 하는 것(아래 결정 필요).
2. **등락 계산 교정**: stooq 종가가 2개 이상이면 `prev = closes[-2]`, `latest = closes[-1]`로 day-over-day 등락을 계산한다. `currentPrice`는 open.er-api live 값을 우선 표시하되, er-api가 비면 `closes[-1]`로 폴백한다. `current == prev`가 되는 자기 비교 경로를 제거한다.
3. **폴백 유지**: stooq 키/데이터가 없으면 `changePercent=0`, 현재가 단일 포인트, `change_source="none"`로 기존과 동일하게 동작시킨다.
4. **history 일관화**: `fetch_market_history`의 `KRW=X` 분기도 동일 게이팅을 따르도록 정리한다.
5. **테스트 갱신**: (a) 키 있고 stooq 종가 2개 → day-over-day 등락이 0이 아니게 계산, (b) er-api 빈 응답에서도 자기 비교로 0이 되지 않음, (c) stooq 비면 0 + `change_source="none"` 폴백 검증.
6. **문서화**: 구현 후 변경 기록 작성 및 feature 문서/색인 갱신(아래 "갱신할 문서").

## 위험과 Risky Change 여부 (AGENTS.md 섹션 9)

- **Provider 호출 동작 변경 (확인 필요)**: 기본 배포에서 FX 스냅샷마다 stooq daily CSV 호출이 1건 추가될 수 있다. `FX_CACHE_TTL_SECONDS=24h` + 스케줄러 주기 때문에 호출량은 낮지만, [market-data.md Open Risks](features/market-data.md)에 "Stooq를 광범위하게 켜지 말 것(ConnectTimeout 반복 배포)"이 명시돼 있어 **provider 동작 변경이므로 사용자 확인을 먼저 받는다.**
- **진행 중 사용자 변경과의 충돌**: 현재 작업트리에 `^NDX` Stooq primary 관련 미커밋 변경(`price_providers.py`, `test_price_providers.py`, feature 문서)이 있다. 같은 파일을 수정하므로 그 변경을 **되돌리지 않고** 그 위에 통합한다.
- DB 스키마/인증/스케줄러 비용/리포트 생성 동작 변경은 **없음**. AI 리포트 실시간 생성 경로도 건드리지 않는다.
- 비용 영향: stooq는 무료 일별 CSV이며 LLM/유료 API 호출이 아니므로 비용 증가는 미미하다.

### 결정 (사용자 승인 완료 — 2026-06-09)

**채택: (A) `STOOQ_API_KEY` 존재 시 항상 활성.** `^NDX`의 `STOOQ_PRIMARY_SYMBOLS` primary 패턴과 일관되게, 별도 환경변수 없이 `STOOQ_API_KEY`가 설정돼 있으면 `KRW=X` 등락 계산용 stooq 일별 종가를 호출한다. `ENABLE_STOOQ_FALLBACK` 값과 무관하게 동작한다.

구현 메모:
- `^NDX` 진행 중 변경과 충돌하지 않도록, `force_stooq` 판정에 `KRW=X`를 FX 전용으로 포함시키는 방식(예: FX 전용 집합 도입 또는 `KRW=X`에 한해 `_stooq_key()` 존재를 게이트로 사용)을 택한다. 기존 `STOOQ_PRIMARY_SYMBOLS`(현재 `^NDX`)의 의미를 흐리지 않도록 주석으로 범위를 명시한다.
- `STOOQ_API_KEY` 미설정 배포에서는 stooq 호출이 추가되지 않고 기존과 동일하게 `changePercent=0` + `change_source="none"`으로 폴백한다.

기각: (B) 신규 플래그, (C) 계산만 교정 — 둘 다 기본 배포에서 변동성이 계속 0으로 남아 목적에 미달.

## 검증 계획 (AGENTS.md 섹션 6 — 최소 집합)

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_price_providers.py -q
```

- 백엔드 service 단위 변경이므로 위 pytest가 1차 검증.
- 실제 외부 호출(open.er-api / stooq)은 테스트에서 mock 처리(실 LLM/네트워크 호출 금지, AGENTS.md 섹션 4).
- 프론트 변경 없음 → `npm run lint`/`npm run build`는 실행 안 함(사유 기록).

## 갱신할 문서

- [docs/harness/features/market-data.md](features/market-data.md): `KRW=X` 동작 설명(10번 항목의 USD/KRW 줄, `change_source`, 게이팅) 갱신, `Change Records`에 구현 기록 링크 추가.
- [docs/harness/feature-index.md](feature-index.md): market-data 항목 갱신(필요 시).
- 구현 단계에서 `docs/harness/krw-fx-change-percent-not-captured-implementation-2026-06-09.md` 변경 기록 작성.
- (B)안 채택 시 [ENVIRONMENT_VARIABLE_SETUP.md](../../ENVIRONMENT_VARIABLE_SETUP.md)에 신규 플래그 추가.
