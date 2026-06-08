# 네이버 뉴스 Open API 도입 계획

- 날짜: 2026-06-08
- 작성 단계: plan (구현 전)
- 대상 기능: 시장 데이터 / 뉴스 (`docs/harness/features/market-data.md`)

## 1. 목적 (Objective)

뉴스를 끌어오는 경로에 **네이버 공식 검색 Open API(뉴스)** 를 정식 provider로 추가한다. 현재 네이버 뉴스는 `search.naver.com` 검색 결과 페이지의 HTML을 정규식으로 긁는 비계약적 스크래핑 방식이며, KR 주식에만 제한적으로 쓰인다. 이를 인증 키 기반의 공식 API(`https://openapi.naver.com/v1/search/news.json`)로 전환·확장해서 안정성과 응답 품질(제목·요약·발행일·출처)을 높인다.

## 2. 현재 동작 / 목표 동작

### 현재 동작
- 뉴스 수집 진입점: [price_providers.py:1219](backend/app/services/price_providers.py#L1219) `fetch_market_news_items(ticker, limit)`.
- 자산군별 분기:
  - US 주식 → Finnhub company-news ([price_providers.py:1153](backend/app/services/price_providers.py#L1153))
  - KR 주식 → `_fetch_naver_finance_news` ([price_providers.py:1184](backend/app/services/price_providers.py#L1184)) — `search.naver.com` HTML을 `news_tit` 클래스 정규식으로 파싱. `published_at`/`summary`가 항상 빈 문자열.
  - 크립토/FX/그외 → Finnhub category-news
- `NAVER_NEWS_URL = "https://search.naver.com/search.naver"` ([price_providers.py:28](backend/app/services/price_providers.py#L28)).
- provider 호출은 `_get_text`/`_get_json`로 통일되어 있고, provider별 semaphore·실패 쿨다운·캐시가 공통 적용된다.
- 캐시: `news:{ticker}:{limit}` 키로 `MARKET_NEWS_REFRESH_MINUTES`(기본 60) 동안 재사용.
- Open Risks 문서에 "Naver Finance News is a non-contractual page-based source"로 이미 위험이 기록되어 있음 ([market-data.md:141](docs/harness/features/market-data.md#L141)).

### 목표 동작
- 새 함수 `_fetch_naver_open_api_news(query, limit)` 추가: 네이버 검색 Open API 호출.
  - 엔드포인트: `https://openapi.naver.com/v1/search/news.json`
  - 헤더: `X-Naver-Client-Id`, `X-Naver-Client-Secret` (env 기반)
  - 파라미터: `query`, `display`(=limit), `sort=date`
  - 응답 `items[]`의 `title`/`description`에서 `<b>` 등 HTML 태그 제거 + `html.unescape`, `link`/`originallink`, `pubDate`(RFC1123) → ISO 정규화하여 기존 뉴스 dict 스키마(`title/link/source/published_at/summary/type`)로 매핑.
- `fetch_market_news_items` 분기 개선:
  - 키(`NAVER_CLIENT_ID`/`NAVER_CLIENT_SECRET`)가 있으면 **KR 주식은 Open API를 우선 사용**, 실패/키 없음 시 기존 `_fetch_naver_finance_news` 스크래핑으로 폴백.
  - (옵션, 사용자 선택) KR 지수/원화(`KRW=X`)·일반 한국 시장 뉴스에도 Open API를 사용하도록 질의어를 구성. 기본안에서는 **KR 주식 한정 + 폴백**으로 범위를 좁게 둔다(아래 위험 참고).
- 키가 전혀 없으면 기존 동작(스크래핑)을 그대로 유지 → 무중단 degrade.

## 3. 변경 대상 파일

### 백엔드 (코드)
- [backend/app/core/config.py](backend/app/core/config.py) — `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` 설정 추가 (`str | None = None`, 기존 `*_API_KEY` 패턴과 동일).
- [backend/app/services/price_providers.py](backend/app/services/price_providers.py)
  - 상수: `NAVER_OPENAPI_NEWS_URL = "https://openapi.naver.com/v1/search/news.json"` 추가.
  - 헬퍼: `_naver_open_api_credentials()` (config에서 client id/secret 읽기).
  - 신규: `_parse_naver_open_api_news(payload, limit)`, `_fetch_naver_open_api_news(query, limit)`.
  - `fetch_market_news_items` 분기에 Open API 우선 + 스크래핑 폴백 로직 반영.

### 백엔드 (테스트)
- [backend/tests/test_price_providers.py](backend/tests/test_price_providers.py) — Open API 응답 파싱(HTML 태그/엔티티 제거, pubDate ISO 변환), 키 부재 시 스크래핑 폴백, 응답 스키마 일치 테스트 추가. **실제 네트워크 호출 없이 mock 응답**으로 검증(AGENTS.md §4).

### 설정/문서 (시크릿 값 미포함)
- [ENVIRONMENT_VARIABLE_RECOMMENDATIONS.md](ENVIRONMENT_VARIABLE_RECOMMENDATIONS.md) (이미 미추적 상태로 존재) 또는 env 가이드 — `NAVER_CLIENT_ID`/`NAVER_CLIENT_SECRET` 항목과 발급 방법(네이버 개발자센터 애플리케이션 등록, 검색 API 사용 설정) 안내 추가. **실제 키 값은 기록하지 않음.**

### 프론트엔드
- 변경 없음. `GET /api/market/news`·`latest-context` 응답 스키마(뉴스 dict)는 그대로 유지되므로 UI 영향 없음.

### DB
- 변경 없음 (스키마/마이그레이션 불필요).

## 4. 단계별 구현 계획

1. `config.py`에 `NAVER_CLIENT_ID`/`NAVER_CLIENT_SECRET` 추가.
2. `price_providers.py`에 Open API 상수·자격증명 헬퍼·파서·fetch 함수 추가.
   - 호출은 기존 `_get_json("naver_news", url, headers=..., params=..., timeout=8.0)` 재사용 → provider semaphore·쿨다운·실패 redact 일관성 유지.
   - `pubDate`(예: `Mon, 08 Jun 2026 10:00:00 +0900`) → `email.utils.parsedate_to_datetime` 후 ISO 변환. 파싱 실패 시 빈 문자열로 degrade.
   - `title`/`description`의 `<b></b>` 등 태그는 정규식 제거 + `html.unescape`.
3. `fetch_market_news_items`에서 KR 주식 분기를 "키 있으면 Open API → 실패 시 스크래핑 폴백" 순서로 변경. 캐시 키/TTL은 기존 유지.
4. 키 부재·API 오류 시 기존 동작 보존 확인(빈 결과 또는 스크래핑 폴백).
5. 테스트 추가 후 `pytest`로 파서/분기/폴백 검증.
6. 기능 문서·색인·변경 기록 갱신 (구현 단계에서).

## 5. 위험과 Risky Change 여부 (AGENTS.md §9)

- **DB 스키마 변경: 없음.** 인증/비밀번호 해시 변경: 없음. 스케줄러 빈도/리포트 비용 변경: 없음.
- **Risky Change 해당 여부: 아니오(낮음).** 단, 아래는 사용자 판단이 필요:
  - **신규 외부 API/네트워크 의존 추가**: 네이버 Open API는 무료지만 **일일 호출 한도(기본 25,000회/일)** 가 있다. 현재 뉴스는 `MARKET_NEWS_REFRESH_MINUTES`(기본 60) 스케줄로 자산마다 호출되므로, 사용 범위를 KR 주식으로 좁히면 한도 내에서 안전하다. 범위를 KR 지수/일반 뉴스까지 넓히면 호출량이 늘어난다 → **기본안은 KR 주식 한정**으로 제안.
  - **시크릿 추가**: `NAVER_CLIENT_ID`/`NAVER_CLIENT_SECRET`는 env로만 주입하고 커밋 금지(AGENTS.md §8). `.env` 직접 열람 없이 키 이름만 문서화.
- 기타 위험:
  - Open API의 뉴스 `link`는 네이버 뉴스 페이지 또는 원본(`originallink`)이 섞여 나온다 → `link`/`originallink` 우선순위 정책을 명시.
  - 스크래핑 폴백 경로는 그대로 두므로, 네이버가 페이지 구조를 바꿔도 Open API 경로가 우선이면 영향이 줄어든다.

## 6. 검증 계획 (AGENTS.md §6 — 최소 집합)

- 백엔드 단위 테스트(네트워크 없이 mock):
  ```powershell
  cd backend
  pytest tests/test_price_providers.py
  ```
  - Open API 응답 파싱(태그/엔티티 제거, pubDate→ISO, 스키마 일치)
  - 키 부재 시 스크래핑 폴백 / 빈 결과 degrade
- 프론트엔드: 응답 스키마 불변이므로 빌드 검증 불필요(필요 시 `npm run build` 생략 사유 기록).
- 실제 키 기반 smoke는 키 보유 시 사용자 환경에서 수동 확인(미실행 시 사유 명시).

## 7. 갱신할 문서

- `docs/harness/naver-news-open-api-implementation-2026-06-08.md` (구현 단계에서 신규 변경 기록 작성).
- [docs/harness/features/market-data.md](docs/harness/features/market-data.md)
  - Data Flow / Contracts에 Naver Open API 뉴스 provider와 `NAVER_CLIENT_ID`/`NAVER_CLIENT_SECRET` 추가.
  - Open Risks의 "non-contractual page-based source" 항목을 "Open API 우선 + 스크래핑 폴백"으로 갱신.
  - Change Records에 본 계획서와 구현 기록 링크 추가.
- [docs/harness/feature-index.md](docs/harness/feature-index.md) — 본 계획서/구현 기록을 market-data 행과 상단 목록에 추가.
- 폴더 ownership 변경 없음 → `DEVELOPMENT_DIRECTION.md` 수정 불필요(루트 문서의 "Naver 뉴스" 언급은 유지).

## 8. 결정 사항 / 사용자 확인 (2026-06-08)

- **적용 범위(확정): (A) KR 주식 한정 + 스크래핑 폴백.** 호출량을 일일 한도 내로 안전하게 유지한다. KR 지수·일반 한국 시장 뉴스 확대(B안)는 채택하지 않음.
- **진행 상태(확정): 계획서만 작성, 구현 보류.** 구현은 추후 `/harness-implement`로 별도 진행한다.
- 후속 준비: 네이버 개발자센터에서 검색 API 애플리케이션을 등록하고 `NAVER_CLIENT_ID`/`NAVER_CLIENT_SECRET`를 발급해 env에 주입해야 함(코드는 키 부재 시 자동 degrade).
