# 챗봇 데이터 정확성 향상 파이프라인 구현 (Phase 1~2)

- 날짜: 2026-06-08
- 작성 단계: implementation (Phase 1~2만 구현, Phase 3~5 보류)
- 대상 기능: Chatbot assistant (`docs/harness/features/chatbot-assistant.md`)
- 계획 문서: `docs/harness/chatbot-data-accuracy-versatility-pipeline-plan-2026-06-08.md`
- 관련 규칙: `AGENTS.md` 섹션 4, 9, 11, 12, 13, 14

> **구현 범위**: 사용자 승인에 따라 계획서의 **Phase 1(엔티티 해석 정확도)**과 **Phase 2(공통 근거 조립 + guard)**만 구현했다. Phase 3(도구 호출 LLM 파이프라인), Phase 4(범용성), Phase 5(관측·비용 가드)는 보류했으며 진행하려면 별도 승인이 필요하다(LLM 비용 증가 영역).

## 1. 목적 (Objective)

챗봇 답변의 **데이터 정확성**을 LLM 비용 증가 없이 향상한다.

- 더 많은 종목 별칭·흔한 오타를 정확히 해석하고, 금융 게이트(`is_financial_query`)를 통과시킨다.
- 시세 근거의 캐시 키 불일치를 한 곳에서 흡수하고, 통화·기준시각을 동반해 규칙 경로와 LLM 경로가 동일 수치를 쓰도록 일원화한다.
- LLM이 근거에 없는 수치를 말하면 경고 문장과 신뢰도 하향으로 환각 노출을 완화한다.

`AGENTS.md` 섹션 14의 절대 원칙은 유지한다: 챗봇은 저장된 스케줄 리포트만 읽고, 어떤 경로로도 리포트를 생성하지 않는다. 신규 근거 조립·guard는 전부 읽기 전용이며 신규 외부 네트워크 호출이 없다.

## 2. 변경 파일 (Files changed)

### 백엔드 (backend/)

1. `backend/app/services/chat_tools.py`
   - `_asset_aliases()` 사전 확장: 미커버 KR_TOP10(`373220.KS` LG에너지솔루션/엘지엔솔, `207940.KS` 삼성바이오로직스/삼바, `068270.KS` 셀트리온, `005490.KS` 포스코/포스코홀딩스, `035420.KS` 네이버, `105560.KS` KB금융/케이비금융/국민은행)와 US 종목(`BRK-B` 버크셔, `LLY` 일라이릴리/릴리, `AVGO` 브로드컴)의 한/영 별칭·흔한 오타(테스라 등) 추가.
   - `is_financial_query()` 보강: 기존 FINANCIAL_KEYWORDS·티커 외에 자산 alias 사전(name·alias)과 `find_category` 매칭도 금융 질문으로 인정. 금융 판정과 엔티티 해석을 일원화해 새 alias가 non_financial로 거절되지 않도록 함.
2. `backend/app/services/chat_grounding.py` (신규)
   - 캐시/저장데이터 기반 공통 근거 조립기. 외부 신규 네트워크 호출 없음.
   - `asset_snapshot(ticker)`: `market_cache["prices"]`에서 `price`/`close`/`currentPrice`, `changePercent`/`change_pct` 키 드리프트를 한 곳에서 흡수해 `{ticker,name,price,change_pct,currency,as_of}` 반환. `currency`는 티커/그룹으로 추론(`.KS`→KRW, US/crypto→USD, 국채→%).
   - `asset_snippet(ticker)`: 통화·기준시각 포함 한 줄 요약(기존 `chat_service._cached_market_snippet` 대체·강화). 미상 티커는 macro 개요로 폴백.
   - `macro_overview_lines()`: macro 등락 라인 + prices `as_of`. 규칙 경로와 LLM 근거가 동일 수치를 쓰도록 공유.
   - 수치 guard: `extract_numbers`(가격/퍼센트형 숫자만 매칭, "10년물"·"TOP10" 같은 맨 정수는 무시), `collect_grounded_numbers`, `guard_answer(answer, grounding) -> GuardResult(grounded, ungrounded)`.
