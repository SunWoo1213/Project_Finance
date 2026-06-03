# 챗봇 LLM 기반 의도이해·능동성 개선 구현 기록

Date: 2026-06-04
Plan: [chatbot-llm-intent-upgrade-plan-2026-06-04.md](chatbot-llm-intent-upgrade-plan-2026-06-04.md)
Status: 구현 완료. 검증(백엔드 pytest, 프론트 lint/build) 통과.

## 목적

챗봇이 "수동적이고 사용자 말을 못 알아듣는" 문제를 개선한다. 키워드 사전에 없는 자연어/오타/문장형 질문을 이해하고, "상세 페이지로 이동하세요" 안내 일변도에서 벗어나 실제 데이터(시세 캐시·저장 리포트)를 근거로 능동적으로 답하며, 멀티턴 대화 맥락을 활용한다. 단, **사용자 요청으로 AI 리포트를 실시간 생성하지 않는다**는 규칙(`AGENTS.md` 섹션 14)을 그대로 유지한다.

## 동작 변화

- 신규 환경변수 `ENABLE_LLM_CHATBOT`(기본 `false`)가 켜져 있고 `OPENAI_API_KEY`가 있으면, 챗봇이 LLM(`gpt-4o-mini`) 경로를 사용한다. 그렇지 않으면 **기존 규칙 기반 동작과 100% 동일**하다.
- LLM 경로는 **grounding-기반**이다. 백엔드가 결정적으로 자산 후보(`find_asset_candidates`), 카테고리(`find_category`), 캐시 시장 스냅샷(`market_cache`, 네트워크 호출 없음), 저장 리포트 요약(`_fetch_saved_report` + `_summarize_report`, 저장본만)을 수집해 LLM에 넘긴다. LLM은 의도 분류 + 자연어 답변 작성 + 노출할 액션 인덱스 선택만 한다.
- 환각 방지: LLM은 grounding에 있는 사실만 사용하도록 system prompt로 강제하고, 액션 URL은 백엔드가 결정적으로 만든다(브라우저 이동은 사용자가 버튼 클릭으로 진행하는 기존 계약 유지).
- 멀티턴: 프론트가 최근 대화(최대 12개 메시지)를 `history`로 전송한다. 서버는 저장하지 않고 프롬프트 컨텍스트로만 사용한다(무상태·프라이버시 원칙 유지).
- 장애 내성: 토글 off, 키 없음, LLM 예외/타임아웃, 빈 답변 등 어떤 실패든 `compose_chat_answer`가 `None`을 반환하고 `handle_chat_message`는 기존 규칙 경로로 자동 폴백한다. 기능 유실 없음.

## 리포트 생성 규칙 (AGENTS.md 섹션 14)

- **사용자/챗봇 요청은 AI 리포트를 생성하지 않는다.** LLM 경로에 리포트 생성 도구/액션은 존재하지 않는다. LLM에는 이미 조회한 *저장* 리포트 요약만 grounding으로 전달되며, 요약이 없으면 "아직 저장된 리포트가 없다"고 안내한다.
- `ALLOWED_INTENTS`에 generate 계열 intent가 없음을 테스트로 보장한다(`test_allowed_intents_have_no_report_generation_intent`).

## 변경 파일

### Backend
- [backend/app/core/config.py](backend/app/core/config.py) — `ENABLE_LLM_CHATBOT`(기본 false), `CHATBOT_LLM_MODEL`(`gpt-4o-mini`), `CHATBOT_HISTORY_MAX_TURNS`(6), `CHATBOT_LLM_TIMEOUT_SECONDS`(20) 추가.
- [backend/app/schemas.py](backend/app/schemas.py) — `ChatTurn` 스키마 추가, `ChatMessageRequest.history` 선택 필드 추가(최대 20개). `ChatResponse` 계약은 불변(프론트 호환).
- [backend/app/services/chat_llm.py](backend/app/services/chat_llm.py) — **신규**. `compose_chat_answer`(grounding + history로 LLM 호출, 구조화 출력 `LlmChatPlan` 반환), 엄격한 system prompt, intent 검증/액션 인덱스 클램핑, 실패 시 `None`. langchain은 지연 import.
- [backend/app/services/chat_service.py](backend/app/services/chat_service.py) — `handle_chat_message` 진입부에 LLM 분기 추가, `_try_llm_response`(grounding 빌드 + 매핑) / `_cached_market_snippet`(네트워크 없는 캐시 스냅샷) 헬퍼 추가.

### Frontend
- [frontend/src/store/chatStore.js](frontend/src/store/chatStore.js) — `sendMessage`가 최근 대화(welcome 제외, 최대 12개)를 `history`로 함께 전송. 응답 렌더링은 기존과 동일.

### Tests
- [backend/tests/test_chat_llm.py](backend/tests/test_chat_llm.py) — **신규**. 토글 off/키 없음 시 None, intent 검증·인덱스 클램핑, LLM 예외 시 None, generate intent 부재 보장.
- [backend/tests/test_chat_service.py](backend/tests/test_chat_service.py) — LLM 경로 매핑(history 전달·액션 매핑·disclaimer 유지·grounding에 생성 액션 부재) + LLM 실패 시 규칙 폴백 테스트 추가. 기존 규칙 테스트는 토글 기본값 off라 그대로 유지.

### DB
- 변경 없음(서버 대화 저장 미도입).

## 검증

- 백엔드: `.venv\Scripts\python.exe -m pytest tests/test_chat_service.py tests/test_chat_llm.py tests/test_chat_api.py -q` → **19 passed**.
- 백엔드 import/컴파일: `python -m compileall app/services/chat_llm.py app/services/chat_service.py app/schemas.py app/core/config.py` → OK, 모듈 import OK.
- 프론트: `npm run lint` → 오류 없음. `npm run build` → 성공(기존 청크 크기 경고만, 본 변경과 무관).
- 실제 LLM 호출 검증은 비용/키가 필요하여 실행하지 않았다. LLM 경로는 `_get_structured_llm`/`compose_chat_answer`를 모킹해 실제 호출 없이 검증했다(`AGENTS.md` 섹션 4: 일반 테스트에서 실 LLM 호출 금지).

## 미실행 명령과 이유

- 토글을 켠 실제 OpenAI 호출 스모크: 유료 API 키와 비용이 필요하므로 미실행. 운영 적용 시 `ENABLE_LLM_CHATBOT=true` + 유효 키로 수동 스모크 권장(사전에 없는 문장형/오타/후속 질문, 리포트 질문 시 저장본만 요약되는지 확인).

## 후속 위험

- **비용**: 토글을 켜면 메시지마다 OpenAI 호출이 발생한다. 완화책으로 기본 off, Pro 전용 유지, `gpt-4o-mini`, 히스토리 턴 제한을 두었으나, 트래픽 증가 시 호출 빈도 제한(rate limit) 추가를 고려해야 한다.
- **grounding 한계**: 시장 스냅샷은 캐시만 사용하므로(네트워크 호출 회피) 캐시가 비면 수치를 답하지 못한다. 그 경우 LLM은 "모른다"고 답하도록 유도된다.
- **저장 리포트 의존**: 리포트 답변은 스케줄러가 생성해 저장한 리포트가 있어야 의미가 있다(기존 제약과 동일).

## 영향받은 문서

- 기능 문서: [docs/harness/features/chatbot-assistant.md](docs/harness/features/chatbot-assistant.md) — Current Behavior/Contracts/Change Rules/Change Records 갱신.
- 색인: [docs/harness/feature-index.md](docs/harness/feature-index.md) — Chatbot assistant 항목 및 상단 목록 갱신.
