# 프로젝트 결점 해결 계획

작성일: 2026-06-02

## 목표

`docs/harness/project-defect-audit-report-2026-06-02.md`에서 확인한 D1-D12 결점을 실제 수정 작업으로 전환하기 위한 실행 순서, 결정 지점, 예상 변경 파일, 검증 기준을 남긴다.

이 문서는 구현 변경이 아니라 후속 구현 계획이다. 실제 수정 시에는 현재 코드와 관련 feature document를 다시 읽고, 변경마다 별도 change record를 작성한다.

## 기준 문서

- `docs/harness/project-defect-audit-report-2026-06-02.md`
- `docs/harness/project-gap-remediation-plan-2026-06-02.md`
- `docs/harness/feature-documentation-guide.md`
- `docs/harness/feature-index.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/chatbot-assistant.md`
- `docs/harness/features/frontend-routing-shell.md`
- `docs/harness/features/favorite-asset-notifications.md`
- `ARCHITECTURE.md`
- `PROJECT_STRUCTURE_ANALYSIS.md`
- `DEVELOPMENT_DIRECTION.md`

## 해결 원칙

- 사용자-facing page load, button click, chatbot message, notification job은 새 AI 리포트 생성을 직접 트리거하지 않는다. 저장된 scheduled report만 읽는다.
- scheduler cadence, scheduler coverage, warm-up, LLM critic, 외부 provider 호출을 늘리는 변경은 비용과 quota 위험이 있으므로 구현 전 승인을 받는다.
- production-like runtime에서는 Alembic migration을 기준으로 두고, `ENABLE_DB_SCHEMA_BOOTSTRAP=false`를 목표 운영 방식으로 유지한다.
- secret 값은 문서화하지 않는다. 변수명, 실패 조건, placeholder 금지 규칙만 기록한다.
- 작은 결점부터 CI 신뢰도를 회복한 뒤, runtime safety와 API 계약을 정리하고, 마지막에 대형 frontend 분해와 warning 정리를 진행한다.

## 우선순위 요약

| Priority | 대상 결점 | 목표 |
| --- | --- | --- |
| P0 | D1 | 백엔드 테스트 실패 1개를 제거해 검증 baseline 회복 |
| P1 | D2, D3, D4 | startup/config/secret failure mode를 운영 안전 기준으로 보강 |
| P2 | D7, D8, D9 | market history와 report ticker 계약을 안정화 |
| P2 | D6 | 댓글 신고 사유 UX와 backend 저장 계약 정합화 |
| P3 | D5, D10, D11 | frontend 유지보수성과 초기 bundle 위험 감소 |
| P4 | D12 | timezone-aware datetime 전환으로 warning과 운영 혼선 축소 |

## Phase 0: 검증 Baseline 회복

### 대상

- D1. 수동 AI 리포트 생성 차단 정책의 테스트/코드 불일치
- 감사 중 확인된 local venv dependency drift와 Windows `npm.ps1` 실행 정책 참고

### 결정 사항

`ensure_report_generation_allowed(user)`의 계약을 먼저 확정한다.

권장안:

1. helper는 인증 완료 후 호출되는 policy gate로 둔다.
2. helper 단위 테스트는 인증된 사용자가 호출해도 항상 `403`을 받는지 검증한다.
3. 미인증 `401`은 endpoint dependency인 `Depends(get_current_user)` 수준의 API test에서 검증한다.

이 접근은 현재 endpoint 구조와 "사용자-facing 수동 생성 비활성화" 정책을 가장 적게 흔든다.

### 예상 변경 파일

- `backend/tests/test_ai_report_quality_gate.py`
- 필요 시 `backend/tests/test_report_access_api.py` 또는 신규 endpoint-level test
- `docs/harness/features/asset-detail-ai-community.md`
- 신규 구현 change record under `docs/harness/`

### 검증

```powershell
cd backend
python -m pytest tests/test_ai_report_quality_gate.py
python -m pytest tests
```

Windows 하네스에서 frontend 검증이 필요한 경우 `npm.cmd run lint`, `npm.cmd run build`를 우선 사용한다.

### 완료 기준

- 백엔드 테스트 전체가 동일 환경에서 통과한다.
- 수동 생성 endpoint는 일반 사용자에게 fresh report generation을 열지 않는다.
- 관련 문서에 `401`은 auth dependency, `403`은 generation policy gate라는 책임 구분이 남는다.

## Phase 1: Runtime Safety와 설정 검증 보강

### 대상

