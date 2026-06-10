# 나스닥(^NDX) 미표시 · USD/KRW 등락 미표시 원인 분석 및 stooq 키 운영 보완 계획

Date: 2026-06-10

## Objective

메인 대시보드에서 **나스닥 100(`^NDX`)이 통째로 안 나오고**, **USD/KRW는 현재가만 나오고 전일 대비 등락이 안 나오는** 문제의 근본 원인을 정리하고, 사용자가 호소한 **"stooq apikey를 매번 수동으로 교체해야 하는"** 운영 부담을 줄이는 방안을 세운다.

사용자 결정(2026-06-10):
- **데이터 소스: stooq 유지 + 운영 보완** (provider를 Alpha Vantage 등으로 교체하지 않는다)
- **나스닥 표시: 실제 지수값(`^NDX`) 유지** (QQQ ETF 프록시로 대체하지 않는다)

따라서 본 계획은 provider 교체가 아니라, **stooq 키가 죽었을 때 (1) 빨리·명확히 감지하고, (2) 운영자에게 재발급 신호를 주고, (3) 화면이 직전 유효값으로 더 오래 버티게** 만드는 운영 견고화에 집중한다. 새 외부 API·새 유료 키는 추가하지 않는다.

## 근본 원인 (코드 실측 기반 확정)

세 증상의 뿌리는 **모두 동일하게 stooq 무료 apikey 의존**이다.

