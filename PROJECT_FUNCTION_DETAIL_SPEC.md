# Project Finance 기능 상세 명세서

문서 목적 : 이 문서는 Project Finance의 전체 구조와 기능을 PPT 상세설명란에 바로 옮겨 적을 수 있도록 `Key : value` 형식으로 정리한 기능 상세 명세서이다.

작성 기준 : 실제 프로젝트 소스 코드 기준으로 프론트엔드 화면, 백엔드 API, 데이터베이스 모델, 외부 데이터 연동, AI 리포트 생성 흐름을 분석하여 작성하였다.

문서 형식 : 표를 사용하지 않고, 각 항목을 `기능명 : 상세 설명` 형태의 텍스트로 작성하였다.

주의 사항 : 기존 `ARCHITECTURE.md`, `PROJECT_STRUCTURE_ANALYSIS.md` 파일 일부는 인코딩이 깨져 있어, 본 명세서는 실제 코드 동작 구조를 우선 기준으로 작성하였다.

## 1. 프로젝트 개요

프로젝트명 : Project Finance

서비스명 : AI Invest

프로젝트 목적 : 글로벌 금융 자산의 시세, 변동률, 차트, 뉴스, AI 분석 리포트, 종목 토론 기능을 제공하는 금융 정보 웹 애플리케이션이다.

핵심 사용자 경험 : 사용자는 메인 화면에서 주요 지수를 확인하고, 카테고리별 자산 목록을 탐색한 뒤, 개별 자산 상세 화면에서 가격 차트와 AI 분석 리포트 및 댓글 토론을 이용할 수 있다.

서비스 구조 : React 기반 프론트엔드와 FastAPI 기반 백엔드가 REST API로 통신하며, PostgreSQL 데이터베이스에 사용자, 자산, AI 리포트, 댓글, 좋아요 데이터를 저장한다.

주요 기능 묶음 : 시장 데이터 조회, 자산 카테고리 탐색, 자산 상세 차트 조회, AI 리포트 생성 및 조회, 회원가입/로그인, 댓글 CRUD, 댓글 좋아요, 주기적 데이터 캐싱, 외부 금융 API 연동으로 구성된다.

## 2. 전체 기술 구조

프론트엔드 : React, Vite, JavaScript, Tailwind CSS 기반의 SPA 구조이다.

프론트엔드 라우팅 : `react-router-dom`을 사용하여 홈, 카테고리, 상세, 로그인, 회원가입 화면을 클라이언트 라우팅으로 전환한다.

프론트엔드 상태 관리 : Zustand를 사용하여 로그인 토큰과 사용자 정보를 전역 상태 및 `localStorage`에 저장한다.

프론트엔드 데이터 통신 : Axios를 사용하여 FastAPI 서버의 REST API를 호출한다.

프론트엔드 차트 표현 : `recharts`와 자체 `SparklineChart` 컴포넌트를 사용하여 미니 차트와 상세 라인 차트를 표시한다.

프론트엔드 마크다운 렌더링 : `react-markdown`을 사용하여 AI 리포트의 Markdown 본문을 상세 화면에 렌더링한다.

백엔드 : FastAPI, SQLAlchemy Async, Pydantic, APScheduler 기반의 비동기 API 서버이다.

백엔드 데이터베이스 : PostgreSQL을 사용하며, SQLAlchemy ORM 모델로 사용자, 자산, 리포트, 댓글, 좋아요 테이블을 정의한다.

백엔드 인증 방식 : 이메일과 비밀번호로 로그인하고, 성공 시 JWT Bearer 토큰을 발급한다.

AI 처리 구조 : LangGraph 기반 워크플로우를 사용하여 금융 정보 조사, 뉴스 조사, 매크로 조사, 사실 통합, 리포트 작성, 품질 평가 단계를 수행한다.

외부 데이터 연동 : yfinance, FRED API, 한국은행 ECOS API, Financial Modeling Prep, Finnhub, CoinGecko 등을 사용하도록 구성되어 있다.

스케줄링 구조 : APScheduler를 사용하여 가격 캐시, 뉴스 캐시, AI 리포트 생성 작업을 주기적으로 실행한다.

인프라 구성 : `docker-compose.yml`에서 PostgreSQL 컨테이너를 실행하도록 정의되어 있다.

## 3. 루트 디렉터리 구조

`backend/` : FastAPI 서버, API 라우터, 서비스 로직, DB 모델, AI 그래프, 테스트 코드가 위치한 백엔드 폴더이다.

`frontend/` : React Vite 애플리케이션, 화면 컴포넌트, 라우팅, 상태 관리, 유틸 함수가 위치한 프론트엔드 폴더이다.

`docker-compose.yml` : PostgreSQL 데이터베이스 컨테이너 실행 설정 파일이다.

`ARCHITECTURE.md` : 프로젝트 아키텍처 설명 문서이나, 현재 일부 텍스트 인코딩이 깨져 있다.

`PROJECT_STRUCTURE_ANALYSIS.md` : 기존 프로젝트 구조 분석 문서이나, 현재 일부 텍스트 인코딩이 깨져 있다.

`test_api.py` : OpenAI API 연결 테스트 용도의 루트 테스트 스크립트이다.

`test_db.py` : 특정 티커의 AI 리포트를 DB에서 조회하는 테스트 스크립트이다.

## 4. 백엔드 폴더 구조

`backend/app/main.py` : FastAPI 앱 생성, CORS 설정, 라우터 등록, 서버 시작 시 DB 초기화, 시장 데이터 캐시 워밍업, 스케줄러 등록, 주요 API 엔드포인트 정의를 담당한다.

