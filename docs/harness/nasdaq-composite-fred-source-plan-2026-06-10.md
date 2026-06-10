# 나스닥 지수를 FRED NASDAQ Composite(`NASDAQCOM`)로 전환 계획

Date: 2026-06-10

## Objective

메인 대시보드의 나스닥 카드를 **Stooq 의존에서 FRED로 전환**하고, 표시 지수를 **NASDAQ Composite(나스닥 종합지수, ~25,000)** 로 바꾼다.

사용자 결정(2026-06-10):
- **데이터 소스: FRED** (`https://api.stlouisfed.org/fred/series/observations`). 프로젝트에 이미 `DGS10` 등 FRED 연동과 유효한 `FRED_API_KEY`가 있다.
- **지수 종류: NASDAQ Composite (`NASDAQCOM`)** — 나스닥 100/선물이 아니라 나스닥 상장 전체 종합지수. 현재 ~25,000.
- **나스닥 등락 기준: FRED가 제공하는 "가장 최신 관측일" 대비 그 직전 관측일** day-over-day 차이를 표시한다(FRED는 EOD·1~2영업일 지연이므로 "최신 = 가장 최근에 제공된 값").
- **USD/KRW(`KRW=X`): 전일 대비 등락 표시를 삭제한다.** 현재가(open.er-api)만 보여주고 등락(`changePercent`)은 더 이상 계산·표시하지 않는다. 이에 따라 **KRW 경로의 Stooq 의존도 제거**된다.

> 결과적으로 본 변경으로 **Stooq는 기본 라이브 경로에서 완전히 빠진다**(나스닥→FRED, KRW→등락 삭제). `STOOQ_API_KEY` 수동 교체 부담이 사라진다. Stooq fallback 코드(US 주식 종가 등, `ENABLE_STOOQ_FALLBACK` 게이트, 기본 false)는 큰 위험 제거를 피하려 그대로 두되 휴면 상태가 된다.

## 배경 — 왜 바꾸나 (실측 확정)

Stooq 무료 apikey CSV 경로가 **죽었다**. 새 키로도 `^ndq`·`aapl.us`·`^spx`·`usdkrw` 전부 빈 200 응답이며, `.com`/`.pl` 두 호스트, 날짜 파라미터 유무 무관하게 동일하다. PoW(`/__verify`) 검증은 성공하지만 CSV만 빈 본문이다. 즉 **키 재발급으로 해결되지 않는 외부(stooq) 변경**이다. 상세 진단은 [nasdaq-fx-stooq-key-resilience-plan-2026-06-10.md](nasdaq-fx-stooq-key-resilience-plan-2026-06-10.md)의 후속 실측으로 확인됨.

FRED 실측(2026-06-10, 기존 키):
- `NASDAQCOM` → 200, 최신 관측치 정상 수신(일별, ~1~2영업일 지연).
- 키·캡차·PoW·일일 한도 수동 교체 부담 없음. 무료.

## 현재 동작 / 목표 동작

| 항목 | 현재 | 목표 |
| --- | --- | --- |
| 나스닥 카드 데이터 | `^NDX` → Stooq 1차(`STOOQ_PRIMARY_SYMBOLS`) → 키 사망으로 빈값/0 | FRED `NASDAQCOM` → 정상 수신 |
| 표시 지수 | NASDAQ-100 (라벨 "Nasdaq 100") | **NASDAQ Composite** (라벨 "Nasdaq Composite") |
| 나스닥 등락(changePercent) | Stooq 일별 종가 기반(현재 0) | **FRED 최신 관측일 vs 직전 관측일** day-over-day |
| 나스닥 history(차트) | Stooq(현재 빈값) | FRED 관측치 |
| USD/KRW 현재가 | open.er-api | **변경 없음**(open.er-api 유지) |
| USD/KRW 등락 | Stooq 종가 기반(현재 0) | **삭제**(표시·계산 모두 제거, `changePercent`=0/미표시) |
| Stooq 키 운영 | 나스닥·KRW 위해 수동 교체 필요 | **라이브 경로에서 Stooq 완전 제거** → 키 교체 부담 소멸 |

## 캐노니컬 티커 결정 (구현 방식 A/B)

나스닥 카드의 내부 티커는 현재 전 코드에서 `^NDX`(=NASDAQ-100)다. NASDAQ Composite의 표준 심볼은 `^IXIC`다. 두 가지 구현 방식이 있다.

