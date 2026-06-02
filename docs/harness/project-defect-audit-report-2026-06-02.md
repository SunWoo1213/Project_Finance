# 프로젝트 결점 감사 보고서

작성일: 2026-06-02

## 목표

현재 `Project_Finance` 저장소의 실제 코드, 기능 문서, 검증 명령을 기준으로 후속 하네스 엔지니어링에서 바로 사용할 수 있는 결점 목록을 남긴다.

이번 보고서는 코드 수정이 아니라 감사 기록이다. 기존 `docs/harness/project-gap-remediation-plan-2026-06-02.md`의 넓은 부족점 계획을 바탕으로, 이번 실행에서 직접 확인한 실패와 구조적 위험을 분리했다.

## 감사 기준

- `git status --short`
- `ARCHITECTURE.md`
- `PROJECT_STRUCTURE_ANALYSIS.md`
- `DEVELOPMENT_DIRECTION.md`
- `docs/harness/feature-index.md`
- `docs/harness/project-gap-remediation-plan-2026-06-02.md`
- 현재 코드:
  - `backend/app/core/config.py`
  - `backend/app/main.py`
  - `backend/app/api/community.py`
  - `backend/app/services/ai_service.py`
  - `backend/app/services/payment_service.py`
  - `backend/app/services/notification_service.py`
  - `frontend/src/App.jsx`
  - `frontend/src/pages/AssetDetail.jsx`
  - `frontend/src/pages/NotificationsSettings.jsx`
  - `frontend/src/utils/apiClient.js`

## 검증 결과 요약

### 통과

- `frontend`에서 `npm.cmd run lint` 통과.
- `frontend`에서 `npm.cmd run build` 통과.
- `aiosqlite` 설치 후 `backend`에서 `python -m pytest tests` 재실행 시 79개 중 78개 통과.

### 실패 또는 경고

- `backend/tests/test_ai_report_quality_gate.py::test_report_generation_policy_rejects_missing_user` 1개 실패.
  - 테스트 기대값: `401`.
  - 실제 코드: `backend/app/main.py`의 `ensure_report_generation_allowed()`가 항상 `403` 반환.
- 최초 백엔드 테스트 실행은 현재 `.venv`에 `aiosqlite`가 없어 SQLite 기반 테스트 15개 수집/실행 경로가 막혔다.
  - `backend/requirements.txt`에는 `aiosqlite`가 있으므로 저장소 요구사항과 로컬 venv 상태가 어긋난 문제다.
  - 감사 중 `.venv`에 `aiosqlite`를 설치한 뒤 재검증했다.
- `npm run lint`와 `npm run build`는 PowerShell 실행 정책 때문에 `npm.ps1`이 막혔다. Windows 하네스에서는 `npm.cmd run ...`를 쓰는 것이 안전하다.
- `vite build`는 단일 JS chunk가 `853.90 kB`로 500 kB 경고를 냈다.
- 백엔드 테스트는 다수의 `datetime.utcnow()` deprecation warning을 출력했다.

## 우선 결점 목록

### D1. 수동 AI 리포트 생성 차단 정책의 테스트/코드 불일치

근거:

- `backend/app/main.py:440`의 `ensure_report_generation_allowed(user)`는 전달된 `user` 값을 보지 않고 항상 `403`을 반환한다.
- `backend/app/main.py:450`의 endpoint는 `Depends(get_current_user)`를 사용하므로 실제 HTTP 요청에서 미인증 사용자는 dependency 단계에서 `401`이 될 수 있다.
- `backend/tests/test_ai_report_quality_gate.py:231`은 helper를 직접 `None`으로 호출했을 때 `401`을 기대한다.

영향:

- 전체 백엔드 테스트가 1개 실패로 남아 CI 신뢰도가 낮다.
- 정책 자체는 "사용자-facing 수동 생성은 비활성화"로 명확하지만, helper 단위 테스트의 계약이 endpoint dependency 계약과 섞여 있다.

권장 후속 작업:

1. 정책을 결정한다.
   - helper가 `None`을 받으면 `401`, 인증된 사용자는 `403`을 반환하게 할지.
   - 또는 helper는 인증 완료 후 호출되는 정책 gate로 보고 테스트 기대값을 `403`으로 바꿀지.
2. endpoint 수준 테스트와 helper 단위 테스트를 분리한다.
3. AI 리포트 문서에는 계속 "사용자-facing 요청은 fresh report generation을 트리거하지 않는다"는 규칙을 유지한다.

### D2. 런타임 기본값이 외부 호출과 비용성 scheduler를 너무 쉽게 켠다

근거:

