# NVDA fact_checker 루프 404 해결 구현 (부호 정규화 + allowed_numbers 정합 + 숫자 정제 폴백)

Date: 2026-06-04
Type: 구현 기록
Feature:
- `docs/harness/features/asset-detail-ai-community.md`
근거/계획:
- 원인 분석: `docs/harness/nvda-report-factchecker-loop-root-cause-2026-06-04.md`
- 계획: `docs/harness/nvda-factchecker-loop-404-remediation-plan-2026-06-04.md`

## 목적

NVDA 등 데이터 풍부 자산이 `fact_checker_node`에서 반복 탈락 → `revision_count>=3` → `ReportQualityError` → DB 미저장 → `/api/reports/NVDA` 영구 404로 끝나는 문제를 해소한다. 원인 분석에서 확정한 3가지를 모두 구현했다.

## 변경 파일

### `backend/app/services/graph/nodes.py`
- **`_normalize_numeric_token` 부호 비민감화**: `,`/`%`/`+` 제거 후 `abs()`를 적용해 절댓값 키로 정규화. 데이터의 등락률(`change_pct=-3.62`)을 writer가 방향을 단어로 표현("3.62% 하락")해도 크기가 일치하면 통과한다. supported set과 draft 토큰이 같은 헬퍼를 쓰므로 양쪽 모두 절댓값 비교로 일관 적용된다.
- **상수 추가**: `ALLOWED_NUMBERS_LIMIT = 150`(writer 화이트리스트 상한, fact_checker 무제한 허용 집합과 정합되도록 상향), `UNSUPPORTED_NUMBER_PLACEHOLDER = "(수치 미확인)"`.
- **`_fact_number_payload(state)` 헬퍼 추가**: `report_facts/structured_facts/financial_facts/news_facts/macro_facts` 묶음을 한 곳에서 만들어 `_find_unsupported_numbers`·`_describe_supported_numbers`·`sanitize_unsupported_numbers`가 동일 소스를 공유(중복 제거).
- **`_describe_supported_numbers` cap 상향**: 기본 `limit`을 40 → `ALLOWED_NUMBERS_LIMIT(150)`로. writer가 안내받는 토큰이 fact_checker 허용 집합에서 누락되지 않게 정합.
- **`sanitize_unsupported_numbers(draft, state)` 신규(public)**: fact_checker와 동일 허용 집합으로 초안을 1패스 정규식 치환해, 미지원 숫자 토큰만 `UNSUPPORTED_NUMBER_PLACEHOLDER`로 결정적 치환. LLM 재호출 없음.

### `backend/app/services/ai_service.py`
- `graph.nodes`에서 `sanitize_unsupported_numbers`, `_find_unsupported_numbers`, `_missing_report_sections`, `_missing_framework_sections`, `_find_unsupported_qualitative_claims` import.
- **`_attempt_numeric_sanitization_fallback(result)` 신규**: `format_check_pass=True && fact_check_pass=False`인 경우에만 마지막 초안의 미지원 숫자를 정제한 뒤 **포맷·프레임워크·숫자·정성** 게이트를 전부 재검증한다. 모두 통과할 때만 정제본(`is_pass=True`, `fact_check_pass=True`, `qualitative_check_pass=True`, `sanitized_numbers`, feedback 메모)을 반환하고, 하나라도 실패하면 `None`을 돌려 기존 미저장 경로를 유지한다.
- **`generate_report_for_ticker` 실패 분기**: `if not result.get("is_pass")`에서 폴백을 먼저 시도. 성공 시 메타데이터를 재생성하고 `fallback_sanitized=True`·`sanitized_numbers`를 메타데이터에 기록한 뒤 정상 저장, 실패 시 종전대로 `ReportQualityError`.

