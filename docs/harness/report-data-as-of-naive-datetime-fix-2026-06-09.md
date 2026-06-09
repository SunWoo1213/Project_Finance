# AI 리포트 저장 실패 수정 - data_as_of timezone 정규화

Date: 2026-06-09
Status: Implemented
Related analysis:
- `docs/harness/report-not-writing-root-cause-remediation-plan-2026-06-09.md`

Related features:
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/deployment-runtime.md`

## Objective

첨부 로그에서 확인된 `NVDA` 리포트 저장 실패를 수정한다. 리포트 작성과 품질 gate는 통과했지만, `AIReport.data_as_of`에 timezone-aware `datetime`이 들어가면서 PostgreSQL `TIMESTAMP WITHOUT TIME ZONE` 컬럼 insert가 실패했다.

## Root Cause

로그상 리포트는 다음 단계까지 진행됐다.

- `리포트 생성 대상 자산 수: 1`
- `NVDA 리포트 생성 시작`
- `writer_node`, `report_format_validator_node`, `fact_checker_node` 반복 실행
- `NVDA fact_checker 루프 소진 후 숫자 정제 폴백으로 저장`

즉 scheduler 미발화나 provider readiness 문제가 아니었다. 실제 실패는 commit 단계였다.

```text
asyncpg.exceptions.DataError:
invalid input for query argument $11:
datetime.datetime(..., tzinfo=datetime.timezone.utc)
(can't subtract offset-naive and offset-aware datetimes)

INSERT INTO ai_reports (..., data_as_of, ..., created_at)
VALUES (..., $11::TIMESTAMP WITHOUT TIME ZONE, ..., $16::TIMESTAMP WITHOUT TIME ZONE)
```

`backend/app/models.py`와 Alembic baseline은 `ai_reports.data_as_of`를 timezone 없는 `DateTime` / `TIMESTAMP WITHOUT TIME ZONE`으로 정의한다. 반면 `metadata["data_as_of"]`는 `2026-06-09T10:59:32.317389+00:00`처럼 UTC offset이 포함된 ISO 문자열이어서 `_parse_iso_datetime()`가 aware datetime을 반환했다. asyncpg는 같은 insert에서 naive timestamp 컬럼에 aware datetime을 bind하려다 실패했다.

## Changes

- `backend/app/services/ai_service.py`
  - `_parse_iso_datetime()`가 timezone-aware 값을 받으면 UTC로 변환한 뒤 `tzinfo`를 제거한 naive datetime을 반환하도록 변경했다.
  - timezone이 없는 기존 ISO/date 문자열은 기존처럼 naive datetime으로 유지한다.
  - metadata JSON에는 원본 ISO 문자열이 그대로 남으므로 API 응답의 기준 시각 정보는 유지된다.

- `backend/tests/test_ai_report_quality_gate.py`
  - `generate_report_for_ticker()` 저장 테스트에서 `data_as_of`가 timezone 없는 DB 저장용 datetime으로 정규화되는지 검증했다.

## Behavior Change

리포트 생성 결과가 `data_as_of`에 `+00:00` 또는 `Z`가 붙은 timestamp를 포함해도 `AIReport` 저장이 실패하지 않는다. DB 컬럼 타입은 변경하지 않았고, 저장용 ORM 필드만 UTC naive로 정규화한다.

사용자-facing 생성 정책은 바뀌지 않았다.

- 상세 페이지와 챗봇은 저장된 scheduled report만 읽는다.
- `POST /api/ai/generate/{ticker}`는 계속 일반 사용자에게 403을 반환한다.
- ordinary user request는 새 리포트를 생성하지 않는다.

## Verification

실행한 명령:

```powershell
.\backend\.venv\Scripts\python.exe -m compileall backend\app
```

결과: 성공.

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests\test_ai_report_quality_gate.py -q -p no:cacheprovider
```

결과: `37 passed in 1.50s`.

참고: 루트에서 `python -m pytest ...`와 `python -m compileall ...`를 먼저 시도했으나, 이 Windows 환경의 `python` 실행 alias가 Python을 찾지 못해 실패했다. 이후 백엔드 venv Python으로 재실행했다. 루트에서 venv pytest를 실행했을 때는 `app` import path가 잡히지 않아 backend 작업 디렉터리에서 다시 실행했다.

## Follow-up Risks

- 운영 DB에는 코드 재배포 후 다음 scheduler 실행이 필요하다. 실패했던 report row는 commit되지 않았으므로 기존 실패분이 자동으로 남아 있지 않다.
- cooldown은 성공 저장된 리포트 기준으로만 작동한다. 이번 실패는 commit 전 rollback이므로 다음 scheduler run에서 다시 생성을 시도할 수 있다.
- `data_as_of` 외 다른 naive `DateTime` 컬럼에 aware datetime을 넣는 경로가 생기면 같은 유형의 오류가 재발할 수 있다. 리포트 경로에서는 현재 확인된 실패 지점만 좁게 수정했다.
