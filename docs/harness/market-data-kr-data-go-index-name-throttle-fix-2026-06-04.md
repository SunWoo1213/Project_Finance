# KR 시장데이터 복구: data.go.kr 지수 idxNm 한글화 + 스냅샷 날짜창 + data_go 동시성/타임아웃 (구현)

Date: 2026-06-04
Status: 구현 완료(Implemented), 배포 검증 대기
Feature: `docs/harness/features/market-data.md`
Related:
- `docs/harness/market-data-warmup-provider-throttle-timeout-implementation-2026-06-04.md` (직전 A+C: 타임아웃 상향 + 워밍업 비차단화)
- `docs/harness/market-data-warmup-provider-throttle-timeout-plan-2026-06-03.md` (후보 B/E의 출처)
- `docs/harness/market-data-provider-migration-implementation-2026-06-03.md`

## 1. 배경 / 증상

직전 A+C 배포 이후에도 배포 로그에서 KR 종목(`.KS`)과 KR 지수(`^KS11`, `^KQ11`)가 전부 `failed: timeout after 30s`로 떨어지고, 첫 종목 `005930.KS`만 빈 메시지 예외(`Market snapshot provider failed (... STOCK_KR): `)로 떨어졌다. 로그에 `apis.data.go.kr` HTTP 성공 줄이 하나도 없는 것이 결정적 단서였다(httpx는 응답 수신 시에만 로깅).

## 2. 원인 확정 (로컬=한국 egress에서 재현, Render 전용 문제 아님)

진단용 스크립트 `backend/scripts/probe_data_go.py`로 data.go.kr을 직접 호출해 다음을 실측 확정했다.

1. **`getStockPriceInfo`(KR 종목)는 날짜 범위 없는 `likeSrtnCd` 조회 시 매우 느림.** `httpx.ReadTimeout`(15s 내부 타임아웃 초과)으로 죽었고(이게 빈 메시지 예외의 정체 = `ReadTimeout('')`), 타임아웃을 40s로 늘리면 200 OK이지만 ~19.6s 소요. 즉 기존 내부 타임아웃 15s가 응답 시간보다 짧았다.
2. **`getStockMarketIndex`(KR 지수)의 `idxNm`은 영문이 아니라 한글이어야 한다.** `idxNm="KOSPI"` → `totalCount=0`(빈 결과), `idxNm="코스피"` → 정상 데이터(clpr 등). 기존 `KR_INDEX_NAMES` 값이 `"KOSPI"`/`"KOSDAQ"`라 지수는 타임아웃 이전에 이미 데이터 매핑 버그로도 비어 있었다.
3. **날짜 범위(`beginBasDt`/`endBasDt`)를 추가하면 쿼리가 빨라진다.** 종목 스냅샷 row 조회가 날짜창 적용 후 ~20s → ~1~3s로 단축됐다(재현 확인).
4. **data.go.kr은 부하/반복 호출 시 게이트웨이 차단 페이지를 반환한다.** 세션 중 반복 호출 후 지수 엔드포인트가 20s 뒤 `HTTP 404` + HTML 본문 `오류발생 알림화면(허용되지 않는 요청을 하셨습니다)`를 일관되게 반환했다. 이는 data.go.kr의 rate-limit/IP 스로틀 신호이며, 동시성 상향을 보수적으로 가져가야 하는 근거다(AGENTS.md 섹션 9, 마이그레이션 문서의 경고와 동일).

직렬 세마포어(`data_go_kr` `Semaphore(1)`) + per-asset 30s wait_for와 결합되어, 느린/실패하는 첫 KR 호출이 큐를 막아 뒤 종목들이 차례를 못 받고 30s에 일괄 타임아웃됐다. 또한 KR 종목 스냅샷은 30s 예산 안에서 data.go.kr을 **2번**(현재가 row + history) 호출하므로 호출당 ~20s면 경합 없이도 30s를 못 채운다.

## 3. 변경 파일과 동작 변화

### `backend/app/services/price_providers.py`
- `KR_INDEX_NAMES` 값 `"KOSPI"/"KOSDAQ"` → `"코스피"/"코스닥"`. 키(`^KS11`/`^KQ11`)는 멤버십 판정용으로 유지. 값은 오직 `idxNm` 파라미터로만 쓰여 안전(다른 표시/매칭에 영향 없음).
- `_provider_concurrency(provider)` 신규: `data_go_kr`만 `settings.DATA_GO_KR_MAX_CONCURRENCY`(최소 1)를 쓰고 나머지는 1 유지. `_provider_semaphore`가 이 값으로 세마포어를 생성한다.
- `_fetch_data_go_rows`의 httpx 타임아웃 `15.0` → `settings.DATA_GO_KR_FETCH_TIMEOUT_SECONDS`.
- `_recent_basdt_window(days=20)` 신규: 최근 20일 `beginBasDt`/`endBasDt` 윈도우. KR 장 휴장(설/추석 포함)도 커버하면서 최신 거래일을 빠르게 반환.
- `_fetch_data_go_snapshot`의 KR 종목/지수 row 조회에 `**_recent_basdt_window()` 추가(history 조회는 이미 날짜창 사용).
- provider 실패 로깅 4곳(`Market snapshot/history/news/events provider failed`)을 `%s` → `%r`로 변경. 빈 메시지 예외(예: `ReadTimeout('')`)의 클래스가 로그에 노출되도록 가시성 보강.