`backend/app/api/auth.py` : 회원가입과 로그인 API를 담당한다.

`backend/app/api/community.py` : 자산별 댓글 작성, 조회, 수정, 삭제, 좋아요 토글 API를 담당한다.

`backend/app/api/deps.py` : JWT 토큰을 검증하고 현재 로그인 사용자를 조회하는 의존성 함수를 담당한다.

`backend/app/core/config.py` : `.env` 파일에서 프로젝트명, DB URL, API Key, JWT 설정을 로드한다.

`backend/app/core/security.py` : 비밀번호 해싱, 비밀번호 검증, JWT 액세스 토큰 생성을 담당한다.

`backend/app/core/cache.py` : 시장 가격 데이터와 뉴스 데이터를 메모리 캐시에 저장하는 전역 객체를 정의한다.

`backend/app/db/base.py` : SQLAlchemy Base 객체를 정의하는 DB 기본 설정 파일이다.

`backend/app/db/session.py` : 비동기 SQLAlchemy 엔진과 세션 팩토리, DB 세션 의존성을 정의한다.

`backend/app/models.py` : User, Asset, AIReport, Comment, CommentLike ORM 모델과 AssetCategory Enum을 정의한다.

`backend/app/schemas.py` : 회원, 자산, 댓글 요청/응답용 Pydantic 스키마를 정의한다.

`backend/app/services/market_service.py` : 금융 자산 목록 정의, 가격 데이터 수집, 뉴스 수집, 시장 데이터 캐시 갱신을 담당한다.

`backend/app/services/macro_service.py` : 미국 채권, 한국 국채, 원자재 데이터 조회와 한국은행 ECOS 데이터 파싱을 담당한다.

`backend/app/services/ai_service.py` : 티커별 AI 리포트 생성, DB 저장, 정기 리포트 배치 생성을 담당한다.

`backend/app/services/external_api_service.py` : FMP, Finnhub, CoinGecko 등 AI 분석 보조용 외부 데이터를 조회한다.

`backend/app/services/graph/graph.py` : LangGraph 워크플로우의 노드 연결과 평가 후 재작성 반복 흐름을 정의한다.

`backend/app/services/graph/nodes.py` : financial_agent, news_agent, macro_agent, synthesizer_node, writer_node, evaluator_node의 실제 처리 로직을 정의한다.

`backend/tests/` : 매크로 데이터 처리와 시장 히스토리 API 관련 테스트 코드가 위치한다.

## 5. 프론트엔드 폴더 구조

`frontend/src/App.jsx` : 전체 라우팅 구조와 공통 Header, Toast 알림 영역을 정의한다.

`frontend/src/main.jsx` : React 앱을 DOM에 마운트하는 진입점이다.

`frontend/src/pages/Home.jsx` : 주요 지수를 카드 형태로 보여주는 홈 화면이다.

`frontend/src/pages/CategoryView.jsx` : 미국 주식, 한국 주식, 채권, 원자재, 암호화폐 카테고리 목록 화면이다.

`frontend/src/pages/AssetDetail.jsx` : 개별 자산의 가격, 변동률, 차트, AI 리포트, 댓글 토론방을 보여주는 상세 화면이다.

`frontend/src/pages/Login.jsx` : 이메일과 비밀번호를 입력하여 JWT 토큰을 발급받는 로그인 화면이다.

`frontend/src/pages/Register.jsx` : 이메일, 닉네임, 비밀번호, 비밀번호 확인을 입력하여 계정을 생성하는 회원가입 화면이다.

`frontend/src/components/Header.jsx` : 서비스 로고, 카테고리 네비게이션, 로그인/회원가입/로그아웃 UI를 제공하는 공통 헤더이다.

`frontend/src/components/SparklineChart.jsx` : 자산 목록과 메인 카드에서 짧은 가격 흐름을 보여주는 미니 차트 컴포넌트이다.

`frontend/src/components/ui/InputField.jsx` : 로그인과 회원가입 폼에서 사용하는 공통 입력 필드 컴포넌트이다.

`frontend/src/components/ui/Button.jsx` : 폼 제출과 로딩 상태 표시를 위한 공통 버튼 컴포넌트이다.

`frontend/src/store/authStore.js` : 로그인 토큰과 사용자 정보를 Zustand 상태와 localStorage에 저장하고, 로그인/로그아웃 동작을 제공한다.

`frontend/src/utils/constants.js` : 티커를 사람이 읽기 쉬운 자산명으로 바꿔주는 매핑 데이터를 제공한다.

`frontend/src/utils/formatters.js` : 가격, 변동률, 시가총액, 티커 표시 형식을 변환하는 유틸 함수이다.

`frontend/src/utils/validationSchemas.js` : 로그인과 회원가입 폼의 Zod 검증 규칙을 정의한다.

## 6. 화면별 기능 상세

홈 화면 : `/` 경로에서 주요 지수인 S&P 500, Nasdaq 100, KOSPI, KOSDAQ의 현재가, 변동률, 미니 차트를 보여준다.

홈 화면 데이터 호출 : 홈 화면은 `GET /api/market/prices` API를 호출하고, 응답의 `macro` 그룹에서 주요 지수 데이터를 추출한다.

홈 화면 카드 클릭 : 사용자가 지수 카드를 클릭하면 `/detail/{ticker}` 경로로 이동하여 해당 지수의 상세 화면을 볼 수 있다.

홈 화면 로딩 상태 : 시장 데이터가 로딩되는 동안 `Loading market data...` 메시지를 표시한다.

