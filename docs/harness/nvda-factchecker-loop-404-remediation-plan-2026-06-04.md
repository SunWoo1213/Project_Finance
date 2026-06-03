# NVDA fact_checker 루프 404 해결 계획 (부호 정규화 + allowed_numbers 정합 + 숫자 정제 폴백)

Date: 2026-06-04
Type: 계획 (plan 단계 — 구현 전)
Feature:
- `docs/harness/features/asset-detail-ai-community.md`
근거(원인 분석):
- `docs/harness/nvda-report-factchecker-loop-root-cause-2026-06-04.md`
관련:
- `docs/harness/report-404-and-secret-log-leak-remediation-plan-2026-06-04.md` (allowed_numbers 화이트리스트 1차 도입)

## Objective

NVDA 등 데이터 풍부 자산이 `fact_checker_node`에서 반복 탈락 → `revision_count>=3` → `ReportQualityError` → DB 미저장 → `/api/reports/NVDA` 영구 404로 끝나는 문제를 해소한다. 원인 분석에서 확정한 3가지를 모두 다룬다.

1. **부호/형식 비대칭 오탐 제거** — `3.62%`(양수)와 `-3.62%`(음수)가 다른 토큰으로 정규화돼, 데이터에 실재하는 등락률을 writer가 다른 부호/표현(예: "3.62% 하락")으로 쓰면 미지원으로 오탐되는 문제.
2. **allowed_numbers cap 정합화** — writer 안내 화이트리스트(상한 40토큰)와 fact_checker 허용 집합(무제한)을 일치시켜, 데이터 풍부 자산에서 필요한 토큰이 cap에 밀려 누락되는 위험 제거.
3. **숫자 정제 폴백 저장** — 루프 소진 시, 마지막 초안에서 **미지원 숫자만 결정적으로 제거/정성 치환** 후 fact_checker를 재실행해 **통과하면 저장**, 통과 못 하면 종전대로 미저장. 품질 게이트 엄격성은 유지하면서 404를 해소.

품질 게이트(fact_checker 판정 로직의 목적)는 약화하지 않는다. (1)은 게이트의 의도("데이터에 없는 크기의 숫자 차단")에 맞춘 매칭 정합화이고, (3)은 통과한 결과만 저장한다.

## 현재 동작 / 목표 동작