### `backend/tests/test_ai_report_quality_gate.py`
- `test_fact_checker_is_sign_insensitive_for_change_pct`: `change_pct=-3.62`에서 "3.62% 하락"/"-3.62%" 모두 통과.
- `test_describe_supported_numbers_caps_at_allowed_numbers_limit`: 토큰이 `ALLOWED_NUMBERS_LIMIT(150)`로 cap됨.
- `test_sanitize_unsupported_numbers_replaces_only_unsupported`: 지원 숫자(200, 1.25) 보존·미지원(22) 치환, 정제 후 미지원 0건.
- `test_generate_report_saves_via_numeric_sanitization_fallback`: 루프 소진 결과를 정제→재검증 통과→저장, 본문에서 22 제거·`fallback_sanitized=True`·`quality_status=pass`.
- `test_numeric_sanitization_fallback_skips_when_format_failed`: 포맷 실패는 폴백 대상 아님 → 미저장 유지.

## 동작 변화

- **부호 비민감 numeric 검증**: numeric 게이트는 "데이터에 없는 크기의 숫자"만 차단하고, **증감 방향 오기는 더 이상 numeric 단계에서 잡지 않는다**(방향 검증 책임은 evaluator/qualitative). `3.62%`/`-3.62%` 부호 불일치 오탐 제거.
- **writer 화이트리스트 정합**: 안내 토큰 상한 40 → 150. 데이터 풍부 자산에서 필요한 토큰 누락 위험 감소.
- **루프 소진 폴백 저장**: 포맷은 통과했으나 숫자 게이트만 탈락한 경우, 미지원 숫자를 정성 표현으로 정제하고 **재검증 통과분만** 저장. 저장되는 리포트는 항상 결정적 게이트를 통과한 상태이므로 품질 게이트 정신은 보존된다. 통과 못 하면 종전대로 미저장(404 유지).
- **메타데이터**: 폴백 저장 시 `metadata_json`에 `fallback_sanitized`, `sanitized_numbers` 기록(감사 추적).

## 스케줄러/리포트 정책 (AGENTS.md 섹션 14)

- 스케줄러 주기·쿨다운·커버리지·수동 생성·챗봇 응답 **변경 없음**. 여전히 스케줄러만 생성하고, 사용자/챗봇 요청은 실시간 생성을 트리거하지 않는다.
- 정제 폴백은 LLM 재호출이 없는 결정적 후처리라 **LLM 호출량·비용 증가 없음**.

## 검증 결과

```powershell
cd backend
.\.venv\Scripts\python.exe -m compileall app   # COMPILE_OK
.\.venv\Scripts\python.exe -m pytest tests\test_ai_report_quality_gate.py   # 31 passed
.\.venv\Scripts\python.exe -c "from app.services.graph.graph import app; import app.main; print('import ok')"   # import ok
```

- 실제 LLM 생성/네트워크 호출은 하지 않음(결정적 헬퍼 + mock DB/그래프만 사용).
- `npm run lint`/`build` 미실행 — 프론트엔드 변경 없음.

## 미실행 명령과 이유

- 실제 스케줄러 run / 외부 provider 호출: 비용·API 키 회피, 결정적 단위 테스트로 갈음.
- NVDA 실제 생성 성공은 사후 확인 대상(다음 스케줄러 run 로그 `NVDA 리포트 생성 완료` + `/api/reports/NVDA` 200).

## 후속 위험

- 부호 비민감화로 증감 방향 오기는 numeric 단계가 잡지 않는다. 방향 정확성은 evaluator/qualitative 검증에 의존한다.
- 정제 폴백은 미지원 숫자를 `(수치 미확인)`으로 치환하므로, 문장 가독성이 다소 떨어질 수 있다(예: "P/E는 (수치 미확인)배"). 잦은 폴백은 writer 환각이 여전히 많다는 신호로, 누적 시 writer 프롬프트/데이터 보강이 필요하다.
- `sanitized_numbers`가 비어있지 않은 저장 리포트가 늘면, 근본적으로 fact 데이터 커버리지를 늘리는 것이 정공법이다.