카테고리 화면 : `/category/:type` 경로에서 선택된 자산 카테고리의 목록을 표시한다.

카테고리 종류 : `us_top10`, `kr_top10`, `bonds`, `commodities`, `cryptos` 카테고리를 지원한다.

카테고리 화면 데이터 호출 : 카테고리 화면은 `GET /api/market/prices` API를 호출하고, URL의 카테고리 키에 해당하는 데이터 그룹만 추출한다.

카테고리 목록 정렬 : 자산 목록은 시가총액이 있는 경우 시가총액 기준으로 내림차순 정렬한다.

카테고리 목록 표시 정보 : 각 자산은 자산명, 티커, 미니 차트, 현재가, 변동률, 시가총액 또는 거시 지표 배지를 표시한다.

카테고리 자산 클릭 : 사용자가 목록의 자산을 클릭하면 `/detail/{symbol}` 경로로 이동하여 상세 화면을 볼 수 있다.

상세 화면 : `/detail/:ticker` 경로에서 개별 자산의 가격 정보, 기간별 차트, AI 분석 리포트, 종목 토론방을 제공한다.

상세 화면 가격 정보 : 현재가, 등락률, 자산명, 티커, 시가총액 또는 거시 지표 여부를 표시한다.

상세 화면 시장 데이터 매칭 : `GET /api/market/prices` 응답 전체 그룹을 순회하여 현재 티커와 일치하는 자산 정보를 찾는다.

상세 화면 기간 선택 : 사용자는 1일, 1개월, 1년, 5년 기간 버튼을 선택하여 차트 조회 범위를 바꿀 수 있다.

상세 화면 히스토리 호출 : 기간 선택에 따라 `GET /api/market/history/{ticker}?period={period}` API를 호출한다.

상세 화면 차트 표시 : 채권이 아닌 자산은 Recharts LineChart로 기간별 가격 차트를 표시한다.

상세 화면 채권 처리 : 채권 자산은 일반 가격 차트보다 AI 매크로 분석 리포트를 중심으로 제공한다는 안내를 표시한다.

상세 화면 리포트 접근 제어 : 로그인하지 않은 사용자는 AI 분석 리포트 영역이 흐림 처리되며, 로그인 버튼을 통해 로그인 화면으로 이동할 수 있다.

상세 화면 리포트 조회 : 로그인한 사용자는 `GET /api/reports/{ticker}` API를 통해 최신 AI 리포트를 조회한다.

상세 화면 리포트 자동 생성 : 리포트 조회 결과가 404이면 `POST /api/ai/generate/{ticker}` API를 호출하여 리포트를 생성한 뒤 다시 조회한다.

상세 화면 리포트 렌더링 : 조회한 AI 리포트의 `final_content`를 Markdown 형식으로 렌더링한다.

상세 화면 댓글 조회 : `GET /api/community/{ticker}/comments` API를 호출하여 해당 자산의 댓글 목록을 가져온다.

상세 화면 댓글 작성 : 로그인한 사용자는 댓글 입력 후 `POST /api/community/{ticker}/comments` API로 댓글을 작성할 수 있다.

상세 화면 댓글 수정 : 댓글 작성자 본인은 수정 버튼을 눌러 내용을 편집하고 `PUT /api/community/{ticker}/comments/{comment_id}` API로 저장할 수 있다.

상세 화면 댓글 삭제 : 댓글 작성자 본인은 삭제 버튼을 눌러 `DELETE /api/community/{ticker}/comments/{comment_id}` API로 댓글을 삭제할 수 있다.

상세 화면 댓글 좋아요 : 로그인한 사용자는 하트 버튼을 눌러 `POST /api/community/comments/{comment_id}/like` API로 좋아요를 추가하거나 취소할 수 있다.

로그인 화면 : `/login` 경로에서 이메일과 비밀번호를 입력하여 로그인할 수 있다.

로그인 폼 검증 : Zod 스키마를 사용하여 이메일 형식과 비밀번호 입력 여부를 검증한다.

로그인 요청 방식 : OAuth2PasswordRequestForm과 호환되도록 `application/x-www-form-urlencoded` 형식으로 `username`, `password`를 전송한다.

로그인 성공 처리 : 서버에서 받은 `access_token`과 닉네임을 Zustand 상태 및 localStorage에 저장하고 홈 화면으로 이동한다.

로그인 실패 처리 : 서버 응답 오류 메시지를 비밀번호 필드 오류로 표시하고, 네트워크 오류는 Toast로 안내한다.

회원가입 화면 : `/register` 경로에서 이메일, 닉네임, 비밀번호, 비밀번호 확인을 입력하여 계정을 생성할 수 있다.

회원가입 폼 검증 : 이메일 형식, 닉네임 길이, 비밀번호 최소 길이, 비밀번호 확인 일치 여부를 Zod 스키마로 검증한다.

회원가입 성공 처리 : 회원가입이 완료되면 성공 Toast를 표시하고 로그인 화면으로 이동한다.

회원가입 실패 처리 : 이메일 또는 닉네임 중복 등의 서버 오류를 해당 입력 필드에 표시한다.

헤더 네비게이션 : 모든 화면 상단에서 홈, 미국 주식, 한국 주식, 채권, 원자재, 암호화폐 카테고리로 이동할 수 있다.

헤더 인증 상태 표시 : 로그인 상태이면 사용자 닉네임과 로그아웃 버튼을 표시하고, 비로그인 상태이면 로그인과 회원가입 버튼을 표시한다.

로그아웃 기능 : 로그아웃 버튼을 누르면 Zustand 상태와 localStorage에서 토큰과 사용자 정보를 제거한다.

