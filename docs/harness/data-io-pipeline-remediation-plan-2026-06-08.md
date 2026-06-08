# 데이터 입출력 파이프라인 문제 해결 계획

Date: 2026-06-08
Status: Plan only - 코드 변경 없음
Feature:
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/deployment-runtime.md`

## 목적

데이터 입출력 파이프라인 보고서와 관련 harness 문서를 기준으로, 시장 데이터 수집/정규화/캐시/조회/API 출력/AI 리포트 입력 경로에서 남은 문제를 실제 코드와 대조해 해결 순서를 정한다.

이번 계획은 구현 전 작업이며, 사용자 화면이나 챗봇 요청이 새 AI 리포트 생성을 트리거하지 않는 기존 제품 규칙을 유지한다. AI 리포트 생성은 저장된 스케줄러 결과만 조회하는 방향을 유지한다.

## 읽은 문서와 코드

- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/market-data-provider-response-format-audit-plan-2026-06-03.md`
- `docs/harness/report-generation-deployment-failure-remediation-plan-2026-06-07.md`
- `backend/app/services/price_providers.py`
- `backend/app/services/macro_service.py`
- `backend/app/main.py`

## 현재 파이프라인 요약

1. 외부 provider 입력은 `price_providers.py`, `macro_service.py`, `market_service.py`에서 수집된다.
2. 가격/뉴스는 startup warm-up과 APScheduler job을 통해 `market_cache`에 적재된다.
3. 사용자 API는 `GET /api/market/prices`, `GET /api/market/news`, `GET /api/market/history/{ticker}`, `GET /api/market/latest-context/{ticker}`를 통해 캐시 또는 TTL provider 결과를 읽는다.
4. AI 리포트 생성은 scheduler 전용이며, `AssetDetail.jsx`와 챗봇은 저장된 `AIReport`만 조회해야 한다.
5. `POST /api/ai/generate/{ticker}`는 일반 사용자에게 HTTP 403을 반환하도록 막혀 있다.

## 확인된 문제

### P1. FX 날짜 출력 오류

`KRW=X` 히스토리 fallback은 open.er-api.com의 `time_last_update_utc`를 그대로 받아 `str(as_of)[:10]`으로 자른다. RFC 스타일 날짜가 들어오면 `Wed, 03 J` 같은 잘못된 날짜가 `points[].date`로 노출될 수 있다.

해결 방향:
- `email.utils.parsedate_to_datetime`로 RFC 날짜를 `YYYY-MM-DD`로 정규화한다.
- ISO 날짜 문자열이면 기존 값을 보존한다.
- 파싱 실패 시 UTC 오늘 날짜로 fallback한다.
- `tests/test_price_providers.py` 또는 `tests/test_market_history_route.py`에 `KRW=X` 날짜 정규화 케이스를 추가한다.

### P1. data.go.kr `serviceKey` 입력 형식 불명확

`_data_go_params()`는 `settings.DATA_GO_KR_API_KEY`를 그대로 `httpx` params에 넣는다. 공공데이터포털에서 받은 URL-encoded key를 환경변수에 넣으면 `%`가 재인코딩되어 인증 실패가 날 수 있다.

해결 방향:
- 코드에서 `urllib.parse.unquote`로 encoded key를 1회 정규화한 뒤 params에 넣는다.
- 로그에는 key 값을 출력하지 않고, missing/invalid 상태만 남긴다.
- `.env.example` 또는 환경 변수 가이드 문서에 decoded/encoded key 허용 정책을 명시한다.
- mock 기반 테스트로 encoded key 입력 시 params가 의도한 형태로 구성되는지 검증한다.

### P1. data.go.kr 히스토리 기간 절단 순서 오류