- D2. 런타임 기본값이 외부 호출과 비용성 scheduler를 너무 쉽게 켠다
- D3. DB bootstrap 실패가 startup 실패로 이어지지 않는다
- D4. 운영 secret 검증이 약하다

### 작업

1. `ENVIRONMENT`별 runtime policy를 명확히 한다.
   - local development는 편의 기본값을 일부 허용할 수 있다.
   - staging/production은 scheduler, market warm-up, AI report generation, notification scheduler가 명시 opt-in인지 검증한다.
2. `ENABLE_MARKET_WARMUP`, `ENABLE_SCHEDULER` 기본값과 `.env_example` 안내를 운영 안전 기준으로 재검토한다.
3. startup 즉시 scheduled report job을 실행하는 `run_date=datetime.now()` 경로는 명시 opt-in 조건을 둔다.
4. DB bootstrap 실패 시 환경별 동작을 분리한다.
   - production-like runtime에서는 schema check 실패가 startup failure로 드러나야 한다.
   - local bootstrap 실패도 `/health`만으로 정상처럼 오해되지 않게 warning과 `/db-check` 의미를 문서화한다.
5. `ENVIRONMENT in {"staging", "production"}`에서 placeholder/default `SECRET_KEY` 사용을 거부한다.
6. provider 활성화 조건별 필수 설정을 검증한다.
   - Google login이 활성화된 운영 환경: `GOOGLE_CLIENT_ID`
   - payment webhook 사용: `PAYMENT_WEBHOOK_SECRET`
   - credentialed CORS 운영 환경: 명시 origin 또는 승인된 regex

### 예상 변경 파일

- `backend/app/core/config.py`
- `backend/app/main.py`
- `.env_example`
- `backend/tests/`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/features/market-data.md`
- 신규 구현 change record under `docs/harness/`

### 검증

```powershell
cd backend
python -m pytest tests
```

가능하면 별도 환경변수 조합으로 startup validation unit test를 추가한다. secret 값은 테스트와 문서에 기록하지 않고 placeholder 문자열만 사용한다.

### 완료 기준

- 운영 환경에서 기본 secret이나 불완전한 provider 설정으로 backend가 조용히 뜨지 않는다.
- 첫 hosted smoke 기준은 scheduler/warm-up disabled 상태로 재현 가능하다.
- scheduler coverage나 report cadence는 비용 승인 없이 확대되지 않는다.

## Phase 2: Market/Report API 계약 안정화

### 대상

- D7. 시장 히스토리 API 응답 계약이 일부 경로에서 불안정하다
- D8. async route 안에서 synchronous yfinance 호출이 실행된다
- D9. 저장 리포트 조회 ticker matching이 다른 시장 API보다 엄격하다

### 작업

1. `GET /api/market/history/{ticker}`의 모든 provider path가 동일한 response shape을 반환하게 한다.
   - 권장 shape: `{ ticker, series_type, unit, points, legacy, source_status }`
   - provider empty는 `points: []`, `legacy: []`, `source_status: "empty"`처럼 명시한다.
2. yfinance 호출을 route handler에서 service layer로 옮긴다.
3. yfinance sync I/O는 thread executor 또는 명시 wrapper로 감싸 event loop blocking을 줄인다.
4. market history timeout/cache 정책을 service에 둔다.
5. report fetch와 market route가 공유할 ticker normalization/alias helper를 만든다.
6. `GET /api/reports/{ticker}`가 소문자, canonical ticker, alias 입력을 일관되게 처리하는지 regression test를 추가한다.

### 예상 변경 파일

- `backend/app/main.py`
- `backend/app/services/market_service.py`
- 필요 시 `backend/app/api/market.py`
- `backend/tests/test_market_history_route.py`
- `backend/tests/test_report_access_api.py`
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`
- 신규 구현 change record under `docs/harness/`

### 검증

```powershell
cd backend
python -m pytest tests/test_market_history_route.py tests/test_report_access_api.py
```

Frontend display 영향이 있으면:

```powershell
cd frontend
npm.cmd run lint
npm.cmd run build
```

### 완료 기준

- 새 API 소비자가 배열 또는 object 혼용을 처리할 필요가 없다.
- empty provider response와 unsupported ticker가 구분된다.
- stored report lookup은 market route와 같은 canonical ticker 의미를 쓴다.

## Phase 3: 댓글 신고 사유 계약 결정

### 대상

- D6. 댓글 신고 UI가 사유 선택을 보여주지만 서버에는 사유를 보내지 않는다

