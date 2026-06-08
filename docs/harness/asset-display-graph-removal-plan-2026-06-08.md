# 자산 표시 그래프 제거 계획

Date: 2026-06-08
Feature area: Market data, Asset detail
Read first:
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`

## 1. 목적

자산을 목록 또는 상세 화면에서 보여줄 때 가격 정보보다 그래프 시각 효과가 먼저 눈에 들어오는 문제를 줄인다. 1차 목표는 `CategoryView.jsx`의 자산 목록 카드에 표시되는 작은 라인 그래프(`SparklineChart`)를 제거하고, 자산명, 티커, 현재가, 등락률, 시가총액/거시 지표 배지만 남겨 더 단순한 리스트형 표시로 바꾸는 것이다.

사용자가 "상세 화면의 큰 차트까지 없애는 것"을 의미한 경우에는 2차 선택 범위로 `AssetDetail.jsx`의 기간 선택 차트 영역까지 제거한다. 이 계획서는 두 범위를 분리해 둔다.

## 2. 현재 동작

- `frontend/src/pages/CategoryView.jsx`
  - `SparklineChart`를 import한다.
  - 각 자산 카드 가운데 영역에서 `data.history_prices`를 `SparklineChart`에 넘겨 미니 라인 그래프를 렌더링한다.
  - 그래프는 `sm:block` 이상 화면에서만 보이고 모바일에서는 숨겨진다.
- `frontend/src/components/SparklineChart.jsx`
  - `recharts`의 `ResponsiveContainer`, `LineChart`, `YAxis`, `Tooltip`, `Line`을 사용한다.
  - `history_prices` 배열을 `{ value, index }` 형태로 바꿔 작은 선 그래프를 만든다.
- `frontend/src/pages/AssetDetail.jsx`
  - `recharts`를 직접 import해 상세 화면 상단에 큰 기간별 차트를 렌더링한다.
  - `GET /api/market/history/{ticker}?period=...`를 호출하고 `selectedPeriod`, `chartData`, `historyMeta` 상태를 관리한다.
  - 채권 자산은 차트를 숨기고 안내 문구를 보여준다.

## 3. 변경 범위

### 1차 범위: 자산 목록 카드의 미니 그래프 제거

대상 파일:

- `frontend/src/pages/CategoryView.jsx`
- `frontend/src/components/SparklineChart.jsx`는 더 이상 참조되지 않으면 삭제하거나 보존 여부를 결정한다.
- `docs/harness/features/market-data.md`
- `docs/harness/feature-index.md`

계획:

1. `CategoryView.jsx`에서 `SparklineChart` import를 제거한다.
2. 자산 카드의 가운데 그래프 컨테이너를 제거한다.
3. 제거된 공간을 가격/등락률 영역에 넘기거나, 자산명 영역과 가격 영역 사이 간격을 정리한다.
4. `strokeColor`가 그래프에만 쓰이면 제거한다. 등락률 배지에는 `formatChangeBadge`만 유지한다.
5. `SparklineChart.jsx`가 프로젝트 어디에서도 쓰이지 않는지 `rg "SparklineChart"`로 확인한다.
6. 참조가 완전히 없어지면 `SparklineChart.jsx` 삭제를 검토한다. 삭제는 파일 제거이므로 구현 전 사용자 확인을 받거나, 우선 미사용 파일로 남겨 두는 보수적 선택을 한다.
7. `frontend/src/components/DEVELOPMENT_DIRECTION.md`의 "차트 표시 컴포넌트" 설명이 실제와 어긋나면 구현 기록 단계에서 갱신한다.

### 2차 선택 범위: 자산 상세 상단 차트 제거

대상 파일:

- `frontend/src/pages/AssetDetail.jsx`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/market-data.md`
- `docs/harness/feature-index.md`

계획:

1. `AssetDetail.jsx`에서 `recharts` import를 제거한다.
2. `selectedPeriod`, `chartData`, `historyMeta`, `hasChartData`, `periods`, `strokeColor` 등 차트 전용 상태와 파생값을 제거한다.
3. `GET /api/market/history/{ticker}` 호출 effect를 제거한다.
4. 차트 카드 JSX와 기간 선택 버튼을 제거한다.
5. 채권 전용 안내 문구는 상세 화면 전체 정책에 맞게 유지 여부를 결정한다. 차트가 모든 자산에서 사라지면 "채권 자산은 AI 매크로 분석 리포트를 중심으로 제공합니다." 문구만 남기는 것은 맥락이 약해질 수 있다.
6. 상세 화면 상단에는 현재가, 등락률, 시가총액/거시 지표, 즐겨찾기 버튼만 남긴다.
7. `recharts`가 다른 화면에서 계속 쓰이는지 확인한다. `MarketSnapshot.jsx`가 계속 `recharts`를 쓰므로 패키지 의존성 제거는 하지 않는다.