### (1) 부호/형식 정규화
- 현재: `_normalize_numeric_token`([nodes.py:164](../../backend/app/services/graph/nodes.py#L164))이 `,`,`%`,`+`만 제거하고 **선행 `-`는 보존**한다. `change_pct`는 `report_facts.price.change_pct`에 그대로 존재([ai_service.py:564-571](../../backend/app/services/ai_service.py#L564-L571))하지만, 부호 표현이 어긋나면 `_find_unsupported_numbers`([nodes.py:207](../../backend/app/services/graph/nodes.py#L207))가 오탐한다.
- 목표: 숫자 검증을 **부호 비민감(절댓값 기준)** 으로 정합화한다. supported set과 draft 토큰 양쪽을 동일 규칙(선행 `-`도 제거한 절댓값 키)으로 비교한다. 등락률 "크기"가 데이터에 있으면 통과시키되, 방향(증감) 오기는 numeric 게이트의 책임 범위가 아님을 문서에 명시(방향 검증은 evaluator/qualitative 영역).

### (2) allowed_numbers cap
- 현재: `_describe_supported_numbers(state, limit=40)`([nodes.py:228](../../backend/app/services/graph/nodes.py#L228))로 writer 화이트리스트가 40토큰 cap. fact_checker `_collect_supported_numbers`는 무제한.
- 목표: writer가 안내받는 토큰 집합이 fact_checker 허용 집합의 **부분집합 누락 없이** 정합되도록 cap을 상향(프롬프트 비대 방지를 위해 합리적 상한, 예: 150)하거나 제거. 절댓값 정규화와 일관되게 원문 토큰을 수집한다.

### (3) 숫자 정제 폴백 저장 (사용자 선택: "숫자 정제 후 깨끗하게 저장")
- 현재: `generate_report_for_ticker`([ai_service.py:825-831](../../backend/app/services/ai_service.py#L825-L831))에서 `result["is_pass"]`가 False면 즉시 `ReportQualityError`. fact_checker 실패가 누적된 마지막 초안은 폐기.
- 목표:
  1. 루프 소진(`is_pass=False`)이고 **실패 사유가 숫자 미지원(`fact_check_pass=False`)인 경우에 한해** 결정적 후처리를 시도한다.
  2. 마지막 `draft_report`에서 `_find_unsupported_numbers`가 지적한 토큰을 **결정적으로 정제**(해당 수치 구절을 정성 표현으로 치환하거나 토큰 제거)한다. LLM 재호출 없음(비용 불변, 결정적).
  3. 정제본을 `_missing_report_sections`(포맷) + `_find_unsupported_numbers`(숫자)로 **재검증**한다.
  4. 재검증 통과 시에만 `final_report`를 정제본으로 교체하고 `quality_status`/메타데이터를 갱신해 정상 저장한다. 통과 못 하면 종전대로 `ReportQualityError`(미저장, 404 유지).
  - 이로써 저장되는 리포트는 항상 숫자 게이트를 통과한 상태이므로 품질 정신은 보존된다.

## 변경 대상 파일

### Backend
- `backend/app/services/graph/nodes.py`
  - `_normalize_numeric_token`: 선행 `-` 제거(절댓값 키) — 또는 비교 함수에서 절댓값 비교로 통일. supported set과 draft 비교 경로 모두 동일 규칙 적용.
  - `_collect_supported_numbers` / `_describe_supported_numbers`: 절댓값 정규화와 일관, `limit` 상향(또는 설정값).
  - (신규) 결정적 정제 헬퍼 예: `_sanitize_unsupported_numbers(draft_report, state) -> str` — 미지원 숫자 토큰이 포함된 구절을 정성 표현으로 치환/제거. nodes.py의 numeric 헬퍼와 같은 모듈에 둬 fact_checker와 규칙을 공유.
- `backend/app/services/ai_service.py`
  - `generate_report_for_ticker`의 `if not result.get("is_pass")` 분기에 폴백 경로 추가: 숫자 정제 → 재검증 → 통과 시 저장 / 실패 시 기존 예외. `_build_generation_metadata` 결과의 `final_report`·`fact_check_pass`·`quality_status`를 정제 결과로 일관 갱신.

### Tests
- `backend/tests/test_ai_report_quality_gate.py`
  - 부호 비대칭 정합: `-3.62`가 supported일 때 draft의 `3.62%`(및 그 역)가 fact_checker를 통과하는 결정적 테스트.
  - allowed_numbers 정합: `_describe_supported_numbers` 토큰이 `_collect_supported_numbers` 허용 집합에 모두 포함(누락 없음).
  - 정제 폴백: 미지원 `22`가 포함된 초안을 `_sanitize_unsupported_numbers`로 정제 후 `_find_unsupported_numbers`가 빈 리스트가 되는지, 그리고 정제 불가 시 미저장 경로가 유지되는지 단위 테스트.
  - 실제 LLM/네트워크 호출 없음(결정적 헬퍼·mock DB만 사용; 기존 `FakeDbSession` 패턴 재사용).

### DB / 설정
- DB 스키마·마이그레이션 변경 **없음**(기존 `AIReport` 컬럼 재사용).
- 신규 환경변수 불필요(정제는 결정적). cap을 설정화한다면 선택적으로 `config.py`에 상수 추가 검토(1차는 코드 상수로 충분).

### Frontend
- 변경 없음. (정제 폴백은 정상 통과 리포트만 저장하므로 `ReportCard.jsx` 계약 불변.)

## 단계별 구현 계획

1. (nodes.py) 절댓값 정규화로 `_normalize_numeric_token`/비교 경로 통일 + 단위 테스트.
2. (nodes.py) `_describe_supported_numbers` cap 상향/정합 + 정합성 테스트.
3. (nodes.py) `_sanitize_unsupported_numbers` 결정적 헬퍼 추가 + 단위 테스트.
4. (ai_service.py) 루프 소진 분기에 정제 → 재검증 → 조건부 저장 폴백 추가.
5. 검증 명령 실행(아래).
6. 구현 기록 작성 + `asset-detail-ai-community.md`(Data Flow 14·16·20 갱신, Change Records 링크) + `feature-index.md` 갱신 + `error-casebook` 사례 보강.

## 위험과 Risky Change 여부 (AGENTS.md 섹션 9)

- **DB 스키마/마이그레이션**: 없음.
- **인증/해시**: 무관.
- **스케줄러 주기·리포트 생성 빈도·트리거 확장**: 없음. 섹션 14 정책 불변(스케줄러만 생성, 조회는 DB 읽기, 사용자/챗봇 트리거 없음). LLM 재호출 추가 없음(정제는 결정적) → 비용 증가 없음.
- **품질 게이트 약화 여부(검토 필요 항목)**:
  - (1) 부호 비민감 매칭은 numeric 게이트의 의도(미존재 크기 차단)에 맞춘 정합화이나, **증감 방향 오기를 numeric 단계에서 더 이상 잡지 않는다**는 의미 변화가 있다. 방향 검증은 evaluator/qualitative 책임으로 명시한다.
  - (3) 폴백 저장은 **재검증 통과분만 저장**하므로 "실패 리포트 저장"이 아니다. Data Flow #20("Failed ... not committed")의 문구를 "정제 후에도 미통과 시 미저장"으로 정밀화한다.
- **파일 삭제/파괴적 작업**: 없음.

→ **사용자 추가 승인이 필요한 Risky Change는 아니다**(폴백 저장 방식은 사용자가 "숫자 정제 후 깨끗하게 저장"으로 이미 선택). 다만 (1)의 방향-검증 책임 이동은 문서로 명시한다.

## 검증 계획 (AGENTS.md 섹션 6 최소 집합)

```powershell
cd backend
py -m compileall app
.\.venv\Scripts\python.exe -m pytest tests\test_ai_report_quality_gate.py
.\.venv\Scripts\python.exe -c "from app.services.graph.graph import app; import app.main; print('import ok')"
```

- 실제 LLM 생성/네트워크 호출 없음(비용·키 회피).
- NVDA 실제 생성 성공은 다음 스케줄러 run 로그(`NVDA 리포트 생성 완료`)와 `/api/reports/NVDA` 200으로 사후 확인.

## 갱신할 문서

- `docs/harness/features/asset-detail-ai-community.md`: Data Flow 14(allowed_numbers 정합)·16(부호 비민감 numeric 검증)·20(정제 폴백 저장 정밀화) 갱신, Change Records에 구현 기록 링크.
- `docs/harness/feature-index.md`: 본 계획·구현 기록 링크 추가.
- `docs/harness/error-casebook-2026-06-03.md`: "fact_checker 부호 비대칭/환각 루프 404" 사례·해결 추가.
- (폴더 ownership 변경 없음 → DEVELOPMENT_DIRECTION 갱신 불필요.)
