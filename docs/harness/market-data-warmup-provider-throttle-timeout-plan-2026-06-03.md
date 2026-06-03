# 시장 데이터 워밍업/스케줄러 provider 직렬화·타임아웃 충돌 해결 계획

Date: 2026-06-03
Status: 계획 수립(Planned) — 구현 전 사용자 승인 필요(Risky Change 포함)
Feature: `docs/harness/features/market-data.md`
Related:
- `docs/harness/market-data-provider-migration-implementation-2026-06-03.md`
- `docs/harness/market-data-provider-response-format-audit-plan-2026-06-03.md`
- `docs/harness/error-casebook-2026-06-03.md`

## 1. 목적(Objective)

배포 로그에서 워밍업/스케줄러가 다수 종목을 빈 `failed:`(=`asyncio.TimeoutError`, `str()`이 빈 문자열)로 떨어뜨리는 문제를 해결한다. HTTP 요청은 모두 `200 OK`였는데도 KR 주식 전체, KR 지수, AAPL을 제외한 US 주식 전부, 일부 KR 뉴스가 실패했다.

근본 원인은 외부 API 오류가 아니라 **provider별 동시 요청 1건 제한(`asyncio.Semaphore(1)`)과 per-asset 타임아웃(가격 15s / 뉴스 8s)의 충돌**이다. 워밍업이 전 종목을 동시에 `gather`로 던지지만, 같은 provider로 가는 요청은 1칸짜리 세마포어를 직렬로 통과해야 하므로, 한 provider에 종목이 몰리면 큐가 타임아웃 안에 빠지지 못한다.

중요: 이 계획은 시장 데이터 수집/캐시 경로만 다룬다. 사용자-facing 요청과 챗봇은 계속 저장된 캐시/스케줄 리포트를 읽으며, 새 AI 리포트 생성 트리거를 추가하지 않는다.

## 2. 확인한 파일(코드 기준)

- `backend/app/services/price_providers.py`
  - `_provider_semaphore()` (L90-97): provider마다 `asyncio.Semaphore(1)` 생성 → provider당 동시 1건.
  - `_get_json()` / `_get_text()` (L220-265): 모든 외부 요청이 `async with _provider_semaphore(provider)`로 직렬화. provider 키: `finnhub`, `coingecko`, `data_go_kr`, `stooq`, `naver_news`, `exchange_rate_open`.
  - `_should_skip_failed_call()` / `FAILED_CALL_TTL_SECONDS=300` (L116-127, L27): 실패 request key 5분 cooldown.
- `backend/app/services/market_service.py`
  - `_collect_prices_group.collect_one()` (L274-281): `asyncio.wait_for(fetch_asset_data, timeout=15)` + `gather`.
  - `_collect_news_group.collect_one()` (L292-299): `asyncio.wait_for(fetch_market_news_items, timeout=8)` + `gather`.
  - `update_prices_task()` (L301-312): 6개 그룹을 동시에 `gather`.
- `backend/app/main.py`
  - `lifespan()` (L157-161): `await update_prices_task()` → `await update_news_task()`를 **port 바인딩 전에 동기로 await**. 스케줄러는 L166-265.
- `backend/app/core/config.py`
  - `Settings` (L55-) 에 `MARKET_PRICES_REFRESH_MINUTES` 등 minutes형 env가 있고 `enforce_minimum_minutes` validator(L184-193)로 최소 1 보정. 신규 튜닝값도 같은 패턴을 따른다.

`.env`는 시크릿 보호 규칙에 따라 읽지 않았다. 변수명/코드 경로만 확인했다.

## 3. 현재 동작 / 목표 동작

### 현재 동작
- provider당 동시 요청 1건. 한 provider에 묶인 종목들이 직렬 큐로 처리된다.
  - `data_go_kr`: KR 주식 ~10종 + KOSPI/KOSDAQ 지수 = 약 12+종이 1칸 큐를 공유.
  - `stooq`: US 주식 10종 + US 지수(^spx/^ndx) + 원자재(xau/xag) history = 약 14종이 1칸 큐를 공유(로그상 1건 ~2s).
  - `naver_news`: KR 뉴스 종목들이 1칸 큐 공유(뉴스 타임아웃 8s).
- per-asset `wait_for` 타임아웃은 모든 task가 거의 동시에 시작하므로 **큐 뒤쪽 종목은 "전체 큐 드레인 시간"만큼 대기**한다. 드레인 시간이 15s/8s를 넘으면 순번을 못 받은 종목이 `TimeoutError`로 떨어진다.
- 워밍업은 `lifespan`에서 port 바인딩 전에 동기 await → 워밍업이 길어질수록 Render의 "No open ports detected" 포트 스캔이 길어진다(로그에 이미 등장).

### 목표 동작
- 한 provider에 종목이 몰려도 워밍업/스케줄러 1회 실행 안에 대부분의 종목이 정상 수집된다(빈 `failed:` 대량 발생 제거).
- free-tier rate limit / IP 차단(특히 비공식 Stooq, 스크레이핑 Naver)을 자극하지 않는 보수적 동시성을 유지한다.
- 워밍업 시간이 늘어도 Render 포트 바인딩/헬스체크를 막지 않는다.
- 타임아웃·동시성은 코드 상수 대신 env로 조정 가능하고, 안전한 기본값을 가진다.