- `backend/app/core/config.py:35` `ENABLE_MARKET_WARMUP=True`.
- `backend/app/core/config.py:36` `ENABLE_SCHEDULER=True`.
- `backend/app/main.py:154` startup market warm-up 실행.
- `backend/app/main.py:201` startup 즉시 `generate_daily_reports` date job 등록.
- `backend/app/main.py:204` `run_date=datetime.now()`로 scheduler 시작 직후 리포트 job이 돈다.

영향:

- 로컬/스테이징에서 backend를 켜기만 해도 외부 market provider와 LLM report pipeline으로 이어질 수 있다.
- `.env_example`에는 첫 hosted smoke에서 false 권장이 적혀 있지만 코드 기본값은 true다.
- OpenAI/API key가 설정된 환경에서 비용 또는 rate limit 위험이 있다.

권장 후속 작업:

1. production/staging 기본 정책을 코드 또는 settings validation으로 강제한다.
2. `ENVIRONMENT != "development"`일 때 scheduler/warmup 기본값을 보수적으로 둘지 검토한다.
3. startup 즉시 리포트 생성 job은 명시 opt-in으로 바꾸거나, 최소한 문서와 smoke checklist에서 강하게 차단한다.

### D3. DB bootstrap 실패가 startup 실패로 이어지지 않는다

근거:

- `backend/app/main.py:133`에서 `ENABLE_DB_SCHEMA_BOOTSTRAP`가 true이면 `Base.metadata.create_all`과 `ALTER TABLE` 보정이 실행된다.
- `backend/app/main.py:141`에서 예외가 발생해도 warning만 남기고 return한다.
- `backend/app/core/config.py:24`의 기본값은 `ENABLE_DB_SCHEMA_BOOTSTRAP=True`.

영향:

- DB 연결 또는 schema 보정 실패 후에도 앱이 뜬 것처럼 보일 수 있다.
- 이후 API 요청에서 산발적인 장애가 발생하고 `/health`만 보면 정상처럼 보일 수 있다.
- migration-managed runtime과 local bootstrap runtime의 실패 모드가 다르다.

권장 후속 작업:

1. bootstrap 실패 시 local/dev에서만 degrade할지, 모든 환경에서 startup fail-fast할지 결정한다.
2. `ENVIRONMENT=production` 또는 `ENABLE_DB_SCHEMA_BOOTSTRAP=false`에서는 이미 schema check가 있으므로 이 경로를 hosted smoke 기준으로 유지한다.
3. `/health`와 `/db-check`의 운영 의미를 분리한다.

### D4. 운영 secret 검증이 약하다

근거:

- `backend/app/core/config.py:30`에 JWT `SECRET_KEY` 기본값이 있다.
- `.env_example`은 강한 secret 사용을 안내하지만, 코드가 production 환경에서 placeholder/default를 차단하지 않는다.

영향:

- 환경변수 누락 상태로도 backend가 실행될 수 있다.
- 인증 토큰 서명이 예측 가능한 값으로 운영에 올라갈 위험이 있다.

권장 후속 작업:

1. `ENVIRONMENT in {"production", "staging"}`일 때 기본 `SECRET_KEY` 사용을 startup에서 거부한다.
2. `GOOGLE_CLIENT_ID`, CORS origin, payment webhook secret 등 운영 필수값도 provider 활성화 조건별로 validation한다.
3. secret 값은 문서에 기록하지 않고 변수명과 실패 조건만 기록한다.

### D5. `AssetDetail.jsx`가 너무 많은 책임을 가진다

근거:

- `frontend/src/pages/AssetDetail.jsx`는 741줄이다.
- 한 파일에서 가격 요약, 히스토리 차트, 최신 뉴스, 저장 리포트 권한/조회, paywall, 댓글 CRUD, 좋아요, 신고, 즐겨찾기를 모두 처리한다.
- 관련 API 호출 근거:
  - report cache/refetch: `frontend/src/pages/AssetDetail.jsx:48`, `:157`, `:160`
  - 댓글 삭제 confirm: `frontend/src/pages/AssetDetail.jsx:279`
  - 댓글 신고: `frontend/src/pages/AssetDetail.jsx:300`, `:306`

영향:

- 리포트 권한, 커뮤니티, 차트 중 하나만 바꿔도 같은 대형 파일에서 회귀 위험이 커진다.
- 상태와 side effect가 얽혀 component-level 테스트를 만들기 어렵다.

권장 후속 작업:

1. 기존 `project-gap-remediation-plan`의 Phase 7처럼 다음 단위로 분리한다.
   - `AssetHeader`
   - `AssetMarketSummary`
   - `AssetHistoryPanel`
   - `LatestContextPanel`
   - `ReportAccessPanel`
   - `CommunitySection`
2. 분리 전후로 `npm.cmd run lint`, `npm.cmd run build`, 주요 `/detail/:ticker` 수동 smoke를 수행한다.

### D6. 댓글 신고 UI가 사유 선택을 보여주지만 서버에는 사유를 보내지 않는다

