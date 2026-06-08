# 자산 표시 그래프 제거 구현

Date: 2026-06-08
Feature area: Market data, Asset detail
Plan: `docs/harness/asset-display-graph-removal-plan-2026-06-08.md`

## 목적

자산 목록과 자산 상세 화면에서 가격 그래프가 현재가, 등락률, 리포트, 뉴스/발표, 댓글 흐름보다 먼저 보이는 문제를 줄이기 위해 그래프 표시를 제거했다.

## 변경 파일

- `frontend/src/pages/CategoryView.jsx`
- `frontend/src/pages/AssetDetail.jsx`
- `frontend/src/pages/DEVELOPMENT_DIRECTION.md`
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/feature-index.md`
- `docs/harness/asset-display-graph-removal-implementation-2026-06-08.md`

## 동작 변경

- `CategoryView.jsx`는 더 이상 `SparklineChart`를 import하거나 자산 카드 중간에 `history_prices` 기반 미니 그래프를 렌더링하지 않는다.
- 자산 목록 카드는 자산명, 티커, 현재가, 등락률 배지, 시가총액/거시 지표 배지, 즐겨찾기 버튼 중심의 텍스트형 표시로 유지된다.
- `AssetDetail.jsx`는 더 이상 `recharts`를 import하지 않고, `/api/market/history/{ticker}`를 호출하지 않는다.
- 상세 화면의 기간 선택 버튼과 상단 가격 차트 카드가 제거되어 현재가/등락률/시가총액 또는 거시 지표 배지 다음에 최신 뉴스와 발표 섹션이 이어진다.
- `MarketSnapshot.jsx`는 계속 `recharts`와 `GET /api/market/history/{ticker}`를 사용하므로 `recharts` 의존성은 제거하지 않았다.
- `frontend/src/components/SparklineChart.jsx`는 삭제하지 않고 보존했다. 현재 직접 참조는 없지만 파일 삭제는 별도 확인이 필요한 정리 작업으로 남긴다.

## AI 리포트 생성 영향

사용자-facing 요청은 계속 저장된 예약 리포트만 읽는다. 이번 변경은 상세 화면의 가격 차트 표시와 history API 호출만 제거하며, AI 리포트 생성 cadence, scheduler coverage, cooldown, chatbot report response, manual generation endpoint를 변경하지 않는다.

## 검증

- 예정: `cd frontend; npm run lint`
- 예정: `cd frontend; npm run build`

## 후속 위험

- `SparklineChart.jsx`가 미사용 파일로 남아 있다. 삭제하려면 참조 재확인 후 별도 승인 또는 명시 요청에 따라 제거한다.
- 실제 브라우저에서 `/category/...`와 `/detail/:ticker` 반응형 레이아웃을 확인하면 즐겨찾기 버튼과 가격 영역의 겹침 여부를 더 확실히 볼 수 있다.
