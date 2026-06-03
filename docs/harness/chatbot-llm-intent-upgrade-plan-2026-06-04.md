# 챗봇 능동성·의도이해 개선 계획 (LLM 기반 업그레이드)

Date: 2026-06-04
Status: Plan only — 코드 미구현. **Risky Change(유료 API/AI 비용) 포함이므로 구현 전 사용자 승인 필요.**

## 1. 목적 (Objective)

현재 챗봇이 "너무 수동적이고 사용자 말을 못 알아듣는" 문제를 해결한다. 구체적으로:

- 사전에 없는 자연어 표현·오타·문장형 질문을 이해하도록 의도 분류를 개선한다.
- "상세 페이지로 이동하세요" 식 안내 일변도에서 벗어나, 실제 데이터(시세·뉴스·저장 리포트)를 근거로 한 답변을 제공한다.
- 멀티턴 맥락(직전 대화)을 활용해 "그거 더 알려줘" 같은 후속 질문을 처리한다.

단, `AGENTS.md` 섹션 14 규칙은 그대로 지킨다: **챗봇은 저장된 스케줄 리포트만 읽고, 사용자 요청으로 AI 리포트를 실시간 생성하지 않는다.**

## 2. 현재 동작 / 목표 동작

### 현재 동작 (코드 기준)
- 진입점: [chat_service.py](backend/app/services/chat_service.py)의 `handle_chat_message`. 완전 규칙 기반, LLM 미사용, 서버 무상태.
- 의도 분류: [chat_tools.py](backend/app/services/chat_tools.py)의 `is_financial_query`, `detect_feature`, `find_category`, `find_asset_candidates` — 모두 키워드/별칭 사전 매칭.
- 한계 지점:
  1. `is_financial_query`가 `FINANCIAL_KEYWORDS`에 안 걸리면 즉시 `NON_FINANCIAL_ANSWER`로 차단 ([chat_service.py:44](backend/app/services/chat_service.py#L44)).
  2. `_is_ambiguous`가 `["보여줘","보고 싶","알려줘","목록","채권","삼성"]` 하드코딩으로 모호성 판단 ([chat_service.py:464](backend/app/services/chat_service.py#L464)) — 깨지기 쉬움.
  3. 거의 모든 분기가 `navigate` 액션 버튼 + 짧은 안내문만 반환. 가격을 물어도 숫자를 거의 답하지 않음.
  4. 서버가 대화 이력을 받지 않음(`conversation_id`/`client_message_id`는 식별자일 뿐) → 멀티턴 불가.
- 프론트: `chatStore.sendMessage`가 단건 메시지만 POST. 사용자가 버튼을 클릭해야만 이동(`preserve user-controlled navigation` 원칙).

### 목표 동작
- LLM(이미 사용 중인 `gpt-4o-mini`, `OPENAI_API_KEY`, [graph/llm.py](backend/app/services/graph/llm.py))을 **의도 이해 + 답변 생성**에 사용한다.
- **Tool/function calling 패턴**: LLM이 직접 자유 답변을 환각하지 않고, 기존 결정적 함수(`find_asset_candidates`, `find_category`, 저장 리포트 조회, 시장 요약 캐시)를 도구로 호출해 실제 데이터를 받아 답한다. 데이터 출처가 없으면 모른다고 답한다.
- **저장 리포트 전용 규칙 유지**: LLM 도구 목록에 "리포트 생성" 도구를 절대 넣지 않는다. 저장 리포트 조회(`_fetch_saved_report`)만 도구로 노출.
- **멀티턴**: 프론트가 직전 N개(예: 6개) 메시지를 함께 전송, 서버는 저장하지 않고 프롬프트 컨텍스트로만 사용(기존 무상태·프라이버시 원칙 유지).
- **안전 토글 + 폴백**: 신규 환경변수 `ENABLE_LLM_CHATBOT`(기본 `false`)로 제어. off이거나 LLM 호출 실패 시 **현재 규칙 기반 로직으로 자동 폴백**. 기능 유실 없음.
- **권한·네비게이션 원칙 유지**: Pro 전용 유지, 백엔드는 액션을 반환할 뿐 직접 브라우저를 이동시키지 않는다.

## 3. 변경 대상 파일

### Backend
- `backend/app/core/config.py` — `ENABLE_LLM_CHATBOT: bool = False`, `CHATBOT_LLM_MODEL: str = "gpt-4o-mini"`, `CHATBOT_HISTORY_MAX_TURNS: int = 6` 추가.
- `backend/app/services/chat_service.py` — LLM 분기 추가. `ENABLE_LLM_CHATBOT`가 켜져 있고 키가 있으면 LLM 경로, 아니면 기존 규칙 경로로 폴백.
- `backend/app/services/chat_llm.py` (신규) — LLM 의도 이해/답변 생성 로직, 도구 정의(기존 `chat_tools` 함수 래핑), 저장 리포트 조회 도구. 환각 방지 system prompt.
- `backend/app/schemas.py` — `ChatMessageRequest`에 `history: list[ChatTurn] | None`(선택) 추가. `ChatResponse`는 기존 계약 유지(`answer/intent/confidence/actions/cards/...`)로 프론트 호환.
- (선택) `backend/app/services/chat_tools.py` — LLM이 호출하기 쉽도록 후보 검색 함수의 반환을 직렬화하는 얇은 헬퍼만 추가. 기존 함수 시그니처는 보존.

### Frontend
- `frontend/src/store/chatStore.js` — 직전 N개 메시지를 `history`로 함께 전송. 응답 렌더링은 기존 그대로(텍스트 + 액션 칩).
- 변경 최소화: `ChatbotPanel.jsx`/`ChatMessageList.jsx`는 응답 스키마가 동일하므로 수정 불필요(능동적 답변은 `answer` 필드 길이만 늘어남).

### 설정 / 문서
- `.env.example` 또는 환경 설정 가이드 문서에 `ENABLE_LLM_CHATBOT` 설명 추가(시크릿 값은 기록하지 않음).

### DB
- **변경 없음.** 서버 대화 저장을 도입하지 않는다(프라이버시·보존정책 부담 회피, feature doc Change Rules 준수).

## 4. 단계별 구현 계획

1. **설정/스키마 토대**: `config.py`에 토글·모델·히스토리 한도 추가. `schemas.py`에 `history`(선택) 필드와 `ChatTurn` 스키마 추가. 기본 off이므로 동작 변화 없음 → 안전한 1단계.
2. **LLM 서비스 골격**: `chat_llm.py`에 `get_chat_llm()`([graph/llm.py](backend/app/services/graph/llm.py) 재사용), 도구 정의(자산 후보 검색, 카테고리 해석, 시장 요약 캐시 조회, **저장 리포트 조회 only**), 엄격한 system prompt(금융/앱 범위 한정, 데이터 없으면 모른다고 답하기, 리포트 생성 절대 금지, 매수·매도 단정 금지 + DISCLAIMER 유지).
3. **chat_service 통합 + 폴백**: `handle_chat_message` 진입부에서 토글·키 확인 후 LLM 경로 시도, 예외/타임아웃 시 기존 규칙 함수로 폴백. LLM 응답을 기존 `ChatResponse` 계약으로 매핑(도구가 만든 후보 → `actions`/`cards`, 본문 → `answer`).
4. **프론트 멀티턴 전송**: `chatStore.js`에서 세션 메시지 중 최근 N개를 `history`로 전송. 서버는 컨텍스트로만 사용.
5. **테스트**: `backend/tests/test_chat_service.py`/`test_chat_api.py`에 (a) 토글 off 시 기존 규칙 동작 보존, (b) LLM 경로는 `get_chat_llm`/도구를 모킹해 실제 호출 없이 검증, (c) 리포트 생성 도구가 존재하지 않음 보장 테스트 추가. **실제 LLM 호출은 테스트에서 금지**(AGENTS.md 섹션 4).
6. **문서화**: 구현 후 변경 기록 + feature doc + index 갱신(섹션 7 참조).

## 5. 위험과 Risky Change 여부

**Risky Change에 해당한다 (`AGENTS.md` 섹션 9: "Adding paid APIs or network-heavy workflows", AI 비용 증가). 구현 전 사용자 승인 필요.**

- **비용**: 사용자 메시지마다 LLM 호출 → OpenAI 비용 발생. 완화책: 기본 `ENABLE_LLM_CHATBOT=false`, Pro 전용 유지, `gpt-4o-mini` 사용, 히스토리 턴 수 제한, (추후) 호출 빈도 제한 고려.
- **리포트 생성 규칙 위반 위험**: LLM이 임의로 리포트를 생성하면 안 됨 → 도구 목록에서 생성 함수를 원천 제외하고, 테스트로 보장(섹션 14 준수).
- **환각/범위 이탈**: tool calling + 엄격한 system prompt + 데이터 없을 때 "모른다" 응답으로 완화. DISCLAIMER 유지.
- **장애 내성**: LLM/네트워크 실패 시 규칙 기반 폴백으로 기능 연속성 확보.
- **인증/스키마/스케줄러**: 변경 없음(인증 흐름·DB 스키마·스케줄러 cadence 불변).

## 6. 검증 계획 (AGENTS.md 섹션 6, 최소 집합)

```powershell
# Backend (from backend/)
pytest tests/test_chat_service.py tests/test_chat_api.py
python -m compileall app

# Frontend (from frontend/)
npm run lint
npm run build
```

- 수동 스모크(토글 off): 기존 동작 그대로인지 — "삼성전자 보여줘" → 상세 액션 반환 확인.
- 수동 스모크(토글 on, 키 보유 시): 사전에 없는 문장형 질문·오타·후속 질문에 데이터 근거 답변이 나오는지, 리포트 질문에 저장 리포트만 요약하는지 확인.
- 실제 LLM 호출 비용이 드는 검증은 사용자 승인·키 준비 후에만 수행하고, 미실행 시 보고서에 명시.

## 7. 갱신할 문서

- 신규 변경 기록: `docs/harness/chatbot-llm-intent-upgrade-implementation-2026-06-04.md`(구현 시).
- feature doc 갱신: [docs/harness/features/chatbot-assistant.md](docs/harness/features/chatbot-assistant.md)
  - Current Behavior에 LLM 토글 경로/폴백/멀티턴 추가, Contracts에 `history` 필드 추가, Change Rules에 "LLM 경로도 저장 리포트만 읽고 생성 금지" 명시, Change Records에 본 계획·구현 링크 추가.
- 색인 갱신: [docs/harness/feature-index.md](docs/harness/feature-index.md)의 Chatbot assistant 행에 본 계획/구현 문서 링크 추가, 상단 목록에도 등재.
- `AGENTS.md` 섹션 14 대상(챗봇 리포트 응답)을 건드리므로, 구현 기록에 "사용자 요청이 리포트 생성을 트리거하지 않음"을 명시.