### 먼저 필요한 제품 결정

1. 신고 사유를 moderation data로 저장할 것인가?
2. 저장하지 않는다면 사유 선택 UI를 제거하고 단순 신고 confirmation으로 바꿀 것인가?

권장안은 신고 사유 저장이다. 현재 UI가 이미 사유 선택을 제공하고 있으므로, 사용자 기대와 운영 moderation audit trail을 맞추는 편이 낫다.

### 작업

1. `CommentReport`에 reason field를 추가한다.
2. request schema에 reason enum 또는 제한된 문자열을 추가한다.
3. frontend `reportComment(comment.id, reason)` 형태로 선택 사유를 body에 보낸다.
4. 중복 신고, 100회 threshold 자동 삭제 정책과 함께 reason 저장이 깨지지 않는지 테스트한다.
5. 기존 report row migration의 nullable/default 정책을 결정한다.

### 예상 변경 파일

- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/app/api/community.py`
- `backend/alembic/versions/`
- `backend/tests/test_community_api.py` 또는 관련 community tests
- `frontend/src/pages/AssetDetail.jsx`
- `docs/harness/features/asset-detail-ai-community.md`
- 신규 구현 change record under `docs/harness/`

### 검증

```powershell
cd backend
python -m pytest tests
```

```powershell
cd frontend
npm.cmd run lint
npm.cmd run build
```

### 완료 기준

- UI에서 선택한 신고 사유가 backend에 저장된다.
- 저장하지 않기로 결정한 경우에는 선택 UI가 제거되어 사용자 기대와 API 동작이 일치한다.

## Phase 4: Frontend 유지보수성과 Bundle 개선

### 대상

- D5. `AssetDetail.jsx`가 너무 많은 책임을 가진다
- D10. 프론트 번들이 이미 경고 임계값을 넘는다
- D11. 미사용 `NotificationsSettings.jsx`가 남아 있다

### 작업 순서

1. `AssetDetail.jsx`를 behavior-preserving 방식으로 분해한다.
   - `AssetHeader`
   - `AssetMarketSummary`
   - `AssetHistoryPanel`
   - `LatestContextPanel`
   - `ReportAccessPanel`
   - `CommunitySection`
2. 분해 중 API 호출 방식, entitlement gate, report pending state, community write auth behavior를 바꾸지 않는다.
3. route-level `React.lazy`와 dynamic import를 검토한다.
   - 우선 후보: `AssetDetail`, `MarketSnapshot`, chatbot/report-heavy UI
4. bundle 분석은 Vite 기본 경고와 build output size 비교부터 시작한다. 새 분석 dependency 추가는 별도 승인 후 진행한다.
5. `NotificationsSettings.jsx`의 소유권을 결정한다.
   - MyPage 통합이 최종이면 deprecated file로 문서화하거나 제거 계획을 세운다.
   - 전용 화면을 되살릴 계획이면 `App.jsx` route와 feature docs를 맞춘다.

### 예상 변경 파일

- `frontend/src/pages/AssetDetail.jsx`
- 신규 파일 under `frontend/src/components/asset-detail/`
- `frontend/src/App.jsx`
- `frontend/src/pages/NotificationsSettings.jsx`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/frontend-routing-shell.md`
- `docs/harness/features/favorite-asset-notifications.md`
- 신규 구현 change record under `docs/harness/`

### 검증

```powershell
cd frontend
npm.cmd run lint
npm.cmd run build
```

Manual smoke:

- `/detail/005930.KS`
- free user report paywall
- entitled user stored report or pending state
- comment create/edit/delete/like/report
- favorite toggle
- `/market/:ticker`
- `/mypage` and `/settings/notifications` route ownership decision path

### 완료 기준

- `AssetDetail.jsx`의 page orchestration은 남기되 feature UI와 side effect가 작은 컴포넌트로 분리된다.
- build chunk warning이 줄거나, 남는 경우 다음 code-splitting 후보와 수치가 기록된다.
- 죽은 알림 설정 화면인지 alias route인지 문서와 route가 일치한다.

## Phase 5: Timezone-aware datetime 정리

### 대상

- D12. Python 3.13 기준 deprecation warning이 많다

### 작업

1. backend 공통 UTC helper를 둔다.
   - 예: `datetime.now(datetime.UTC)` 기반 helper
2. DB 저장 정책을 먼저 정한다.
   - 기존 column이 timezone-naive라면 persistence boundary에서 naive UTC로 변환할지, timezone-aware로 전환할지 결정한다.