Toast 알림 기능 : 로그인 성공, 회원가입 성공, 네트워크 오류 등 주요 사용자 피드백을 `react-hot-toast`로 표시한다.

## 7. 백엔드 API 상세

헬스 체크 API : `GET /health`는 서버 상태와 프로젝트명을 반환하여 백엔드 서버가 정상 동작 중인지 확인한다.

DB 연결 확인 API : `GET /db-check`는 PostgreSQL에 `SELECT 1`을 실행하여 DB 연결 상태를 확인한다.

시장 가격 조회 API : `GET /api/market/prices`는 메모리 캐시에 저장된 전체 시장 가격 데이터를 반환한다.

시장 뉴스 조회 API : `GET /api/market/news`는 메모리 캐시에 저장된 전체 뉴스 데이터를 반환한다.

시장 히스토리 조회 API : `GET /api/market/history/{ticker}`는 특정 티커의 기간별 가격 또는 수익률 히스토리를 반환한다.

시장 히스토리 기간 옵션 : `period` 쿼리 파라미터는 `1d`, `1mo`, `1y`, `5y` 값을 지원한다.

시장 히스토리 주식 처리 : 일반 주식, 지수, 암호화폐는 yfinance에서 히스토리 데이터를 조회한다.

시장 히스토리 1일 처리 : 1일 데이터는 yfinance `5m` interval로 조회하여 더 촘촘한 장중 데이터를 제공한다.

시장 히스토리 1개월/1년 처리 : 1개월과 1년 데이터는 yfinance `1d` interval로 조회한다.

시장 히스토리 5년 처리 : 5년 데이터는 yfinance `1wk` interval로 조회한다.

시장 히스토리 한국 국채 처리 : `KTB_1Y`, `KTB_3Y`, `KTB_5Y`, `KTB_10Y`, `KTB_20Y`, `KTB_30Y`는 한국은행 ECOS 기반 수익률 데이터로 조회한다.

시장 히스토리 미국 채권 처리 : `DGS10`, `DGS30`, `DGS1`, `DGS3MO`, `DGS2MO`는 FRED 기반 수익률 데이터로 조회한다.

시장 히스토리 원자재 처리 : `XAU`, `XAG`, `GC=F`, `SI=F`는 금과 은 가격 데이터로 조회한다.

시장 히스토리 응답 구조 : 응답은 `ticker`, `series_type`, `unit`, `points`, `legacy` 필드를 포함하도록 정규화된다.

시장 히스토리 가격 단위 : 일반 자산과 원자재는 가격 데이터로 처리하고, 채권은 수익률 데이터로 처리한다.

AI 리포트 생성 API : `POST /api/ai/generate/{ticker}`는 특정 티커의 최신 캐시 데이터와 뉴스 데이터를 기반으로 AI 분석 리포트를 생성하고 DB에 저장한다.

AI 리포트 조회 API : `GET /api/reports/{ticker}`는 로그인한 사용자만 접근할 수 있으며, 특정 티커의 최신 AI 리포트를 반환한다.

AI 리포트 조회 인증 : `GET /api/reports/{ticker}`는 JWT Bearer 토큰을 요구하고, 토큰이 없거나 잘못되면 인증 오류를 반환한다.

회원가입 API : `POST /api/auth/register`는 이메일, 비밀번호, 닉네임을 받아 신규 사용자를 생성한다.

회원가입 이메일 중복 검사 : 동일한 이메일이 이미 존재하면 400 오류를 반환한다.

회원가입 닉네임 중복 검사 : 동일한 닉네임이 이미 존재하면 400 오류를 반환한다.

회원가입 비밀번호 저장 : 입력된 비밀번호는 bcrypt 해시로 변환하여 DB에 저장한다.

로그인 API : `POST /api/auth/login`은 이메일과 비밀번호를 검증하고 JWT 액세스 토큰과 닉네임을 반환한다.

로그인 실패 처리 : 이메일이 없거나 비밀번호 검증이 실패하면 401 오류를 반환한다.

댓글 작성 API : `POST /api/community/{asset_id}/comments`는 로그인한 사용자가 특정 자산에 댓글을 작성한다.

댓글 작성 자산 식별 : `asset_id` 경로 값은 숫자 ID 또는 티커 문자열 모두 허용한다.

댓글 작성 내용 검증 : 공백만 있는 댓글은 422 오류를 반환한다.

댓글 조회 API : `GET /api/community/{asset_id}/comments`는 특정 자산의 댓글 목록을 최신순으로 반환한다.

댓글 조회 작성자 정보 : 댓글 목록에는 작성자 닉네임과 좋아요 수가 함께 포함된다.

댓글 수정 API : `PUT /api/community/{asset_id}/comments/{comment_id}`는 작성자 본인만 댓글 내용을 수정할 수 있다.

댓글 수정 권한 검증 : 댓글 작성자가 현재 로그인 사용자와 다르면 403 오류를 반환한다.

댓글 삭제 API : `DELETE /api/community/{asset_id}/comments/{comment_id}`는 작성자 본인만 댓글을 삭제할 수 있다.

댓글 삭제 결과 : 삭제 성공 시 `삭제 완료` 메시지를 반환한다.

댓글 좋아요 API : `POST /api/community/comments/{comment_id}/like`는 현재 사용자의 좋아요를 토글한다.

댓글 좋아요 추가 : 기존 좋아요가 없으면 CommentLike 레코드를 생성하고 `liked` 상태를 반환한다.

댓글 좋아요 취소 : 기존 좋아요가 있으면 CommentLike 레코드를 삭제하고 `unliked` 상태를 반환한다.

