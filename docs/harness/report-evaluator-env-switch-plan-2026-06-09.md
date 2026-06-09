# 리포트 evaluator 환경변수 분리 계획

Date: 2026-06-09
Status: Plan only - 코드 변경 전 설계 문서

## Objective

무료 market provider 제약으로 구조화 fact가 빈약한 환경에서 writer 초안이 deterministic gate는 통과하지만 최종 LLM `evaluator_node`에서 반복 기각되어 `AIReport`가 저장되지 않는 문제를 완화한다.

새 backend-only 환경변수로 최종 report evaluator를 켜고 끌 수 있게 하되, 사용자-facing 요청과 챗봇 요청이 새 report 생성을 트리거하지 않는 기존 정책은 유지한다. 또한 format validator, numeric fact checker, qualitative claim checker 같은 결정론적 안전 게이트는 기본적으로 계속 유지한다.

## Current Code Findings

1. `backend/app/services/graph/graph.py`는 `writer_node -> report_format_validator_node -> fact_checker_node -> qualitative_claim_checker_node -> evaluator_node` 순서로 최종 루프를 구성한다.
2. `qualitative_claim_checker_node`가 통과하면 현재는 항상 `evaluator_node`로 라우팅된다.
3. `evaluator_node`는 `backend/app/services/graph/nodes.py`에서 `EvaluationResult` 구조화 출력 LLM 호출을 수행하고, `is_pass=false`이면 writer로 되돌린다.
4. `route_evaluation()`은 `is_pass=true` 또는 `revision_count >= settings.REPORT_MAX_REVISIONS`일 때 END로 간다.
5. `backend/app/services/ai_service.py`는 graph 결과의 `is_pass`가 false이면 `ReportQualityError`를 발생시키고 DB에 저장하지 않는다.
6. 현재 `ENABLE_LLM_REPORT_CRITICS`와 `REPORT_CRITIC_MODE`는 metadata에 기록되지만, 실제 `evaluator_node` 실행 여부를 제어하지 않는다.
7. `ENABLE_AI_REPORT_GENERATION`은 전체 scheduler/background report generation 진입을 제어하는 상위 스위치다. 이번 계획은 생성 자체가 아니라 최종 evaluator gate만 제어한다.
8. 사용자 화면과 챗봇은 저장된 scheduled `AIReport`만 읽는다. 이 계획은 사용자-facing 생성 트리거를 추가하지 않는다.

## Design Decision

권장 환경변수:

```dotenv
ENABLE_REPORT_EVALUATOR=true
```

- 기본값은 `true`로 둔다. 기존 strict 품질 정책을 기본 동작으로 유지한다.
- `false`이면 `qualitative_claim_checker_node` 통과 후 LLM evaluator를 호출하지 않고 저장 가능 상태로 종료한다.
- 변수명은 `ENABLE_AI_REPORT_GENERATION`처럼 report runtime policy에 맞춰 backend-only 설정으로 둔다.
- `ENABLE_LLM_REPORT_CRITICS`는 “추가 LLM critic” 의미로 이미 문서화되어 있으므로 재사용하지 않는다.

대안:

- `ENABLE_LLM_REPORT_EVALUATOR`: LLM 성격이 분명하지만 기존 `ENABLE_AI_REPORT_GENERATION`보다 길고, 사용자 요청의 “report evaluator”와 조금 멀다.
- `REPORT_EVALUATOR_MODE=strict|skip`: 향후 모드 확장에는 좋지만 이번 요구는 on/off이므로 bool이 더 단순하다.

## Target Behavior

`ENABLE_REPORT_EVALUATOR=true`:

- 현재와 동일하게 `evaluator_node`가 실행된다.
- evaluator가 fail하면 writer로 돌아가고, revision limit까지 실패하면 `ReportQualityError`로 저장하지 않는다.

`ENABLE_REPORT_EVALUATOR=false`:

- `report_format_validator_node`, `fact_checker_node`, `qualitative_claim_checker_node`는 그대로 실행한다.
- qualitative check가 pass된 경우 `evaluator_node`를 건너뛴다.
- graph state는 다음 값을 갖도록 한다.
  - `is_pass=true`
  - `evaluator_skipped=true`
  - `feedback`에는 `Report evaluator skipped by ENABLE_REPORT_EVALUATOR=false after deterministic gates passed.` 같은 짧은 문구를 추가한다.
- `AIReport.final_content`는 저장된다.
- `metadata_json`에는 아래 값을 남긴다.
  - `report_evaluator_enabled=false`
  - `evaluator_skipped=true`
  - `quality_status="pass"` 유지 또는 `quality_status="pass_evaluator_skipped"` 사용 여부 결정

