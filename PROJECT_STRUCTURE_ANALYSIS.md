# Project Finance 구조 분석

## 1) 한눈에 보는 구성
이 프로젝트는 **React(Vite) 프론트엔드 + FastAPI 백엔드 + PostgreSQL** 기반의 금융 정보/리포트 서비스입니다.

- 프론트엔드: 시세/차트/리포트/커뮤니티 UI 제공
- 백엔드: 시장 데이터 수집, 캐시 제공, AI 리포트 생성/조회, 인증/커뮤니티 API 제공
- DB: 사용자, 자산, AI 리포트, 댓글/좋아요 저장
- 배포/개발 보조: `docker-compose.yml`로 Postgres 실행

## 2) 루트 디렉터리 구조
```text
Project_Finance/
├─ backend/                    # FastAPI 서버
│  ├─ app/
│  │  ├─ api/                  # 라우터 (auth, community, deps)
│  │  ├─ core/                 # 설정/보안/캐시
│  │  ├─ db/                   # SQLAlchemy Base, Async Session
│  │  ├─ services/             # 시장데이터/매크로/AI/그래프 로직
│  │  ├─ main.py               # 앱 엔트리포인트 + 스케줄러
│  │  ├─ models.py             # ORM 모델
│  │  └─ schemas.py            # Pydantic 스키마
│  ├─ tests/                   # 백엔드 테스트
│  └─ requirements.txt
├─ frontend/                   # React + Vite 클라이언트
│  ├─ src/
│  │  ├─ pages/                # Home, CategoryView, AssetDetail, Login, Register
│  │  ├─ components/           # 공통 UI/차트/헤더/라우트 보호
│  │  ├─ store/                # Zustand 인증 스토어
│  │  ├─ utils/                # 포맷터/상수/검증 스키마
│  │  ├─ App.jsx               # 라우팅 정의
│  │  └─ main.jsx              # 렌더 엔트리
│  └─ package.json
├─ docker-compose.yml          # PostgreSQL 컨테이너 실행
├─ ARCHITECTURE.md             # 고수준 설계 문서
├─ test_api.py, test_db.py     # 루트 단위 테스트 스크립트
└─ *.log                       # 서버 로그 파일
```

## 3) 백엔드 구조 분석

### 3-1. 엔트리포인트: `backend/app/main.py`
- FastAPI 앱 초기화 및 CORS 설정
- 앱 시작(lifespan) 시:
1. DB 테이블 생성 (`Base.metadata.create_all`)
2. 시장 캐시 초기 워밍업 (`update_prices_task`, `update_news_task`)
3. `APScheduler` 주기 작업 등록
  - 가격 캐시 갱신: 5분
  - 뉴스 캐시 갱신: 1시간
  - AI 리포트 생성: 6시간

### 3-2. API 레이어 (`backend/app/api`)
- `auth.py`
  - 회원가입 (`/api/auth/register`)
  - 로그인 (`/api/auth/login`, OAuth2 form)
- `community.py`
  - 댓글 CRUD 및 좋아요 토글
  - 자산 ID/티커 모두 허용하는 자산 해석 로직 포함
- `deps.py`
  - JWT 기반 현재 사용자 의존성 주입

### 3-3. 서비스 레이어 (`backend/app/services`)
- `market_service.py`
  - 자산 그룹별 시세/뉴스 비동기 수집
  - 표준 포맷으로 normalize 후 in-memory 캐시에 저장
- `macro_service.py`
  - 채권/원자재 매크로 데이터 조회
- `ai_service.py` + `services/graph/*`
  - 종목별 AI 리포트 생성 파이프라인
  - Graph 관련 상태/노드/LLM 구성 분리
- `external_api_service.py`
  - 외부 API 연동 추상화 역할

### 3-4. 데이터 레이어
- `models.py`
  - `User`, `Asset`, `AIReport`, `Comment`, `CommentLike`
  - `AssetCategory` enum 기반 자산 분류
- `schemas.py`
  - 인증/자산/댓글 요청·응답 모델 정의
- `db/session.py`
  - Async SQLAlchemy 세션/엔진 관리

## 4) 프론트엔드 구조 분석

### 4-1. 라우팅 및 페이지
- `App.jsx` 라우트
  - `/` 홈
  - `/category/:type` 카테고리 뷰
  - `/detail/:ticker` 자산 상세
  - `/login`, `/register`

### 4-2. 상태 관리
- `store/authStore.js` (Zustand)
  - `token`, `user`를 localStorage와 동기화
  - `login/logout` 액션 제공

### 4-3. 데이터 연동 방식
- `Home.jsx`
  - `/api/market/prices` 호출 후 주요 지수 렌더링
- `AssetDetail.jsx`
  - 가격/히스토리/리포트/댓글 API를 집중 호출
  - 로그인 상태일 때만 리포트 조회/댓글 작성 허용
  - 리포트 미존재(404) 시 생성 API 호출 후 재조회하는 흐름 구현

## 5) 실행 및 인프라 관점

### 5-1. `docker-compose.yml`
- 현재 PostgreSQL 단일 서비스만 정의
- 앱 서버(backend/frontend)는 컨테이너 외부 실행 전제

### 5-2. 설정
- `.env`를 `backend/app/core/config.py`에서 로드
- 주요 키:
  - `DATABASE_URL`
  - `OPENAI_API_KEY`
  - `ALPHA_VANTAGE_API_KEY`, `FRED_API_KEY`, `ECOS_API_KEY`
  - JWT 시크릿/만료 설정

## 6) 요청 흐름 요약
1. 프론트가 백엔드 REST API 호출
2. 백엔드는 캐시 또는 외부 데이터 소스(yfinance/매크로 소스) 조회
3. 리포트 요청 시 DB의 최신 리포트 조회 (없으면 생성 루트 존재)
4. 커뮤니티 요청은 JWT 인증 후 DB CRUD 수행

## 7) 구조적 특징
- 장점
  - 백엔드 레이어 분리가 명확함 (`api/core/db/services`)
  - 캐시 + 스케줄러로 실시간 요청 부담 완화
  - 프론트 페이지 책임이 비교적 분명하고 상태관리 단순함
- 유의점
  - 프론트 API 베이스 URL이 하드코딩(`http://localhost:8000`)되어 있어 환경별 설정 분리 필요
  - `ARCHITECTURE.md`의 기술 스택 설명(Next.js/TypeScript)과 실제 코드(React+Vite, JS) 간 불일치 존재
  - `docker-compose.yml`에 DB 자격정보가 평문으로 포함되어 있어 `.env` 분리 권장

## 8) 결론
현재 구조는 **데이터 수집/캐시/AI 리포트/커뮤니티**가 하나의 백엔드 안에서 유기적으로 동작하도록 잘 구성되어 있습니다.  
특히 시장 데이터 캐시와 리포트 생성 스케줄링이 핵심이며, 프론트는 이 API를 중심으로 자산 상세 경험을 완성하는 형태입니다.
