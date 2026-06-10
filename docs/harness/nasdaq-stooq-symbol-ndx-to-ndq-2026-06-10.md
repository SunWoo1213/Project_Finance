# 나스닥 100 Stooq 심볼 `^ndx` → `^ndq` 변경

Date: 2026-06-10

## Objective

메인 대시보드의 나스닥 100 지수를 Stooq에서 가져올 때 사용하는 심볼을 `^ndx`에서 **`^ndq`** 로 바꾼다. Stooq에서 NASDAQ 100 지수의 정식 심볼은 `^ndq`이며, `^ndx`로는 CSV가 내려오지 않아 지수 카드가 비는 원인 중 하나였다.

내부 표준(canonical) 심볼은 기존대로 `^NDX`를 유지한다. 프론트엔드·config·chat 도구 등 다른 코드는 모두 `^NDX`를 그대로 쓰고, **Stooq로 요청을 보낼 때의 매핑값만** 변경한다.

## 변경 파일

| 파일 | 변경 |
| --- | --- |
| [backend/app/services/price_providers.py](../../backend/app/services/price_providers.py#L58) | `STOOQ_SYMBOLS`의 `"^NDX": "^ndx"` → `"^NDX": "^ndq"`. Stooq `s=` 파라미터가 `^ndq`로 전송된다. |
| [backend/tests/test_price_providers.py](../../backend/tests/test_price_providers.py#L339) | `test_ndx_history_uses_stooq_without_global_optin`의 `s == "^ndx"` 단언 → `"^ndq"` |
| [backend/tests/test_price_providers.py](../../backend/tests/test_price_providers.py#L367) | `test_ndx_snapshot_uses_stooq_without_global_optin`의 `provider_meta["symbol"] == "^ndx"` 단언 → `"^ndq"` |

## 동작 변화

- `fetch_market_history("^NDX", ...)` / `fetch_market_snapshot("^NDX", "INDEX")`가 Stooq에 `s=^ndq`로 요청한다.
- `STOOQ_PRIMARY_SYMBOLS = {"^NDX"}`, `FMP_SYMBOL_CANDIDATES`, `provider` 라우팅 등 나머지 로직은 불변. 내부/프론트 표시 심볼 `^NDX`도 불변.
- 표시 라벨·constants·chat 매핑은 영향 없음.

## 검증

- `cd backend` 후 `python -m pytest tests/test_price_providers.py -k ndx` → 3 passed.
  - 테스트 수집을 위해 임시 env(`PROJECT_NAME`, `API_V1_STR`, `DATABASE_URL=sqlite+aiosqlite:///./test.db`)만 주입. 시크릿은 출력·열람하지 않음.
- 미실행: 전체 `pytest`, 프론트 `npm run build`(이번 변경은 백엔드 심볼 매핑 1줄이라 프론트 표시 로직 변경 없음).
- 라이브 smoke(실 STOOQ_API_KEY로 `^ndq` CSV 수신 여부)는 배포 환경에서 1회 확인 필요. 키 한도/만료 시 빈 응답은 별도 키 운영 보완 계획([nasdaq-fx-stooq-key-resilience-plan-2026-06-10.md](nasdaq-fx-stooq-key-resilience-plan-2026-06-10.md)) 참고.

## 후속 위험

- `^ndq`로도 키 한도 소진 시 빈 본문이 오면 카드가 여전히 비어 보일 수 있다. 이는 심볼 문제가 아니라 키 운영 문제이며 위 키 운영 보완 계획에서 다룬다.
- Stooq가 `^ndq` 외 다른 표기를 요구하도록 정책을 바꾸면 이 매핑을 다시 조정해야 한다.

## Feature Links

- [docs/harness/features/market-data.md](features/market-data.md)
- [docs/harness/feature-index.md](feature-index.md)
- [docs/harness/nasdaq-index-stooq-primary-implementation-2026-06-09.md](nasdaq-index-stooq-primary-implementation-2026-06-09.md)
- [docs/harness/nasdaq-fx-stooq-key-resilience-plan-2026-06-10.md](nasdaq-fx-stooq-key-resilience-plan-2026-06-10.md)
