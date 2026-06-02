---
description: AGENTS.md 규칙대로 구현하고 변경 기록·기능 문서·색인을 동기화 (implement 단계)
argument-hint: <작업 설명 또는 계획 문서 경로>
---

요청 작업: **$ARGUMENTS**

당신은 `Project_Finance`의 하네스 엔지니어다. `AGENTS.md`와 `CLAUDE.md` 규칙을 따른다.

## 1. 사전 확인
- `git status --short`로 기존 사용자 변경을 확인하고 되돌리지 않는다.
- 관련 `docs/harness/features/*.md`와 ownership map의 코드를 읽는다. 계획 문서가 있으면 먼저 읽는다.
- `.env`/시크릿은 읽거나 출력하지 않는다.

## 2. 구현 (AGENTS.md 섹션 4·5)
- 요청과 직접 관련된 파일만 수정한다. 대규모 무관 리팩터 금지.
- Backend: 라우트는 `backend/app/api/`, 비즈니스 로직은 `backend/app/services/`, 모델은 `models.py`, 계약은 `schemas.py`, 설정은 `core/`. Async SQLAlchemy 패턴 유지.
- Frontend: 라우트는 `App.jsx`, 화면은 `pages/`, 공유 UI는 `components/`, 상태는 `store/`, 순수 로직은 `utils/`. React+Vite+JS 스타일 유지.
- Risky Change(AGENTS.md 섹션 9)는 사용자 승인 없이 진행하지 않는다.
- 동작이 바뀌면 변경 레이어 가까이에 테스트를 추가/갱신한다(`backend/tests/`).

## 3. 검증
변경에 맞는 최소 검증을 실행한다. 백엔드는 관련 `pytest`, 프론트는 `npm run lint`/`npm run build`. 실행 불가하면 이유를 명시한다.

## 4. 문서 동기화 (반드시)
1. `docs/harness/<작업-slug>-implementation-2026-06-02.md`에 한국어 구현 기록 작성: 날짜·목적·변경 파일·동작 변화·검증 결과·미실행 명령과 이유·후속 위험·영향받은 feature 문서 링크.
2. 해당 `docs/harness/features/*.md`의 본문을 갱신하고 `Change Records`에 이 기록 링크 추가.
3. `docs/harness/feature-index.md` 항목 갱신. 새 기능 영역이면 새 feature 문서 생성 후 색인에 추가(필요하면 `/feature-doc` 사용).
4. 폴더 소유권이 바뀌면 가장 가까운 `DEVELOPMENT_DIRECTION.md` 갱신.
- AI 리포트 스케줄러/쿨다운/수동 생성/챗봇 리포트 관련 변경이면 AGENTS.md 섹션 14에 따라 문서화하고 사용자 요청이 실시간 생성을 유발하는지 명시한다.

문서 작성은 `harness-doc-writer` 서브에이전트에 위임할 수 있다.

## 5. 보고 (AGENTS.md 섹션 11, 한국어)
변경 파일, 실행한 검증과 결과, 실행하지 않은 명령과 이유, 남은 위험을 보고한다. 시크릿은 노출하지 않는다.
