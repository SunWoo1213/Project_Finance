# Pages 개발 방향성

이 폴더는 라우트 단위 화면을 담당합니다.

## 현재 화면

- `Home.jsx`: 주요 시장 데이터 요약
- `CategoryView.jsx`: 자산군별 목록
- `MarketSnapshot.jsx`: 홈 주요 지수/환율 클릭 후 시간 단위 차트와 관련 대시보드 이동
- `AssetDetail.jsx`: 상세 가격, 차트, AI 리포트, 댓글
- `Login.jsx`: Google 로그인

## 개발 원칙

페이지는 사용자의 흐름과 상태 조합을 책임집니다. 단순 버튼, 카드, 입력 필드, 반복 리스트 아이템은 `components`로 분리합니다.

API 호출이 많아질 경우 페이지 내부에 계속 쌓지 말고 공통 API 클라이언트 또는 page-specific hook으로 분리합니다.

`AssetDetail.jsx`는 현재 가장 많은 책임을 가진 화면입니다. 새 기능을 추가할 때는 차트, 리포트, 댓글, 가격 정보가 서로 불필요하게 결합되지 않도록 분리 우선순위를 검토합니다.

로그인이 필요한 기능은 UI 잠금, API 인증 헤더, 실패 처리 세 가지를 함께 다룹니다.

## 하네스 문서 연계

페이지별 기능 변경은 해당 기능 문서와 함께 갱신합니다.

- `Home.jsx`, `CategoryView.jsx`: `docs/harness/features/market-data.md`
- `AssetDetail.jsx`: `docs/harness/features/asset-detail-ai-community.md`와, 가격/차트 변경이면 `docs/harness/features/market-data.md`
- `Login.jsx`: `docs/harness/features/authentication.md`
- 라우트 추가/삭제: `docs/harness/features/frontend-routing-shell.md`

페이지의 API 호출, route param, 로그인 필요 여부, fallback UI가 바뀌면 변경 기록을 `docs/harness/`에 남기고 기능 문서의 `Data Flow`와 `Contracts`를 수정합니다.
