# AI 리포트 생성 환경변수 분리 구현

날짜: 2026-06-03

## 목적

`ENABLE_SCHEDULER`와 별도로 AI 리포트 생성만 끌 수 있는 `ENABLE_AI_REPORT_GENERATION` 운영 스위치를 구현했다. 가격/뉴스 scheduler를 검증하거나 운영하면서도 LLM 기반 리포트 생성 비용을 별도로 차단할 수 있게 하는 것이 목표다.

사용자 화면 요청과 챗봇 요청은 계속 저장된 scheduled report만 읽는다. 이 변경은 `POST /api/ai/generate/{ticker}`를 다시 여는 작업이 아니다.

## 변경 파일

- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/app/services/ai_service.py`
- `backend/tests/test_database_config.py`
- `backend/tests/test_ai_report_quality_gate.py`
- `backend/tests/test_ai_report_generation_switch.py`
- `.env_example`
- `ENVIRONMENT_VARIABLE_SETUP.md`
- `docs/harness/feature-index.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/chatbot-assistant.md`
- `docs/harness/features/deployment-runtime.md`

## 동작 변경

- `backend/app/core/config.py`에 `ENABLE_AI_REPORT_GENERATION: bool = True`를 추가했다.
- `DB_PREPARED_STATEMENT_CACHE_SIZE`는 `.env`에서 빈 문자열로 들어와도 `None`으로 처리하도록 보강했다. `.env_example`에서 빈 값을 안내하고 있어 설정 로드와 문서가 일치해야 하기 때문이다.
- `ENABLE_SCHEDULER=true`, `ENABLE_AI_REPORT_GENERATION=false`이면 `update_prices_task`, `update_news_task`는 scheduler에 등록되지만 `generate_daily_reports`, `generate_daily_reports_startup`은 등록되지 않는다.
- `generate_daily_reports()`는 `ENABLE_AI_REPORT_GENERATION=false`일 때 DB 세션을 열기 전에 즉시 return한다.
- `generate_report_for_ticker()`는 `ENABLE_AI_REPORT_GENERATION=false`일 때 DB/provider/LLM workflow를 호출하기 전에 `RuntimeError`로 차단한다.
- `GET /api/reports/{ticker}` 저장 리포트 조회와 챗봇의 저장 리포트 요약 정책은 변경하지 않았다.
- `POST /api/ai/generate/{ticker}`는 계속 일반 사용자에게 HTTP 403을 반환한다.

## 환경변수 문서

- `.env_example`에 `ENABLE_AI_REPORT_GENERATION=true` 기본 예시를 추가했다.
- hosted smoke preset에는 `ENABLE_AI_REPORT_GENERATION=false`를 추가했다.
- `ENVIRONMENT_VARIABLE_SETUP.md`에 다음 운영 조합을 문서화했다.
  - `ENABLE_SCHEDULER=false`: 전체 scheduler 미실행.
  - `ENABLE_SCHEDULER=true`, `ENABLE_AI_REPORT_GENERATION=false`: 가격/뉴스 scheduler는 검증 가능, AI 리포트 생성은 미실행.
  - `ENABLE_SCHEDULER=true`, `ENABLE_AI_REPORT_GENERATION=true`: 예약 AI 리포트 생성 실행.

## 테스트

- `backend/tests/test_database_config.py`: 새 설정의 기본값이 `True`인지 확인하고, 빈 optional int 설정값이 `None`으로 처리되는지 검증.
- `backend/tests/test_ai_report_generation_switch.py`: 스위치가 꺼졌을 때 report scheduler job 미등록, `generate_daily_reports()`의 조기 return, `generate_report_for_ticker()`의 서비스 차단을 검증.
- `backend/tests/test_ai_report_quality_gate.py`: 로컬 `.env`의 스위치 값과 무관하게 기존 report-quality 테스트는 명시적으로 생성 허용 상태에서 실행되도록 보정.

## 검증

아래 명령으로 확인했다.

```powershell
cd backend
.\.venv\Scripts\python.exe -m compileall app
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_database_config.py tests/test_ai_report_generation_switch.py tests/test_ai_report_quality_gate.py
```

결과: `compileall` 통과, pytest `32 passed`.

## 후속 위험

- 기본값은 `true`라서 운영 또는 hosted smoke 환경에서는 명시적으로 `ENABLE_AI_REPORT_GENERATION=false`를 넣어야 비용성 리포트 생성을 막을 수 있다.
- `generate_report_for_ticker()`도 차단하므로 향후 관리자 전용 수동 생성 기능을 만들더라도 이 환경변수가 false이면 생성이 막힌다. 관리자 생성이 필요하면 별도 권한 설계와 비용 승인 후 값을 켜야 한다.
- `ENABLE_AI_REPORT_GENERATION=false` 상태에서는 저장된 기존 리포트만 제공된다. 신규 ticker 또는 오래된 리포트는 스위치를 다시 켤 때까지 갱신되지 않는다.