## 8. 시장 데이터 기능 상세

시장 데이터 캐시 목적 : 외부 금융 API를 사용자 요청마다 직접 호출하지 않고, 서버 메모리에 가격과 뉴스 데이터를 저장하여 빠르게 응답하기 위한 구조이다.

가격 캐시 구조 : `market_cache["prices"]`에 카테고리별 가격 데이터가 저장된다.

뉴스 캐시 구조 : `market_cache["news"]`에 카테고리별 뉴스 데이터가 저장된다.

캐시 갱신 시간 기록 : `market_cache["last_updated"]`에 가격과 뉴스의 마지막 갱신 시간이 저장된다.

가격 캐시 초기화 : 서버 시작 시 `update_prices_task()`가 실행되어 시장 가격 데이터를 먼저 수집한다.

뉴스 캐시 초기화 : 서버 시작 시 `update_news_task()`가 실행되어 시장 뉴스 데이터를 먼저 수집한다.

가격 캐시 주기 갱신 : APScheduler가 5분마다 `update_prices_task()`를 실행한다.

뉴스 캐시 주기 갱신 : APScheduler가 1시간마다 `update_news_task()`를 실행한다.

AI 리포트 주기 생성 : APScheduler가 6시간마다 `generate_daily_reports()`를 실행한다.

지원 지수 : S&P 500, Nasdaq 100, KOSPI, KOSDAQ 데이터를 지원한다.

지원 환율 : USDKRW 환율 데이터를 지원한다.

지원 미국 주식 : AAPL, MSFT, NVDA, GOOGL, AMZN, META, BRK-B, LLY, AVGO, TSLA를 지원한다.

지원 한국 주식 : 삼성전자, SK하이닉스, LG에너지솔루션, 삼성바이오로직스, 현대차, 기아, 셀트리온, POSCO홀딩스, NAVER, KB금융을 지원한다.

지원 미국 채권 : 미국 3개월물 Treasury와 미국 10년물 Treasury 데이터를 지원한다.

지원 한국 국채 : 한국 1년, 10년, 30년 국채 수익률 데이터를 지원한다.

지원 원자재 : 금과 은 데이터를 지원한다.

지원 암호화폐 : Bitcoin과 Ethereum 데이터를 지원한다.

일반 자산 가격 수집 : yfinance를 사용하여 현재가, 전일 대비 변동률, 최근 1개월 종가 히스토리, 시가총액을 수집한다.

원자재 가격 수집 : 금과 은은 yfinance 선물 티커 또는 내부 표준 티커를 매핑하여 가격 데이터를 수집한다.

미국 채권 데이터 수집 : FRED API를 사용하여 채권 수익률 관측치를 조회한다.

한국 국채 데이터 수집 : 한국은행 ECOS API를 사용하여 국채 수익률 데이터를 조회한다.

암호화폐 가격 수집 : 기본 가격 목록은 yfinance 티커를 사용하고, AI 보조 정보는 CoinGecko에서 조회할 수 있도록 구성되어 있다.

뉴스 데이터 수집 : yfinance의 뉴스 데이터를 사용하여 자산별 뉴스 제목, 링크, 출처를 수집한다.

시장 데이터 정규화 : 백엔드는 `currentPrice`, `changePercent`, `history_prices`, `marketCap` 형태로 데이터를 표준화한다.

프론트엔드 호환 처리 : 백엔드는 기존 프론트엔드 키와 호환되도록 `price`, `change_pct`도 함께 반환한다.

외부 API 실패 처리 : 일부 매크로 API 실패 시 기본 응답 또는 빈 히스토리를 반환하여 서버 전체 장애를 방지한다.

한국 국채 실패 캐시 : ECOS API 실패 요청은 일정 시간 동안 반복 호출을 피하기 위해 실패 캐시에 기록한다.

## 9. AI 리포트 기능 상세

AI 리포트 목적 : 특정 금융 자산에 대해 가격 데이터, 뉴스, 재무 정보, 매크로 정보를 종합하여 한국어 투자 분석 리포트를 생성한다.

AI 리포트 생성 트리거 : 사용자가 상세 화면에서 리포트를 조회했을 때 기존 리포트가 없으면 즉시 생성할 수 있다.

AI 리포트 배치 트리거 : 서버 스케줄러가 6시간마다 DB에 등록된 자산을 대상으로 리포트를 생성할 수 있다.

AI 리포트 생성 전제 : 리포트 생성 대상 티커는 `market_cache["prices"]`에 가격 데이터가 존재해야 한다.

AI 리포트 이전 문맥 : 같은 티커의 최신 이전 리포트를 조회하여 새 리포트 작성 시 변화점 비교에 활용한다.

AI 리포트 자산 분류 : 티커를 기준으로 INDEX, BOND_US, BOND_KR, STOCK_US, STOCK_KR, COMMODITY, CRYPTO 카테고리로 분류한다.

AI 리포트 저장 대상 : 생성된 리포트는 `AIReport` 테이블에 저장되고, 자산 정보가 없으면 `Asset` 테이블에 새로 생성한다.

AI 리포트 저장 내용 : 상승 요약, 하락 또는 리스크 요약, 최종 리포트 본문, 생성 시간이 저장된다.

LangGraph 시작 단계 : `financial_agent`, `news_agent`, `macro_agent`가 병렬로 실행되어 서로 다른 관점의 정보를 수집한다.

재무 분석 에이전트 : 주식과 지수에 대해 FMP 데이터와 검색 도구를 활용하여 재무 지표, 실적, 밸류에이션 관련 맥락을 수집한다.

