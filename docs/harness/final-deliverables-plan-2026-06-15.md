# 최종 산출물 작성 계획

- 날짜: 2026-06-15
- 작성자: Claude Code 하네스 (plan 단계)
- 작업 slug: `final-deliverables`

## 1. 목적 (Objective)

캡스톤 최종 제출용 **필수 산출물 7종**을 저장소 루트에 새 폴더를 만들어 한국어 문서로 작성한다. 산출물은 현재 실제 구현된 코드(`backend/`, `frontend/`)와 기존 문서(`PROJECT_FUNCTION_DETAIL_SPEC.md`, `docs/harness/features/*`, `DEVELOPMENT_DIRECTION.md`)를 단일 진실 소스로 삼아 도출한다. 문서와 코드가 충돌하면 **현재 코드를 기준**으로 한다(AGENTS.md 섹션 1·13).

필수 산출물 7종:
1. Flow Chart / 시스템 흐름도
2. Story 보드(Storyboard)
3. 기능상세 명세서
4. ERD (Entity Relationship Diagram)
5. API 명세서
6. 개발 환경
7. 방학 목표

## 2. 현재 동작 / 목표 동작

- 현재 동작: 산출물에 해당하는 정보가 코드와 `docs/harness/` 곳곳에 흩어져 있고, 제출용으로 정리된 단일 폴더가 없다. `ARCHITECTURE.md`에는 실제 구현과 다른 Next.js/TypeScript 청사진이 섞여 있어 그대로 쓰면 오해를 부른다.
- 목표 동작: 루트의 `최종산출물/` 폴더에 7개 산출물 문서가 모여, 평가자가 실제 구현 기준으로 시스템 흐름·화면 흐름·기능·데이터 모델·API·개발 환경·방학 목표를 한눈에 확인할 수 있다.

## 3. 변경 대상 파일

이 작업은 **신규 문서 생성만** 수행하며 기존 소스 코드/DB/설정은 수정하지 않는다.

### 신규 생성 (루트 `최종산출물/` 폴더)
- `최종산출물/README.md` — 산출물 색인 및 작성 기준(코드=진실 소스) 안내
- `최종산출물/01-시스템-흐름도.md` — Flow Chart / 시스템 흐름도 (Mermaid)
- `최종산출물/02-스토리보드.md` — 주요 화면별 Story 보드
- `최종산출물/03-기능상세-명세서.md` — 기능상세 명세서
- `최종산출물/04-ERD.md` — ERD (Mermaid erDiagram)
- `최종산출물/05-API-명세서.md` — REST API 엔드포인트 명세
- `최종산출물/06-개발-환경.md` — 개발 환경 / 기술 스택 / 실행 방법
- `최종산출물/07-방학-목표.md` — 방학 기간 개발 목표

> 폴더명은 한글 `최종산출물/`을 기본으로 한다. 평가 제출 규격상 영문 폴더명(`final-deliverables/`)이 필요하면 1번 질문에서 확정한다.

### 참고(읽기 전용, 수정 안 함)
- 기능상세 명세서 출처: `PROJECT_FUNCTION_DETAIL_SPEC.md`, `docs/harness/features/*.md`
- ERD 출처: `backend/app/models.py`, `backend/alembic/`
- API 명세서 출처: `backend/app/api/auth.py`, `billing.py`, `chat.py`, `community.py`, `favorites.py`, `notifications.py`, `profile.py`, 그리고 `backend/app/main.py`(시장 데이터 라우트), `backend/app/schemas.py`
- 시스템 흐름도/개발 환경 출처: `DEVELOPMENT_DIRECTION.md`, `docker-compose.yml`, `backend/requirements.txt`, `frontend/package.json`, `backend/app/services/`(시장·매크로·AI 리포트·스케줄러)
- 스토리보드 출처: `frontend/src/App.jsx`(라우트), `frontend/src/pages/*.jsx`

## 4. 단계별 구현 계획