`fetch_data_go_stock_history()`와 `fetch_data_go_index_history()`는 provider row를 point로 만든 뒤 `points[-_period_to_days(period):]`를 먼저 적용하고, 그 뒤 `_history_payload()` 내부에서 정렬한다. provider가 최신순 또는 비정렬로 내려오면 최근 N개가 아니라 임의 N개가 남을 수 있다.

해결 방향:
- `_history_payload()`에 `limit` 인자를 추가하거나, 호출 전에 `_normalize_points(points, limit=...)`를 명시적으로 사용한다.
- 모든 history provider가 "정렬 후 limit" 원칙을 공유하도록 helper를 정리한다.
- 비정렬/최신순 fixture를 넣어 최근 N개가 오름차순으로 반환되는지 테스트한다.

### P1. 미국 채권 히스토리 provider 날짜 손실

`/api/market/history/DGS10` 계열은 `fetch_us_bond_data()`가 반환한 `history_prices`를 `main.py`의 `build_points()`로 현재 날짜 기준 재생성한다. FRED 관측일이 사라져 휴장일/결측일/실제 발표일과 다른 차트가 된다.

해결 방향:
- `macro_service.py`에 FRED observation `date`를 보존하는 `fetch_us_bond_history()`를 추가한다.
- `main.py`의 US bond history 경로가 `fetch_us_bond_history()`를 사용하게 한다.
- 기존 `fetch_us_bond_data()` snapshot은 유지하되 내부에서 새 helper를 재사용할 수 있게 정리한다.
- FRED fixture로 날짜 보존, `.` 결측 fallback, 오름차순 정렬을 검증한다.

### P2. `period=1d` 의미 불일치

`price_providers._period_to_days("1d")`는 30일을 반환하지만, `main.py` bond route는 `1d`를 7일로 본다. feature 문서는 "1d는 intraday가 아닌 provider-dated daily points"라고 설명하지만 실제 point 개수 정책은 일관되지 않다.

해결 방향:
- 정책을 하나로 결정한다. 권장안은 `1d=7 daily points`, `1mo=30 daily points`, `1y=365`, `5y=1825`이다.
- `price_providers.py`, `main.py`, frontend 기간 UI 문구, feature 문서를 같은 정책으로 맞춘다.
- chart가 intraday처럼 보이지 않도록 UI 라벨을 "최근 일간 데이터" 계열로 유지한다.

### P2. public price/history 출력의 provider metadata 부족

일부 snapshot/history payload에는 `provider_meta`가 붙지만, `GET /api/market/history/{ticker}`는 `provider_meta`를 응답에서 버린다. 화면과 리포트 진단에서 EOD/delayed/T+1/reference rate 같은 데이터 신선도를 설명하기 어렵다.

해결 방향:
- `history` API 응답에 optional `provider_meta`를 통과시킨다.
- 기존 frontend가 무시해도 깨지지 않는 optional field로 둔다.
- 필요한 화면에만 `as_of`, `freshness`, `provider`를 작게 표시한다.
- open.er-api.com, FMP, Stooq fallback, data.go.kr의 freshness 의미를 feature 문서에 고정한다.

### P2. 배포 환경 AI 리포트 미생성 원인 관측 부족

스케줄러가 꺼져 있거나 provider/readiness/quality gate에서 막혀도 최종 사용자는 `GET /api/reports/{ticker}` 404만 본다. 운영자가 실패 유형을 빠르게 분류하기 어렵다.

해결 방향:
- 우선 로그 메시지를 `scheduler_disabled`, `provider_unavailable`, `readiness_blocked`, `quality_failed`, `db_commit_failed` 수준으로 분류한다.
- secret redaction은 기존 `redact_secrets()` 계약을 유지한다.
- 운영 진단이 계속 어렵다면 후속 승인 후 `report_generation_runs` 감사 테이블을 별도 migration으로 추가한다.

### P3. provider 실패/cooldown 테스트 부족

문서상 Finnhub 429/timeout, Stooq key missing, data.go.kr empty response, Naver selector 변경에 대한 단위 테스트가 부족하다.

