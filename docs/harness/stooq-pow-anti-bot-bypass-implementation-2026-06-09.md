# Stooq proof-of-work anti-bot 대응 구현 (2026-06-09)

## 목적

`STOOQ_API_KEY`와 `ENABLE_STOOQ_FALLBACK` 등 환경변수를 모두 설정했는데도 나스닥 100(`^NDX`) 지수가 들어오지 않던 문제를 해결한다. 원인은 키가 아니라 stooq.com이 새로 추가한 **JavaScript proof-of-work(PoW) anti-bot 챌린지**였다.

## 근본 원인 (실측)

`https://stooq.com/q/d/l/?s=^ndx&i=d&apikey=<key>` 를 일반 HTTP 클라이언트(httpx)로 호출하면:

1. CSV가 아니라 **PoW 챌린지 HTML**이 반환된다(`status=200`, 본문은 `<script>...fetch("/__verify"...)`).
2. **apikey가 있어도 PoW를 우회하지 못한다**(32자 정상 키로도 동일하게 챌린지 HTML 반환).
3. 챌린지를 풀어(`SHA-256(c + nonce)`의 hex가 0 `d`개로 시작하는 최소 `nonce` 탐색) `https://stooq.com/__verify` 로 `c`, `n`을 POST하면 세션 쿠키가 발급되고, **같은 클라이언트로 apikey 요청을 재시도하면 그제서야 CSV가 내려온다**.

기존 [fetch_stooq_history](../../backend/app/services/price_providers.py)는 매 호출마다 새 `httpx.AsyncClient`(쿠키 미보존)로 단순 GET만 하던 `_get_text`를 사용해, 항상 챌린지 HTML만 받고 `_parse_stooq_csv`가 빈 결과를 돌려주고 있었다. 즉 키/플래그와 무관하게 Stooq 경로 전체가 막혀 있었다.

## 변경 파일

- `backend/app/services/price_providers.py`
  - `STOOQ_VERIFY_URL = "https://stooq.com/__verify"` 상수 추가.
  - 모듈 레벨 `_stooq_verify_cookies: dict[str, str]` 추가 — `/__verify` 통과 쿠키를 재사용해 매 호출 PoW 재계산을 피한다. stooq provider는 `Semaphore(1)`로 직렬화되어 race 없음.
  - `import hashlib` 추가.
  - `_parse_stooq_challenge(text)` — 응답이 PoW 챌린지면 `(challenge, difficulty)`, CSV면 `None`.
  - `_solve_stooq_challenge(challenge, difficulty, *, max_iterations=8_000_000)` — PoW nonce 탐색. 챌린지 포맷 이상으로 difficulty가 비정상적으로 커질 때를 대비한 상한 포함.
  - `_get_stooq_text(params, *, timeout)` — stooq 전용 fetch. 한 `AsyncClient`(쿠키 유지) 안에서 GET → 챌린지 감지 시 `asyncio.to_thread`로 PoW 풀이 → `/__verify` POST → 쿠키 저장 → 재 GET. 기존 `_get_text`와 동일하게 `_should_skip_failed_call`/`_mark_failed_call` 쿨다운을 적용.
  - `fetch_stooq_history`가 `_get_text` 대신 `_get_stooq_text`를 사용하도록 교체. 키 게이트(`STOOQ_API_KEY`, `STOOQ_PRIMARY_SYMBOLS`/`STOOQ_FX_SYMBOLS` 강제 경로, `ENABLE_STOOQ_FALLBACK`)는 그대로 유지.
- `backend/tests/test_price_providers.py`
  - `_get_text`를 mock하던 기존 stooq 테스트 6개를 `_get_stooq_text` mock으로 갱신(시그니처가 `(params, *, timeout)`로 바뀜).
  - `_parse_stooq_challenge`/`_solve_stooq_challenge` 단위 테스트 추가.
  - 가짜 `httpx.AsyncClient`로 챌린지 → `/__verify` → CSV 재시도 흐름을 재현하는 `test_get_stooq_text_solves_pow_then_returns_csv` 추가.

## 동작 변화

- `STOOQ_API_KEY`가 설정된 상태에서 `^NDX`/`KRW=X`(키만 있으면 강제) 및 `ENABLE_STOOQ_FALLBACK=true`인 기타 Stooq 경로가 PoW 벽을 자동으로 통과해 실제 일별 CSV를 가져온다.
- PoW 풀이는 CPU 바운드(difficulty=4 기준 평균 약 6.5만 회 SHA-256)지만 `asyncio.to_thread`로 이벤트 루프를 막지 않는다. 발급 쿠키 재사용으로 매 호출 재계산을 줄인다.
- 키가 없거나 폴백이 꺼진 비강제 심볼(예: `AAPL`, `ENABLE_STOOQ_FALLBACK=false`)은 기존과 동일하게 Stooq를 호출하지 않고 빈 history로 degrade.

## 검증

- `cd backend && .venv/Scripts/python.exe -m pytest tests/test_price_providers.py -q` → **44 passed**.
- 라이브 통합 확인(설정된 실제 키 사용, 키 값은 출력하지 않음):
  - `fetch_stooq_history("^NDX","1mo")` → 30 포인트, 최신 `2026-06-09 = 29514.617`.
  - `fetch_stooq_history("KRW=X","1mo")` → 30 포인트.
  - `fetch_market_snapshot("^NDX","INDEX")` → `currentPrice=29514.617`, `provider_meta.provider=stooq`.
  - `AAPL` → 0 포인트(강제 대상 아님 + 폴백 off로 정상 degrade).

## 후속 위험

- stooq.com이 PoW 챌린지의 **스크립트 포맷이나 검증 엔드포인트(`/__verify`)를 바꾸면** `_parse_stooq_challenge`의 정규식(`c="..."`, `,d=<n>`)과 `_get_stooq_text`의 POST가 깨질 수 있다. 그 경우 응답이 다시 챌린지 HTML로 남아 빈 history로 degrade한다(가격 0 고착이 아니라 폴백 경로로 빠짐).
- PoW difficulty가 크게 오르면 풀이 비용이 증가한다. 현재 `max_iterations=8_000_000` 상한으로 무한 루프는 방지하되, 초과 시 `RuntimeError`로 빠져 쿨다운 처리된다.
- 무료 apikey의 **일일 다운로드 한도**는 여전히 존재한다. 12시간 history 캐시로 호출을 줄이지만, 대상 심볼이 크게 늘면 한도 초과 시 `Get your apikey:` 응답으로 빈 결과가 될 수 있다.
- 사용자용 발급 절차는 루트 `STOOQ_APIKEY_GUIDE.md` 참고. apikey가 PoW를 우회하지 못한다는 점(본 구현으로 해소)도 거기에 기록돼 있다.

## 참고

- 사용자 가이드: `STOOQ_APIKEY_GUIDE.md` (루트)
- 관련: `docs/harness/nasdaq-index-stooq-primary-implementation-2026-06-09.md`, `docs/harness/krw-fx-change-percent-not-captured-implementation-2026-06-09.md`, `docs/harness/stooq-timeout-fallback-2026-06-07.md`
