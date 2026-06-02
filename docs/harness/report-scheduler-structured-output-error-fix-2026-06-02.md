# 리포트 스케줄러 구조화 출력 오류 수정 기록

Date: 2026-06-02

## Objective

backend startup scheduler가 AI 리포트를 생성할 때 OpenAI structured output schema 오류로 실패하고, 실패 로깅 중 SQLAlchemy `MissingGreenlet` 2차 오류가 발생하던 문제를 수정한다.

## Files Changed

- `backend/app/services/graph/nodes.py`
- `backend/app/services/ai_service.py`
- `backend/tests/test_ai_report_quality_gate.py`
- `docs/harness/report-scheduler-structured-output-error-fix-2026-06-02.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/market-data.md`
- `docs/harness/feature-index.md`

## Behavior Changes

- `StructuredFacts`와 `EvaluationResult`의 LangChain structured output 호출을 `method="function_calling"`으로 고정했다.
- `StructuredFacts`는 `dict[str, Any]`, `list[dict[str, Any] | str]`처럼 유연한 필드를 포함하므로 OpenAI strict JSON schema response format으로 보내면 `additionalProperties` 제약 오류가 날 수 있다.
- scheduled report loop가 `rollback()` 이후 ORM `Asset` 객체 속성을 다시 읽지 않도록, loop 시작 전에 `asset_id`와 `ticker`를 plain dict로 복사해 사용한다.
- 사용자-facing 요청은 여전히 리포트 생성을 직접 트리거하지 않는다. 생성은 backend scheduler 경로에만 남아 있다.

## Verification Performed

- `backend/tests/test_ai_report_quality_gate.py`에 외부 API/LLM을 호출하지 않는 단위 테스트를 추가했다.
  - flexible structured output helper가 `method="function_calling"`을 넘기는지 확인.
  - scheduled report job 값이 ORM 객체에서 plain dict로 분리되는지 확인.
- 기존 수동 리포트 생성 정책 테스트가 현재 구현의 HTTP 403 정책을 검증하도록 기대값을 정리했다.
- `cd backend; .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\test_ai_report_quality_gate.py`
  - Result: `23 passed`
- `.\backend\.venv\Scripts\python.exe -m compileall backend\app`
  - Result: success

## Commands Not Run

- `npm run build`: backend-only 수정이라 실행하지 않았다.
- 실제 scheduler smoke: OpenAI API 비용과 외부 provider 의존성이 있어 자동 검증으로 실행하지 않았다.

## Follow-up Risks

- 이 수정은 OpenAI schema 400과 실패 로깅 중 `MissingGreenlet`을 막는 좁은 수정이다.
- 실제 scheduled report 생성은 여전히 OpenAI API, 외부 시장/뉴스 provider, DB 상태, rate limit에 영향을 받는다.
- 비용이 발생할 수 있으므로 일반 검증에서는 `ENABLE_SCHEDULER=false`를 유지하고, 실제 생성 smoke는 명시적으로 수행해야 한다.

## Feature Links

- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/market-data.md`
