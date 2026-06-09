# 최종 투자리포트 본문만 사용자에게 표시

Date: 2026-06-09
Status: Implemented
Related features:
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/deployment-runtime.md`

## Objective

자산 상세 화면의 AI 리포트 영역에서 내부 품질 metadata, research packet, Bull/Bear 요약, source/fact matrix 정보를 사용자에게 노출하지 않고 최종 투자리포트 본문(`final_content`)만 보여준다.

## Background

저장된 리포트 metadata에는 readiness, source status, missing facts, risk summary, research packet 같은 내부 진단 정보가 포함된다. 일부 provider 실패 문자열에는 외부 요청 URL이 들어갈 수 있고, 그 URL의 query string에 API key가 포함될 수 있다. 따라서 화면에서 숨기는 것만으로는 부족하며, report fetch API 응답에서도 내부 metadata를 사용자-facing payload로 내려주지 않는 쪽이 안전하다.

사용자가 제공한 로그/화면 텍스트에 provider API key가 포함되어 있었으므로 해당 키는 노출된 것으로 보고 provider 콘솔에서 회전해야 한다. 이 문서에는 secret 값을 기록하지 않는다.

## Changes

- `frontend/src/components/ReportCard.jsx`
  - 성공한 저장 리포트 화면에서 `Quality and source metadata`, `Research packet`, `Bull view`, `Bear view` 섹션을 제거했다.
  - 최종 Markdown 본문만 렌더링한다.
  - scheduled pending / unavailable 상태 UI는 유지한다.

- `backend/app/main.py`
  - `report_metadata_payload()`가 내부 진단 metadata를 사용자-facing API 응답에 포함하지 않고 `{}`를 반환하도록 변경했다.
  - `bull_summary`, `bear_summary`, `final_content` 응답 문자열에는 `redact_secrets()`를 적용해 혹시 저장 본문에 provider URL이 섞여도 query secret이 마스킹되도록 했다.
  - 저장 DB의 `metadata_json` 자체는 유지한다. 운영/하네스 진단에는 여전히 DB 내부 metadata를 사용할 수 있지만, 일반 report fetch 응답에서는 노출하지 않는다.

- `backend/tests/test_report_access_api.py`
  - `report_metadata_payload()`가 내부 진단 metadata를 숨기는지 검증하는 테스트를 추가했다.

## Behavior Change

Plus/Pro 사용자가 `/detail/{ticker}`에서 AI 리포트를 볼 때 다음만 표시된다.

- 리포트 제목/완료 배지
- 최종 투자리포트 Markdown 본문

다음은 더 이상 사용자 화면에 표시하지 않는다.

- Quality and source metadata
- Readiness / Format / Numbers / Claims
- Missing facts
- Research packet
- Fact matrix
- Bull view / Bear view 요약 카드
- provider 실패 URL 또는 내부 limitation 문자열

사용자-facing 생성 정책은 변경하지 않았다.

- 상세 페이지와 챗봇은 저장된 scheduled report만 읽는다.
- `POST /api/ai/generate/{ticker}`는 계속 일반 사용자에게 403을 반환한다.
- ordinary user request는 새 리포트를 생성하지 않는다.

## Verification

실행한 명령:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests\test_report_access_api.py -q -p no:cacheprovider
```

결과: `5 passed in 1.08s`.

```powershell
.\backend\.venv\Scripts\python.exe -m compileall backend\app
```

결과: 성공.

```powershell
cd frontend
npm.cmd run lint
```

결과: 성공.

```powershell
cd frontend
npm.cmd run build
```

결과: 성공. Vite가 chunk size warning을 출력했지만 빌드는 완료됐다.

참고: PowerShell에서 `npm run lint`와 `npm run build`는 `npm.ps1` 실행 정책 때문에 실패했다. 동일 명령을 `npm.cmd`로 재실행해 통과했다.

## Follow-up Risks

- 이미 화면/로그/채팅에 노출된 provider key는 코드 수정으로 회수할 수 없다. provider 콘솔에서 키를 회전하고 배포 환경변수를 갱신해야 한다.
- DB 내부 `metadata_json`에는 과거 저장된 provider 실패 문자열이 남아 있을 수 있다. 사용자-facing API에서는 숨기지만, 운영자가 DB를 직접 조회할 때는 secret 포함 여부에 주의해야 한다.
- 관리자용 진단 화면을 나중에 만들 경우, metadata를 보여주기 전에 재귀적 secret redaction을 적용해야 한다.
