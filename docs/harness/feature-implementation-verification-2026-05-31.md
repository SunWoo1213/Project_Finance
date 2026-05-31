# docs/harness 기능 구현 검증 보고서

Date: 2026-05-31

## 목적

`docs/harness`와 `docs/harness/features` 문서가 설명하는 기능이 현재 코드에 실제로 구현되어 있는지 확인했다. 이번 작업은 검증과 기록만 수행했으며, 런타임 코드와 기존 기능 문서는 수정하지 않았다.

## 후속 조치 상태

이 보고서의 수정 후보 중 낮은 위험으로 바로 처리 가능한 항목은 이후 `docs/harness/feature-implementation-fixes-2026-05-31.md`에서 구현과 검증까지 완료했다.

완료된 항목:

- 오래된 변경 기록의 인증 상태 설명 갱신
- `feature-index.md`의 AI 리포트 품질 변경 기록 링크 보강
- `ReportCard.jsx`를 실제 `AssetDetail.jsx` 리포트 렌더링 경로에 연결
- 자산 상세 화면의 한국 주식/암호화폐/환율/거시 지표 표시 카테고리 판별 공통화
- 선택적 `FMP_API_KEY`, `FINNHUB_API_KEY` 설정 필드 추가
- 한국 채권 히스토리 테스트 monkeypatch 대상 정정
- 잘못된 JWT `sub` 값의 인증 오류 처리를 401로 보강
- `pytest`, `pytest-asyncio` 테스트 의존성 추가와 관련 테스트 실행
- 로컬 백엔드 health 스모크를 위한 `ENABLE_MARKET_WARMUP`, `ENABLE_SCHEDULER` 런타임 플래그 추가

보수적으로 유지한 항목:

- 스케줄러가 모든 기본 시장 캐시 자산을 자동으로 DB `Asset`으로 확장하는 동작은 추가하지 않았다. LLM/API 호출량이 늘 수 있어 제품/비용 승인이 필요한 변경으로 문서화했다.

## 검증 범위

- 인증 및 Google 로그인
- 시장 데이터, 가격, 뉴스, 히스토리
- 홈 주요 시장 카드와 `/market/:ticker` 스냅샷
- 자산 즐겨찾기
- 자산 상세, AI 리포트, 최신 컨텍스트
- 커뮤니티 댓글, 좋아요, 신고
- AI 리포트 품질 게이트, 역할 노드, 포맷 검증, 팩트 체크
- `docs/harness` 변경 기록과 실제 코드 간 정합성

## 실행한 검증