재무 분석 생략 조건 : 채권, 원자재, 암호화폐처럼 기업 재무제표가 없는 자산은 재무 분석을 생략하고 거시 자산 분석 중심으로 처리한다.

뉴스 분석 에이전트 : 최근 뉴스, 헤드라인, 시장 반응, 호재와 악재를 조사하여 뉴스 맥락을 생성한다.

매크로 분석 에이전트 : 금리, 환율, 인플레이션, 유동성, 위험 선호도 등 거시경제 요인을 조사한다.

암호화폐 보조 데이터 : 암호화폐 자산은 CoinGecko에서 가격, 24시간 거래량, 24시간 변동률 정보를 보조 맥락으로 사용할 수 있다.

사실 통합 노드 : 재무, 뉴스, 매크로 맥락을 읽고 핵심 숫자, 시장 심리 뉴스, 상승 요인, 하락 요인, 요약으로 구조화한다.

리포트 작성 노드 : 구조화된 사실과 이전 리포트를 바탕으로 Markdown 형식의 투자 분석 리포트를 작성한다.

변화점 분석 : 이전 리포트가 있으면 현재 사실과 비교하여 무엇이 달라졌는지를 리포트 앞부분에 반영한다.

리포트 언어 조건 : 최종 리포트는 한국어로 작성되도록 프롬프트에서 강하게 제한한다.

평가 노드 : 작성된 리포트가 최신성, 사실성, 한국어 품질 조건을 만족하는지 평가한다.

재작성 루프 : 평가가 통과되지 않으면 피드백을 기반으로 최대 3회까지 writer_node를 다시 실행한다.

리포트 최종 반환 : 평가를 통과하거나 재작성 횟수가 한계에 도달하면 최종 리포트를 반환한다.

## 10. 인증 기능 상세

사용자 모델 : 사용자는 이메일, 해시된 비밀번호, 닉네임, 생성 시간을 가진다.

회원가입 입력값 : 이메일, 비밀번호, 닉네임을 입력받는다.

이메일 유일성 : 이메일은 DB에서 유일해야 하며 중복 가입을 방지한다.

닉네임 유일성 : 닉네임은 DB에서 유일해야 하며 댓글 작성자 표시명으로 사용된다.

비밀번호 암호화 : 비밀번호는 passlib bcrypt를 사용하여 해시한 뒤 저장한다.

로그인 입력값 : 로그인은 OAuth2 표준에 맞춰 `username` 필드에 이메일을 담고 `password` 필드에 비밀번호를 담는다.

로그인 검증 : 입력 이메일로 사용자를 조회하고 bcrypt 해시와 평문 비밀번호를 비교한다.

JWT 발급 : 로그인 성공 시 사용자 ID를 `sub` 클레임에 담은 JWT 액세스 토큰을 발급한다.

JWT 만료 시간 : 기본 만료 시간은 설정값 기준 7일이다.

JWT 검증 : 보호 API는 Authorization 헤더의 Bearer 토큰을 디코딩하여 사용자 ID를 확인한다.

현재 사용자 조회 : 토큰의 사용자 ID로 DB에서 User 레코드를 조회하고, 없으면 인증 실패로 처리한다.

프론트엔드 토큰 저장 : 로그인 성공 시 토큰과 사용자 정보가 localStorage에 저장되어 새로고침 후에도 로그인 상태를 유지한다.

로그아웃 처리 : 로그아웃 시 localStorage와 Zustand 상태에서 토큰과 사용자 정보를 제거한다.

## 11. 커뮤니티 기능 상세

커뮤니티 목적 : 각 금융 자산 상세 화면에서 사용자들이 의견을 남기고 좋아요로 반응할 수 있는 종목 토론 기능이다.

댓글 모델 : 댓글은 사용자 ID, 자산 ID, 내용, 생성 시간을 가진다.

댓글 작성 조건 : 로그인한 사용자만 댓글을 작성할 수 있다.

댓글 조회 조건 : 로그인하지 않아도 특정 자산의 댓글 목록은 조회할 수 있다.

댓글 자산 연결 : 댓글은 Asset 테이블의 특정 자산과 연결된다.

댓글 최신순 정렬 : 댓글 목록은 생성 시간이 최신인 댓글부터 보여준다.

댓글 작성자 표시 : 댓글 목록에는 User 테이블의 닉네임을 조인하여 작성자 닉네임을 표시한다.

댓글 좋아요 수 표시 : 댓글 목록 조회 시 CommentLike 개수를 집계하여 `likes_count`로 반환한다.

댓글 수정 조건 : 댓글을 작성한 본인만 수정할 수 있다.

댓글 삭제 조건 : 댓글을 작성한 본인만 삭제할 수 있다.

댓글 빈 내용 방지 : 댓글 작성과 수정 시 공백만 있는 내용은 저장하지 않는다.

댓글 좋아요 모델 : `CommentLike`는 사용자 ID와 댓글 ID를 복합 기본키로 사용하여 한 사용자가 같은 댓글에 중복 좋아요를 누르지 못하게 한다.

좋아요 토글 방식 : 이미 좋아요가 있으면 삭제하고, 없으면 새로 생성하는 방식으로 좋아요와 좋아요 취소를 하나의 API에서 처리한다.

프론트엔드 댓글 입력 : 상세 화면 하단의 입력창에 댓글을 입력하고 전송 버튼을 누르면 댓글이 등록된다.

프론트엔드 댓글 편집 : 작성자 본인의 댓글에는 수정, 삭제 버튼이 표시된다.

프론트엔드 댓글 시간 표시 : 댓글 생성 시간은 한국 시간 기준 문자열로 표시된다.