해결 방향:
- `_get_json()`/`_get_text()` 실패 후 동일 request key가 TTL 동안 재호출되지 않는지 검증한다.
- provider key missing이 네트워크 호출 없이 빈 응답/metadata로 degrade되는지 검증한다.
- Naver HTML 구조 변경 시 빈 `items: []`로 degrade되는지 검증한다.

## 구현 순서

1. 날짜와 정렬처럼 사용자 출력 정확도에 직접 영향을 주는 P1부터 처리한다.
2. `KRW=X` 날짜 parser와 테스트를 추가한다.
3. data.go.kr key 정규화와 히스토리 정렬 후 limit를 함께 반영한다.
4. US bond 날짜 보존 helper를 만들고 `main.py` history route를 교체한다.
5. `period=1d` 정책을 확정해 backend/frontend/docs를 동기화한다.
6. optional `provider_meta` 통과를 추가하고, 화면 표시는 최소 범위로 분리한다.
7. AI report scheduler 실패 로그 분류를 추가한다.
8. provider failure/cooldown 테스트를 보강한다.

## 예상 수정 파일

- `backend/app/services/price_providers.py`
- `backend/app/services/macro_service.py`
- `backend/app/main.py`
- `backend/app/services/market_service.py` 가능성 있음
- `backend/app/core/config.py` 가능성 있음
- `frontend/src/pages/AssetDetail.jsx` 가능성 있음
- `frontend/src/pages/MarketSnapshot.jsx` 가능성 있음
- `frontend/src/components/SparklineChart.jsx` 가능성 있음
- `backend/tests/test_price_providers.py`
- `backend/tests/test_market_history_route.py`
- `backend/tests/test_macro_service.py`
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/feature-index.md`

## 검증 계획

Backend:

```powershell
cd backend
python -m pytest tests/test_price_providers.py tests/test_market_history_route.py tests/test_macro_service.py
```

Report/scheduler 관련 로그 분류를 구현하는 경우:

```powershell
cd backend
python -m pytest tests/test_ai_report_generation_switch.py tests/test_ai_report_quality_gate.py
```

Frontend 표시를 변경하는 경우:

```powershell
cd frontend
npm run lint
npm run build
```

수동 smoke:

- `GET /api/market/history/KRW%3DX?period=1d`
- `GET /api/market/history/DGS10?period=1mo`
- `GET /api/market/history/005930.KS?period=1mo`
- `GET /api/market/prices`
- `GET /api/reports/NVDA`는 저장된 리포트 조회만 확인하고, 사용자 경로에서 새 생성이 발생하지 않는지 확인한다.

## 승인 필요 항목

- AI report scheduler cadence, coverage, cooldown을 넓히는 변경.
- `report_generation_runs` 같은 새 DB 테이블/migration 추가.
- 외부 cron/task endpoint 추가.
- provider 유료 플랜 또는 네트워크 호출량 증가.

## 남은 리스크

- 무료 provider의 응답 형식, rate limit, 지연은 코드 변경 없이도 달라질 수 있다.
- data.go.kr와 Stooq는 실제 key가 있는 환경에서 추가 smoke가 필요하다.
- Naver 뉴스는 비공식 HTML scraping 경로라 selector 변경에 취약하다.
- `provider_meta`를 화면에 노출하면 사용자에게 데이터 지연/출처를 설명하는 장점이 있지만 UI 밀도가 올라간다.
- broad AI report generation은 계속 비활성/보수 정책을 유지해야 비용 리스크를 피할 수 있다.

## 문서 후속 작업

구현 단계에서는 별도 구현 기록을 `docs/harness/data-io-pipeline-remediation-implementation-YYYY-MM-DD.md`로 남긴다. 변경된 기능 문서의 `Change Records`에 구현 기록을 추가하고, `docs/harness/feature-index.md`도 함께 갱신한다.