3. warning이 많은 서비스부터 순차 변경한다.
   - `backend/app/services/payment_service.py`
   - `backend/app/services/notification_service.py`
   - `backend/app/services/subscription_service.py`
   - report metadata 관련 경로
4. billing period, notification cooldown, report `generated_at`/`data_as_of` 계약을 regression test로 보호한다.

### 예상 변경 파일

- `backend/app/core/` helper module 또는 기존 utility location
- `backend/app/services/payment_service.py`
- `backend/app/services/notification_service.py`
- `backend/app/services/subscription_service.py`
- `backend/app/services/ai_service.py`
- 관련 backend tests
- 관련 feature docs and 신규 change record

### 검증

```powershell
cd backend
python -m pytest tests
```

가능하면 warning count가 줄었는지 pytest output으로 확인한다.

### 완료 기준

- `datetime.utcnow()` deprecation warning이 주요 runtime/service path에서 제거된다.
- billing, notification, report timestamp 의미가 문서와 테스트에 남는다.

## Phase 6: 최종 검증 Matrix와 문서 정합성

### 작업

1. 각 phase 구현 후 해당 feature doc의 `Change Records`와 `Open Risks`를 갱신한다.
2. `docs/harness/feature-index.md`에 구현 기록을 연결한다.
3. phase별 verification command와 결과를 change record에 남긴다.
4. 다음 전체 검증을 마지막 gate로 둔다.

```powershell
cd backend
python -m pytest tests
```

```powershell
cd frontend
npm.cmd run lint
npm.cmd run build
```

5. DB schema가 바뀐 phase는 별도로 다음을 수행한다.

```powershell
cd backend
python -m alembic upgrade head
```

### 완료 기준

- 감사 보고서 D1-D12가 각각 해결됨, 보류됨, 또는 승인 대기 중 하나로 명확히 분류된다.
- 사용자-facing report/chatbot/notification 경로가 fresh report generation을 트리거하지 않는다는 규칙이 유지된다.
- secret, DB URL, provider token은 어떤 문서에도 남지 않는다.

## 승인 필요 항목

- scheduler/warm-up/report generation 기본값을 더 보수적으로 바꾸는 범위
- startup 즉시 report generation job 제거 또는 opt-in 전환
- 신고 사유 저장을 위한 DB schema 변경
- route-level code splitting 외 새 frontend 분석/test dependency 도입
- notification provider 운영 발송, retry, unsubscribe 정책 변경
- broad report coverage, LLM critic, live LLM smoke처럼 비용이 증가할 수 있는 작업
- production/staging secret validation에서 어떤 provider를 필수로 볼지에 대한 운영 정책

## 이번 계획서 작성에서 수행한 확인

- `git status --short`
- `docs/harness/project-defect-audit-report-2026-06-02.md` 확인
- `docs/harness/project-gap-remediation-plan-2026-06-02.md` 확인
- `docs/harness/feature-documentation-guide.md` 확인
- `docs/harness/feature-index.md` 확인
- `ARCHITECTURE.md` 확인
- `PROJECT_STRUCTURE_ANALYSIS.md` 확인
- `DEVELOPMENT_DIRECTION.md` 확인
- 관련 feature docs 확인:
  - `docs/harness/features/deployment-runtime.md`
  - `docs/harness/features/market-data.md`
  - `docs/harness/features/asset-detail-ai-community.md`
  - `docs/harness/features/chatbot-assistant.md`
  - `docs/harness/features/frontend-routing-shell.md`
  - `docs/harness/features/favorite-asset-notifications.md`

## 실행하지 않은 명령

- `python -m pytest tests`
- `npm.cmd run lint`
- `npm.cmd run build`
- `python -m alembic upgrade head`

이번 작업은 계획 문서와 문서 링크 작성만 목표로 했으므로 runtime 검증 명령은 실행하지 않았다.

## 후속 위험

- 감사 보고서의 결점 중 D2, D3, D4는 운영 정책 선택에 따라 구현 방향이 달라진다.
- D6과 D12는 DB schema 또는 timestamp 저장 의미에 영향을 줄 수 있으므로 migration과 기존 데이터 호환성을 먼저 확인해야 한다.
- D5, D10은 behavior-preserving refactor라도 화면 회귀 가능성이 있어 manual smoke가 필요하다.
- D2의 scheduler 관련 변경은 AI/API 비용을 줄일 수 있지만, 기존 local 개발 편의와 충돌할 수 있다.
