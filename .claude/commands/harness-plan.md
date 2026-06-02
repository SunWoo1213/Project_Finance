---
description: 하네스 작업 계획 문서를 docs/harness/에 작성 (plan 단계)
argument-hint: <작업 설명>
allowed-tools: Read, Glob, Grep, Write, Bash(git status:*), Bash(git diff:*)
---

요청 작업: **$ARGUMENTS**

당신은 `Project_Finance`의 하네스 엔지니어다. 코드를 수정하기 **전에** 계획만 세운다. 아직 구현하지 마라.

## 1. 필수 읽기 순서 (docs/harness/feature-documentation-guide.md 기준)
다음을 순서대로 읽고 작업과 관련된 부분을 파악한다.
1. `AGENTS.md`
2. 루트 `DEVELOPMENT_DIRECTION.md`
3. 작업이 닿는 각 폴더의 가장 가까운 `DEVELOPMENT_DIRECTION.md`
4. `docs/harness/feature-index.md` — 대상 기능 문서를 찾는다
5. 해당 `docs/harness/features/*.md`
6. 거기에 연결된 `docs/harness/` 변경 기록
그 다음 ownership map에 적힌 실제 코드 경로를 읽어 현재 구현을 확인한다. 코드와 문서가 충돌하면 **코드가 기준**이다.

## 2. `git status --short`로 기존 사용자 변경을 확인한다. `.env`나 시크릿은 읽지 않는다.

## 3. 계획 문서 작성
`docs/harness/<작업-slug>-plan-2026-06-02.md`에 한국어로 작성한다. 날짜는 오늘(2026-06-02). 다음을 포함한다:
- **목적(Objective)**
- **현재 동작 / 목표 동작**
- **변경 대상 파일** (frontend / backend / DB / 설정 구분)
- **단계별 구현 계획**
- **위험과 Risky Change 여부** (AGENTS.md 섹션 9 — DB 스키마, 인증, 스케줄러/리포트 비용, 파일 삭제 등은 사용자 확인 필요)
- **검증 계획** (변경에 맞는 최소 명령; AGENTS.md 섹션 6)
- **갱신할 문서**: 어떤 feature 문서와 `feature-index.md` 항목을 고칠지

## 4. 마지막에 계획 요약과 위험을 한국어로 보고하고, Risky Change가 있으면 사용자 승인을 먼저 요청한다.