### 방식 A — 새 티커 `^IXIC` 도입 (권장, 의미상 정확)
- 나스닥 카드의 캐노니컬 티커를 `^NDX` → **`^IXIC`** 로 교체. 라벨 자연스럽게 "Nasdaq Composite".
- 장점: 티커·라벨·데이터가 모두 "나스닥 종합"으로 일치. 미래 혼선 없음.
- 단점: `^NDX`를 참조하는 파일이 많아 변경 면적이 넓다(아래 목록).

### 방식 B — 기존 `^NDX` 슬롯을 FRED Composite로 재지정 + 라벨만 변경 (최소 변경)
- 캐노니컬 티커 `^NDX` 유지하되 라우팅만 FRED `NASDAQCOM`으로, 라벨만 "Nasdaq Composite"로.
- 장점: 변경 파일 최소(asset-detail 딥링크 `/market/%5ENDX`, 챗봇 매핑, 데모 키 등 그대로).
- 단점: 티커 `^NDX`가 실제로는 Composite를 가리켜 **의미 불일치**(주석·문서로 보완 필요).

> 본 계획은 **방식 A(`^IXIC` 도입)** 를 권장한다. 사용자가 최소 변경을 원하면 방식 B로 축소한다. 아래 변경 대상은 방식 A 기준이며, B는 해당 항목이 줄어든다.

## 변경 대상 파일 (방식 A 기준)