## 12. 데이터베이스 모델 상세

User 테이블 : 서비스 사용자 계정 정보를 저장한다.

User 주요 필드 : `id`, `email`, `hashed_password`, `nickname`, `created_at`으로 구성된다.

User 관계 : 한 사용자는 여러 댓글과 여러 댓글 좋아요를 가질 수 있다.

Asset 테이블 : 개별 금융 자산의 기본 정보를 저장한다.

Asset 주요 필드 : `id`, `category`, `ticker`, `name`으로 구성된다.

Asset 카테고리 : INDEX, BOND_US, BOND_KR, STOCK_US, STOCK_KR, COMMODITY, CRYPTO를 지원한다.

Asset 관계 : 한 자산은 여러 AI 리포트와 여러 댓글을 가질 수 있다.

AIReport 테이블 : 특정 자산에 대해 생성된 AI 분석 리포트를 저장한다.

AIReport 주요 필드 : `id`, `asset_id`, `bull_summary`, `bear_summary`, `final_content`, `created_at`으로 구성된다.

AIReport 관계 : 여러 AI 리포트는 하나의 Asset에 연결된다.

Comment 테이블 : 자산별 사용자 댓글을 저장한다.

Comment 주요 필드 : `id`, `user_id`, `asset_id`, `content`, `created_at`으로 구성된다.

Comment 시간대 : 댓글 생성 시간은 Asia/Seoul 기준 현재 시간으로 저장하도록 구성되어 있다.

Comment 관계 : 댓글은 하나의 User와 하나의 Asset에 연결되고, 여러 CommentLike를 가질 수 있다.

CommentLike 테이블 : 댓글 좋아요 관계를 저장한다.

CommentLike 주요 필드 : `user_id`, `comment_id`로 구성된다.

CommentLike 기본키 : `user_id`와 `comment_id`를 복합 기본키로 사용한다.

DB 초기화 방식 : 서버 시작 시 `Base.metadata.create_all`을 실행하여 정의된 테이블이 없으면 생성한다.

DB 세션 방식 : 비동기 SQLAlchemy 세션을 FastAPI 의존성으로 주입하여 API 요청마다 사용한다.

## 13. 주요 데이터 흐름

시장 데이터 조회 흐름 : 프론트엔드가 가격 조회 API를 호출하면 백엔드는 외부 API를 즉시 호출하지 않고 메모리 캐시에 저장된 가격 데이터를 반환한다.

가격 캐시 갱신 흐름 : 스케줄러가 자산 그룹별 수집 함수를 병렬 실행하고, 수집 결과를 카테고리별 딕셔너리로 묶어 캐시에 저장한다.

뉴스 캐시 갱신 흐름 : 스케줄러가 yfinance 뉴스 데이터를 자산별로 가져오고, 제목, 링크, 출처를 정리하여 캐시에 저장한다.

상세 차트 조회 흐름 : 사용자가 기간 버튼을 누르면 프론트엔드가 히스토리 API를 호출하고, 백엔드는 자산 종류에 맞는 데이터 소스에서 기간별 포인트를 반환한다.

AI 리포트 조회 흐름 : 로그인 사용자가 상세 화면에 들어오면 프론트엔드가 최신 리포트를 조회하고, 없으면 생성 API를 호출한 뒤 다시 조회한다.

AI 리포트 생성 흐름 : 백엔드는 캐시된 가격/뉴스 데이터와 외부 보조 데이터를 LangGraph에 전달하고, 최종 리포트를 DB에 저장한다.

댓글 작성 흐름 : 사용자가 댓글을 작성하면 프론트엔드가 JWT 토큰과 함께 댓글 API를 호출하고, 백엔드는 사용자와 자산을 확인한 후 DB에 저장한다.

댓글 좋아요 흐름 : 사용자가 하트 버튼을 누르면 좋아요 API가 현재 좋아요 존재 여부를 확인하고 추가 또는 삭제 후 댓글 목록을 다시 조회한다.

로그인 흐름 : 사용자가 이메일과 비밀번호를 제출하면 백엔드는 검증 후 JWT를 반환하고, 프론트엔드는 토큰을 저장해 보호 기능 접근에 사용한다.

## 14. 외부 연동 상세

yfinance 연동 : 지수, 주식, 일부 원자재, 암호화폐 가격과 뉴스 조회에 사용된다.

FRED 연동 : 미국 국채 수익률 시계열 데이터를 조회하는 데 사용된다.

ECOS 연동 : 한국은행 경제통계시스템에서 한국 국채 수익률 데이터를 조회하는 데 사용된다.

FMP 연동 : AI 리포트 생성 시 기업 프로필, 산업, 베타, 시가총액, 가격, 평균 거래량, 기업 설명을 보조 정보로 제공한다.

Finnhub 연동 : AI 리포트 생성 시 최근 기업 뉴스 데이터를 보조 정보로 제공한다.

CoinGecko 연동 : AI 리포트 생성 시 암호화폐의 현재 가격, 24시간 거래량, 24시간 변동률을 보조 정보로 제공한다.

OpenAI 연동 : LangGraph 노드에서 LLM을 호출하여 조사 결과 정리, 리포트 작성, 품질 평가를 수행한다.

DuckDuckGo 또는 검색 도구 연동 : LangGraph ReAct agent의 도구로 최신 금융 정보를 조사하는 데 활용된다.

## 15. 설정 및 환경 변수

프로젝트명 설정 : `PROJECT_NAME` 환경 변수로 FastAPI 프로젝트명을 설정한다.

