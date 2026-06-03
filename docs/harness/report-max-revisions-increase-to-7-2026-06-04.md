# 리포트 재작성(revision) 한도 3 → 7 상향

Date: 2026-06-04
Type: 구현 기록
Feature:
- `docs/harness/features/asset-detail-ai-community.md`
관련:
- `docs/harness/nvda-factchecker-loop-404-remediation-implementation-2026-06-04.md` (루프 소진 후 숫자 정제 폴백)

## 목적

품질 게이트(포맷/숫자/정성/평가) 실패 시 writer가 재작성할 수 있는 최대 횟수를 3회 → **7회**로 늘려, 첫 몇 초안에서 미지원 숫자/포맷 문제가 있던 리포트도 더 많은 재작성 기회를 통해 통과할 수 있게 한다(사용자 요청).

## 현재 동작 / 목표 동작

- 현재: `graph.py`의 4개 라우팅 함수(`route_fact_check`, `route_qualitative_check`, `route_format_check`, `route_evaluation`)가 `revision_count >= 3`에서 그래프를 `END`로 보냈다. 즉 최대 3회 재작성 후 미통과 시 종료.
- 목표: 한도를 설정값 `REPORT_MAX_REVISIONS`(기본 7)로 두고, 4개 함수가 이를 참조한다. 도달 시 `END`로 빠지는 동작은 동일하며, 이후 `ai_service`의 숫자 정제 폴백 저장이 그대로 이어진다.

## 변경 파일

### Backend
- `backend/app/core/config.py`
  - `REPORT_MAX_REVISIONS: int = 7` 추가(주석: 값이 클수록 통과율↑·실패 리포트당 LLM 호출↑·비용↑).
- `backend/app/services/graph/graph.py`
  - `from ...core.config import settings` import 추가.
  - 4개 라우팅 함수의 `revision_count >= 3` → `revision_count >= settings.REPORT_MAX_REVISIONS`.

### Tests
- `backend/tests/test_ai_report_quality_gate.py`
  - `from app.core.config import settings` import 추가.
  - 한도를 하드코딩(3)하던 `test_fact_checker_routes_to_end_after_revision_limit`·`test_report_format_validator_routes_to_end_after_revision_limit`를 `settings.REPORT_MAX_REVISIONS` 기준으로 정정.
  - 신규: `test_report_max_revisions_default_is_seven`(기본값 7 고정), `test_fact_checker_keeps_routing_to_writer_below_revision_limit`(한도 미만에서 writer로 계속 재작성 확인).

## 동작 변화

- 품질 게이트 실패 리포트는 이제 최대 **7회**까지 재작성된다(기존 3회). 한도 도달 시 동작(END → 숫자 정제 폴백 저장 시도)은 변경 없음.
- `REPORT_MAX_REVISIONS` 환경변수로 운영 중 조정 가능.

## 위험 (AGENTS.md 섹션 9 — 사용자 요청으로 승인됨)

- **비용 증가**: 게이트를 계속 실패하는 리포트는 writer LLM 호출이 자산당 최대 3회 → 7회로 늘 수 있다. 통과하면 추가 호출은 발생하지 않으므로, 정상 통과 리포트의 비용은 불변이다. 늘어나는 것은 "반복 실패 케이스"의 호출량뿐이다.
- 스케줄러 주기·커버리지·쿨다운·트리거 정책은 **불변**. 사용자/챗봇 요청이 실시간 생성을 트리거하지 않는 정책도 그대로(섹션 14).
- DB 스키마·인증 변경 없음.

## 검증 결과

```powershell
cd backend
.\.venv\Scripts\python.exe -m compileall app                 # COMPILE_OK
.\.venv\Scripts\python.exe -m pytest tests\test_ai_report_quality_gate.py   # 33 passed
.\.venv\Scripts\python.exe -c "from app.services.graph.graph import app; import app.main; from app.core.config import settings; print(settings.REPORT_MAX_REVISIONS)"   # 7
```

- 실제 LLM/네트워크 호출 없음. 프론트엔드 변경 없어 `npm` 명령 미실행.

## 후속 위험

- 한도 상향은 통과율을 올리지만, writer가 같은 환각을 반복하면 7회까지 모두 소모한 뒤에야 폴백으로 넘어가 지연이 늘 수 있다. 반복 실패가 잦으면 한도보다 데이터 커버리지/프롬프트 개선이 정공법이다.
