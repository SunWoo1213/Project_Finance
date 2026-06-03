# AI 리포트 생성 환경변수 분리 계획

날짜: 2026-06-03

## 목적

AI 리포트 작성 작업을 `ENABLE_SCHEDULER`와 분리된 환경변수로 켜고 끌 수 있도록 설계한다. 목표는 백엔드의 가격/뉴스/알림 스케줄러는 계속 실행하면서도, 비용이 발생할 수 있는 AI 리포트 생성만 운영 환경별로 명확하게 비활성화할 수 있게 만드는 것이다.

일반 사용자 요청과 챗봇 요청은 계속 저장된 예약 리포트만 읽어야 한다. 이 계획은 사용자 화면이나 챗봇 요청이 새 리포트를 생성하도록 되돌리는 작업이 아니다.

## 제안 설정

- 새 환경변수: `ENABLE_AI_REPORT_GENERATION`
- 타입: boolean
- 권장 기본값: `true`
- 운영 smoke 또는 비용 통제 시 권장값: `false`

`ENABLE_SCHEDULER=false`는 전체 APScheduler 등록을 끈다. `ENABLE_AI_REPORT_GENERATION=false`는 `ENABLE_SCHEDULER=true`여도 AI 리포트 생성 작업만 등록하지 않거나 즉시 건너뛰게 만든다.

권장 조합:

| ENABLE_SCHEDULER | ENABLE_AI_REPORT_GENERATION | 결과 |
| --- | --- | --- |
| `false` | `false` 또는 `true` | 가격/뉴스/알림/리포트 스케줄러 모두 미실행 |
| `true` | `false` | 가격/뉴스 및 별도 알림 스케줄러는 실행 가능, AI 리포트 생성은 미실행 |
| `true` | `true` | 기존처럼 예약 AI 리포트 생성 실행 |

## 현재 구현 맥락

- `backend/app/core/config.py`에는 `ENABLE_SCHEDULER`, `REPORT_SCHEDULER_*`, `ENABLE_LLM_REPORT_CRITICS`가 이미 있다.
- `backend/app/main.py`의 lifespan은 `ENABLE_SCHEDULER=true`일 때 가격 갱신, 뉴스 갱신, AI 리포트 생성 작업, 시작 시 1회 리포트 생성 작업을 같은 스케줄러에 등록한다.
- `backend/app/services/ai_service.py`의 `generate_daily_reports()`는 `REPORT_SCHEDULER_TARGET_TICKERS`, cooldown, max-per-run 정책에 따라 리포트를 생성한다.
- `POST /api/ai/generate/{ticker}`는 현재 일반 사용자에게 `403`을 반환하므로 사용자 요청 기반 수동 생성은 비활성화되어 있다.
- `GET /api/reports/{ticker}`와 챗봇 리포트 응답은 저장된 `AIReport`만 읽어야 한다.

## 구현 계획

1. 설정 추가
   - `backend/app/core/config.py`의 런타임 작업 설정 영역에 `ENABLE_AI_REPORT_GENERATION: bool = True`를 추가한다.
   - `.env_example`과 `ENVIRONMENT_VARIABLE_SETUP.md`에 이 값을 문서화한다.
   - 실제 `.env` 값은 출력하거나 문서에 복사하지 않는다.

2. 스케줄러 등록 분리
   - `backend/app/main.py`에서 `ENABLE_SCHEDULER=true`인 경우에도 주기 리포트 작업과 시작 시 1회 리포트 작업은 `settings.ENABLE_AI_REPORT_GENERATION`이 true일 때만 등록한다.
   - 값이 false일 때는 `"AI report generation scheduler skipped"`처럼 명확한 로그를 남긴다.
   - 스케줄러 시작 로그도 리포트 작업이 등록되었는지에 따라 오해 없이 표시한다.

3. 서비스 수준 방어선 추가
   - `backend/app/services/ai_service.py`의 `generate_daily_reports()` 시작부에서 `ENABLE_AI_REPORT_GENERATION=false`이면 DB 세션이나 LLM/provider 호출 전에 즉시 return한다.
   - 비용 통제를 더 강하게 하려면 `generate_report_for_ticker()`에도 같은 차단 조건을 둔다. 이 경우 향후 관리자 전용 생성도 환경변수 false에서는 차단된다.
   - 차단 조건은 저장된 리포트 읽기에는 영향을 주면 안 된다.

