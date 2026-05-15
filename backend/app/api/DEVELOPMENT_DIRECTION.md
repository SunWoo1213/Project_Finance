# API 레이어 개발 방향성

이 폴더는 HTTP 엔드포인트의 입구입니다.

## 이 폴더가 책임지는 것

- URL path, method, status code 정의
- Request/response schema 연결
- 인증 사용자 주입
- 권한 체크
- 서비스 호출 결과를 HTTP 응답으로 변환

## 이 폴더에서 피해야 하는 것

- yfinance, ECOS, OpenAI 같은 외부 API 직접 호출
- 복잡한 데이터 정규화
- 캐시 갱신 로직
- LangGraph 노드 또는 LLM 프롬프트 구성
- DB 세션 생성 직접 관리

## 현재 라우터

- `auth.py`: 회원가입, 로그인, JWT 토큰 발급
- `community.py`: 댓글 작성, 조회, 수정, 삭제, 좋아요
- `deps.py`: 현재 사용자 인증 의존성

## 확장 방향

현재 `main.py`에 시장 데이터와 리포트 관련 엔드포인트가 일부 남아 있습니다. 기능이 커질 경우 다음 라우터로 분리합니다.

- `market.py`: `/api/market/prices`, `/api/market/news`, `/api/market/history/{ticker}`
- `reports.py`: `/api/reports/{ticker}`, `/api/ai/generate/{ticker}`