### 1) USD/KRW는 현재가만 살아있는 이유
- 현재가는 `open.er-api.com`(무료·무인증)에서 가져온다 → stooq와 무관하게 항상 표시됨.
  - [_fetch_fx_snapshot](../../backend/app/services/price_providers.py#L753) (`live_rate = rates["KRW"]`)
- **등락(`changePercent`)은 stooq 일별 종가(`usdkrw`)로만 계산**한다. open.er-api는 전일 종가를 주지 않기 때문.
  - [_fetch_fx_snapshot](../../backend/app/services/price_providers.py#L762-L797)
- 즉 stooq가 비면 → 현재가는 남고 **등락만 0으로 사라진다.** (= 사용자가 본 증상 그대로)

### 2) 나스닥(^NDX)이 통째로 사라지는 이유
- `^NDX`는 가격·등락·history를 **전부 stooq에서만** 가져온다. FMP free/stable이 지수를 못 주기 때문에 `STOOQ_PRIMARY_SYMBOLS = {"^NDX"}`로 stooq 1차 고정.
  - [_fetch_stooq_snapshot](../../backend/app/services/price_providers.py#L970), [fetch_market_snapshot INDEX 분기](../../backend/app/services/price_providers.py#L1213-L1222)
- 대체 소스가 없으므로 stooq가 비면 → `currentPrice=0` → 카드 전체가 사라진다.

### 3) "키를 매번 수동 교체해야 한다"의 정체
- stooq 무료 apikey의 한계(루트 [STOOQ_APIKEY_GUIDE.md](../../STOOQ_APIKEY_GUIDE.md) §5에 기록):
  - **캡차로 사람이 브라우저에서 직접 발급** → 자동 갱신 불가.
  - **무료 키는 일일 다운로드 한도**가 있다. 한도를 넘으면 응답이 CSV가 아니라 **`Get your apikey:`** 빈 메시지 → [_parse_stooq_csv](../../backend/app/services/price_providers.py#L881-L882)가 빈 결과 반환.
- 어제(2026-06-09) PoW anti-bot 우회는 구현·실측 검증되어 동작했다(`stooq-pow-anti-bot-bypass-implementation-2026-06-09.md`). 그러므로 **오늘 다시 안 나오는 직접 원인은 코드 회귀가 아니라 키 한도 소진/만료(또는 프로세스 재시작으로 인한 콜드 캐시)** 가 유력하다.
  - 확인: PoW 수정 이후 커밋(`지수 변경`=빈 history 캐시 고착 수정, `메인대쉬보드 그래프 삭제`)은 provider 라우팅을 회귀시키지 않았다.

### 라이브 실측 결과 (2026-06-10, 키 없이 실제 stooq 호출)
코드 경로(`_get_stooq_text`)를 그대로 태워 `^ndx` CSV를 요청한 결과:
- GET1 → **PoW 챌린지 HTML(796B)**. `_parse_stooq_challenge`가 **정상 파싱(difficulty=4)** → 정규식·코드는 깨지지 않았다.
- 챌린지 스크립트 원문 확인: `SHA-256(c+n)` 풀이 → `POST /__verify` (`c`,`n`) → `if(r.ok) location.reload()`. **우리 코드 흐름과 100% 동일.**
- `POST /__verify` → **`ok` + `auth` 쿠키(Max-Age 86400) 발급** → **PoW 검증은 지금도 성공한다.**
- 검증 후 재요청(GET2) → **HTTP 200 + 빈 본문('')**. 챌린지 HTML이 아니므로 쿠키는 수용됨. 키 없음/가짜키 모두 동일하게 빈 응답.
- **핵심 변화**: 예전엔 키 없으면 `Get your apikey:` **텍스트**가 왔는데, **지금은 빈 본문**으로 바뀌었다. 즉 `/q/d/l/`은 **유효 apikey가 있어야 CSV를 주고, 없으면/만료/한도초과면 빈 200**을 준다.

### 결론 — "지금 왜 안 가져오나"
**PoW/verify 코드는 정상이다.** 못 가져오는 직접 원인은 **유효한 `STOOQ_API_KEY`로 CSV가 내려오지 않기 때문**이다(키 미설정/만료/한도소진). stooq가 빈 본문을 주고 → `_parse_stooq_csv`가 빈 포인트 → `^NDX` 0, `KRW=X` 등락 0. **배포 환경에서 실제 키로 CSV가 오는지 서버에서 1회 확인이 반드시 필요**하다(아래 1단계).

### 현재 코드가 키 소진을 다루는 방식의 빈틈
- stooq가 이제 키 문제를 **빈 본문**으로 알려주므로, `_parse_stooq_csv`의 `"Get your apikey" in text` 분기는 더 이상 트리거되지 않는다. `Get your apikey`(구버전)와 **빈 본문(현 버전)** 을 모두 키 소진 신호로 분류해야 한다.
- 빈 결과는 12h 캐시에 쓰지 않고 300s 쿨다운만 거는 보정([fetch_stooq_history](../../backend/app/services/price_providers.py#L933-L956))이 이미 있어, **프로세스가 한 번이라도 유효값을 받았다면** 직전값을 유지한다.
- 그러나 **콜드 스타트(재배포 직후) + 키 사망** 조합에서는 직전 유효값이 메모리에 없어 그대로 0/빈값으로 굳는다. `_history_cache`/`_snapshot_cache`는 in-memory라 재시작 시 사라진다.

## 현재 동작 / 목표 동작

| 항목 | 현재 | 목표 |
| --- | --- | --- |
| ^NDX 표시 | 키 소진 시 카드 사라짐 | 실제 지수값 유지. 직전 유효값으로 더 오래 버팀 |
| USD/KRW 등락 | 키 소진 시 0으로 사라짐 | 키 살아있으면 표시. 콜드 캐시여도 직전값 유지 |
| 키 소진 감지 | 빈 결과와 구분 안 됨(조용히 degrade) | `Get your apikey:`/PoW 실패를 **명시적으로 분류·로깅** |
| 운영자 인지 | 로그를 직접 뒤져야 함 | 읽기전용 provider 상태 신호 제공(키 값 비노출) |
| 키 수동 교체 | 한도 소진 때마다 캡차 재발급 | (근본 제거는 불가) 호출량 최소화로 한도 여유 확보 + 재발급 시점 명확화 |

> 한계 인정: stooq 무료 키의 **캡차 재발급 자체는 자동화할 수 없다**(stooq 정책). 본 계획은 재발급 빈도를 낮추고(호출 최소화), 재발급이 필요한 순간을 명확히 알리며, 그동안 화면이 무너지지 않게 하는 것이 목표다. 키 교체를 0으로 만들지는 못한다.

## 변경 대상 파일

| 구분 | 파일 | 변경 |
| --- | --- | --- |
| backend (핵심) | `backend/app/services/price_providers.py` | stooq 응답을 `csv` / `apikey_exhausted`(`Get your apikey`) / `pow_challenge` / `empty`로 분류. 모듈 레벨 `_stooq_key_status`(상태+timestamp) 갱신. 키 소진 시 actionable WARNING 로깅 |
| backend (운영 신호) | `backend/app/main.py` (또는 신설 `backend/app/api/market.py`) | 읽기전용 `GET /api/market/provider-health` 추가 — `{stooq: {status, last_ok, last_checked}}`만 노출, **키 값·시크릿 비노출** |
| backend (옵션) | `backend/app/services/notification_service.py` | (옵션) alive→exhausted 전이 1회 운영자 Telegram 알림. 일 1회 throttle. 현재 working tree에서 수정 중이므로 충돌 주의 → 별도 단계로 분리 |
| 설정(기본값 유지) | `backend/app/core/config.py` | 변경 없음 권장. `ENABLE_STOOQ_FALLBACK=false` 유지로 stooq 호출을 `^NDX`·`KRW=X` 2심볼로 제한해 일일 한도 여유 확보 |
| test | `backend/tests/test_price_providers.py` | `Get your apikey` 응답 → `apikey_exhausted` 분류/상태/로깅 단위 테스트. 콜드 캐시+소진 시 직전값 유지 테스트 |
| 문서(가이드) | `STOOQ_APIKEY_GUIDE.md` | "한도 소진 증상 = 나스닥/달러등락만 사라짐", provider-health로 상태 확인하는 법, 재발급 절차 재안내 보강(시크릿 미기재) |
| 문서(기능) | `docs/harness/features/market-data.md`, `docs/harness/feature-index.md` | 키 소진 감지·상태 신호 동작 명시 및 구현 기록 링크 추가 |

## 단계별 구현 계획

### 1단계 — 즉시 조치 (운영, 코드 변경 없음 / 사용자·배포 담당)
지금 안 나오는 직접 원인 해소.
1. 현재 stooq 키 생존 확인: 앱 경로로 `fetch_stooq_history("^NDX","1mo")` / `fetch_stooq_history("KRW=X","1mo")`를 실행해 포인트가 들어오는지 본다(키 값은 출력하지 않는다). PoW 때문에 단순 curl은 챌린지 HTML이 올 수 있으므로 **앱 경로**로 확인한다(가이드 §5).
2. 빈 결과면 [STOOQ_APIKEY_GUIDE.md](../../STOOQ_APIKEY_GUIDE.md) §2 절차로 **캡차 재발급 → `.env`의 `STOOQ_API_KEY` 교체 → 백엔드 재기동**.
3. `ENABLE_STOOQ_FALLBACK`는 **false 유지**(stooq 호출을 2심볼로 묶어 한도 여유 확보).

### 2단계 — 키 소진 명시적 감지 + 상태 추적 (backend 핵심)
- `_parse_stooq_csv` 또는 `_get_stooq_text`에서 응답 본문을 분류:
  - `Get your apikey` 포함 **또는 PoW 검증 성공 후 빈 본문** → `apikey_exhausted` (2026-06-10 실측: stooq가 키 없음/만료/한도초과를 빈 200으로 응답)
  - `_parse_stooq_challenge`가 non-None인데 verify 후에도 다시 챌린지 → `pow_challenge`(포맷 변경 의심)
  - 헤더가 `Date,Open,...`로 시작 → `csv`
  - 그 외 빈 → `empty`
- 모듈 레벨 `_stooq_key_status = {"status": ..., "last_ok": ts, "last_checked": ts}` 갱신(stooq provider는 `Semaphore(1)`로 직렬화되어 race 없음 — 기존 `_stooq_verify_cookies` 패턴과 동일).
- `apikey_exhausted` 전이 시 한 번만 `logger.warning("STOOQ_API_KEY exhausted/invalid — reissue via STOOQ_APIKEY_GUIDE.md")` (시크릿 미포함, `redact_secrets` 경유).

### 3단계 — 읽기전용 provider 상태 엔드포인트 (운영 가시성)
- `GET /api/market/provider-health` → `{"stooq": {"status": "csv|apikey_exhausted|pow_challenge|empty|unknown", "last_ok": iso, "last_checked": iso}}`.
- **키 값·`.env`·시크릿은 절대 반환하지 않는다.** 상태 문자열과 타임스탬프만.
- 운영자가 "나스닥/달러등락이 안 보일 때" 이 엔드포인트만 보고 재발급 필요 여부를 즉시 판단.

### 4단계 — 콜드 캐시 견고화 (선택, 범위 작게)
- 우선은 기존 in-memory stale 유지(이미 구현됨)로 충분한지 1·2단계 적용 후 관찰.
- 재배포 직후 키 사망으로 카드가 비는 경우가 반복되면, `^NDX`·`KRW=X` **직전 유효 일별 종가만** 가벼운 영속 저장(파일 캐시 또는 소형 테이블)으로 보존하는 후속을 검토. **DB 스키마 추가는 Risky Change(아래)** 이므로 별도 승인 후 진행.

### 5단계 — 운영자 알림 (옵션)
- alive→exhausted 전이 시 기존 `notification_service`로 운영자에게 1회(일 1회 throttle) Telegram/메일 알림. 사용자 향이 아니라 운영자 향. `notification_service.py`가 현재 working tree에서 수정 중이므로 **충돌을 피해 마지막 단계로 분리**하고, 진행 여부는 사용자 확인 후 결정.

## 위험과 Risky Change 여부 (AGENTS.md 섹션 9)

- **2·3단계(감지·상태 엔드포인트)**: 가격 데이터 라우팅·우선순위를 바꾸지 않는다. DB·인증·리포트 비용과 무관. provider 호출 패턴 불변. → **저위험**.
- **provider-health 엔드포인트의 시크릿 비노출**: 키 값/`.env`/토큰을 응답에 절대 포함하지 않도록 구현·테스트로 보장(AGENTS.md 섹션 8). 상태 문자열·타임스탬프만.
- **4단계 영속 저장에서 DB 테이블 신설 시**: 스키마 변경 = **Risky Change → 사용자 승인 필요**. 우선 파일 캐시/관찰로 대체하고, DB가 필요해지면 별도 계획·승인.
- **5단계 운영자 알림**: 알림 동작 변경 + `notification_service.py` working tree 수정과 충돌 가능 → **옵션, 사용자 확인 후 진행**.
- **`ENABLE_STOOQ_FALLBACK` 전역 활성화는 비권장**: 켜면 STOCK_US 종가 등 다른 경로까지 stooq를 호출해 **일일 한도를 더 빨리 소진**시켜 사용자가 호소한 "수동 교체" 문제를 악화시킨다. false 유지가 핵심.
- **AI 리포트**: 본 변경은 스케줄·cooldown·생성 트리거를 건드리지 않는다(AGENTS.md 섹션 14 무관). 사용자/챗봇은 저장된 리포트만 읽는다.
- 비용: 새 유료 API 없음. stooq는 무료 daily CSV. 호출량은 오히려 2심볼로 제한 유지.

## 검증 계획 (AGENTS.md 섹션 6, 최소 집합)

1. 정적 확인
   - `rg -n "Get your apikey|_parse_stooq_csv|_get_stooq_text|_stooq_key_status|provider-health" backend/app/services/price_providers.py backend/app/main.py`
2. 백엔드 단위 테스트 (실 LLM·실 네트워크 없이 mock — AGENTS.md 섹션 4)
   - `cd backend`
   - `pytest tests/test_price_providers.py`
   - 추가: `Get your apikey` 응답 → `apikey_exhausted` 분류·상태·WARNING 로깅 / CSV 응답 → `csv` 상태 / 콜드 캐시+소진 시 직전값 유지.
3. 라이브 smoke (실키 필요, 키 값 비출력)
   - 앱 경로로 `fetch_stooq_history("^NDX","1mo")`·`fetch_stooq_history("KRW=X","1mo")` 포인트 확인.
   - `GET /api/market/provider-health` → stooq `status` 확인(시크릿 미노출 확인).
   - `GET /api/market/prices`의 `macro`에서 `^NDX` `currentPrice`≠0, `KRW=X` `changePercent`≠0 확인.
   - frontend `/`에서 Nasdaq 100 카드 표시 및 USD/KRW 등락 표시 확인.
4. 프런트 영향 시 `cd frontend && npm run build` (이번 변경은 백엔드 위주라 표시 로직 변경 없으면 생략 가능).
5. 미실행/보호
   - 본 단계는 계획서 작성만 — 테스트/빌드/실 provider 호출 미실행.
   - `.env`·`STOOQ_API_KEY` 등 시크릿은 열람·출력하지 않음.

## 갱신할 문서

- `docs/harness/features/market-data.md`
  - "stooq 키 소진(`Get your apikey`) 명시적 감지·상태 추적, `GET /api/market/provider-health` 읽기전용 상태 신호, `ENABLE_STOOQ_FALLBACK=false` 유지로 호출량 제한" 추가. 구현 기록 링크를 `Change Records`에 연결.
- `docs/harness/feature-index.md`
  - Market data 변경 기록에 본 계획 및 후속 구현 기록 연결.
- `STOOQ_APIKEY_GUIDE.md`
  - "나스닥/달러등락만 사라지면 키 한도 소진 신호", provider-health로 확인하는 법, 재발급 절차 재안내 보강(시크릿 미기재).

## Feature Links

- `docs/harness/features/market-data.md`
- `docs/harness/feature-index.md`
- `docs/harness/stooq-pow-anti-bot-bypass-implementation-2026-06-09.md`
- `docs/harness/nasdaq-index-stooq-primary-implementation-2026-06-09.md`
- `docs/harness/krw-fx-change-percent-not-captured-implementation-2026-06-09.md`
- `docs/harness/stooq-empty-history-12h-cache-stuck-fix-2026-06-09.md`
- `STOOQ_APIKEY_GUIDE.md`
