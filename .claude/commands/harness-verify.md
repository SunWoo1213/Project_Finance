---
description: 변경에 맞는 최소 검증을 실행하고 한국어 검증 기록을 남김 (verify 단계)
argument-hint: <검증할 작업/변경 설명>
allowed-tools: Read, Glob, Grep, Write, Bash
---

검증 대상: **$ARGUMENTS**

당신은 `Project_Finance`의 하네스 검증자다. 코드를 새로 바꾸지 말고 **현재 변경을 검증**한다.

## 1. 범위 파악
- `git status --short`와 `git diff`로 변경 범위를 확인한다.
- 관련 `docs/harness/features/*.md`의 `Verification` 섹션을 읽어 그 기능의 최소 검증 방법을 따른다.

## 2. 최소 검증 실행 (AGENTS.md 섹션 6·10)
변경 레이어에 맞는 가장 작은 검증만 실행한다.
- Backend API/service: 관련 `pytest` (전체 스위트가 아니라 해당 테스트). 실제 LLM 호출은 명시 요청이 없으면 피하고 mock/격리 테스트 선호.
- Frontend: `npm run lint`, 가능하면 `npm run build`.
- Cross-stack: 양쪽 검증.
- DB 의존 변경: 먼저 `docker compose up -d db`로 PostgreSQL이 떠 있는지 확인.
- 서비스/의존성/네트워크/시크릿 부재로 실행 불가하면 그 사실을 분명히 보고한다.

## 3. 검증 기록 작성
`docs/harness/<작업-slug>-verification-2026-06-02.md`에 한국어로: 날짜·검증 대상·실행한 명령과 결과(통과/실패)·실행하지 않은 명령과 이유·발견된 문제·후속 위험·관련 feature 문서 링크. 명령 출력의 시크릿은 제외한다.

## 4. 결과를 한국어로 요약 보고한다. 실패가 있으면 출력과 함께 솔직히 보고한다.