권장 metadata 정책:

- DB scalar `quality_status`는 기존 UI/조회 호환성을 위해 `"pass"`로 유지한다.
- 상세 구분은 `metadata_json.evaluator_skipped=true`와 `metadata_json.report_evaluator_enabled=false`로 남긴다.
- 추후 UI에 품질 badge를 추가할 때 “최종 편집장 평가 생략” 표시를 할 수 있다.

## Non-Goals

- `ENABLE_AI_REPORT_GENERATION` 의미를 바꾸지 않는다.
- `REPORT_MAX_REVISIONS` 기본값을 바꾸지 않는다.
- report scheduler cadence, target ticker coverage, startup delay를 바꾸지 않는다.
- user-facing manual generation endpoint를 다시 열지 않는다.
- format/numeric/qualitative deterministic gate를 끄지 않는다.
- 무료 provider가 제공하지 않는 숫자나 사실을 임의로 만들어 저장하지 않는다.

## Implementation Plan

### Phase 1. 설정 추가

- `backend/app/core/config.py`
  - `ENABLE_REPORT_EVALUATOR: bool = True`를 report runtime 설정 근처에 추가한다.
- `.env.example`
  - 빠른 목록과 Runtime tasks 섹션에 `ENABLE_REPORT_EVALUATOR=true`를 추가한다.
- `ENVIRONMENT_VARIABLE_SETUP.md`
  - 이 값은 backend-only, non-secret policy switch임을 문서화한다.
  - `false`는 비용/저장률 개선용 우회이며 최종 LLM 품질 판정을 생략한다는 위험을 명시한다.

### Phase 2. Graph 라우팅 변경

권장 구현:

- `backend/app/services/graph/graph.py`
  - `route_qualitative_check()`에서 `qualitative_check_pass`가 true이고 `settings.ENABLE_REPORT_EVALUATOR`가 false이면 `END`로 보낸다.
  - 단순히 END로만 보내면 `is_pass`가 false인 초기 state가 그대로 남을 수 있으므로, graph node 또는 route 전에 state를 업데이트할 방법이 필요하다.

더 안전한 구현:

- `backend/app/services/graph/nodes.py`에 작은 node를 추가한다.
  - 예: `evaluator_bypass_node(state)`.
  - 이 node는 `is_pass=true`, `evaluator_skipped=true`, `feedback` 추가만 수행한다.
- `graph.py`에서 `qualitative_claim_checker_node`의 conditional edge를 아래처럼 나눈다.
  - fail below revision limit → `writer_node`
  - fail at revision limit → END
  - pass + `ENABLE_REPORT_EVALUATOR=true` → `evaluator_node`
  - pass + `ENABLE_REPORT_EVALUATOR=false` → `evaluator_bypass_node` → END

이 방식은 graph state에 명시적으로 bypass 결과를 남기므로 `ai_service.py`가 저장 여부를 판단하기 쉽다.

### Phase 3. Metadata 반영

- `backend/app/services/ai_service.py`
  - `_build_generation_metadata()`에 다음 값을 추가한다.
    - `report_evaluator_enabled: settings.ENABLE_REPORT_EVALUATOR`
    - `evaluator_skipped: bool(result.get("evaluator_skipped"))`
  - `llm_report_critics_enabled`는 기존 의미 그대로 유지한다.
  - `quality_status`는 기존 호환성을 위해 `is_pass=true`이면 `"pass"`로 유지한다.
- `ReportQualityError` 경로는 유지한다.
  - deterministic gate 미통과, readiness blocked, provider unavailable은 여전히 저장하지 않는다.

### Phase 4. Tests

- `backend/tests/test_ai_report_quality_gate.py`
  - `ENABLE_REPORT_EVALUATOR=true`일 때 기존 evaluator routing이 유지되는지 확인한다.
  - `ENABLE_REPORT_EVALUATOR=false`이고 qualitative check가 pass이면 evaluator node를 호출하지 않고 `is_pass=true`, `evaluator_skipped=true`가 되는지 확인한다.
  - format/numeric/qualitative fail은 evaluator off 상태에서도 저장 가능 상태로 바뀌지 않는지 확인한다.
  - `_build_generation_metadata()` 또는 `generate_report_for_ticker()` 결과 metadata에 `report_evaluator_enabled=false`, `evaluator_skipped=true`가 남는지 확인한다.
- 테스트는 실제 LLM 호출 없이 graph route/node 단위 또는 FakeGraph로 작성한다.

### Phase 5. Documentation

