# 리포트 evaluator 환경변수 분리 구현

Date: 2026-06-09

## Objective

무료 market provider 제약으로 최종 LLM `evaluator_node`에서 리포트가 반복 기각되어 저장되지 않는 상황을 완화하기 위해, 최종 evaluator만 켜고 끌 수 있는 backend-only 환경변수 `ENABLE_REPORT_EVALUATOR`를 추가했다.

사용자-facing 상세 페이지, 챗봇, 알림 발송은 새 리포트 생성을 트리거하지 않는 기존 정책을 유지한다. 이 구현은 scheduled/background report generation 내부의 최종 evaluator gate만 제어한다.

## Files Changed

- `backend/app/core/config.py`
  - `ENABLE_REPORT_EVALUATOR: bool = True`를 추가했다.
- `backend/app/services/graph/state.py`
  - graph state에 `evaluator_skipped` flag를 추가했다.
- `backend/app/services/graph/nodes.py`
  - `evaluator_bypass_node()`를 추가했다.
  - evaluator bypass는 `is_pass=true`, `evaluator_skipped=true`, feedback 문구만 남긴다.
- `backend/app/services/graph/graph.py`
  - `route_qualitative_check()`가 `ENABLE_REPORT_EVALUATOR=false`이면 `evaluator_bypass_node`로 분기하도록 변경했다.
  - evaluator bypass node는 바로 `END`로 연결된다.
- `backend/app/services/ai_service.py`
  - generation metadata에 `report_evaluator_enabled`, `evaluator_skipped`를 저장한다.
  - initial state와 readiness blocked metadata에도 evaluator 상태를 포함한다.
- `backend/tests/test_ai_report_quality_gate.py`
  - evaluator enabled 기본 metadata를 검증한다.
  - evaluator disabled 저장 metadata를 검증한다.
  - qualitative route가 evaluator on/off에 따라 분기하는지 검증한다.
  - evaluator disabled 상태에서도 qualitative failure는 writer rewrite로 유지되는지 검증한다.
  - bypass node가 저장 가능 state를 만드는지 검증한다.
- `.env.example`
  - `ENABLE_REPORT_EVALUATOR=true` 예시와 설명을 추가했다.
- `ENVIRONMENT_VARIABLE_SETUP.md`
  - `ENABLE_REPORT_EVALUATOR`의 용도, 기본값, 위험을 문서화했다.
- `docs/harness/features/asset-detail-ai-community.md`
  - report runtime policy 변수 목록과 change record를 갱신했다.
- `docs/harness/features/deployment-runtime.md`
  - backend deployment env 설명과 change record를 갱신했다.
- `docs/harness/feature-index.md`
  - 계획서와 구현 기록을 연결했다.

## Behavior Changes

`ENABLE_REPORT_EVALUATOR=true`:

- 기존처럼 `qualitative_claim_checker_node` 통과 후 `evaluator_node`가 실행된다.
- evaluator가 fail하면 writer로 되돌아가며, revision limit까지 실패하면 저장하지 않는다.

`ENABLE_REPORT_EVALUATOR=false`:

- `report_format_validator_node`, `fact_checker_node`, `qualitative_claim_checker_node`는 그대로 실행된다.
- qualitative check가 통과하면 최종 LLM evaluator를 호출하지 않는다.
- graph result는 `is_pass=true`, `evaluator_skipped=true`가 되어 `AIReport` 저장을 허용한다.
- `metadata_json.report_evaluator_enabled=false`, `metadata_json.evaluator_skipped=true`가 저장된다.
- `quality_status`는 기존 조회/UI 호환성을 위해 `pass`로 유지한다.

## Verification Performed

구현 후 아래 명령을 실행했다.

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_ai_report_quality_gate.py
.\.venv\Scripts\python.exe -m compileall app
```

결과:

- `tests/test_ai_report_quality_gate.py`: 37 passed.
- `compileall app`: 성공.

주의:

- `python -m pytest ...`는 Windows 실행 별칭 문제로 `Python was not found`가 발생해, 프로젝트 가상환경 Python인 `.\.venv\Scripts\python.exe`로 재실행했다.
- pytest는 테스트 통과 후 `.pytest_cache` 쓰기 권한 경고(`WinError 5 Access is denied`)를 출력했다. 테스트 결과는 성공이다.

## Commands Not Run

- 실제 scheduler/LLM/provider smoke: 비용과 외부 provider 호출이 발생할 수 있어 수행하지 않았다.
- frontend build: frontend 코드를 변경하지 않았다.

## Follow-Up Risks

- evaluator를 끄면 최종 LLM 편집장 품질 판정이 생략되어 문체, 논리, 균형감 품질이 낮은 리포트가 저장될 수 있다.
- deterministic gate는 섹션, 숫자, 일부 고위험 주장만 방어하므로 전체 분석 품질을 보장하지 않는다.
- readiness blocked는 evaluator off로 우회되지 않는다. 무료 API의 primary fact 부족은 별도 provider 안정화가 필요하다.
- UI에서 evaluator 통과 리포트와 evaluator skipped 리포트를 구분하려면 `metadata.evaluator_skipped` 표시 작업이 필요하다.

## Linked Feature Docs

- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/deployment-runtime.md`

## AI Report Generation Rule

이 구현은 scheduled/background report generation 내부의 최종 evaluator gate만 제어한다. 사용자-facing 요청, 챗봇 요청, 알림 발송은 새 AI report 생성을 트리거하지 않고 저장된 scheduled report만 읽어야 한다.
