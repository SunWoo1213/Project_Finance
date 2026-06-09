# 메인 대쉬보드 지수 스냅샷 히스토리 그래프 제거

Date: 2026-06-10

## 목적

메인 대쉬보드([Home.jsx](../../frontend/src/pages/Home.jsx))에서 지수 4개(S&P 500, Nasdaq 100, 원/달러, KOSPI) 카드를 클릭하면 이동하는 `/market/:ticker` 스냅샷 화면에서 히스토리(일별 흐름) 그래프를 제거한다. 카드 클릭 → `/market/:ticker` 이동 동작은 그대로 유지하고, 그래프 영역만 삭제한다.

## 변경 파일

- `frontend/src/pages/MarketSnapshot.jsx`
- `docs/harness/features/frontend-routing-shell.md`
- `docs/harness/feature-index.md`

## 동작 변화

- `/market/:ticker` 화면에서 일별 라인 차트(recharts `LineChart`)를 완전히 제거했다.
- 현재가·등락률 헤더와 관련 대쉬보드 이동 링크는 그대로 유지된다.
- 차트 전용으로만 쓰이던 코드를 함께 정리했다.
  - import 제거: `useMemo`, `recharts`(`Line`, `LineChart`, `ResponsiveContainer`, `Tooltip`, `XAxis`, `YAxis`).
  - 상태/로직 제거: `chartData` state, `toDailyPoints` 헬퍼, `latestPoint`, `strokeColor`.
  - 데이터 호출 변경: 더 이상 `GET /api/market/history/:ticker?period=1d`를 호출하지 않고 `GET /api/market/prices`만 호출한다.
- 헤더 라벨 문구를 "최근 일별 흐름" → "현재 시세"로, 로딩 문구를 "일별 흐름 데이터를 불러오는 중입니다..." → "시세 데이터를 불러오는 중입니다..."로 조정했다.
- Home 카드의 클릭 이동(`navigate('/market/:ticker')`)과 `/market/:ticker` 라우트, `MarketSnapshot.jsx` 파일 자체는 유지된다(이동 유지 + 그래프만 제거 결정).

## 검증

- `cd frontend && npx eslint src/pages/MarketSnapshot.jsx` 통과(출력 없음).

## 미실행 명령 및 사유

- `npm run build`, `npm run lint`(전체)는 실행하지 않았다. 변경이 단일 페이지 컴포넌트의 코드 축소에 한정되고 해당 파일 eslint가 통과해, 대상 파일 린트로 최소 검증을 대체했다. 필요 시 전체 빌드/린트로 추가 확인할 수 있다.
- 백엔드/DB 스모크 체크는 프론트엔드 한정 변경이라 실행하지 않았다.

## 후속 위험

- `/api/market/history` 엔드포인트는 이 화면에서 더 이상 사용하지 않지만 다른 화면(예: 자산 상세)에서 쓰일 수 있으므로 백엔드 라우트는 건드리지 않았다.
- 향후 스냅샷 화면에 차트를 다시 넣으려면 본 기록과 [main-market-snapshot-and-news.md](main-market-snapshot-and-news.md)를 함께 참고해 데이터 호출/포맷 로직을 복원해야 한다.

## Feature Docs

- `docs/harness/features/frontend-routing-shell.md`
