# Services 레이어 개발 방향성

이 폴더는 백엔드의 비즈니스 로직 중심입니다.

## 현재 책임

- `market_service.py`: 자산 목록, 가격/뉴스 수집, 프론트용 데이터 형태 정규화, 시장 캐시 갱신
- `macro_service.py`: 한국/미국 채권, 원자재 등 매크로 데이터 조회
- `ai_service.py`: AI 리포트 생성 요청의 상위 orchestration
- `external_api_service.py`: 외부 API 연동 추상화 지점
- `graph`: LangGraph 기반 멀티 에이전트 리포트 생성 로직

## 개발 원칙

서비스는 라우터보다 오래 살아남는 도메인 로직입니다. 같은 기능이 여러 API에서 쓰일 가능성이 있으면 서비스 함수로 만듭니다.

외부 API 응답은 이 레이어에서 백엔드 내부 표준 형태로 변환합니다. 프론트는 yfinance, ECOS, FRED의 원본 응답 구조를 알 필요가 없습니다.

금융 데이터는 빈 값, 휴장일, 지연 응답, provider별 ticker 차이를 고려해야 합니다. 새 provider를 붙일 때는 실패 시 fallback 또는 명확한 빈 응답을 제공합니다.

새 자산군을 추가할 때는 다음을 함께 확인합니다.

- 서비스의 자산 목록
- DB `AssetCategory`
- 프론트 `ASSET_NAMES`
- 카테고리/상세 화면의 표시 규칙
- 히스토리 API의 `series_type`, `unit`