### `backend/app/core/config.py`
- `MARKET_PRICE_FETCH_TIMEOUT_SECONDS` 기본값 `30` → `55`. KR 스냅샷의 2회 data.go.kr 호출(2×25s)을 경합 없이 수용하기 위함. 미만이면 단일 KR 자산도 절대 완료 불가.
- 신규 `DATA_GO_KR_FETCH_TIMEOUT_SECONDS: int = 25`(최소 5초 보정), `DATA_GO_KR_MAX_CONCURRENCY: int = 2`(최소 1 보정).
- 동시성 기본값 2는 보수적 선택: data.go.kr이 부하 시 "허용되지 않는 요청" 게이트웨이 차단을 반환하므로, 배포가 견디면 env로 3까지 올린다.
- validator: 새 타임아웃은 기존 `enforce_minimum_fetch_timeout`에 합류(최소 5), 동시성은 신규 `enforce_minimum_concurrency`(최소 1).

### `backend/scripts/probe_data_go.py` (신규, 진단 전용)
- data.go.kr 종목/지수 도달성을 단발 호출로 분류(ConnectTimeout/ReadTimeout/HTTPStatusError/200). serviceKey 값은 출력하지 않고 설정 여부만 bool 표시. 프로덕션 쿼리와 동일하게 한글 `idxNm` + 날짜창을 사용.

## 4. 검증 결과

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests\test_market_warmup_timeout.py tests\test_price_providers.py -q
```
결과: **17 passed**(기존 9 + 신규 8).

신규 테스트:
- `test_price_fetch_timeout_default_covers_two_data_go_calls`: 코드 기본값 `MARKET_PRICE_FETCH_TIMEOUT_SECONDS >= 2 * DATA_GO_KR_FETCH_TIMEOUT_SECONDS` 불변식.
- `test_data_go_settings_enforce_minimums` / `..._accept_configured_values`: 신규 설정 validator.
- `test_kr_index_names_use_korean_idxnm`: 지수 idxNm 한글 회귀 가드.
- `test_recent_basdt_window_is_ordered_yyyymmdd`: 날짜창 형식/순서.
- `test_data_go_semaphore_uses_configured_concurrency`: `data_go_kr`=설정값, 그 외 provider=1.
- `test_data_go_rows_use_configured_timeout`: `_fetch_data_go_rows`가 설정 타임아웃을 `_get_json`에 전달.
- `test_kr_index_snapshot_query_uses_korean_name_and_date_window`: 지수 스냅샷 쿼리가 `idxNm="코스피"` + 날짜창 사용.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```
결과: **122 passed, 2 failed**. 실패 2건은 `tests/test_subscription_api.py::test_billing_checkout_paid_tiers_return_provider_checkout_url[PLUS|PRO]`로, 본 변경을 `git stash`로 제거해도 동일하게 실패하는 **사전 존재(pre-existing) 실패**다(원인: `PAYMENT_MOCK_CHECKOUT_BASE_URL` 설정 드리프트). 본 작업과 무관.

```powershell
.\.venv\Scripts\python.exe -W error::SyntaxWarning -m py_compile app\core\config.py app\services\price_providers.py scripts\probe_data_go.py
```
결과: clean.

진단 스크립트 실측(로컬, 한국 egress):
- `[stock] status=200 elapsed≈1~3s` (날짜창 적용 후 정상·고속)
- `[index] status=404 ... "허용되지 않는 요청"` (반복 호출로 인한 게이트웨이 차단 재현; 코드는 `raise_for_status()`로 예외화→DEFAULT+쿨다운으로 정상 degrade)

## 5. 실행하지 않은 명령과 이유

- `.env.example` 갱신: 하네스 권한이 `.env*` 매칭을 차단. 신규 env는 본 문서와 feature 문서 `Contracts`에 명시. 필요 시 사용자가 직접 추가: `MARKET_PRICE_FETCH_TIMEOUT_SECONDS=55`, `DATA_GO_KR_FETCH_TIMEOUT_SECONDS=25`, `DATA_GO_KR_MAX_CONCURRENCY=2`.
- `npm run lint`/`npm run build`: 프론트엔드 변경 없음.
- 실제 배포 워밍업 smoke: 외부 key/네트워크 의존. 다음 배포 로그에서 (1) KR 종목 `failed:` 감소, (2) KOSPI/KOSDAQ 현재가 표시, (3) 실패 시 `%r` 예외 클래스 노출로 확인 예정.

## 6. 남은 위험과 후속

- **data.go.kr 게이트웨이 차단("허용되지 않는 요청")**: 부하/반복 호출 시 404 HTML로 차단된다. 코드는 정상 degrade하지만, KOSPI/KOSDAQ가 일시적으로 0으로 보일 수 있다. `DATA_GO_KR_MAX_CONCURRENCY`를 함부로 올리면 차단 빈도가 증가하므로 배포 관찰 후 조정한다.
- **지수 엔드포인트 불안정**: `getStockMarketIndex`가 종목 엔드포인트보다 느리고 간헐적으로 404를 반환한다(서버측). 한글 idxNm은 올바른 쿼리이며, 차단은 환경/부하 요인이다.
- **2회 호출 구조**: KR 종목 스냅샷은 여전히 data.go.kr을 2번 호출한다. 더 줄이려면 계획서 후보 E(스냅샷을 history 마지막 점으로 대체, 호출 2→1)를 별도 승인 후 진행.
- 캐시로 점진 복구: history 12h, snapshot row 30분(`DATA_GO_CACHE_TTL_SECONDS`), 실패 쿨다운 5분. 첫 워밍업에서 일부만 성공해도 후속 스케줄러 사이클에서 캐시가 채워진다.

## 7. 영향받은 문서

- `docs/harness/features/market-data.md` — Data Flow, Contracts, Open Risks, Change Records 갱신.
- `docs/harness/feature-index.md` — market-data 행에 본 기록 링크 추가.
