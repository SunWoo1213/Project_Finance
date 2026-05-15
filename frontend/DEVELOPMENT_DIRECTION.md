# Frontend 개발 방향성

프론트엔드는 사용자가 시장 데이터, 차트, AI 리포트, 커뮤니티 기능을 탐색하는 React Vite 앱입니다.

## 현재 실제 스택

- React
- Vite
- JavaScript
- Tailwind CSS
- Zustand
- React Router
- Axios
- Recharts
- React Markdown

주의: 상위 설계 문서의 Next.js/TypeScript 설명은 현재 코드와 다릅니다. 현재 프론트 개발은 Vite 구조를 기준으로 합니다.

## 폴더 기준

- `src/pages`: 라우트 단위 화면과 화면별 데이터 흐름
- `src/components`: 재사용 UI 조각
- `src/components/ui`: 버튼, 입력 같은 원자 UI
- `src/store`: 전역 클라이언트 상태
- `src/utils`: 포맷터, 상수, 검증 스키마 같은 순수 유틸
- `src/assets`, `public`: 정적 자산

## 개발 원칙

페이지 컴포넌트는 화면 조립과 사용자 흐름을 담당합니다. 반복되는 UI는 컴포넌트로 분리하고, 데이터 변환과 포맷팅은 `utils`로 이동합니다.

API 주소는 장기적으로 환경변수와 공통 API 클라이언트로 모아야 합니다. 페이지마다 `http://localhost:8000`을 직접 쓰는 방식은 유지보수 비용이 큽니다.

백엔드 응답 구조가 바뀔 때는 프론트 표시 로직뿐 아니라 fallback 처리도 함께 확인합니다. 특히 `points`, `legacy`, `history_prices`, `currentPrice`, `changePercent`처럼 호환을 위해 남겨둔 필드가 있습니다.

