# Components 개발 방향성

이 폴더는 여러 화면에서 재사용되는 UI 조각을 둡니다.

## 현재 책임

- Header
- 가격 카드
- 리포트 카드
- 티커 칩
- 차트 표시 컴포넌트
- 보호 라우트
- 공통 UI 입력/버튼

## 개발 원칙

컴포넌트는 가능한 한 props를 통해 데이터를 받고, 직접 API를 호출하지 않습니다. 화면 단위 데이터 흐름은 `pages`가 책임지는 것이 기본입니다.

표시 전용 컴포넌트와 상태를 가진 컴포넌트를 구분합니다. 단순 표시 컴포넌트는 포맷팅 결과를 받거나 `utils`의 순수 함수를 사용합니다.

공통 UI 컴포넌트는 도메인 문구를 직접 품지 않습니다. 예를 들어 `Button`은 금융/리포트 문구를 알 필요가 없습니다.

아이콘이 필요한 버튼은 이미 사용 중인 `lucide-react`를 우선 사용합니다.

## 하네스 문서 연계

공유 UI 변경은 우선 `docs/harness/features/frontend-routing-shell.md`를 확인합니다. 특정 기능과 결합된 컴포넌트라면 해당 기능 문서도 함께 갱신합니다.

- 인증 표시, 로그인/로그아웃 링크: `docs/harness/features/authentication.md`
- 가격 카드, 차트, 티커 칩: `docs/harness/features/market-data.md`
- 리포트 카드, 상세 화면 보조 UI: `docs/harness/features/asset-detail-ai-community.md`

컴포넌트 props 계약이나 재사용 위치가 바뀌면 변경 기록에 어떤 페이지가 영향을 받는지 적습니다.
