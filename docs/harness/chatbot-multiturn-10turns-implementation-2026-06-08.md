# 챗봇 멀티턴 대화 10턴 확장 구현 기록

- 날짜: 2026-06-08
- 작업 유형: 구현(변경) 기록
- 관련 기능 문서: [docs/harness/features/chatbot-assistant.md](docs/harness/features/chatbot-assistant.md)

## 목적

사용자가 챗봇과 여러 차례 이어지는 대화(예: "댓글 어떻게 작성해?" → "들어왔는데 어떻게해?" 같은 후속 질문)를 나눌 수 있도록 멀티턴 맥락 유지 범위를 기존 **6턴에서 10턴(=20메시지)** 으로 확장한다. 또한 사용자가 채팅창을 초기화하면 대화내역을 잊는 동작이 그대로 유지되는지 확인한다.

## 사전 확인 결과 (이미 구현되어 있던 것)

- **멀티턴 맥락**은 이미 구현되어 있었다. 프론트가 최근 메시지를 `history`로 전송하고([frontend/src/store/chatStore.js](frontend/src/store/chatStore.js)), 백엔드 LLM 경로가 이를 system prompt 뒤에 대화 메시지로 붙여 이전 맥락을 이해한다([backend/app/services/chat_llm.py](backend/app/services/chat_llm.py#L141-L149)).
- **초기화 시 대화 망각**도 이미 구현되어 있었다. 패널의 휴지통 버튼이 `clear()`를 호출해 메시지를 환영 메시지로 되돌리고 새 `conversationId`를 발급한다([chatStore.js](frontend/src/store/chatStore.js#L30-L36)). 백엔드는 `history`를 저장하지 않고 프롬프트 컨텍스트로만 사용하므로, 초기화하면 이후 요청에 과거 대화가 전달되지 않는다.

따라서 이번 작업은 새 기능 추가가 아니라 **턴 수 한도 상향 조정**이다.

## 변경 파일

- [backend/app/core/config.py](backend/app/core/config.py#L143) — `CHATBOT_HISTORY_MAX_TURNS` 기본값 `6` → `10`. 백엔드가 history를 `CHATBOT_HISTORY_MAX_TURNS * 2`(=20) 메시지로 트리밍한다.
- [frontend/src/store/chatStore.js](frontend/src/store/chatStore.js#L47-L52) — `sendMessage`에서 보내는 history를 `.slice(-12)` → `.slice(-20)`(10턴=20메시지)로 확대하고, 주석에 "서버 미저장이라 초기화 시 대화를 잊는다"는 점을 명시.
- [backend/app/schemas.py](backend/app/schemas.py#L221) — `ChatMessageRequest.history`의 `max_length` `20` → `24`로 상향(20메시지 경계에서의 검증 거부 방지용 여유). 백엔드가 어차피 20메시지로 트리밍하므로 안전.
- [ENVIRONMENT_VARIABLE_RECOMMENDATIONS.md](ENVIRONMENT_VARIABLE_RECOMMENDATIONS.md#L149) — `CHATBOT_HISTORY_MAX_TURNS` 권장값 `6` → `10`로 갱신, 설명 보강.

## 동작 변화

- LLM 경로(`ENABLE_LLM_CHATBOT=true`) 활성화 시, 챗봇이 최근 최대 10턴(사용자+어시스턴트 20메시지)의 대화 맥락을 참고해 후속 질문을 이해한다. 토큰·비용은 그만큼 증가한다.
- 규칙 기반 폴백 경로는 history를 사용하지 않으므로 동작 불변.
- 초기화(`clear()`) 동작은 변경 없음 — 여전히 대화내역을 잊는다.

## 검증

- 백엔드 챗봇 테스트(더미 env 주입) 실행 — 통과:
  ```powershell
  cd backend
  $env:PROJECT_NAME="test"; $env:API_V1_STR="/api"; $env:DATABASE_URL="sqlite+aiosqlite:///:memory:"
  python -m pytest tests/test_chat_api.py tests/test_chat_llm.py tests/test_chat_service.py tests/test_chat_grounding.py -q
  # 32 passed
  ```
- 프론트엔드 검증 (frontend/) — 통과:
  ```powershell
  cd frontend
  npm run lint   # eslint . 오류 없음
  npm run build  # vite 빌드 성공 (built in ~3.3s)
  ```
  - 빌드 시 출력되는 500kB 청크 크기 경고는 기존부터 있던 사항으로 이번 변경과 무관하다.

## 후속 위험

- 턴 수 상향으로 LLM 경로의 메시지당 입력 토큰·비용이 증가한다. 트래픽이 늘면 `CHATBOT_HISTORY_MAX_TURNS`를 env로 낮추거나 레이트리밋을 검토한다.
- 대화내역은 여전히 브라우저 세션 메모리에만 존재한다. 새로고침하면 사라지며, 서버 영속 저장은 별도 프라이버시/보존/삭제 설계 없이는 추가하지 않는다.