- `git status --short`: 기존 사용자/이전 작업 변경사항 확인
- `py -m compileall backend\app backend\tests`: 통과
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_ai_report_quality_gate.py backend\tests\test_market_history_route.py backend\tests\test_macro_service.py`: 실행 불가, 현재 가상환경에 `pytest` 모듈 없음
- `npm.cmd run build` from `frontend/`: 통과, Vite large chunk warning 있음
- `npm.cmd run lint` from `frontend/`: 통과

## 구현 확인 결과

대부분의 핵심 기능은 문서와 코드가 일치한다.

- Google 전용 로그인은 `frontend/src/pages/Login.jsx`, `backend/app/api/auth.py`, `backend/app/api/deps.py`에 구현되어 있다.
- `/register` 라우트와 로컬 로그인 UI는 현재 라우트 테이블에 없다.
- `POST /api/ai/generate/{ticker}`와 `GET /api/reports/{ticker}`는 현재 인증 의존성을 사용한다.
- 시장 가격/뉴스 캐시는 FastAPI lifespan에서 초기화되고, 가격 5분/뉴스 1시간 주기로 스케줄링된다.
- 홈 화면은 S&P 500, Nasdaq 100, USD/KRW, KOSPI 카드를 `/market/:ticker`로 보낸다.
- `/market/:ticker`는 AI 리포트/커뮤니티 없이 1일 차트와 관련 대시보드 링크를 표시한다.
- 즐겨찾기는 `favoriteAssets` localStorage 키와 Zustand store로 구현되어 있다.
- 자산 상세 화면은 히스토리, 최신 뉴스/일정, 인증 기반 AI 리포트, 댓글 영역을 함께 처리한다.
- 댓글 생성/수정/삭제/좋아요/신고는 백엔드에서 인증과 소유권을 확인한다.
- 댓글 신고는 사용자-댓글 복합 키로 중복을 막고, 100건 이상이면 댓글을 삭제한다.
- AI 리포트 파이프라인에는 역할 노드, 포맷 검증, 숫자 팩트 체크, 평가 실패 시 저장 차단 로직이 들어 있다.

## 수정이 필요하다고 판단되는 부분

### 1. 오래된 변경 기록이 현재 구현과 충돌함

`docs/harness/latest-context-report-quality.md`는 `POST /api/ai/generate/{ticker}`가 아직 인증되지 않았다고 적고 있다. 하지만 현재 `backend/app/main.py`의 `generate_report`는 `current_user: User = Depends(get_current_user)`를 사용하므로 인증이 필요하다.

수정 제안:

- `docs/harness/latest-context-report-quality.md`의 follow-up risk에서 해당 문장을 “이후 Phase 1에서 인증 보호가 완료됨”으로 갱신한다.
- 필요하면 `docs/harness/report-quality-phase-1.md` 링크를 함께 붙여 문서 흐름을 명확히 한다.

### 2. `feature-index.md`의 AI 리포트 변경 기록 목록이 일부 누락됨

`docs/harness/features/asset-detail-ai-community.md`에는 Phase 1, Phase 2, Fact Checker 문서까지 연결되어 있지만, `docs/harness/feature-index.md`의 Asset detail 행에는 일부 최신 리포트 품질 문서만 들어 있다.

수정 제안:

- `docs/harness/feature-index.md`의 Asset detail 변경 기록에 다음 문서를 추가한다.
- `docs/harness/report-quality-phase-1.md`
- `docs/harness/report-quality-phase-2.md`
- `docs/harness/report-quality-fact-checker.md`

### 3. `ReportCard.jsx`는 문서상 주요 파일이지만 실제 화면에서 사용되지 않음

`docs/harness/features/asset-detail-ai-community.md`와 `feature-index.md`는 `frontend/src/components/ReportCard.jsx`를 리포트 표시 지원 컴포넌트로 언급한다. 하지만 현재 `AssetDetail.jsx`는 `ReportCard`를 import하지 않고 `ReactMarkdown`으로 `report.final_content`만 직접 렌더링한다.

수정 제안:

- 실제 의도가 요약 카드까지 보여주는 것이라면 `AssetDetail.jsx`에서 `ReportCard`를 사용하도록 기능 수정이 필요하다.
- 반대로 현재 단일 Markdown 렌더링이 의도라면 문서에서 `ReportCard.jsx`를 “레거시/미사용 후보”로 표시하거나 소유권 목록에서 제외한다.

### 4. 한국 주식/암호화폐/환율 상세 화면의 표시 카테고리 판별이 불완전함

`frontend/src/pages/AssetDetail.jsx`의 `uiCategory`는 `bonds`, `commodities`만 별도 처리하고 나머지를 `US_STOCK`으로 처리한다. 그 결과 `kr_top10`, `cryptos`, `macro`의 일부 자산은 상세 화면에서 가격/시가총액 포맷이 실제 자산군과 다르게 표시될 수 있다.

수정 제안:

- `assetGroup === "kr_top10"`은 `KR_STOCK`
- `assetGroup === "cryptos"`는 `CRYPTO` 또는 별도 포맷 정책
- `assetGroup === "macro"`에서 `KRW=X`는 `FX`, `^KS11`은 `KR_STOCK`
- 이 로직을 `CategoryView.jsx`의 `getUiCategory`와 공통 유틸로 맞추는 것이 좋다.

### 5. FMP/Finnhub 구조화 provider 키가 `.env`에서 로드되지 않을 가능성이 큼

`backend/app/services/external_api_service.py`는 `os.getenv("FMP_API_KEY")`, `os.getenv("FINNHUB_API_KEY")` 또는 `settings` 속성을 본다. 하지만 `backend/app/core/config.py`의 `Settings`에는 `FMP_API_KEY`, `FINNHUB_API_KEY` 필드가 없다. 이 저장소는 `.env`를 Pydantic settings로 읽는 구조라서, 키가 `.env`에만 있을 경우 provider 함수가 계속 `missing` 상태를 반환할 수 있다.

수정 제안:

- `Settings`에 `FMP_API_KEY: str | None = None`, `FINNHUB_API_KEY: str | None = None`를 추가한다.
- provider 키 사용 여부와 필수/선택 상태를 관련 문서에 명확히 적는다.

### 6. 시장 히스토리 테스트가 현재 구현과 맞지 않음

`backend/app/main.py`의 한국 채권 히스토리 경로는 현재 `fetch_kr_bond_history`를 호출한다. 하지만 `backend/tests/test_market_history_route.py`는 `main.fetch_kr_bond_data`를 monkeypatch하고 있어, `pytest`가 설치되면 의도한 테스트가 실패하거나 실제 경로를 제대로 검증하지 못할 가능성이 높다.

수정 제안:

- 테스트 monkeypatch 대상을 `main.fetch_kr_bond_history`로 바꾼다.
- 기대 결과도 `points` 기반 응답에 맞춰 정리한다.

### 7. 잘못된 JWT `sub` 값에 대한 인증 에러 처리가 약함

`backend/app/api/deps.py`는 JWT decode 후 `int(user_id_str)`를 수행한다. 토큰 서명은 유효하지만 `sub`가 숫자가 아닌 경우 `ValueError`가 발생해 401 대신 500으로 이어질 수 있다.

수정 제안:

- `int(user_id_str)` 변환을 `try/except (TypeError, ValueError)`로 감싸고 기존 `credentials_exception`을 반환한다.

### 8. 스케줄러 기반 리포트 생성은 DB에 이미 존재하는 Asset만 대상으로 함

`generate_daily_reports()`는 DB의 `assets` 테이블을 조회해 리포트를 생성한다. 시장 캐시에 있는 모든 기본 자산을 자동으로 DB 자산으로 보장하지는 않는다. 따라서 초기 DB에서는 스케줄러가 문서상 기대되는 “전체 기본 자산 리포트 생성”처럼 동작하지 않을 수 있다.

수정 제안:

- 제품 의도가 전체 기본 자산의 배치 생성이라면, 스케줄러 전에 시장 캐시 자산을 DB `assets`에 동기화하는 단계가 필요하다.
- 제품 의도가 “사용자가 접근하거나 댓글/리포트 생성으로 만들어진 자산만 배치 갱신”이라면, 문서에 그 제한을 명확히 적는다.

## 현재 바로 수정하지 않은 이유

사용자가 “수정은 하지마세요”라고 요청했으므로 런타임 코드와 기존 기능 문서는 변경하지 않았다. 위 항목은 후속 작업에서 수정 후보로 다루면 된다.

## 남은 리스크

- `pytest`가 설치되지 않아 백엔드 테스트의 실제 pass/fail은 확인하지 못했다.
- 실제 Google 로그인, DB 연동, 외부 provider, LLM 호출은 비용/시크릿/네트워크 의존성이 있어 실행하지 않았다.
- 문서상 리포트 품질 기능은 정적 코드 대조 기준으로는 구현되어 있으나, 실제 LLM 출력 품질은 별도 수동 스모크 테스트가 필요하다.