## 4. 해결 후보와 트레이드오프

| 후보 | 효과 | 위험 |
| --- | --- | --- |
| A. per-asset 타임아웃 상향(가격 15s→~30s, 뉴스 8s→~20s) | 큐 드레인 시간 < 타임아웃이 되어 직렬 처리로도 대부분 성공. rate limit을 건드리지 않는 가장 안전한 레버. | 1회 실행 시간이 길어짐. 워밍업이 동기 await면 startup이 길어짐(후보 C로 분리 해결). |
| B. provider 동시성 상향(`Semaphore(1)`→2~3, provider별 설정) | 큐 드레인 시간을 1/N로 단축. | **free-tier rate limit / 차단 위험**(Finnhub 분당 제한, 비공식 Stooq, 스크레이핑 Naver). Risky. |
| C. 워밍업 비차단화(`await` 제거, background task) | port 즉시 바인딩, 배포 헬스체크와 워밍업 시간 분리. 후보 A의 startup 지연 위험 제거. | 기동 직후 짧은 시간 캐시가 비어 있을 수 있음(엔드포인트는 빈 캐시를 정상 처리해야 함). |
| D. 워밍업 그룹 순차/배치 처리 | 동시 폭주 완화로 평균 응답시간 안정화. | 총 시간 증가. A/C와 효과 일부 중복. |
| E. 스냅샷에서 history 호출 분리(가격 스냅샷은 현재가/변동률만, history는 history 엔드포인트로) | provider 호출 수 자체 감소(특히 Stooq). | 변경 범위가 넓고 스냅샷 계약/프론트 sparkline 영향 확인 필요. 별도 작업으로 분리 권장. |

### 권장 조합
**A(타임아웃 상향) + C(워밍업 비차단화)** 를 1차로 채택한다. rate limit을 자극하지 않고 구조적으로 큐 드레인을 보장하며, startup 지연 위험을 C가 제거한다.

**B(동시성 상향)** 는 선택적 2차 레버로, **공식 API(`data_go_kr`, `finnhub`, `coingecko`)만 동시성 2** 로 올리고 **비공식/스크레이핑(`stooq`, `naver_news`)은 1 유지**하는 provider별 설정으로만 도입한다. 기본값은 보수적으로 두고, 실제 key로 smoke 후 단계적으로 조정한다. D/E는 후속 과제로 남긴다.

드레인 추정(보수): `stooq` ~2s × 14 ≈ 28s(동시성1) → 타임아웃 30s면 마지막 종목도 통과. `data_go_kr` ~1.5s × 12 ≈ 18s → 30s 안. 뉴스 ~1s × KR뉴스 종목수 → 20s 안. 동시성 2 적용 시 절반으로 단축되어 여유가 더 생긴다.

## 5. 변경 대상 파일

- 백엔드(코드)
  - `backend/app/core/config.py` — 신규 env 추가 + 최소값 validator 확장.
  - `backend/app/services/price_providers.py` — `_provider_semaphore()`가 provider별 설정 동시성을 읽도록 수정.
  - `backend/app/services/market_service.py` — `wait_for` 타임아웃을 설정값으로 치환.
  - `backend/app/main.py` — 워밍업을 비차단(background task)으로 전환.
- 백엔드(테스트)
  - `backend/tests/test_price_providers.py` 또는 신규 `backend/tests/test_market_warmup_concurrency.py` — 세마포어 동시성/타임아웃/cooldown 동작 검증.
- 설정/문서
  - `.env.example` — 신규 env와 기본값/권장값 설명 추가(시크릿 아님).
- DB: 변경 없음. 프론트: 변경 없음.

### 신규 env(안, 기존 `MARKET_*` 패턴 일치, 기본값 보수적)
- `MARKET_PRICE_FETCH_TIMEOUT_SECONDS` (기본 30, 최소 5)
- `MARKET_NEWS_FETCH_TIMEOUT_SECONDS` (기본 20, 최소 5)
- `MARKET_PROVIDER_MAX_CONCURRENCY` (기본 1 = 현행 유지) — 공식 API 한정 상향 시 사용
- (선택) `MARKET_PROVIDER_CONCURRENCY_OVERRIDES` 또는 코드 내 provider별 맵: `data_go_kr=2,finnhub=2,coingecko=2` / `stooq=1,naver_news=1`

기본값을 현행과 동일(동시성 1)하게 두면 env 미설정 환경에서 동작이 바뀌지 않고, 배포 환경에서만 점진적으로 올릴 수 있다.

## 6. 단계별 구현 계획