- `docs/harness/features/asset-detail-ai-community.md`
  - Optional report runtime policy variables에 `ENABLE_REPORT_EVALUATOR`를 추가한다.
  - evaluator off는 최종 LLM 품질 판정을 생략하지만 deterministic gates는 유지한다는 점을 기록한다.
- `docs/harness/features/deployment-runtime.md`
  - hosted env policy 목록에 `ENABLE_REPORT_EVALUATOR`를 추가한다.
- `docs/harness/feature-index.md`
  - 이 계획서와 향후 구현 기록을 Asset detail/report change records에 연결한다.
- 구현 시 별도 implementation record를 추가한다.

## Verification Plan

구현 후 최소 검증:

```powershell
cd backend
python -m pytest tests/test_ai_report_quality_gate.py
python -m compileall app
```

실제 LLM/provider smoke는 별도 승인 후 target 1개로만 수행한다.

```powershell
# 예시: hosted/runtime에서 env만 켠 뒤 로그 확인
ENABLE_AI_REPORT_GENERATION=true
ENABLE_REPORT_EVALUATOR=false
REPORT_SCHEDULER_MAX_REPORTS_PER_RUN=1
REPORT_SCHEDULER_TARGET_TICKERS=NVDA
```

확인할 로그:

- `graph_node: qualitative_claim_checker_node pass`
- `evaluator_skipped=true` 또는 bypass node 로그
- `report generation completed`
- `GET /api/reports/{ticker}` 200

## Rollout Plan

1. 기본값 `ENABLE_REPORT_EVALUATOR=true`로 배포해 기존 동작을 유지한다.
2. 무료 provider 환경에서 저장률 개선이 필요한 runtime에만 `ENABLE_REPORT_EVALUATOR=false`를 적용한다.
3. `REPORT_SCHEDULER_MAX_REPORTS_PER_RUN=1`과 단일 ticker로 저장 성공을 확인한다.
4. 품질과 사용자 표시를 확인한 뒤 target을 점진 확대한다.
5. 장기적으로는 provider 품질이 개선되면 evaluator를 다시 켜는 것을 권장한다.

## Risks

- evaluator를 끄면 최종 LLM 편집장 품질 판정이 사라져, 문체·논리·균형감이 낮은 리포트가 저장될 수 있다.
- deterministic gate는 숫자/섹션/일부 고위험 주장만 방어하므로, 전체 분석 설득력은 보장하지 않는다.
- `quality_status="pass"`로 저장하면 외부 UI에서는 evaluator 통과 리포트와 구분되지 않을 수 있다. metadata flag를 UI에 노출하는 후속 작업이 필요할 수 있다.
- 무료 API의 데이터 부족 자체는 해결되지 않는다. readiness blocked는 evaluator off로 우회할 수 없다.
- evaluator off는 OpenAI evaluator 호출 비용을 줄일 수 있지만 writer 호출과 provider 호출 비용은 그대로 남는다.

## Commands Run For This Plan

- `git status --short`
- `Get-Content docs/harness/feature-index.md`
- `Get-Content docs/harness/features/asset-detail-ai-community.md`
- `Get-Content docs/harness/features/market-data.md`
- `Get-Content backend/app/core/config.py`
- `rg -n "evaluator|evaluate|quality|ENABLE_LLM_REPORT_CRITICS|REPORT_CRITIC_MODE|quality_status|is_pass|fact_check|format_check|qualitative" backend/app/services backend/app/core backend/tests docs/harness`
- `Get-Content backend/app/services/ai_service.py` relevant section
- `Get-Content backend/app/services/graph/graph.py`
- `Get-Content backend/app/services/graph/nodes.py` evaluator/gate context
- `Get-Content docs/harness/report-generation-pipeline-diagnosis-2026-06-08.md`
- `Get-Content docs/harness/report-backend-generation-remediation-plan-2026-06-08.md`

## Commands Not Run

- `python -m pytest ...`: 계획 수립만 수행했고 코드 구현을 하지 않았다.
- `python -m compileall app`: 계획 수립만 수행했고 코드 구현을 하지 않았다.
- 실제 scheduler/LLM/provider smoke: 비용과 외부 provider 호출이 발생할 수 있어 수행하지 않았다.
- `.env` 확인: secret 보호 규칙에 따라 읽지 않았다.

## AI Report Generation Rule

이 계획은 scheduled/background report generation 내부의 최종 evaluator gate만 제어한다. 사용자-facing 요청, 챗봇 요청, 알림 발송은 새 AI report 생성을 트리거하지 않고 저장된 scheduled report만 읽어야 한다.
