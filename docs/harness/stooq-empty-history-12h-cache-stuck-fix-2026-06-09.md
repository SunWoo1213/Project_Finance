# Stooq 빈 history 12시간 캐시 고착 수정 (2026-06-09)

## 목적

카드는 유지되지만 나스닥(`^NDX`) 등 지수 값이 계속 0으로 나오는(=지수를 못 가져오는) 문제를 해결한다.

## 근본 원인

[fetch_stooq_history](../../backend/app/services/price_providers.py)는 CSV 파싱 결과가 비어도(`points == []`) 그 **빈 payload를 `_history_cache`에 `HISTORY_CACHE_TTL_SECONDS`(12시간) 동안 캐시**하고 있었다.

```python
if not points:
    _mark_failed_call(cache_key)      # 300s 쿨다운
return _cache_set(_history_cache, cache_key, payload)  # 빈 payload도 12h 캐시
```

즉 서버 기동 직후 첫 호출이 한 번이라도 일시적으로 실패하면(PoW 미통과, apikey 일일 한도, 네트워크 블립 등), 빈 결과가 12시간 캐시되어 이후 모든 호출이 같은 빈 값을 반환 → 지수 카드가 종일 0으로 고착됐다. 300s `_mark_failed_call` 쿨다운이 풀려도 12h 캐시가 그대로라 live 재시도가 일어나지 않았다.

> 검증: 동일 머신에서 `_get_stooq_text`로 `^ndx`/`usdkrw`/`^spx`를 직접 호출하면 모두 정상 CSV(예: `^ndx` 22,836행)가 내려온다. 즉 코드·키·네트워크는 정상이고, 문제는 "한 번 빈 결과가 12h 캐시되어 고착되는" 구조였다.

## 변경 파일

- `backend/app/services/price_providers.py` — `fetch_stooq_history`: `points`가 비면 빈 payload를 **캐시에 쓰지 않는다.** 300s 쿨다운만 걸고, 직전 유효값(stale)이 있으면 그것을 반환, 없으면 빈 payload를 캐시 없이 반환해 다음 수집 주기에 live 재시도하게 둔다. 정상(points 존재) 경로는 기존대로 12h 캐시.
- `backend/tests/test_price_providers.py`
  - `test_stooq_history_does_not_cache_empty_result`: 빈 결과가 `_history_cache`에 남지 않음을 검증.
  - `test_stooq_history_reuses_last_good_when_parse_empties`: 직전 유효값이 있으면 빈 파싱 시 그것을 유지함을 검증.

## 동작 변화

- Stooq fetch가 일시적으로 빈 결과를 줘도 더 이상 12시간 0으로 고착되지 않는다. 직전 유효값을 유지하거나, 다음 주기에 곧바로 재시도해 회복한다.
- 정상 데이터 수신·캐시 동작은 동일.

## 검증

- `cd backend && .venv/Scripts/python.exe -m pytest tests/test_price_providers.py tests/test_market_warmup_timeout.py -q` → **57 passed**.
- 라이브: `_get_stooq_text`로 `^ndx`/`usdkrw`/`^spx` 모두 CSV 정상, `fetch_stooq_history("^NDX")` 30 포인트.

## 후속 위험 / 확인 필요

- **이 수정은 "고착"을 푼다. 실제 fetch가 계속 실패하는 환경이면 값은 여전히 0이지만, 12h 고착 대신 매 주기 재시도하므로 조건이 회복되면 자동 복구된다.**
- 백엔드가 **배포 환경(Render 등 클라우드 IP)** 이면 stooq가 데이터센터 IP에 더 강한 anti-bot(해석 불가 챌린지/차단)을 줄 수 있다. 그 경우 PoW 통과가 안 돼 빈 결과가 반복될 수 있으므로, 로컬에서 정상이고 배포에서만 0이면 provider 대체(예: yfinance/다른 무료 소스)를 검토한다.
- 즉시 복구하려면 백엔드를 재시작해 12h 캐시를 비우거나, 다음 수집 주기를 기다린다.
- 동일한 "빈 결과 12h 캐시" 패턴이 `fetch_market_history`(차트 엔드포인트)와 `fetch_coingecko_history`/`fetch_data_go_*`에도 있다. 이번 수정은 카드(스냅샷)가 의존하는 `fetch_stooq_history`에 한정했다. 차트가 같은 증상을 보이면 동일 패턴으로 후속 적용한다.

## 참고

- `docs/harness/stooq-pow-anti-bot-bypass-implementation-2026-06-09.md`
- `docs/harness/market-card-disappear-on-fetch-failure-fix-2026-06-09.md`