1. **(완료, 직전 변경)** 로그 정직화: `failed: timeout after 15s/8s`와 `{exc!r}` 출력, `break` in `finally` 경고 제거. (`market_service.py`, `main.py` 워킹트리에 반영됨) — 다음 배포 로그에서 원인 확정에 사용.
2. config에 신규 env 추가 + `enforce_minimum_*` validator로 최소값 보정. 안전한 기본값(동시성 1, 타임아웃 30/20s).
3. `_provider_semaphore()`가 provider별 동시성(맵/설정)을 읽도록 수정. 기본 1, 공식 API만 선택적으로 상향 가능하게.
4. `market_service`의 `wait_for(timeout=...)` 두 곳을 설정값으로 치환.
5. `main.py` 워밍업을 `asyncio.create_task(...)`로 비차단 전환. 단, 작업 시작 로그/실패 로그가 유실되지 않게 task 예외를 잡아 print. yield 후 종료 시 미완료 task 정리.
6. 테스트 추가: (a) 동일 provider 요청이 설정 동시성을 초과하지 않음, (b) 타임아웃 초과 시 빈 결과로 degrade하고 다른 종목을 막지 않음, (c) 실패 후 `FAILED_CALL_TTL` 안에서 재호출 안 함.
7. `.env.example`와 feature 문서/색인 갱신.
8. 실제 key가 있는 배포/스테이징에서 워밍업 로그로 실패 종목 수가 0~소수로 줄었는지 확인하고 동시성 상향 여부 결정.

## 7. 위험과 Risky Change 여부 (AGENTS.md 섹션 9)

- **Risky Change에 해당** — "스케줄러 빈도/네트워크 부하/외부 API 호출 패턴 변경"에 가깝다(동시성 상향은 호출 폭주·rate limit·비용/차단 위험). 구현 전 **사용자 승인 필요**.
- 후보 B(동시성 상향)는 특히 **비공식 Stooq / 스크레이핑 Naver의 IP 차단** 위험이 있어 기본값에서 제외하고 공식 API만 선택 상향한다.
- 후보 C(비차단 워밍업)는 기동 직후 짧게 캐시가 비어 보일 수 있다 → 엔드포인트가 빈 캐시를 정상 처리하는지 확인(이미 빈 응답 degrade 설계).
- DB 스키마/마이그레이션, 인증, AI 리포트 생성 동작 변경은 **없음**. 비용 증가형 변경(유료 API 추가) 없음.
- 기본 env 미설정 시 현행 동작과 동일(타임아웃만 상향)하도록 기본값을 설계해 회귀 위험을 최소화한다.

## 8. 검증 계획 (AGENTS.md 섹션 6, 최소 집합)

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests\test_price_providers.py tests\test_market_history_route.py
# 신규 테스트 파일을 추가하면 함께 지정
```

구문/경고 확인:

```powershell
.\.venv\Scripts\python.exe -W error::SyntaxWarning -m py_compile app\main.py app\services\market_service.py app\services\price_providers.py app\core\config.py
```

실제 key가 있는 배포/스테이징 수동 smoke(시크릿 출력 금지, 실패 종목 수만 확인):
- 워밍업 로그에서 `[update_prices_task] ... failed:` 줄 수가 0~소수로 감소했는지.
- 남은 실패가 있으면 `timeout after Ns`인지 `{exc!r}`(실제 provider 오류)인지 구분.
- `GET /api/market/prices`, `GET /api/market/news`가 그룹별로 채워지는지.

프론트 변경이 없으므로 `npm run build`는 필수 아님(스냅샷 계약을 건드리는 후보 E로 확장 시에만 수행).

## 9. 갱신할 문서

- `docs/harness/features/market-data.md`
  - `Data Flow`: 워밍업 비차단화와 provider 동시성/타임아웃 튜닝 반영.
  - `Contracts`: 신규 env(`MARKET_PRICE_FETCH_TIMEOUT_SECONDS`, `MARKET_NEWS_FETCH_TIMEOUT_SECONDS`, `MARKET_PROVIDER_MAX_CONCURRENCY` 등) 추가.
  - `Open Risks`: provider 동시성 상향의 rate-limit/차단 위험 명시.
  - `Change Records`: 본 계획서와 후속 구현 기록 링크 추가.
- `docs/harness/feature-index.md`: 본 계획서를 market-data 행 Change records와 상단 목록에 추가.
- `docs/harness/error-casebook-2026-06-03.md`: "빈 `failed:` = provider 직렬화 + per-asset 타임아웃 충돌" 사례 누적.
- 구현 시 `backend/app/services/DEVELOPMENT_DIRECTION.md`는 폴더 소유권 변화가 없으므로 갱신 불필요(동작/계약 변경은 feature 문서로 흡수).

## 10. 남은 리스크

- 무료/비공식 provider는 동시성 상향 시 rate limit·차단 정책이 예고 없이 바뀔 수 있다. 동시성은 실제 key smoke 후 단계적으로만 올린다.
- 타임아웃 상향은 1회 실행 시간을 늘린다. 비차단 워밍업으로 startup은 보호되지만, 스케줄러 간격(`MARKET_PRICES_REFRESH_MINUTES`)보다 1회 실행이 길어지지 않는지 확인해야 한다(현재 기본 5분, 드레인 추정 30s 이내라 여유).
- 근본적으로 종목 수가 더 늘면 같은 문제가 재발할 수 있다. 후보 E(스냅샷에서 history 분리)로 provider 호출 수 자체를 줄이는 것이 장기 해법이며 별도 계획으로 분리한다.