근거:

- `frontend/src/pages/AssetDetail.jsx:16`에 `REPORT_REASONS`가 있다.
- `frontend/src/pages/AssetDetail.jsx:699`에서 사유 버튼을 렌더링한다.
- `frontend/src/pages/AssetDetail.jsx:703`의 클릭은 `reportComment(comment.id)`만 호출한다.
- `frontend/src/pages/AssetDetail.jsx:306`의 API body는 `{}`이다.
- `backend/app/api/community.py`의 `report_comment` endpoint도 사유 schema를 받지 않는다.

영향:

- 사용자는 사유를 선택한다고 느끼지만 실제 신고 데이터에는 사유가 저장되지 않는다.
- 운영 moderation이나 abuse 분석에 필요한 정보가 없다.

권장 후속 작업:

1. product 결정: 신고 사유를 저장할지, 사유 UI를 제거할지 선택한다.
2. 저장한다면 `CommentReport` 모델, schema, Alembic migration, API test를 추가한다.
3. 신고 threshold 자동 삭제 정책과 함께 moderation audit trail을 재검토한다.

### D7. 시장 히스토리 API 응답 계약이 일부 경로에서 불안정하다

근거:

- `backend/app/main.py:328` `/api/market/history/{ticker}`.
- macro/bond/commodity 경로는 `{ticker, series_type, unit, points, legacy}` 구조를 반환한다.
- yfinance 경로에서 `df.empty`이면 `backend/app/main.py:417` 이후 `backend/app/main.py:418`에서 빈 배열 `[]`을 반환한다.
- 일반 yfinance 성공 경로는 object를 반환한다.

영향:

- 프론트가 배열과 object를 모두 처리해야 하며, 새 소비자가 API 계약을 오해하기 쉽다.
- 404가 필요한 경우와 "데이터 없음" 배열이 섞인다.

권장 후속 작업:

1. 모든 경로에서 동일한 response shape을 반환한다.
2. 데이터 없음은 `{ points: [], legacy: [], source_status: "empty" }` 또는 명시적 404 중 하나로 정한다.
3. `backend/tests/test_market_history_route.py`에 empty yfinance path regression을 추가한다.

### D8. async route 안에서 synchronous yfinance 호출이 실행된다

근거:

- `backend/app/main.py:414`에서 `yf.Ticker(asset_ticker)`.
- 바로 다음 줄에서 `stock.history(...)`를 호출한다.

영향:

- `/api/market/history/{ticker}` 요청 중 외부 I/O가 event loop를 막을 수 있다.
- 느린 provider 응답이 다른 요청 지연으로 번질 수 있다.

권장 후속 작업:

1. yfinance 호출을 service layer로 옮기고 thread executor 또는 async-friendly wrapper를 검토한다.
2. timeout/cache 정책을 명시한다.
3. market route를 `backend/app/api/market.py`로 분리하는 작업과 묶어도 좋다.

### D9. 저장 리포트 조회 ticker matching이 다른 시장 API보다 엄격하다

근거:

- `backend/app/main.py:482`에서 `Asset.ticker == ticker`로 조회한다.
- `/api/market/history/{ticker}`는 `asset_ticker = ...upper()`로 일부 normalization을 한다.

영향:

- URL에서 소문자나 alias가 들어오면 저장 리포트가 있는데도 404가 날 수 있다.
- scheduler target alias 정책과 사용자 입력 경로가 어긋날 수 있다.

권장 후속 작업:

1. report 조회에도 ticker normalization/alias helper를 공유한다.
2. `BTC`, `bitcoin`, `005930` 같은 alias 정책을 frontend/backend에서 일관화한다.
3. `test_report_access_api.py`에 normalization regression을 추가한다.

### D10. 프론트 번들이 이미 경고 임계값을 넘는다

근거:

- `npm.cmd run build` 결과 `dist/assets/index-*.js`가 `853.90 kB`, gzip `262.05 kB`.
- Vite가 500 kB 초과 chunk 경고를 출력했다.
- `frontend/src/App.jsx`는 route-level lazy loading을 사용하지 않는다.

영향:

- 초기 로딩 비용이 커질 수 있다.
- `recharts`, `react-markdown`, chatbot/report 관련 UI가 첫 화면에 모두 묶일 가능성이 있다.

권장 후속 작업:

1. route-level `React.lazy`/dynamic import를 검토한다.
2. `AssetDetail`, `MarketSnapshot`, chatbot panel처럼 무거운 route/component부터 분리한다.
3. 분리 후 build chunk와 첫 화면 smoke를 비교한다.

### D11. 미사용 `NotificationsSettings.jsx`가 남아 있다

근거:

