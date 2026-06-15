# 최종 산출물 작성 구현 기록

- 날짜: 2026-06-15
- 작업 slug: `final-deliverables`
- 계획 문서: [final-deliverables-plan-2026-06-15.md](final-deliverables-plan-2026-06-15.md)

## 목적

캡스톤 최종 제출용 필수 산출물 7종(+색인)을 저장소 루트 `최종산출물/` 폴더에 한국어 문서로 작성한다. 모든 산출물은 현재 실제 구현 코드를 단일 진실 소스로 삼았다.

## 변경 파일 (신규 생성, 코드 변경 없음)

- `최종산출물/README.md` — 산출물 색인 및 작성 기준
- `최종산출물/01-시스템-흐름도.md` — Mermaid flowchart (전체 구성/인증/시장데이터/AI리포트/알림)
- `최종산출물/02-스토리보드.md` — 라우트↔화면 매핑, 사용자 여정, 화면 와이어프레임, 권한별 노출
- `최종산출물/03-기능상세-명세서.md` — 기능 단위 입력/처리/출력/권한/예외
- `최종산출물/04-ERD.md` — Mermaid erDiagram + 엔티티 요약
- `최종산출물/05-API-명세서.md` — 라우터별 엔드포인트 표
- `최종산출물/06-개발-환경.md` — 스택/외부연동/실행방법/환경변수(이름만)
- `최종산출물/07-방학-목표.md` — 마일스톤 초안([보완 필요] 표시)

## 도출 근거 (교차 확인한 소스)

- ERD: `backend/app/models.py` (14개 테이블, AssetCategory Enum)
- API: `backend/app/main.py`(시장/리포트/헬스 라우트, 라우터 등록), `backend/app/api/auth.py`·`billing.py`·`chat.py`·`community.py`·`favorites.py`·`notifications.py`·`profile.py`
- 화면/라우트: `frontend/src/App.jsx`, `frontend/src/pages/*.jsx`
- 구독 등급: `backend/app/services/subscription_service.py` (FREE/PLUS/PRO entitlement)
- 환경: `backend/requirements.txt`, `frontend/package.json`, `docker-compose.yml`
- 정책: `DEVELOPMENT_DIRECTION.md`, AGENTS.md 섹션 14(사용자/챗봇 실시간 리포트 생성 금지)

## 동작 변화

- 런타임 동작 변화 없음(문서 전용). 코드/DB/스케줄러/결제 미변경.

## 현재 코드와 기존 스펙의 불일치 반영

- `PROJECT_FUNCTION_DETAIL_SPEC.md`는 이메일/비밀번호 로그인 + `/register` 회원가입을 기술하나, **현재 코드는 Google 로그인 단일 흐름**(`POST /api/auth/google`만 존재). 산출물은 현재 코드 기준으로 작성하고 README/명세서에 차이를 명시했다.

## 검증

- 문서 전용 작업으로 빌드/테스트 불필요(AGENTS.md 섹션 6).
- 수행: API 명세 엔드포인트를 `grep`으로 추출한 실제 라우트와 교차 확인, ERD 엔티티를 `models.py`와 대조, Mermaid 코드블록 문법 점검.
- 미실행: `pytest`, `npm run lint/build` — 코드 변경이 없어 해당 없음.

## 후속 위험 / 보완

- `07-방학-목표.md`는 초안이며 실제 기간·역할·실결제 도입 여부는 사용자 입력 필요(`[보완 필요]`).
- 코드가 추가/변경되면 본 산출물(특히 04 ERD, 05 API)을 동기 갱신해야 한다.

## 영향받은 문서

- `docs/harness/feature-index.md` Documentation Workflow 목록에 본 계획·구현 기록 링크 추가.