| 구분 | 파일 | 변경 |
| --- | --- | --- |
| backend (FRED fetch) | `backend/app/services/price_providers.py` | FRED 관측치 fetch 헬퍼(`fetch_fred_history(series_id, ...)`) 추가. `^IXIC`(또는 `^NDX`) 스냅샷/히스토리를 FRED `NASDAQCOM`으로 라우팅. `STOOQ_PRIMARY_SYMBOLS`에서 나스닥 제거. **순환 import 주의**: `macro_service`가 `price_providers`를 import하므로, FRED 호출은 `price_providers` 내부에 자체 구현(httpx+settings+redact_secrets 재사용)하거나 함수 내부 지연 import로 처리한다. |
| backend (라우팅 상수) | `backend/app/services/price_providers.py` | `NASDAQCOM` ↔ 캐노니컬 티커 매핑 상수(`FRED_INDEX_SYMBOLS = {"^IXIC": "NASDAQCOM"}`) 추가. |
| backend (지수 목록·라벨) | `backend/app/services/market_service.py` | `INDICES`의 `"Nasdaq 100": "^NDX"` → `"Nasdaq Composite": "^IXIC"`. |
| backend (live allowlist) | `backend/app/core/config.py` | `MARKET_LIVE_TICKERS` 기본값의 `^NDX` → `^IXIC`. (allowlist에 없으면 mock으로 degrade) |
| backend (데모 mock) | `backend/app/services/demo_market_data.py` | `DEFAULT_LIVE_TICKERS`의 `^NDX` → `^IXIC`, mock 가격 키 `"^NDX": 19042.11` → `"^IXIC": <Composite 근사값>`. |
| backend (챗봇 매핑) | `backend/app/services/chat_tools.py`, `backend/app/services/chat_grounding.py` | "나스닥/nasdaq" 후보 티커 `^NDX` → `^IXIC`, grounding 지수 집합 갱신. |
| frontend (라벨) | `frontend/src/utils/constants.js` | `"^NDX": "Nasdaq 100"` → `"^IXIC": "Nasdaq Composite"`. |
| frontend (스냅샷 설정) | `frontend/src/pages/MarketSnapshot.jsx` | `"^NDX": {...}` 키/라벨을 `^IXIC`/"Nasdaq Composite"로. |
| frontend (홈 카드) | `frontend/src/pages/Home.jsx` | `{ label: 'Nasdaq 100', dataKey: 'Nasdaq 100', ticker: '^NDX', ... }` → `label/dataKey: 'Nasdaq Composite', ticker: '^IXIC'`. dataKey는 백엔드 `macro` 응답 키(라벨)와 일치해야 한다. |
| backend (USD/KRW 등락 삭제) | `backend/app/services/price_providers.py` | [_fetch_fx_snapshot](../../backend/app/services/price_providers.py#L753): Stooq 일별 종가 호출·등락 계산 블록 제거. `currentPrice = open.er-api live_rate`만 사용, `changePercent = 0.0`, `history_prices = [current_price]`. `provider_meta.change_source = "none"`. [fetch_market_history](../../backend/app/services/price_providers.py#L1268) `KRW=X` 분기에서 Stooq history 호출 제거(현재가 1점만). `STOOQ_FX_SYMBOLS` 사용 제거(상수는 남겨두되 라우팅에서 미참조). |
| frontend (USD/KRW 등락 숨김) | `frontend/src/pages/Home.jsx` | 매크로 카드 등락 배지([Home.jsx:70-86](../../frontend/src/pages/Home.jsx#L70-L86))에서 `USDKRW`(또는 `category==='FX'`)는 `change_pct` 배지를 렌더하지 않도록 조건 분기. `MarketSnapshot.jsx`·`AssetDetail.jsx`에 환율 등락이 노출되면 동일 처리. |
| test | `backend/tests/test_price_providers.py` | 기존 `^NDX` Stooq primary 테스트(`test_ndx_history_uses_stooq_*`, `test_ndx_snapshot_uses_stooq_*`, `test_ndx_stooq_requires_key`)를 FRED 경로 테스트로 교체/갱신. FRED 응답 mock → currentPrice/changePercent(최신일 vs 직전일)/history 검증. **USD/KRW 테스트**: Stooq 키가 있어도 `KRW=X` 스냅샷 `changePercent==0`이고 Stooq를 호출하지 않음을 검증(기존 `krw-fx-change` 관련 테스트가 있으면 등락=0 기대로 수정). |
| test | `backend/tests/test_market_warmup_timeout.py`, `test_chat_service.py` | `^NDX` 하드코딩(`/market/%5ENDX` 등)을 새 티커에 맞게 갱신. |
| 문서(기능) | `docs/harness/features/market-data.md`, `docs/harness/feature-index.md` | 나스닥 소스=FRED `NASDAQCOM`, 라벨 변경, Stooq 나스닥 경로 제거 명시. 구현 기록 링크 연결. |
| 문서(가이드) | `STOOQ_APIKEY_GUIDE.md` | "나스닥은 FRED로 이전. USD/KRW 등락은 삭제됨. **Stooq는 라이브 기본 경로에서 더 이상 사용하지 않음**(휴면 fallback만 잔존). `STOOQ_API_KEY` 수동 교체 불필요" 보강. |

## FRED fetch 설계 (요지)

- 요청: `GET FRED_BASE_URL?series_id=NASDAQCOM&api_key=<KEY>&file_type=json&sort_order=desc&limit=<N>`
- 파싱: 기존 [fetch_us_bond_history](../../backend/app/services/macro_service.py#L151) 패턴 재사용 — `value == "."`(휴장/결측)는 직전 유효값 carry-forward, `desc`로 받아 `reversed`로 오래된→최신 정렬.
- 스냅샷(나스닥 등락): **FRED가 제공한 가장 최신 관측일이 `points[-1]`, 그 직전 관측일이 `points[-2]`**. `currentPrice = points[-1].value`, `prev = points[-2].value`, `changePercent = (cur-prev)/prev*100`, `history_prices = [p.value...]`. 즉 "오늘"이 아니라 **제공처(FRED) 기준 최신일 대비 직전일** 차이다(EOD·지연 반영). `provider_meta.provider = "fred"`, `series_id`, `freshness = "provider_observation"`, `as_of = points[-1].date`.
- 캐시: 기존 `_history_cache`/`_snapshot_cache`(12h TTL) 재사용. FRED는 일 1회 갱신이라 12h로 호출 최소화. 실패 시 기존 stale-retention 로직으로 직전 유효값 유지.
- 키 미설정/HTTP 오류: `redact_secrets`로 URL의 `api_key` 마스킹 후 WARNING, 빈 payload로 degrade(카드 carry-forward).

## 위험과 Risky Change 여부 (AGENTS.md 섹션 9)

- **provider 전환(Stooq→FRED, 나스닥 한정)**: DB·인증·리포트 비용과 무관. FRED는 무료·기설치 키. 새 유료 API 없음. → 저위험. 단 "데이터 소스 교체"이므로 본 계획서로 명시.
- **지수 종류 변경(NASDAQ-100→Composite)**: 표시 값이 ~29,400→~25,000으로 바뀐다. 사용자 의도(2026-06-10)에 따른 것. 라벨도 함께 바꿔 혼선 방지.
- **캐노니컬 티커 변경(방식 A, `^NDX`→`^IXIC`)**: asset-detail 딥링크·챗봇·데모·allowlist 동시 갱신 필요. 누락 시 카드 mock degrade 또는 링크 깨짐. 변경 파일을 한 번에 처리하고 `npm run build`/관련 pytest로 확인. 최소화하려면 방식 B.
- **AI 리포트**: 나스닥은 `REPORT_SCHEDULER_TARGET_TICKERS`(`DGS10,XAU,BTC-USD,NVDA,005930.KS`)에 없어 스케줄 리포트 대상이 아니다. 스케줄·cooldown·생성 트리거 불변(AGENTS.md 섹션 14 무관). 사용자/챗봇은 저장된 리포트만 읽음.
- **FRED 지연**: NASDAQCOM은 EOD·~1~2영업일 지연. 실시간이 아니라 일별 종가 기준임을 feature 문서에 명시.
- **USD/KRW 등락 삭제**: 현재가(open.er-api)는 유지되고 등락만 사라진다. 사용자가 사용성 측면에서 등락 표시를 원치 않아 결정. 부수효과로 KRW의 Stooq 의존이 제거돼 Stooq가 라이브 경로에서 완전히 빠진다. 환율 카드에 등락 배지가 안 보이는지 프런트에서 확인.
- **Stooq 휴면화**: Stooq 라우팅은 라이브 기본 경로에서 더는 호출되지 않는다. 코드·상수(`ENABLE_STOOQ_FALLBACK`, `STOOQ_*`)는 제거하지 않고 남겨 둔다(대규모 삭제 = 별도 위험). 추후 완전 제거를 원하면 별도 정리 작업으로 분리.

## 검증 계획 (AGENTS.md 섹션 6, 최소 집합)

1. 정적 확인
   - `rg -n "NASDAQCOM|\^IXIC|\^NDX|fetch_fred_history|FRED_INDEX_SYMBOLS" backend/app frontend/src`
2. 백엔드 단위 테스트 (실 LLM·실 네트워크 없이 mock — AGENTS.md 섹션 4)
   - `cd backend`; `python -m pytest tests/test_price_providers.py`
   - FRED 응답 mock → `^IXIC` 스냅샷 `currentPrice`(=최신일)/`changePercent`(=최신일 vs 직전일)/`history` 검증, 키 없을 때 빈 degrade, `"."` carry-forward.
   - `KRW=X` 스냅샷 → Stooq 키 유무와 무관하게 `changePercent==0`, Stooq 미호출, `currentPrice`는 open.er-api live_rate 검증.
   - 테스트 수집에 필요한 임시 env: `PROJECT_NAME`, `API_V1_STR`, `DATABASE_URL=sqlite+aiosqlite:///./test.db`(시크릿 비노출).
3. 프런트 빌드
   - `cd frontend`; `npm run lint`; `npm run build` — 라벨/티커 변경 후 깨짐 없는지.
4. 라이브 smoke (실 `FRED_API_KEY`, 키 비출력)
   - 앱 경로로 `fetch_market_snapshot("^IXIC","INDEX")` → `currentPrice` ~25,000, `changePercent`≠0(최신일 vs 직전일) 확인.
   - 배포 후 `GET /api/market/prices`의 `macro["Nasdaq Composite"]` 값 확인. `macro["USDKRW"].changePercent==0` 확인. 프런트 `/`에서 나스닥 카드 표시 + 환율 카드에 **등락 배지 미표시** 확인.
5. 미실행/보호
   - 본 단계는 계획서 작성만 — 코드 변경·테스트·빌드 미실행.
   - `.env`·`FRED_API_KEY`·`STOOQ_API_KEY` 등 시크릿은 열람·출력하지 않음.

## 갱신할 문서

- `docs/harness/features/market-data.md` — 나스닥 소스=FRED `NASDAQCOM`, 라벨 "Nasdaq Composite", Stooq 나스닥 경로 제거, FRED 지연 특성. 구현 기록 링크 연결.
- `docs/harness/feature-index.md` — Market data 변경 기록에 본 계획·후속 구현 기록 연결.
- `STOOQ_APIKEY_GUIDE.md` — 나스닥은 FRED로 이전, USD/KRW 등락 삭제, Stooq는 라이브 기본 경로 미사용(휴면) 명시.

## Feature Links

- `docs/harness/features/market-data.md`
- `docs/harness/feature-index.md`
- `docs/harness/nasdaq-fx-stooq-key-resilience-plan-2026-06-10.md`
- `docs/harness/nasdaq-stooq-symbol-ndx-to-ndq-2026-06-10.md`
- `docs/harness/nasdaq-index-stooq-primary-implementation-2026-06-09.md`