- `frontend/src/pages/NotificationsSettings.jsx:21`에 독립 설정 화면이 있다.
- `frontend/src/App.jsx:85`는 `/settings/notifications`를 `<MyPage />`로 연결한다.
- 기능 문서에는 현재 `/settings/notifications`가 MyPage alias라고 적혀 있다.

영향:

- 후속 하네스가 죽은 화면을 실제 route로 착각해 수정할 수 있다.
- 알림 채널 verification 전용 UI가 필요한지, MyPage 통합이 최종인지 소유권이 흐려진다.

권장 후속 작업:

1. MyPage 통합이 최종이면 `NotificationsSettings.jsx`를 제거하거나 문서에 deprecated file로 명시한다.
2. 전용 화면을 되살릴 계획이면 `App.jsx` route와 feature doc을 맞춘다.
3. 알림 운영화 작업 전에는 반드시 `docs/harness/features/favorite-asset-notifications.md`와 `docs/harness/features/mypage-profile.md`를 함께 확인한다.

### D12. Python 3.13 기준 deprecation warning이 많다

근거:

- 백엔드 테스트 재실행에서 `datetime.datetime.utcnow()` deprecation warning이 90개 이상 출력됐다.
- 주요 위치:
  - `backend/app/services/payment_service.py`
  - `backend/app/services/notification_service.py`
  - `backend/app/services/subscription_service.py`
  - 일부 backend tests

영향:

- 당장은 테스트 실패는 아니지만 Python 3.13+ 기준 노이즈가 많아 실제 warning을 놓치기 쉽다.
- timezone naive datetime이 billing period, notification cooldown, report metadata에서 장기 운영 혼선을 만들 수 있다.

권장 후속 작업:

1. UTC helper를 한 곳에 두고 `datetime.now(datetime.UTC)` 또는 저장 정책에 맞는 timezone-aware datetime으로 전환한다.
2. DB column과 Pydantic response의 timezone 정책을 먼저 정한다.
3. billing/notification/report 영역별 focused test로 회귀를 막는다.

## 이미 개선된 것으로 확인된 항목

- 프론트 페이지 단위 `http://localhost:8000` 직접 호출은 현재 `frontend/src/utils/apiClient.js` 기본값 외에는 발견되지 않았다.
- `.env_example`은 현재 `backend/app/core/config.py`의 주요 runtime/payment/notification 변수명을 대부분 반영한다.
- favorite/account sync 관련 문서는 현재 MyPage 통합 흐름을 반영한다.
- production payment provider가 없는 상태는 기능 문서에 명확히 "provider-unavailable/mock boundary"로 기록되어 있다.

## 후속 작업 추천 순서

1. D1 테스트/정책 불일치 수정.
2. D2, D3, D4 운영 startup/config validation 보강.
3. D6 신고 사유 UX/API 계약 결정.
4. D7, D8, D9 market/report ticker API 계약 정리.
5. D5 AssetDetail 책임 분리.
6. D10 route-level code splitting.
7. D11 알림 설정 화면 소유권 정리.
8. D12 datetime timezone 정리.

## 이번 감사에서 실행한 명령

```powershell
git status --short
Get-Content -Path ARCHITECTURE.md
Get-Content -Path PROJECT_STRUCTURE_ANALYSIS.md
Get-Content -Path DEVELOPMENT_DIRECTION.md
Get-Content -Path docs\harness\feature-index.md
Get-Content -Path docs\harness\project-gap-remediation-plan-2026-06-02.md
rg -n "localhost:8000|127\.0\.0\.1:8000|VITE_API_BASE_URL|API_BASE_URL" frontend\src
rg -n "include_router|@app\.|APIRouter|ENABLE_DB_SCHEMA_BOOTSTRAP|ENABLE_SCHEDULER|ENABLE_NOTIFICATION_SCHEDULER|/api/ai/generate|/api/reports" backend\app
npm.cmd run lint
npm.cmd run build
python -m pytest tests
python -m pip show aiosqlite
python -m pip install aiosqlite
python -m pytest tests
```

## 명령 실행 참고

- Windows PowerShell에서는 `npm run ...`이 `npm.ps1` execution policy로 막힐 수 있다. 하네스는 `npm.cmd run lint`, `npm.cmd run build`를 우선 사용한다.
- 백엔드 테스트는 repository root가 아니라 `backend/`를 작업 디렉터리로 두고 실행해야 `app` import가 정상 동작한다.
- 이번 감사 중 테스트 캐시 임시 디렉터리 `pytest-cache-files-*`가 생성되어 정리했다.

## 남은 위험

- 이 보고서는 live DB, live provider, live LLM 호출을 수행하지 않았다.
- scheduler coverage 확대, payment provider 연동, notification provider 운영 발송은 비용과 외부 계정 설정이 필요하므로 별도 승인 후 진행해야 한다.
- `.env` 파일은 열람하지 않았고 secret 값은 기록하지 않았다.
