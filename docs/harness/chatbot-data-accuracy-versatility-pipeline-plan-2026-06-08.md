# 챗봇 데이터 정확성·답변 범용성 향상 파이프라인 구축 계획

- 날짜: 2026-06-08
- 작성 단계: plan (구현 전, 코드 미수정)
- 대상 기능: Chatbot assistant (`docs/harness/features/chatbot-assistant.md`)
- 관련 규칙: `AGENTS.md` 섹션 4, 9, 11, 12, 13, 14

> **승인된 구현 범위 (2026-06-08)**: 사용자 승인에 따라 **Phase 1~2만 구현**한다(저위험, LLM 비용 증가 없음). Phase 3(도구 호출 LLM 파이프라인), Phase 4(범용성), Phase 5(비용 가드)는 보류하며, 진행하려면 별도 승인이 필요하다. 아래 전체 단계는 참고용 로드맵으로 유지한다.

## 1. 목적 (Objective)

현재 챗봇은 (1) 규칙 기반 의도 분류 + (2) 선택적 LLM 의도 이해(기본 off) 구조다. 사용자가 원하는 두 가지를 개선한다.

- **데이터 정확성 향상**: 답변에 들어가는 시세·등락·뉴스·리포트 요약이 실제 캐시/DB의 최신 사실과 정합하도록 "근거 조립(grounding)" 단계를 표준화하고, 답변의 모든 수치가 근거에서만 나오도록 검증(guard)한다.
- **답변 범용성 향상**: 단일 의도 1회 응답에서, 범위 내 다중 의도·비교·랭킹·후속 질문에 능동적으로 답하도록 도구 호출(tool-calling) 기반 파이프라인으로 확장한다.

단, `AGENTS.md` 섹션 14의 절대 원칙은 유지한다: **챗봇은 저장된 스케줄 리포트만 읽고, 어떤 경로로도 리포트를 생성하지 않는다.** 모든 신규 도구는 읽기 전용이며 리포트 생성 도구는 만들지 않는다.

## 2. 현재 동작 / 목표 동작

### 현재 동작 (코드 기준)

