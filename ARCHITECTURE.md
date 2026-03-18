# 🏛️ AI 기반 글로벌 금융 인텔리전스 플랫폼 (System Blueprint)

## 1. 프로젝트 개요 (Overview)
본 프로젝트는 글로벌 금융 자산(지수, 주식, 암호화폐, 환율, 원자재)의 실시간 데이터를 제공하고, LangGraph 기반의 멀티 에이전트가 작성한 심층 투자 리포트를 제공하는 풀스택 웹 애플리케이션이다. 
실시간 LLM 호출로 인한 지연 시간과 비용을 방지하기 위해 **'스케줄러 기반의 백그라운드 배치(Batch) 처리'** 아키텍처를 채택한다.

## 2. 기술 스택 (Tech Stack)
- **Frontend:** Next.js 14+ (App Router), TypeScript, Tailwind CSS, Zustand, Lightweight Charts
- **Backend:** Python 3.11+, FastAPI, SQLAlchemy (Async), Alembic, APScheduler
- **AI / LLM:** LangGraph, Langchain, OpenAI API (gpt-4o-mini)
- **Database:** PostgreSQL (asyncpg 드라이버 사용)
- **Package Manager:** uv

## 3. 데이터 소스 전략 (100% Free APIs)
비용과 Rate Limit 문제를 방지하기 위해 다음의 무료 소스만 혼합하여 사용한다.
- **주식/지수/원자재/환율:** `yfinance` 패키지 (`^KS11`, `^KQ11`, `^NDX`, `^GSPC`, `GC=F`, `SI=F`, `KRW=X`)
- **암호화폐:** `CoinGecko API` (REST API)
- **뉴스 검색 (AI Context):** `DuckDuckGoSearchRun` 또는 `Tavily API` (무료 티어)

## 4. 핵심 아키텍처 및 워크플로우

### 4.1. AI 리포트 배치 파이프라인 (Backend / LangGraph)
사용자 요청 시 LLM을 호출하지 않는다. 
1. **스케줄러 작동:** `APScheduler`가 매일 특정 시간에 백그라운드 워커를 실행한다.
2. **데이터 수집:** `yfinance`와 뉴스 검색 도구를 통해 팩트 데이터를 수집한다.
3. **멀티 에이전트 토론 (LangGraph State):**
   - `Bull_Agent`: 매수 논거 작성
   - `Bear_Agent`: 매도/리스크 논거 작성
   - `Synthesizer_Agent`: 두 의견을 종합하여 최종 마크다운 리포트 생성
4. **DB 저장:** 완성된 리포트를 `AI_Reports` 테이블에 `INSERT` 한다.

### 4.2. 사용자 서빙 파이프라인 (Frontend <-> FastAPI)
1. **시장 데이터 (`/api/market/...`):** FastAPI가 `yfinance` 데이터를 비동기로 조회 후 즉시 반환 (필요시 In-memory 캐싱 적용).
2. **AI 리포트 (`/api/ai/report/{ticker}`):** DB의 `AI_Reports` 테이블에서 최신 리포트를 0.1초 만에 `SELECT` 하여 반환.

## 5. 데이터베이스 스키마 (ERD Core)
비동기 세션을 통해 접근하며, 무결성을 철저히 지킨다.
- **`users`**: `id`, `email`, `hashed_password`, `created_at`
- **`assets`**: `id`, `ticker` (Unique ID, 예: USDKRW, ^KS11), `name`, `asset_type`
- **`ai_reports`**: `id`, `asset_id` (FK), `bull_summary`, `bear_summary`, `final_content`, `created_at` (Index 적용)
- **`community_posts`**: `id`, `user_id` (FK), `asset_id` (FK), `vote_type` (BULL/BEAR), `content`, `created_at`

## 6. 백엔드 폴더 구조 (Clean Architecture)
```text
backend/
├── app/
│   ├── api/          # 라우터 (엔드포인트) 정의
│   ├── core/         # 환경설정(config.py), 스케줄러 설정
│   ├── db/           # 데이터베이스 비동기 세션 (session.py)
│   ├── models/       # SQLAlchemy 테이블 클래스
│   ├── schemas/      # Pydantic 검증 모델
│   └── services/     # 비즈니스 로직 (yfinance 호출, LangGraph 워크플로우)
├── main.py           # FastAPI 엔트리 포인트 (CORS, 라우터 등록)
└── requirements.txt  # 의존성 관리