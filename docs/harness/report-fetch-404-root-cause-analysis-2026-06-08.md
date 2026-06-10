# 리포트 조회 404 근본 원인 분석 (코드 기준)

- 날짜: 2026-06-08
- 작성 목적: "리포트를 가져오면 404가 뜬다. 환경변수는 다 바꿔봤는데 해결이 안 된다"는 증상에 대해, 실제 코드 경로를 추적해 **404가 발생하는 정확한 조건**과 **환경변수로 해결되지 않는 이유**를 분류한다.
- 분류: 분석/진단 문서 (이 문서 자체는 코드를 변경하지 않는다)
- 대상 코드: `backend/app/main.py`, `backend/app/services/ai_service.py`, `backend/app/services/market_service.py`, `backend/app/core/config.py`, `frontend/src/pages/AssetDetail.jsx`

---

## 1. 결론 요약 (TL;DR)

리포트 404는 **라우트(주소) 불일치 문제가 아니다.** 프론트 요청 경로와 백엔드 라우트 경로는 정확히 일치한다.

404는 단 하나의 조건에서만 발생한다 — **요청한 ticker에 대한 `AIReport` 레코드가 DB에 없을 때.** ([main.py:505-506](../../backend/app/main.py#L505-L506))

그래서 진짜 질문은 "주소가 틀렸나?"가 아니라 **"왜 DB에 리포트가 없나?"** 이며, 원인은 크게 두 갈래다.

1. **(구조적) 리포트 생성 대상이 5개 티커뿐이다.** `DGS10, XAU, BTC-USD, NVDA, 005930.KS` 외의 자산은 스케줄러가 애초에 리포트를 만들지 않으므로 **영구적으로 404**다. ([config.py:129](../../backend/app/core/config.py#L129), [ai_service.py:945-950](../../backend/app/services/ai_service.py#L945-L950))
2. **(생성 실패) 대상 5개여도 생성이 실패하면 저장되지 않는다.** readiness blocked / 품질 게이트 실패 / provider 데이터 없음 등으로 예외가 나면 `db.rollback()` 되어 레코드가 남지 않고, 다음 조회는 404다. ([ai_service.py:984-1012](../../backend/app/services/ai_service.py#L984-L1012))

**환경변수를 다 바꿔도 해결이 안 되는 이유:** 위 두 원인 모두 단순 env 토글로는 풀리지 않는다. (1)은 "지금 보고 있는 티커가 대상 목록에 있는가"의 문제이고, (2)는 OpenAI 키·시장 데이터 provider 가용성·품질 루프 통과 여부의 문제다. `ENABLE_SCHEDULER`/`ENABLE_AI_REPORT_GENERATION`을 켜는 것은 **필요조건일 뿐 충분조건이 아니다.**

---

## 2. 요청 경로 추적 — 주소는 일치한다

### 프론트엔드 호출
[AssetDetail.jsx:117-119](../../frontend/src/pages/AssetDetail.jsx#L117-L119)
```javascript
const reportRes = await apiClient.get(`/api/reports/${encodeURIComponent(assetTicker)}`, {
  headers: authHeaders,
});
```
- base URL: `import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"` ([apiClient.js](../../frontend/src/utils/apiClient.js))
- `assetTicker`는 `/api/market/prices` 응답에서 `info.symbol === assetTicker`로 매칭된 값이다. ([AssetDetail.jsx:98-107](../../frontend/src/pages/AssetDetail.jsx#L98-L107))

### 백엔드 라우트
[main.py:490-506](../../backend/app/main.py#L490-L506)
```python
@app.get("/api/reports/{ticker}")
async def get_latest_report(ticker, current_user=Depends(require_report_access), db=...):
    query = (select(AIReport, Asset).join(Asset, AIReport.asset_id == Asset.id)
             .where(Asset.ticker == ticker).order_by(AIReport.created_at.desc()).limit(1))
    row = (await db.execute(query)).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No report found for ticker: {ticker}")
```

**경로(`/api/reports/{ticker}`), 메서드(GET), 인증 헤더 모두 일치한다.** 별도 라우터 없이 `main.py`에 직접 정의돼 있어 prefix 불일치 가능성도 없다.

### 시장 symbol ↔ 리포트 ticker 정렬 (오해하기 쉬운 부분)
프론트의 `assetTicker`는 시장 데이터의 `symbol`이고, 백엔드 조회는 `Asset.ticker`로 한다. 둘이 다르면 404가 날 수 있다. 그러나 대상 5개는 **일부러 일치하도록** 설계돼 있다.

- 금(Gold)은 실제 시세를 `GC=F`로 가져오지만 프론트로 내보내는 `symbol`은 `XAU`다. ([market_service.py:46](../../backend/app/services/market_service.py#L46), [market_service.py:50-54](../../backend/app/services/market_service.py#L50-L54), payload의 `symbol = payload["ticker"]` → [market_service.py:351-356](../../backend/app/services/market_service.py#L351-L356))
- 즉 5개 대상(`DGS10/XAU/BTC-USD/NVDA/005930.KS`)은 시장 `symbol`과 리포트 저장 `ticker`가 같다. **이 5개에 한해서는 symbol 불일치가 404 원인이 아니다.**

> 주의: 리포트 **읽기** 엔드포인트에는 별칭(alias) 정규화가 없다. 별칭(`GC=F→XAU`, `BTC→BTC-USD` 등)은 스케줄러 **쓰기** 쪽에서만 적용된다. ([ai_service.py:43-50](../../backend/app/services/ai_service.py#L43-L50), [ai_service.py:262](../../backend/app/services/ai_service.py#L262)) 따라서 만약 어떤 경로로 `Asset.ticker`가 시장 symbol과 다른 형태로 저장되거나, 대소문자/형식이 다른 ticker로 요청하면 읽기에서 404가 난다. (대상 5개 기본 경로에서는 발생하지 않지만, 커스텀 티커를 다룰 때의 잠재 위험으로 기록한다.)

---

## 3. 404가 발생하는 정확한 코드 조건

404는 [main.py:505-506](../../backend/app/main.py#L505-L506) 한 곳에서만 난다 → `row is None`, 즉 **해당 ticker의 `AIReport`가 0건.**

구분해야 할 다른 응답:
- **403** (`require_report_access`): 구독 등급이 Plus/Pro가 아니면 403. ([deps.py:74-84](../../backend/app/api/deps.py#L74-L84)) → 증상이 404라면 구독/권한 문제는 아니다.
- **라우트 404 vs 데이터 404**: FastAPI가 경로를 못 찾으면 본문이 `{"detail":"Not Found"}`이고, 데이터가 없을 때는 `{"detail":"No report found for ticker: ..."}`이다. **응답 본문의 detail 문자열로 둘을 반드시 구분**해야 한다. `VITE_API_BASE_URL`이 라우트가 없는 호스트를 가리키면 전자가 나온다.

---

## 4. 왜 DB에 리포트가 없을 수 있나 — 원인 분류

### 4.1 (구조적) 생성 대상이 5개 티커로 한정됨 — 가장 흔한 원인
- 기본 대상: `REPORT_SCHEDULER_TARGET_TICKERS = "DGS10,XAU,BTC-USD,NVDA,005930.KS"` ([config.py:129](../../backend/app/core/config.py#L129))
- coverage 정책이 `conservative`로 고정돼 있고, `conservative`가 아니어도 **정책상 광범위 생성은 비활성**이라고 경고만 찍고 넘어간다. ([config.py:121](../../backend/app/core/config.py#L121), [ai_service.py:945-950](../../backend/app/services/ai_service.py#L945-L950))
- 스케줄러는 `_configured_scheduled_report_tickers()`가 만든 자산만 순회한다. ([ai_service.py:951-955](../../backend/app/services/ai_service.py#L951-L955), [ai_service.py:277-301](../../backend/app/services/ai_service.py#L277-L301))

➡️ **결과:** `AAPL`, `TSLA`, `Ethereum`, `Silver`, KOSPI 개별 종목 등 **5개 대상 외의 어떤 자산을 열어도 항상 404**다. 이는 버그가 아니라 비용 보호용 의도된 동작이다(매뉴얼 생성도 막혀 있음 — [main.py:457-469](../../backend/app/main.py#L457-L469)).

### 4.2 (생성 실패) 대상 5개여도 저장이 안 됨
대상 티커라도 생성 파이프라인이 예외를 던지면 해당 자산은 `rollback`되어 레코드가 남지 않는다. ([ai_service.py:984-1012](../../backend/app/services/ai_service.py#L984-L1012)) 실패 유형:

- **readiness blocked** — 필수 시장 데이터 부족 시 `ReportReadinessError` → 미저장. ([ai_service.py:799-830](../../backend/app/services/ai_service.py#L799-L830)) 시장 캐시 miss면 per-ticker 캐시 fill을 시도하지만, 그래도 없으면 `No cached market data found` ValueError. ([ai_service.py:775-783](../../backend/app/services/ai_service.py#L775-L783))
- **품질 게이트 실패** — fact/format/qualitative 루프 소진 후 숫자 정제 폴백도 실패하면 `ReportQualityError` → 미저장. ([ai_service.py:877-896](../../backend/app/services/ai_service.py#L877-L896))
- **provider unavailable / 기타 예외** — 시장 provider 장애, OpenAI 호출 실패 등 일반 예외도 rollback. ([ai_service.py:1002-1012](../../backend/app/services/ai_service.py#L1002-L1012))
- LLM 그래프 호출(`graph_app.ainvoke`)이 동작하려면 **OpenAI 키가 유효**해야 한다. ([ai_service.py:872-873](../../backend/app/services/ai_service.py#L872-L873)) 키 누락/오류는 env로 키를 채우면 해결되지만, 키가 있어도 위 품질/데이터 사유로 실패할 수 있다.

➡️ 이 경로의 실패는 **`ENABLE_*` 토글이 아니라** 시장 데이터 가용성·OpenAI 키·품질 루프 통과 여부에 달려 있어, 단순 env 변경으로 해결되지 않는다. 본 저장소에 이미 누적된 분석 문서들이 이 경로를 다룬다(아래 9절).

### 4.3 (스케줄러 미발화/비활성) 생성 시도 자체가 없음
- `ENABLE_SCHEDULER`(기본 True)와 `ENABLE_AI_REPORT_GENERATION`(기본 True) 중 하나라도 False면 리포트 잡이 등록/실행되지 않는다. ([main.py:184-234](../../backend/app/main.py#L184-L234), [config.py:91](../../backend/app/core/config.py#L91), [config.py:120](../../backend/app/core/config.py#L120))
- 첫 발화는 기동 후 `REPORT_SCHEDULER_STARTUP_DELAY_SECONDS`(기본 60초) 뒤, 이후 `REPORT_SCHEDULER_INTERVAL_HOURS`(기본 6시간) 주기. ([main.py:218-227](../../backend/app/main.py#L218-L227), [config.py:122-128](../../backend/app/core/config.py#L122-L128))
- 회당 최대 5건(`REPORT_SCHEDULER_MAX_REPORTS_PER_RUN`), 6시간 쿨다운(`REPORT_SCHEDULER_ASSET_COOLDOWN_HOURS`) 이내 자산은 건너뜀. ([ai_service.py:958-975](../../backend/app/services/ai_service.py#L958-L975))
- sleep/재시작형 런타임(예: Render free)은 첫 발화 전에 인스턴스가 죽으면 한 번도 생성하지 못한다(이 위험을 줄이려 `next_run_time`으로 기동 직후 1회 발화를 명시해 둠 — [main.py:214-227](../../backend/app/main.py#L214-L227)).

➡️ 이 경로는 env로 켤 수 있으나, **켠 직후엔 DB가 비어 있다.** 첫 발화(기동 60초 후) → 생성 성공 → commit까지 끝나야 비로소 404가 사라진다. "env를 바꿨는데 바로 안 됐다"의 상당 부분이 이 타이밍이다.

### 4.4 프론트는 404를 정상 처리한다 (참고)
404를 받으면 프론트는 에러가 아니라 "예약 리포트 준비 중" 상태로 표시한다. ([AssetDetail.jsx:122-132](../../frontend/src/pages/AssetDetail.jsx#L122-L132)) 즉 화면상 "리포트 없음/준비 중" 표시는 위 1~3 원인의 정상적 귀결이다.

---

## 5. "환경변수를 다 바꿔도 안 되는" 이유 정리

| 시도한 env | 왜 그것만으로 안 풀리나 |
| --- | --- |
| `ENABLE_SCHEDULER`, `ENABLE_AI_REPORT_GENERATION` 켜기 | 생성 *시도*를 켤 뿐. 대상 외 티커는 여전히 영구 404(4.1), 생성 실패면 저장 안 됨(4.2). |
| `REPORT_SCHEDULER_TARGET_TICKERS`에 티커 추가 | 추가해도 해당 자산의 시장 데이터/품질 통과가 안 되면 4.2로 미저장. 또 프론트에서 그 자산을 여는 `symbol`과 저장 `ticker`가 일치해야 함. |
| `VITE_API_BASE_URL` 변경 | 라우트 404(detail="Not Found")라면 의미 있지만, 데이터 404(detail="No report found...")에는 무관. |
| 주기/지연 관련 env | 첫 발화 타이밍만 바꿀 뿐, 생성 성공 여부와 무관. |

핵심: **404를 푸는 것은 env가 아니라 "대상 티커 + 생성 성공 1건의 commit"이다.**

---

## 6. 확정 진단 절차 (권장 순서)

1. **응답 본문 확인** — 브라우저 Network 탭 또는 curl로 `/api/reports/<ticker>` 응답 detail을 본다.
   - `"No report found for ticker: X"` → 데이터 404. 4.1~4.3로 진행.
   - `"Not Found"` → 라우트/호스트 문제. `VITE_API_BASE_URL`과 배포 백엔드 라우팅 확인.
   - 403 → 구독 등급 문제(404 아님).
2. **DB에 리포트가 있나 확인** — `ai_reports` 테이블과 `assets.ticker` 조인 결과가 있는지 조회. 0건이면 생성이 한 번도 성공 안 한 것.
3. **테스트 중인 티커가 5개 대상인가** — `DGS10/XAU/BTC-USD/NVDA/005930.KS` 중 하나인지 확인. 아니면 4.1(설계상 404).
4. **백엔드 로그 확인** — `리포트 실패`, `failure_type=readiness_blocked`, `failure_type=quality_failed`, `failure_type=provider_unavailable`, `No cached market data found` 문자열을 찾는다([ai_service.py:984-1012](../../backend/app/services/ai_service.py#L984-L1012)). 어떤 단계에서 막혔는지 특정된다.
5. **스케줄러 발화 여부** — 기동 로그의 `[lifespan] scheduler started ... reports: in 60s then every 6 hours`와 `AI 리포트 생성 시작/종료`([main.py:281-285](../../backend/app/main.py#L281-L285), [ai_service.py:941](../../backend/app/services/ai_service.py#L941))를 확인. 미발화면 4.3.

---

## 7. 미실행/주의

- 이 문서는 진단만 수행했고 코드는 변경하지 않았다. 실제 환경 DB 조회·배포 로그 확인은 사용자 환경에서 실행해야 한다(시크릿 노출 방지를 위해 `.env`는 출력하지 않음).
- 매뉴얼 리포트 생성은 정책상 막혀 있으므로([main.py:457-469](../../backend/app/main.py#L457-L469)), 즉시 1건을 만들려면 스케줄러 발화를 기다리거나 별도 운영 절차가 필요하다.

## 8. 후속 위험 / 개선 여지 (제안, 미적용)

- 대상 외 티커의 404가 "버그처럼" 보이는 UX 문제는 프론트에서 이미 "준비 중"으로 완화돼 있으나, 사용자에게 "이 자산은 리포트 대상이 아님"을 명시하면 혼동이 준다.
- 읽기 엔드포인트에 별칭 정규화가 없으므로([main.py:496-499](../../backend/app/main.py#L496-L499)), 향후 시장 symbol과 다른 ticker 체계를 쓰게 되면 404 위험이 재발할 수 있다.

## 9. 관련 문서

- `docs/harness/report-404-and-secret-log-leak-remediation-implementation-2026-06-04.md`
- `docs/harness/nvda-report-factchecker-loop-root-cause-2026-06-04.md`
- `docs/harness/report-generation-scheduler-not-firing-log-audit-2026-06-08.md`
- `docs/harness/report-generation-pipeline-diagnosis-2026-06-08.md`
- `docs/harness/report-backend-generation-failure-analysis-2026-06-08.md`
- 기능 문서: `docs/harness/features/asset-detail-ai-community.md`