- 진입점: `backend/app/api/chat.py` → `chat_service.handle_chat_message()`.
- `ENABLE_LLM_CHATBOT=true` + `OPENAI_API_KEY`가 있으면 `_try_llm_response()` 시도, 실패 시 규칙 경로로 폴백 ([chat_service.py:46](backend/app/services/chat_service.py#L46)).
- 근거(grounding)는 한 번에 얕게 조립됨 ([chat_service.py:215](backend/app/services/chat_service.py#L215)):
  - 자산 후보(name+ticker), 카테고리 라벨, `_cached_market_snippet()` 문자열, primary ticker의 저장 리포트 요약, 사전 구성된 actions.
  - 시세 정확성: `_cached_market_snippet()`은 `market_cache["prices"]`에서 symbol 일치 항목의 price/changePercent만 문자열로 만든다 ([chat_service.py:248](backend/app/services/chat_service.py#L248)). 캐시 miss·필드명 불일치 시 근거가 비고, 등락만 macro로 대체된다.
  - 뉴스/일정은 `market_summary` intent에서만 `fetch_latest_asset_context()`로 조회 ([chat_service.py:466](backend/app/services/chat_service.py#L466)). LLM 경로 근거에는 뉴스가 없다.
- LLM은 사전 구성 actions 중 인덱스만 선택하고 answer를 작성한다. 추가 데이터를 스스로 요청할 수 없다(tool-calling 없음).
- 엔티티 해석은 정적 alias 사전(약 25개 티커) + 캐시 자산 + 티커 정규식 ([chat_tools.py:291](backend/app/services/chat_tools.py#L291)). feature 문서의 Open Risk로 "사전이 작다"가 명시됨.
- 규칙 경로는 단일 feature/intent만 처리 → 비교·복합 질문에 약함.

### 목표 동작

1. **공통 근거 조립 레이어**: LLM/규칙 양 경로가 동일한 정확 근거(가격·등락·통화·as-of·뉴스 헤드라인·저장 리포트 요약)를 사용. 데이터에는 항상 "기준 시각/신선도(source_status)"를 동반.
2. **도구 호출 파이프라인(LLM on일 때)**: LLM이 범위 내 읽기 전용 도구(`get_quote`, `get_news`, `get_report_summary`, `list_category`, `compare_assets`)를 호출해 필요한 근거만 정확히 가져온 뒤 답한다. 리포트 생성 도구는 없음.
3. **근거 검증(guard)**: 최종 answer의 수치 토큰이 근거 집합에 없으면 제거/완화하거나 "확인되지 않음"으로 표기. 환각 차단.
4. **범용성**: 다중 의도·비교·랭킹·후속 질문 응답. 규칙 경로도 다중 후보/복합 요청을 더 잘 처리.
5. **안전·비용 가드**: LLM 경로는 기본 off 유지, 도구 호출 라운드 수 상한, per-user rate limit, 폴백 보존.

## 3. 변경 대상 파일

### 백엔드 (backend/)

- 신규 `backend/app/services/chat_grounding.py` — 공통 근거 조립기. 캐시/DB/기존 서비스에서 정확한 시세·등락·통화·as-of·뉴스·저장 리포트 요약을 구조화해 반환. (외부 신규 네트워크 호출 없음; `fetch_latest_asset_context`는 기존 TTL 캐시 정책 그대로 재사용.)
- 신규 `backend/app/services/chat_grounding_guard.py` (또는 `chat_grounding.py` 내 함수) — 답변 수치 ↔ 근거 정합 검증/정제.
- 수정 `backend/app/services/chat_llm.py` — (a) 구조화 근거 블록 확장, (b) tool-calling 경로 추가(읽기 전용 도구만 바인딩), (c) 도구 라운드 수/타임아웃 상한.
- 수정 `backend/app/services/chat_service.py` — 근거 조립을 `chat_grounding`에 위임, LLM/규칙 양 경로가 공통 근거 사용, guard 적용, 다중 의도/비교 응답 분기 추가.
- 수정 `backend/app/services/chat_tools.py` — 엔티티 해석 강화(alias 확장, 정규화/퍼지 보강, 캐시 자산 인덱스 우선순위 정리). 도구가 호출할 조회 헬퍼 추가.
- 수정 `backend/app/core/config.py` — 신규 토글: `CHATBOT_USE_TOOLS`(기본 False), `CHATBOT_MAX_TOOL_ROUNDS`(기본 3), `CHATBOT_RATE_LIMIT_PER_MIN`(기본값 설정), `CHATBOT_GROUNDING_GUARD`(기본 True). 기존 `ENABLE_LLM_CHATBOT` 등은 유지.
- 신규/수정 테스트:
  - `backend/tests/test_chat_grounding.py` — 근거 조립/guard 단위 테스트(캐시 fixture 기반, LLM 미호출).
  - `backend/tests/test_chat_service.py`, `backend/tests/test_chat_api.py` — 회귀(폴백 동작 불변, 리포트 생성 미발생) 보강.

### 프론트엔드 (frontend/)

- 원칙적으로 계약(`ChatResponse`) 유지 시 무변경. 단 비교/다중 카드 UX를 살리려면:
  - 수정 가능 `frontend/src/components/ChatMessageList.jsx` — 카드 4개 초과·비교 결과 렌더 개선(선택 항목).
  - 응답 스키마에 필드를 추가하지 않는 것을 1차 목표로 한다(프론트 변경 최소화).

### DB

- **스키마 변경 없음.** 저장 리포트(`AIReport`)는 읽기만 한다. 서버측 대화 저장은 도입하지 않는다(feature 문서 Change Rule 준수).

### 설정/환경변수

- `backend/app/core/config.py`에 위 토글 추가. 신규 변수는 `ENVIRONMENT_VARIABLE_RECOMMENDATIONS.md`(이미 미추적 파일로 존재)와 배포 런타임 feature 문서에 기록.

## 4. 단계별 구현 계획 (Phase)

각 Phase는 독립 검증 가능하도록 나눈다. Phase 1~2는 LLM 없이도 정확성을 올린다. Phase 3 이후가 비용/Risky 영역이다.

### Phase 1 — 엔티티 해석 정확도 (LLM 불필요, 저위험)
- `chat_tools.py`의 alias 사전 확장(현 약 25개 → 운영 자산군 전체 커버), 한/영/약어/오타 변형 정규화 강화.
- 캐시 자산(`_cached_assets`) 우선순위/중복 정리, 동명이의(채권·환율) 모호성 처리 명확화.
- 검증: `pytest tests/test_chat_service.py`(후보 해석 케이스 추가).

### Phase 2 — 공통 근거 조립 + guard (LLM 불필요, 저위험)
- `chat_grounding.py` 신설: ticker별 정확 시세(price/changePercent/통화/as-of/source_status), 뉴스 헤드라인(캐시 TTL 내), 저장 리포트 요약을 구조화해 반환. 필드명 불일치(`changePercent`/`change_pct`, `price`/`close`)를 한 곳에서 흡수.
- `_cached_market_snippet`를 이 조립기로 대체, 규칙 경로 응답(`_market_summary_response` 등)도 동일 근거 사용 → 경로 간 수치 불일치 제거.
- `chat_grounding_guard`: 답변 수치 토큰이 근거에 없으면 정제. 규칙 경로/LLM 경로 모두 최종 단계에서 통과.
- 검증: `pytest tests/test_chat_grounding.py tests/test_chat_service.py`, `python -m compileall app`.

### Phase 3 — 도구 호출 LLM 파이프라인 (LLM on, **Risky**)
- `chat_llm.py`에 읽기 전용 도구 바인딩: `get_quote(ticker)`, `get_news(ticker)`, `get_report_summary(ticker)`, `list_category(key)`, `compare_assets([tickers])`. 모든 도구는 `chat_grounding`만 호출 → 외부 신규 호출/리포트 생성 없음.
- `CHATBOT_USE_TOOLS` 토글(기본 False)과 `CHATBOT_MAX_TOOL_ROUNDS` 상한. 도구 미사용 시 기존 Phase 2 근거 주입 방식으로 동작.
- 실패/타임아웃/상한 초과 시 규칙 경로 폴백 보존.
- 검증: 도구 핸들러 단위 테스트(LLM 모킹), 토글 off 시 동작 불변 회귀.

### Phase 4 — 범용성(다중 의도·비교·랭킹)
- 규칙 경로: 복합 요청(예: "삼성전자랑 SK하이닉스 비교", "리포트랑 주가 같이") 분기 추가, 다중 후보 카드/액션 동시 노출.
- LLM 경로: intent 집합 확장 또는 다중 action 선택 강화(스키마 확장 시 프론트 영향 최소화 검토).
- 검증: 시나리오 테스트(비교/복합/후속질문), 프론트 `npm run build`/`npm run lint`(렌더 변경 시).

### Phase 5 — 관측·평가·비용 가드
- per-user rate limit(`CHATBOT_RATE_LIMIT_PER_MIN`), 토큰/라운드 상한, 폴백 카운터 로깅(시크릿 미포함).
- 골든셋 회귀 테스트(대표 질문→기대 intent/근거 존재 여부)로 정확성/범용성 회귀 방지.

## 5. 위험과 Risky Change 여부 (AGENTS.md 섹션 9)

- **LLM 비용 증가 (Risky, 사용자 확인 필요)**: Phase 3 도구 호출은 라운드트립으로 토큰/호출이 늘 수 있다. → 기본 off, 라운드 상한, rate limit, Pro 전용으로 통제. **이 기능을 기본 on으로 켤지 여부는 사용자 승인 후 결정.**
- **리포트 생성 위험 (절대 금지)**: 도구·프롬프트 어디에도 리포트 생성 경로를 두지 않는다. `get_report_summary`는 저장 `AIReport`만 읽음(섹션 14).
- **DB 스키마/인증 변경 없음**: 마이그레이션·인증 동작 변경 없음. 저위험.
- **계약 변경 최소화**: `ChatResponse` 스키마 변경은 프론트 영향 → Phase 4에서 필요 시에만, 하위 호환 유지.
- **외부 API 추가 없음**: 신규 provider/네트워크 워크플로 도입하지 않음(섹션 9의 paid API/network-heavy 회피). 기존 `fetch_latest_asset_context` TTL 캐시만 재사용.
- 환각/오정보 위험: Phase 4 guard로 완화하나 100% 제거는 불가 → disclaimer 유지, 근거 없으면 "모른다" 응답 강제.

## 6. 검증 계획 (AGENTS.md 섹션 6 — 최소 검증)

- 백엔드 단위/회귀 (from `backend/`):
  - `pytest tests/test_chat_grounding.py tests/test_chat_service.py tests/test_chat_api.py`
  - `python -m compileall app`
- 프론트엔드(렌더 변경 시, from `frontend/`): `npm run lint`, `npm run build`
- 수동 스모크: `/`에서 "삼성전자 주가랑 리포트 알려줘" → 근거 기반 답변·정확한 등락·액션 확인. 토글 off 상태에서 기존 동작 불변 확인.
- LLM 실호출은 기본 테스트에서 모킹(섹션 4: 일반 테스트에서 실제 LLM 호출 회피).

## 7. 갱신할 문서

- `docs/harness/features/chatbot-assistant.md` — Current Behavior에 "공통 근거 조립 + 도구 호출(옵션) + guard" 추가, Ownership Map에 `chat_grounding.py` 등 신규 파일, Change Rules에 "신규 도구는 읽기 전용·리포트 생성 금지" 명문화, Open Risks 갱신, 본 계획 및 후속 구현 기록을 Change Records에 링크.
- `docs/harness/feature-index.md` — Chatbot 행에 신규 백엔드 파일과 본 문서 링크 추가, 상단 목록에 한 줄 추가.
- `docs/harness/features/deployment-runtime.md` 및 `ENVIRONMENT_VARIABLE_RECOMMENDATIONS.md` — 신규 환경변수(`CHATBOT_USE_TOOLS`, `CHATBOT_MAX_TOOL_ROUNDS`, `CHATBOT_RATE_LIMIT_PER_MIN`, `CHATBOT_GROUNDING_GUARD`) 기록.
- 구현 단계에서 `docs/harness/chatbot-data-accuracy-versatility-pipeline-implementation-2026-06-08.md`(또는 Phase별) 변경 기록 작성.

## 8. 후속 위험 / 메모

- Phase 3 활성화 전 비용 시뮬레이션 권장(평균 도구 라운드 수 × 토큰).
- guard의 수치 검증은 통화/포맷 다양성(%, 원, $, 천단위) 때문에 정규식만으로 부족할 수 있어 근거 화이트리스트 방식 우선.
- 서버측 대화 저장은 본 계획 범위 밖(프라이버시·보존·삭제 설계 필요, feature Change Rule).
