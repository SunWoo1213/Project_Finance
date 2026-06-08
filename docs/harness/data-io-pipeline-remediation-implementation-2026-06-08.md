# 데이터 입출력 파이프라인 문제 해결 구현 기록

Date: 2026-06-08
Status: Implemented
Plan: `docs/harness/data-io-pipeline-remediation-plan-2026-06-08.md`
Feature:
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/deployment-runtime.md`

## 목적

시장 데이터 입출력 파이프라인에서 날짜, 기간 제한, provider metadata, AI 리포트 스케줄러 실패 관측성 문제를 해결했다. 사용자 화면과 챗봇은 계속 저장된 scheduled report만 조회하며, 이번 변경은 새 사용자발 리포트 생성 경로를 추가하지 않는다.

## 변경 파일

- `backend/app/services/price_providers.py`
- `backend/app/services/macro_service.py`
- `backend/app/main.py`
- `backend/app/services/ai_service.py`
- `backend/tests/test_price_providers.py`
- `backend/tests/test_market_history_route.py`
- `backend/tests/test_macro_service.py`
- `docs/harness/features/market-data.md`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/deployment-runtime.md`
- `docs/harness/feature-index.md`

## 동작 변경

1. `KRW=X` history fallback이 open.er-api.com의 RFC 날짜(`time_last_update_utc`)를 `YYYY-MM-DD`로 정규화한다.
2. data.go.kr `DATA_GO_KR_API_KEY`는 URL-encoded 값이어도 1회 `unquote()` 후 `httpx` params에 넣는다. 키 값은 로그나 문서에 출력하지 않는다.
3. data.go.kr stock/index history는 provider row를 정렬한 뒤 period limit을 적용한다. 최신순/비정렬 응답에서도 최근 N개 일간 point가 오름차순으로 반환된다.
4. `period=1d`의 daily point 정책을 7개로 통일했다. `1mo=30`, `1y=365`, `5y=1825`는 유지한다.
5. 미국 채권 history는 `fetch_us_bond_history()`를 통해 FRED observation `date`를 보존한다. `/api/market/history/DGS10` 계열은 더 이상 현재 날짜 기준으로 point 날짜를 재생성하지 않는다.
6. `/api/market/history/{ticker}`는 provider payload에 `provider_meta`가 있으면 optional field로 응답에 포함한다.
7. Stooq/data.go.kr/FRED history 경로에 최소 provider metadata를 붙였다.
8. scheduled AI report 실패 로그를 `readiness_blocked`, `quality_failed`, `provider_unavailable`, 기존 catch-all로 분류해 운영 로그에서 원인을 더 빨리 구분할 수 있게 했다.

## 검증

실행:

```powershell
cd backend
$env:PROJECT_NAME='test'; $env:API_V1_STR='/api'; $env:DATABASE_URL='sqlite+aiosqlite:///./test.db'; python -m pytest tests/test_price_providers.py tests/test_market_history_route.py tests/test_macro_service.py
```

결과: `38 passed`, warning 1개(`langchain_community` deprecation).

실행:

```powershell
cd backend
$env:PROJECT_NAME='test'; $env:API_V1_STR='/api'; $env:DATABASE_URL='sqlite+aiosqlite:///./test.db'; $env:COINGECKO_DEMO_API_KEY='test-key'; python -m pytest tests/test_ai_report_generation_switch.py tests/test_ai_report_quality_gate.py
```

결과: `36 passed`, warning 1개(`langchain_community` deprecation).

참고: 같은 AI 리포트 테스트를 `COINGECKO_DEMO_API_KEY` 없이 실행하면 기존 `external_api_service` 테스트가 `UNKNOWN-USD`를 `unsupported` 대신 `missing`으로 받아 실패한다. 이번 변경 범위 밖의 환경 의존 테스트 조건이므로 더미 키를 넣어 의도한 분기만 검증했다.

## 남은 리스크

- 실제 data.go.kr와 Stooq key가 있는 배포 환경에서 smoke가 필요하다.
- Naver 뉴스 scraping selector 변경 리스크는 이번 변경에서 직접 해결하지 않았다.
- `provider_meta`는 API 응답에 통과되지만 UI 노출은 아직 최소화되어 있다. 화면에 표시하려면 별도 UI 변경과 `npm run lint`, `npm run build` 검증이 필요하다.
- `report_generation_runs` 감사 테이블은 추가하지 않았다. DB schema 변경이므로 별도 승인과 migration 계획이 필요하다.

## 후속 작업

- provider key가 있는 staging에서 `/api/market/history/KRW%3DX?period=1d`, `/api/market/history/DGS10?period=1mo`, `/api/market/history/005930.KS?period=1mo` smoke를 수행한다.
- history metadata를 화면에 표시할지 제품 판단 후 별도 UI 작업으로 분리한다.