API 버전 문자열 설정 : `API_V1_STR` 환경 변수를 로드하지만, 현재 주요 라우터는 직접 `/api/...` 경로를 사용한다.

DB 연결 설정 : `DATABASE_URL` 환경 변수로 PostgreSQL 연결 주소를 설정한다.

OpenAI 설정 : `OPENAI_API_KEY` 환경 변수로 AI 리포트 생성에 필요한 OpenAI API Key를 설정한다.

FRED 설정 : `FRED_API_KEY` 환경 변수로 미국 채권 데이터 조회 API Key를 설정한다.

ECOS 설정 : `ECOS_API_KEY` 환경 변수로 한국은행 ECOS API Key를 설정한다.

Alpha Vantage 설정 : `ALPHA_VANTAGE_API_KEY` 환경 변수를 로드하지만, 현재 주요 코드에서는 직접적인 핵심 호출이 제한적으로만 준비되어 있다.

JWT Secret 설정 : `SECRET_KEY`로 JWT 서명 키를 설정한다.

JWT 알고리즘 설정 : 기본 알고리즘은 HS256이다.

JWT 만료 설정 : `ACCESS_TOKEN_EXPIRE_MINUTES`로 액세스 토큰 만료 시간을 설정한다.

환경 파일 위치 : 백엔드 설정은 프로젝트 루트의 `.env` 파일을 읽도록 구성되어 있다.

## 16. 테스트 및 검증 코드

매크로 서비스 테스트 : 한국 국채 티커와 ECOS item code 매핑, 날짜 범위 보정, 잘못된 티커 기본 응답, 실패 호출 캐시 동작을 검증한다.

시장 히스토리 라우트 테스트 : 한국 국채 히스토리 데이터가 없을 때 404를 반환하는지, 자산 티커가 서비스 함수로 올바르게 전달되는지 검증한다.

OpenAI 연결 테스트 : `test_api.py`는 `.env`의 OpenAI API Key를 로드하여 LangChain ChatOpenAI 호출이 가능한지 확인한다.

DB 조회 테스트 : `test_db.py`는 BTC-USD의 최신 AI 리포트가 DB에 저장되어 있는지 조회하는 스크립트이다.

## 17. 구현상 유의사항

프론트엔드 API 주소 : 현재 프론트엔드 코드에서 백엔드 주소가 `http://localhost:8000`으로 하드코딩되어 있어 배포 환경에서는 환경 변수 분리가 필요하다.

문자열 인코딩 : 일부 기존 문서와 일부 UI 문자열에 인코딩 깨짐이 보이며, 실제 발표 자료 작성 시 사용자에게 보이는 한글 문구는 정리할 필요가 있다.

아키텍처 문서 불일치 : 기존 아키텍처 문서에는 Next.js, TypeScript 등으로 적힌 부분이 있으나, 실제 프론트엔드는 React Vite JavaScript 구조이다.

DB 마이그레이션 : 현재 서버 시작 시 `create_all`로 테이블을 생성하며, Alembic 마이그레이션 구조는 명확히 사용되지 않는다.

보안 설정 : `docker-compose.yml`에 DB 계정 정보가 직접 포함되어 있어 실제 배포 시 환경 변수 또는 Secret 관리가 필요하다.

AI 비용 관리 : 리포트 생성은 LLM 호출을 포함하므로, 캐싱, 정기 배치 간격, 호출 실패 처리, Rate Limit 보호가 중요하다.

캐시 의존성 : AI 리포트 생성은 시장 가격 캐시에 해당 티커 데이터가 있어야 정상 동작한다.

자산 DB 등록 방식 : AI 리포트 생성 시 자산이 DB에 없으면 자동 생성되지만, 댓글 작성은 자산이 이미 DB에 있어야 한다.

비로그인 사용자 제한 : 비로그인 사용자는 가격과 댓글 조회는 가능하지만, AI 리포트 열람과 댓글 작성, 좋아요 기능은 제한된다.

## 18. PPT에 넣기 좋은 핵심 요약

서비스 한 줄 설명 : AI Invest는 글로벌 주식, 지수, 채권, 원자재, 암호화폐의 시장 데이터를 제공하고, AI가 생성한 투자 분석 리포트와 종목 토론 기능을 함께 제공하는 금융 정보 플랫폼이다.

핵심 기능 1 : 주요 지수와 카테고리별 금융 자산의 현재가, 변동률, 미니 차트를 제공한다.

핵심 기능 2 : 개별 자산 상세 화면에서 기간별 가격 차트와 시가총액, 거시 지표 여부를 확인할 수 있다.

핵심 기능 3 : 로그인 사용자는 AI가 생성한 한국어 투자 분석 리포트를 조회할 수 있으며, 리포트가 없으면 즉시 생성할 수 있다.

핵심 기능 4 : 자산별 댓글 토론방을 통해 사용자가 의견을 작성, 수정, 삭제하고 좋아요로 반응할 수 있다.

핵심 기능 5 : 백엔드는 외부 금융 API 데이터를 주기적으로 수집하여 메모리 캐시에 저장하고 빠른 응답을 제공한다.

핵심 기능 6 : LangGraph 기반 AI 파이프라인이 재무, 뉴스, 매크로 정보를 수집하고 통합하여 최종 투자 리포트를 생성한다.

핵심 기능 7 : JWT 인증을 통해 리포트 조회, 댓글 작성, 수정, 삭제, 좋아요 같은 사용자 기능을 보호한다.

핵심 기능 8 : PostgreSQL에 사용자, 자산, AI 리포트, 댓글, 좋아요 데이터를 관계형 구조로 저장한다.