4. API 정책 유지
   - `POST /api/ai/generate/{ticker}`는 계속 일반 사용자에게 `403`을 반환한다.
   - `ENABLE_AI_REPORT_GENERATION=true`가 수동 생성 엔드포인트를 다시 여는 의미가 되지 않도록 문서화한다.
   - 향후 관리자 전용 생성이 필요하면 별도 권한 설계와 비용 승인 절차를 먼저 만든다.

5. 배포 문서 정리
   - 호스팅 백엔드 smoke 단계에서는 `ENABLE_SCHEDULER=true`, `ENABLE_AI_REPORT_GENERATION=false` 조합으로 가격/뉴스 스케줄러만 먼저 검증할 수 있다고 안내한다.
   - 리포트 작업을 켜기 전에 `REPORT_SCHEDULER_TARGET_TICKERS`, `REPORT_SCHEDULER_MAX_REPORTS_PER_RUN`, `REPORT_SCHEDULER_ASSET_COOLDOWN_HOURS`, provider/API key, LLM 비용 한도를 확인하도록 확인 목록에 추가한다.

6. 테스트 계획
   - 설정 파싱 테스트 또는 import 수준 확인으로 `ENABLE_AI_REPORT_GENERATION` 기본값을 확인한다.
   - 스케줄러 등록 테스트: `ENABLE_SCHEDULER=true`, `ENABLE_AI_REPORT_GENERATION=false`일 때 리포트 작업 ID `generate_daily_reports`와 `generate_daily_reports_startup`이 등록되지 않아야 한다.
   - 서비스 테스트: `ENABLE_AI_REPORT_GENERATION=false`일 때 `generate_daily_reports()`가 `ensure_scheduled_report_assets()`나 `generate_report_for_ticker()`를 호출하지 않아야 한다.
   - API 회귀 테스트: `GET /api/reports/{ticker}`는 저장 리포트 읽기만 수행하고, `POST /api/ai/generate/{ticker}`는 계속 일반 사용자에게 `403`이어야 한다.

## 변경 권장 파일

- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/app/services/ai_service.py`
- `.env_example`
- `ENVIRONMENT_VARIABLE_SETUP.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/chatbot-assistant.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/feature-index.md`
- `backend/tests/` 아래의 신규 또는 기존 백엔드 테스트 파일

## 검증 명령

구현 후 최소 검증:

```powershell
cd backend
python -m compileall app
pytest
```

프론트엔드 동작이 바뀌지 않더라도 배포 문서나 환경변수 문서를 함께 수정하면 필요에 따라 다음을 추가로 실행한다.

```powershell
cd frontend
npm run build
```

실제 LLM 리포트 생성은 일반 검증에서 실행하지 않는다. 리포트 스케줄러 동작은 mock 또는 `ENABLE_AI_REPORT_GENERATION=false` 조합으로 skip 여부를 확인한다.

## 후속 위험

- 기본값을 `true`로 두면 기존 로컬 동작은 보존되지만, 호스팅 런타임에서 값을 명시하지 않으면 리포트 작업이 계속 실행될 수 있다. 배포 확인 목록에서 production/smoke 값을 반드시 확인해야 한다.
- `generate_report_for_ticker()`까지 차단하면 미래의 관리자 전용 생성도 환경변수 false에서 막힌다. 이는 비용 통제에는 안전하지만 운영자가 긴급 리포트를 수동 생성하려면 값을 켜야 한다.
- `ENABLE_AI_REPORT_GENERATION=false` 상태에서는 기존 저장 리포트만 제공된다. 신규 ticker 또는 오래된 리포트는 스케줄러를 다시 켤 때까지 갱신되지 않는다.
- 이 계획은 DB schema 변경을 요구하지 않는다.

## 사용자 요청 기반 생성 정책

사용자 화면 요청은 리포트 생성을 트리거하지 않는다. 일반 사용자의 asset detail 리포트 조회와 챗봇 리포트 응답은 저장된 예약 리포트만 읽는다. `ENABLE_AI_REPORT_GENERATION`은 백엔드 예약/백그라운드 생성을 제어하는 운영 스위치이며, 사용자 요청 기반 생성을 허용하는 스위치가 아니다.

## 관련 기능 문서

- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/chatbot-assistant.md`
- `docs/harness/features/deployment-runtime.md`
