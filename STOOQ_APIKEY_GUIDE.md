# Stooq apikey 발급 및 연결 가이드

> **2026-06-10 업데이트 — Stooq는 라이브 기본 경로에서 더 이상 사용하지 않는다.**
> Stooq 무료 apikey CSV 경로가 막혀(새 키로도 모든 심볼이 빈 200 응답, PoW는 성공) 신뢰할 수 없게 되었다.
> - **나스닥 지수**는 FRED NASDAQ Composite(`NASDAQCOM`, 티커 `^IXIC`)로 이전했다(`FRED_API_KEY` 사용).
> - **USD/KRW 등락 표시**는 삭제했다(현재가만 open.er-api에서 제공, 등락 미표시).
> 따라서 `STOOQ_API_KEY` 수동 교체는 더 이상 필요하지 않다. Stooq 코드는 `ENABLE_STOOQ_FALLBACK`(기본 false) 게이트의 휴면 fallback으로만 남아 있다.
> 구현 기록: [docs/harness/nasdaq-composite-fred-source-implementation-2026-06-10.md](docs/harness/nasdaq-composite-fred-source-implementation-2026-06-10.md)

이 문서는 `Project_Finance` 백엔드의 (현재는 휴면) 시세 폴백 소스인 **Stooq**를 연결하기 위한 절차를 정리한다.
관련 코드: [backend/app/services/price_providers.py](backend/app/services/price_providers.py)

## 1. 핵심 요약

- Stooq는 **개발자 포털에서 이메일로 발급받는 일반 API 키가 없다.** 대신 캡차로 받는 **계정/발급 단위 `apikey` 토큰**을 쓴다.
- 이 `apikey`는 **심볼별이 아니다.** 한 번 발급받으면 AAPL, ^NDX, USDKRW 등 모든 심볼을 같은 키 하나로 가져온다.
- 과거에 통하던 "키 없이 CSV 다운로드"는 현재 막혀 있다. Stooq가 다음 두 겹의 벽을 추가했다.
  1. **JavaScript proof-of-work(PoW) anti-bot 챌린지** — curl/httpx/requests 같은 일반 HTTP 클라이언트는 CSV 대신 챌린지 HTML을 받는다.
  2. PoW를 넘어도 익명 일일 쿼터가 막혀 **`Get your apikey:` 메시지**를 반환한다 → `apikey` 필요.

> 실측(2026-06): `https://stooq.com/q/d/l/?s=aapl.us&i=d` 를 키 없이 호출하면 PoW HTML이 오고, PoW를 풀어도 `Get your apikey:` 가 반환됨. `stooq.pl` 도 동일.

## 2. apikey 발급 절차

1. **브라우저로** 아래 주소에 접속한다. (서버/스크립트가 아니라 사람이 브라우저에서 해야 한다 — 캡차 때문)

   ```
   https://stooq.com/q/d/?s=aapl.us&get_apikey
   ```

   - `s=aapl.us` 는 캡차 페이지를 띄우기 위한 예시 심볼일 뿐이다. 어떤 심볼이어도 상관없다.

2. 화면의 **캡차 코드**를 입력한다.

3. 페이지 **하단의 CSV 다운로드 링크**를 확인한다. 링크 안에 `&apikey=...` 형태로 **발급된 키 값**이 박혀 있다. 그 키 값만 복사한다.

   - 예: `https://stooq.com/q/d/l/?s=aapl.us&i=d&apikey=XXXXXXXX` → 여기서 `XXXXXXXX` 부분.

4. 발급은 **딱 한 번**이면 된다. 이후 모든 심볼은 `s=` 파라미터만 바꿔가며 같은 키를 재사용한다.

## 3. 프로젝트에 키 적용

발급받은 키를 백엔드 `.env` 에 넣는다. (`.env` 는 절대 커밋하지 않는다.)

```dotenv
STOOQ_API_KEY=발급받은키값

# 폴백을 전역으로 켜려면(US 주식 종가 등 기타 경로 포함):
ENABLE_STOOQ_FALLBACK=true
```

관련 설정: [backend/app/core/config.py](backend/app/core/config.py) — `STOOQ_API_KEY`, `ENABLE_STOOQ_FALLBACK`, `STOOQ_FETCH_TIMEOUT_SECONDS`.

참고: 다음 심볼은 `ENABLE_STOOQ_FALLBACK` 이 꺼져 있어도 `STOOQ_API_KEY` 만 있으면 Stooq에서 가져온다.
- `^NDX` — [STOOQ_PRIMARY_SYMBOLS](backend/app/services/price_providers.py#L74)
- `KRW=X` (USD/KRW) — [STOOQ_FX_SYMBOLS](backend/app/services/price_providers.py#L79)

## 4. 연결 검증

키를 넣은 뒤, 실제로 CSV가 내려오는지(= apikey가 PoW 벽까지 우회하는지) 확인한다.

```powershell
# 백엔드 가상환경 파이썬으로 직접 호출 (PowerShell)
cd backend
.venv\Scripts\python.exe -c "import httpx, os; print(httpx.get('https://stooq.com/q/d/l/', params={'s':'aapl.us','i':'d','apikey':os.environ['STOOQ_API_KEY']}, headers={'User-Agent':'Mozilla/5.0'}, timeout=15).text[:200])"
```

판정:
- 응답이 `Date,Open,High,Low,Close,Volume` 로 시작 → **정상 연결됨.**
- 응답이 `Get your apikey:` → 키가 비었거나 잘못됨 / 쿼터 초과.
- 응답이 `<!DOCTYPE html>...__verify...` → apikey가 PoW를 우회하지 못함. 이 경우 코드에 PoW 해결 단계 추가가 필요하다(아래 5번).

서비스 레벨 검증은 캐시·폴백 경로까지 확인:

```powershell
cd backend
pytest tests/test_price_providers.py
```

## 5. 주의사항 및 한계

- **무료 apikey는 일일 다운로드 횟수 제한이 있다.** 종목이 많으면 한도를 넘길 수 있다. 현재 코드는 [HISTORY_CACHE_TTL_SECONDS](backend/app/services/price_providers.py#L35)(12시간 캐시)로 호출을 줄이므로 대상 종목이 십수 개 수준이면 보통 괜찮다.
- **apikey는 PoW 벽을 우회하지 못한다.** 그래서 백엔드는 [_get_stooq_text](backend/app/services/price_providers.py)에서 PoW를 자동으로 푼다(SHA-256 nonce 탐색 → `/__verify` POST → 세션 쿠키 재사용 → apikey로 재요청). 따라서 위 4번 직접 호출 예시에서 `__verify` HTML이 오더라도, **앱을 통한 fetch는 정상 동작**한다. 직접 검증하려면 PoW를 함께 풀어야 한다. 구현 기록: `docs/harness/stooq-pow-anti-bot-bypass-implementation-2026-06-09.md`.
- 키가 노출되면(채팅/로그/커밋) 즉시 폐기로 간주하고 재발급한다. 키는 `.env` 환경변수로만 둔다.

## 6. 대안

Stooq 연결이 불안정하면 다음 경로로 대체할 수 있다. 프로젝트는 이미 멀티 프로바이더 구조다.
- 지수/종가 보강을 FMP·Finnhub·data.go.kr 등 기존 프로바이더로 분산.
- `^NDX`/USDKRW 보강을 yfinance 등 다른 공개 소스로 교체.

---

최종 업데이트: 2026-06-09