## 4. UX 방향

- 자산 목록은 그래프 대신 텍스트 중심의 빠른 스캔 UI로 만든다.
- 카드 안에 불필요한 빈 중앙 영역이 남지 않도록 `flex` 비율과 `min-width`를 조정한다.
- 데스크톱과 모바일 모두에서 자산명, 티커, 현재가, 등락률, 즐겨찾기 버튼이 겹치지 않아야 한다.
- 그래프 제거 뒤에도 상승/하락 색상 의미는 등락률 배지로 유지한다.
- 자산 카드 클릭과 즐겨찾기 버튼 클릭 동작은 그대로 유지한다.

## 5. 구현 순서

1. `git status --short`로 사용자 변경사항을 재확인한다.
2. `rg "SparklineChart|recharts|history_prices|market/history" frontend/src`로 실제 참조 범위를 확인한다.
3. 1차 범위만 적용할지, 2차 선택 범위까지 적용할지 사용자 의도 또는 작업 지시를 확정한다.
4. 1차 범위 구현:
   - `CategoryView.jsx`의 그래프 import와 JSX 제거.
   - 카드 레이아웃 정리.
   - 필요 시 `SparklineChart.jsx` 보존/삭제 결정.
5. 2차 선택 범위 구현 시:
   - `AssetDetail.jsx`의 history fetch와 차트 전용 상태 제거.
   - 상세 상단 레이아웃 정리.
6. 구현 후 관련 기능 문서와 구현 기록을 갱신한다.

## 6. 검증 계획

프론트엔드 표시 변경이므로 최소 검증은 다음과 같다.

```powershell
cd frontend
npm run lint
npm run build
```

가능하면 개발 서버에서 수동 확인도 수행한다.

```powershell
cd frontend
npm run dev
```

수동 확인 대상:

- `/category/...` 또는 앱 내 자산 목록 화면에서 그래프가 보이지 않는지 확인한다.
- 자산 카드 클릭이 `/detail/:ticker`로 이동하는지 확인한다.
- 즐겨찾기 별 버튼 클릭이 카드 이동을 트리거하지 않는지 확인한다.
- 데스크톱/모바일 폭에서 자산명, 가격, 배지, 즐겨찾기 버튼이 겹치지 않는지 확인한다.
- 2차 범위까지 적용한 경우 `/detail/:ticker`에서 차트와 기간 버튼이 사라지고 현재가/리포트/뉴스/댓글 흐름이 정상인지 확인한다.

## 7. 문서 갱신 계획

구현 단계에서 다음 문서를 갱신한다.

- `docs/harness/features/market-data.md`
  - Current Behavior와 Data Flow에서 `CategoryView.jsx`의 미니 그래프 설명을 제거하거나 "그래프 없는 텍스트형 카드"로 수정한다.
  - Change Records에 구현 기록을 추가한다.
- `docs/harness/features/asset-detail-ai-community.md`
  - 2차 범위까지 적용한 경우 상세 차트 관련 설명을 제거한다.
  - Change Records에 구현 기록을 추가한다.
- `docs/harness/feature-index.md`
  - 관련 Feature Map의 Change records에 구현 기록을 추가한다.
- `docs/harness/asset-display-graph-removal-implementation-2026-06-08.md`
  - 실제 변경 파일, 동작 변경, 검증 결과, 남은 위험을 기록한다.

## 8. 위험과 확인 사항

- "그래프 효과 제거"가 목록 카드의 미니 그래프만 뜻하는지, 상세 화면의 큰 차트까지 뜻하는지 확인이 필요하다.
- `SparklineChart.jsx` 삭제는 파일 제거이므로 구현 시 사용자 확인 또는 명시 지시가 안전하다. 보수적으로는 import만 제거하고 파일은 남겨 둘 수 있다.
- `AssetDetail.jsx`의 history fetch를 제거하면 `/api/market/history` 호출량은 줄지만, 상세 화면에서 기간별 가격 흐름 확인 기능도 사라진다.
- `MarketSnapshot.jsx`는 주요 지수/환율 페이지의 차트로 별도 기능이므로 이 계획의 기본 범위에서는 건드리지 않는다.
- 백엔드 API, DB, AI 리포트 생성 정책은 변경하지 않는다.