1. **소스 정밀 확인**: `backend/app/models.py`(엔티티·관계), `backend/app/main.py` 및 `backend/app/api/*.py`(라우트·메서드·인증), `backend/app/schemas.py`(요청/응답), `frontend/src/App.jsx`(화면 라우트), `docker-compose.yml`·`requirements.txt`·`package.json`(환경)을 읽어 사실을 추출한다.
2. **폴더 생성**: 루트에 `최종산출물/` 생성 후 `README.md` 색인 작성.
3. **시스템 흐름도(01)**: 브라우저 → 프론트(React/Vite) → 백엔드(FastAPI) → 외부 데이터/LLM/스케줄러 → PostgreSQL의 데이터 흐름을 Mermaid `flowchart`로 작성. AI 리포트는 "사용자 요청이 실시간 LLM 호출을 트리거하지 않고 스케줄러가 생성·저장한 리포트를 조회" 원칙을 명시(AGENTS.md 섹션 14).
4. **스토리보드(02)**: 로그인 → 홈/대시보드 → 카테고리 → 자산 상세(AI 리포트/커뮤니티) → 즐겨찾기/알림 설정 → 구독·결제 → 챗봇의 화면 전환을 텍스트 와이어프레임 + 흐름 표로 작성.
5. **기능상세 명세서(03)**: feature-index의 기능 단위(인증, 마이페이지, 구독결제, 시장데이터, 자산상세/AI리포트/커뮤니티, 즐겨찾기, 알림, 챗봇, 배포)별로 입력/처리/출력/권한/예외를 표로 정리.
6. **ERD(04)**: `models.py`의 테이블과 FK 관계를 Mermaid `erDiagram`으로 작성하고 주요 컬럼·제약을 표로 보강.
7. **API 명세서(05)**: 라우터별 `METHOD PATH`, 요청 파라미터/바디, 응답 요약, 인증 필요 여부, 구독 등급 제한을 표로 정리.
8. **개발 환경(06)**: 기술 스택, 버전(가능한 범위), 로컬 실행 명령(AGENTS.md 섹션 6), 외부 연동(Finnhub/CoinGecko/공공데이터/Stooq/FRED/Naver 뉴스/Gmail/Telegram/Toss), 배포(Vercel/Render/Supabase) 정리.
9. **방학 목표(07)**: 현재 진행 상황과 남은 과제(`docs/harness/` 최근 변경 기록 기반)를 토대로 방학 기간 목표를 마일스톤으로 작성. 구체 일정/항목은 사용자 입력이 필요하므로 초안 + 보완 표시.
10. **검증 및 문서 동기화**: Mermaid 문법 점검, 링크 점검 후 보고.

## 5. 위험과 Risky Change 여부

- **Risky Change 아님**: 코드/DB 스키마/인증/스케줄러/결제 동작을 변경하지 않고 신규 문서만 생성한다(AGENTS.md 섹션 9 해당 없음).
- 시크릿 노출 위험: API 명세서·개발 환경 문서에 **실제 키/시크릿/`.env` 값은 절대 기재하지 않고** 변수명만 표기한다(AGENTS.md 섹션 8).
- 정확성 위험: `ARCHITECTURE.md`의 Next.js/TypeScript 서술을 그대로 옮기지 않는다. 반드시 현재 React+Vite / FastAPI 코드 기준으로 작성.
- "방학 목표"는 외부 정보(학사 일정·팀 합의)가 필요한 산출물이라 코드만으로 확정 불가 → 초안 작성 후 사용자 보완 필요.

## 6. 검증 계획 (최소)

문서 전용 작업이므로 빌드/테스트는 불필요하다(AGENTS.md 섹션 6의 "변경에 맞는 최소 검증").
- Mermaid 코드블록 문법 자체 점검(흐름도·ERD).
- 산출물 7종 파일 존재 및 `README.md` 색인 링크 정합 확인.
- API 명세서의 엔드포인트가 실제 `backend/app/api/*.py`·`main.py`와 일치하는지 교차 확인.
- ERD 엔티티가 `backend/app/models.py`와 일치하는지 교차 확인.

## 7. 갱신할 문서

- `docs/harness/feature-index.md`: 본 계획 문서와 후속 구현 기록 링크 추가(Documentation Workflow 목록).
- 구현 단계에서 `docs/harness/final-deliverables-implementation-2026-06-15.md` 변경 기록 생성.
- 신규 기능 코드가 아니므로 `docs/harness/features/*.md` 신규 추가는 하지 않는다(산출물은 기존 기능의 정리 문서).
- 저장소 구조 변경이 아니므로 `CODE_UNDERSTANDING.md`/`DEVELOPMENT_DIRECTION.md` 갱신은 불필요.

## 8. 확정된 결정 사항 (2026-06-15 사용자 확인)

1. 폴더명: 한글 **`최종산출물/`** 로 확정.
2. "방학 목표"(07): **초안 자동 작성**으로 확정. 최근 `docs/harness/` 변경 기록과 미완 과제를 근거로 마일스톤 초안을 작성하고, 실제 날짜/세부 항목은 `[보완 필요]`로 표시해 사용자가 이후 채운다.
