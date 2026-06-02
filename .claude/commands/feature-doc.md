---
description: docs/harness/features/ 기능 문서를 생성·갱신하고 feature-index에 연결
argument-hint: <기능 영역 이름>
allowed-tools: Read, Glob, Grep, Write, Edit, Bash(git status:*)
---

대상 기능: **$ARGUMENTS**

`docs/harness/feature-documentation-guide.md`의 규칙에 따라 기능 문서를 작성/갱신한다.

## 1. 확인
- `docs/harness/feature-index.md`에서 이 기능 문서가 이미 있는지 확인한다.
- 있으면 그 문서와 ownership map의 코드를 읽고, 현재 구현과 어긋난 부분을 찾는다(코드가 기준).
- 없으면 관련 코드 경로를 탐색해 ownership map을 구성한다.

## 2. 문서 작성 (`docs/harness/features/<기능>.md`)
필수 섹션을 모두 한국어로 채운다(코드 식별자·경로·API 경로는 원문 유지):
- **Current Behavior** — 사용자에게 보이는 동작과 중요한 엣지 케이스
- **Ownership Map** — route/UI/state/service/model/schema/config를 소유하는 파일
- **Data Flow** — frontend→backend→service→cache→DB→external API 흐름
- **Contracts** — API 경로, 요청/응답 기대, 저장 필드, 인증 요구
- **Change Rules** — 향후 에이전트가 지켜야 할 제약
- **Verification** — 이 기능의 최소 검증 명령/체크
- **Change Records** — `docs/harness/` 변경 기록 링크
- **Open Risks** — 알려진 공백, 마이그레이션 필요, 불안정 의존성

시크릿·환경값·토큰·비밀번호는 포함하지 않는다. 변수명만 기록한다.

## 3. 색인·연계 갱신
- `docs/harness/feature-index.md`의 Feature Map에 행을 추가/갱신한다(Read first / Primary frontend files / Primary backend files / Change records).
- 새 폴더 소유권이 생기면 가장 가까운 `DEVELOPMENT_DIRECTION.md`를 갱신한다.
- AI 리포트 관련 기능이면 가이드의 Report Generation Documentation Rule에 따라 `asset-detail-ai-community.md`/`chatbot-assistant.md`/`market-data.md`에 연결한다.

## 4. 무엇을 만들고 어디에 연결했는지 한국어로 보고한다.
