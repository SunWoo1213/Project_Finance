# 최종 산출물 (AI Invest / Project Finance)

이 폴더는 캡스톤 최종 제출용 **필수 산출물 7종**을 담는다. 모든 문서는 **현재 실제 구현된 코드**(`backend/`, `frontend/`)를 단일 진실 소스로 삼아 작성했다. 과거 청사진 문서(`ARCHITECTURE.md`의 Next.js/TypeScript 서술 등)와 충돌하면 현재 코드가 기준이다.

- 작성일: 2026-06-15
- 서비스명: AI Invest
- 스택: React + Vite (Frontend) / FastAPI + Async SQLAlchemy + PostgreSQL (Backend) / LangGraph + OpenAI (AI 리포트)

## 산출물 색인

| # | 산출물 | 파일 |
| --- | --- | --- |
| 1 | Flow Chart / 시스템 흐름도 | [01-시스템-흐름도.md](01-시스템-흐름도.md) |
| 2 | Story 보드 | [02-스토리보드.md](02-스토리보드.md) |
| 3 | 기능상세 명세서 | [03-기능상세-명세서.md](03-기능상세-명세서.md) |
| 4 | ERD | [04-ERD.md](04-ERD.md) |
| 5 | API 명세서 | [05-API-명세서.md](05-API-명세서.md) |
| 6 | 개발 환경 | [06-개발-환경.md](06-개발-환경.md) |
| 7 | 방학 목표 | [07-방학-목표.md](07-방학-목표.md) |

## 다이어그램 보기

흐름도(01)와 ERD(04)는 [Mermaid](https://mermaid.js.org/) 문법으로 작성되어 있다. GitHub, VS Code(Markdown Preview Mermaid Support 확장), Typora 등에서 렌더링된다.

## 출처 기준

- 기능/화면: `frontend/src/App.jsx`, `frontend/src/pages/*.jsx`
- 데이터 모델(ERD): `backend/app/models.py`
- API: `backend/app/main.py`, `backend/app/api/*.py`, `backend/app/schemas.py`
- 환경: `backend/requirements.txt`, `frontend/package.json`, `docker-compose.yml`
- 보조 설명: `PROJECT_FUNCTION_DETAIL_SPEC.md`, `docs/harness/features/*.md`, `DEVELOPMENT_DIRECTION.md`

> 참고: `PROJECT_FUNCTION_DETAIL_SPEC.md`는 이메일/비밀번호 로그인·회원가입(`/register`)을 기술하지만, **현재 코드는 Google 로그인 단일 흐름**이다(`backend/app/api/auth.py`는 `POST /api/auth/google`만 제공). 본 산출물은 현재 코드를 기준으로 한다.
