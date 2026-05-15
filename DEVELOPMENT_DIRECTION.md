# Project Finance 개발 방향성

이 문서는 이후 개발자가 프로젝트 구조를 오해하지 않도록 하는 최상위 가드레일입니다.

## 현재 실제 아키텍처

이 프로젝트는 현재 다음 구조로 동작합니다.

- Frontend: React + Vite + JavaScript + Tailwind CSS
- Backend: FastAPI + SQLAlchemy Async + APScheduler
- Database: PostgreSQL
- AI/Report: LangGraph/LangChain 기반 리포트 생성 파이프라인
- External Data: yfinance, ECOS/FRED 계열 매크로 데이터, 기타 무료 데이터 소스

주의: `ARCHITECTURE.md`에는 Next.js, TypeScript, uv 중심의 미래 청사진이 섞여 있습니다. 실제 코드는 React Vite와 `requirements.txt` 기반 FastAPI 프로젝트입니다. 개발 판단은 현재 실행되는 코드 구조를 우선합니다.

## 개발 원칙

1. API 라우터는 요청/응답, 인증, 권한, 상태 코드만 책임집니다.
2. 외부 API 호출, 데이터 정규화, 캐시 갱신, AI 리포트 생성은 `backend/app/services`에서 처리합니다.
3. DB 연결과 세션 관리는 `backend/app/db`에서만 다룹니다.
4. Pydantic 스키마는 API 계약이며, ORM 모델과 섞지 않습니다.
5. 프론트엔드 페이지는 화면 흐름을 책임지고, 반복 UI는 `components`, 순수 계산은 `utils`, 전역 인증 상태는 `store`에 둡니다.
6. 외부 API와 LLM은 실패할 수 있다는 전제로 작성합니다.
7. 티커 표기(`KTB_10Y`, `DGS10`, `005930.KS`, `BTC-USD`)는 백엔드와 프론트가 같은 의미로 해석해야 합니다.

## 앞으로 혼동하기 쉬운 지점

- 현재 시장 데이터 라우트 일부는 `backend/app/main.py`에 직접 있습니다. 기능이 커지면 `backend/app/api/market.py`로 분리하는 것이 자연스럽습니다.
- AI 리포트는 사용자 요청마다 실시간 LLM 호출을 하는 구조가 아니라, DB에 저장된 최신 리포트를 조회하는 방향을 기본으로 합니다.
- 프론트 API 주소가 일부 페이지에 직접 하드코딩되어 있습니다. 추후에는 공통 API 클라이언트와 환경변수 기반 URL로 모으는 것이 좋습니다.
- 자산 메타데이터는 프론트 `utils/constants.js`, 백엔드 `market_service.py`, DB `Asset` 모델 사이에서 중복될 수 있습니다. 새 자산을 추가할 때는 세 위치의 의미가 어긋나지 않게 확인해야 합니다.