3. `backend/app/services/chat_service.py`
   - `chat_grounding` import. `_cached_market_snippet` 함수 제거(→ `chat_grounding.asset_snippet`/`macro_overview_lines`로 이관). 사용되지 않게 된 `market_cache` import 제거.
   - LLM 경로(`_try_llm_response`): grounding에 구조화된 `quotes`(후보/현재 티커의 `asset_snapshot` 목록) 추가. plan 생성 후 `settings.CHATBOT_GROUNDING_GUARD`가 켜져 있으면 `guard_answer`로 답변 내 가격/퍼센트 수치가 근거에 없을 때 confidence를 0.5 이하로 낮추고 "일부 수치는 최신 캐시에서 확인되지 않아 참고용으로만 봐주세요." 경고 문장을 덧붙임(답변 문장 자체는 재작성하지 않음).
   - `_market_summary_response`의 macro 분기를 `chat_grounding.macro_overview_lines()` 사용으로 정리.
4. `backend/app/services/chat_llm.py`
   - `_grounding_block`에 구조화 시세(quotes) 라인 노출(이름(티커) 가격 통화 등락% 기준시각).
5. `backend/app/core/config.py`
   - 신규 토글 `CHATBOT_GROUNDING_GUARD: bool = True` 추가([config.py:146](backend/app/core/config.py#L146)).

### 테스트 (backend/tests/)

6. `backend/tests/test_chat_grounding.py` (신규): `asset_snapshot` 키드리프트/통화, `asset_snippet` 통화·`as_of`, `macro_overview_lines`, guard grounded/ungrounded/맨정수 무시.
7. `backend/tests/test_chat_service.py`: 확장 alias 해석 파라미터 케이스(네이버/엘지엔솔/브로드컴/일라이릴리/포스코홀딩스) 추가.

### 프론트엔드 (frontend/)

- 변경 없음. `ChatResponse` 계약 유지.

### DB / 설정

- 스키마 변경 없음. 저장 리포트(`AIReport`)는 읽기만 한다.
- 신규 환경변수 `CHATBOT_GROUNDING_GUARD`(기본 `True`)는 토글이며 시크릿이 아니다.

## 3. 동작 변화 (Behavior changes)

1. 더 많은 종목 별칭·오타를 정확히 해석하고 금융 게이트를 통과한다.
2. 시세 근거의 키 불일치를 `chat_grounding`에서 흡수하고 통화·기준시각을 동반해 정확도가 향상되며, 규칙 경로와 LLM 경로가 동일 수치를 사용한다.
3. LLM이 근거에 없는 수치를 말하면 경고 문장과 신뢰도 하향으로 환각 노출을 완화한다(답변 문장은 재작성하지 않고 참고용 경고만 부가).
4. 모든 신규 동작은 읽기 전용이며 리포트 생성 경로를 추가하지 않는다.

## 4. AGENTS.md 섹션 14 준수

- 리포트 생성 경로 추가 없음.
- guard/grounding은 저장된 `AIReport` 요약만 근거로 사용하며, 사용자 요청이 실시간 리포트 생성을 유발하지 않는다.
- 신규 외부 provider/네트워크 호출 없음. 기존 캐시/저장데이터만 재사용한다.

## 5. 검증 결과 (Verification performed)

- 이 환경에는 `.env`가 없어 Settings 초기화에 필요한 환경변수(`PROJECT_NAME`, `API_V1_STR`, `DATABASE_URL=sqlite+aiosqlite:///:memory:`)를 임시 주입해 backend에서 실행했다.
- `python -m pytest tests/test_chat_grounding.py tests/test_chat_service.py tests/test_chat_api.py -q` → **27 passed**.
- 변경 모듈 import OK, `compileall` 오류 없음.

## 6. 실행하지 않은 명령과 이유 (Commands not run and why)

- 프론트엔드 `npm run lint` / `npm run build`: 프론트엔드 변경이 없고 `ChatResponse` 계약을 유지했으므로 미실행.
- LLM 실호출 검증: 일반 테스트에서 실제 LLM 호출을 회피한다(`AGENTS.md` 섹션 4). guard 로직은 모킹/단위 테스트로 검증.

## 7. 후속 위험 (Follow-up risks)

- Phase 3~5(도구 호출 LLM, 비교/랭킹 범용성, rate limit)는 보류 상태다. 진행하려면 별도 승인이 필요하다(LLM 비용 증가).
- guard의 수치 검증은 통화/포맷 다양성(%, 원, $, 천단위) 때문에 일부 정상 수치를 근거 미확인으로 놓칠 수 있어, 답변을 재작성하지 않고 보수적으로 경고만 부가하도록 설계했다.

## 8. 관련 feature 문서

- `docs/harness/features/chatbot-assistant.md` (Current Behavior / Ownership Map / Change Rules / Open Risks / Change Records 갱신)
- `docs/harness/feature-index.md` (Chatbot assistant 행, 상단 목록 갱신)
