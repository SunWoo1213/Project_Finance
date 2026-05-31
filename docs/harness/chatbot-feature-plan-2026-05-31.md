# 챗봇 기능 상세 구현 계획서

Date: 2026-05-31

## 목적

Project Finance에 상용 서비스형 챗봇처럼 보이되, 첫 구현은 안전하고 비용이 낮은 "금융 서비스 내비게이터 + 데이터 설명 도우미"로 도입한다. 사용자가 전역 대화창에 용무를 말하면 챗봇은 의도를 분류하고, 기존 앱의 적절한 화면으로 이동할 수 있는 액션 버튼과 짧은 설명을 제공한다.

이 문서는 구현을 위한 상세 계획서다. 이 변경 범위에서는 코드 구현, 의존성 추가, API 생성, DB 스키마 변경을 하지 않는다.

## 현재 프로젝트 이해

### 실제 스택

- Frontend: React + Vite + JavaScript + Tailwind CSS + Zustand + React Router
- Backend: FastAPI + Async SQLAlchemy + PostgreSQL + APScheduler
- AI/report: LangGraph/LangChain 기반 리포트 생성 파이프라인
- Market data: `market_cache` 기반 가격/뉴스 캐시, yfinance 및 매크로 서비스
- Auth: Google 로그인 전용, 앱 JWT를 `authStore`와 `localStorage`에 저장

`ARCHITECTURE.md`에는 Next.js/TypeScript/uv 중심의 오래된 청사진이 일부 남아 있으므로, 구현 시에는 현재 코드 구조를 우선한다.

### 현재 사용자 흐름

현재 라우트는 `frontend/src/App.jsx`에서 다음처럼 구성된다.

| Route | 화면 | 주요 역할 |
| --- | --- | --- |
| `/` | `Home.jsx` | 주요 지수/환율 카드, 글로벌 뉴스 |
| `/category/:type` | `CategoryView.jsx` | 자산군별 목록, 즐겨찾기 |
| `/market/:ticker` | `MarketSnapshot.jsx` | 주요 지수/환율 1일 스냅샷 |
| `/detail/:ticker` | `AssetDetail.jsx` | 자산 상세, 차트, 최신 뉴스/일정, AI 리포트, 커뮤니티 |
| `/login` | `Login.jsx` | Google 로그인 |

### 현재 백엔드 공개/보호 API

| API | 인증 | 용도 |
| --- | --- | --- |
| `GET /api/market/prices` | public | 카테고리별 가격 캐시 |
| `GET /api/market/news` | public | 글로벌 뉴스 캐시 |
| `GET /api/market/latest-context/{ticker}` | public | 티커별 최신 뉴스/일정 TTL 캐시 |
| `GET /api/market/history/{ticker}` | public | 가격/수익률 히스토리 |
| `GET /api/reports/{ticker}` | required | 저장된 최신 AI 리포트 조회 |
| `POST /api/ai/generate/{ticker}` | required | LLM 기반 리포트 생성 |
| `GET /api/community/{asset_id}/comments` | public | 댓글 목록 |
| community write/like/report APIs | required | 댓글 작성/수정/삭제/좋아요/신고 |
| `POST /api/auth/google` | public | Google credential 검증 후 앱 JWT 발급 |

챗봇은 이 기존 표면을 재사용해야 하며, 특히 `POST /api/ai/generate/{ticker}`를 자동 호출하지 않아야 한다.

## 제품 원칙

### 챗봇의 포지션

챗봇은 투자 조언자가 아니라 앱 안에서 사용자가 원하는 기능을 빠르게 찾도록 돕는 도우미다.

- 가능: "삼성전자 페이지로 이동", "AI 리포트는 로그인 후 상세 페이지에서 볼 수 있음", "나스닥 스냅샷 바로가기", "현재 페이지의 리포트 요약"
- 제한: 매수/매도/보유 단정, 수익률 보장, 확정적 가격 예측, 사용자 투자금/계좌 정보 요구
- 범위 제한: 금융, 시장 데이터, AI 리포트, 앱 기능 안내와 무관한 질문에는 답변하지 않고 금융 관련 질문만 요청한다.
- 비용 보호: 일반 챗봇 질문만으로 LLM 리포트 생성 또는 외부 provider 직접 호출 금지

### 첫 구현의 핵심 경험

1. 사용자는 어느 화면에서든 우하단 챗봇 버튼을 누른다.
2. 패널이 열리고 "무엇을 도와드릴까요?" 입력창이 보인다.
3. 사용자가 "테슬라 보고서 보여줘"처럼 입력한다.
4. 백엔드는 의도를 분류하고, 자산/기능/라우트를 해석한다.
5. 프론트는 답변과 액션 버튼을 렌더링한다.
6. 사용자가 버튼을 누르면 React Router `navigate(url)`로 이동한다.

자동 이동은 하지 않는다. 사용자가 버튼을 눌러야 이동한다.

## 범위 정의

### Phase 1 MVP: 내비게이션형 챗봇

목표: 기존 화면으로 가는 가장 빠른 길을 제공한다.

포함:

- 전역 플로팅 챗봇 버튼과 패널
- 브라우저 세션 단위 대화 상태
- `POST /api/chat/message` 단일 엔드포인트
- 규칙 기반 의도 분류
- 자산명/티커/카테고리/기능명 기반 라우트 추천
- 모호한 요청에 대한 후보 카드
- 금융과 무관한 질문에 대한 고정 안내 문구
- 로그인 필요 기능에 대한 안내와 `/login` 액션
- 금융 안전 문구와 데이터 한계 문구

제외:

- 서버 DB에 대화 저장
- 챗봇의 자동 페이지 이동
- 챗봇의 자동 리포트 생성
- 스트리밍 응답
- 장기 대화 메모리
- 사용자의 개인 포트폴리오 기반 추천
- 실시간 외부 API 직접 조회

### Phase 2: 데이터 설명형 챗봇

목표: 이동 안내에 더해 현재 캐시된 시장 데이터와 최신 컨텍스트를 짧게 설명한다.

포함 후보:

- `GET /api/market/prices` 캐시 기반 시장 요약
- 현재 상세 페이지의 티커를 백엔드에 전달
- `GET /api/market/latest-context/{ticker}` 결과를 3줄 요약
- 데이터 기준 시점, source status, missing data 안내
- 사용자가 "이 화면 설명해줘"라고 할 때 현재 route context 활용

주의:

- 챗봇 서비스가 yfinance 등 외부 provider를 직접 호출하지 않는다.
- 기존 `fetch_latest_asset_context`의 TTL 정책을 재사용한다.
- 실패/빈 데이터는 정상 상태로 보고 친절하게 안내한다.

### Phase 3: 저장 리포트 요약 연동

목표: 로그인 사용자가 이미 저장된 AI 리포트를 챗봇에서 짧게 이해할 수 있게 한다.

포함 후보:

- `GET /api/reports/{ticker}` 조회 결과를 짧게 요약
- Bull/Bear/Risk 관점 비교
- `metadata.data_as_of`, `metadata.source_status`, `metadata.risk_summary` 표시
- 리포트가 없으면 상세 페이지의 기존 리포트 영역으로 이동 안내

명확한 금지:

- 챗봇 메시지만으로 `POST /api/ai/generate/{ticker}` 호출 금지
- 챗봇 응답 중 조용히 LLM 리포트 생성 금지
- 리포트 생성 허용은 별도 사용자 확인 UI, rate limit, 비용 안내가 설계된 뒤 별도 단계에서만 검토

### Phase 4: 상용형 에이전트 경험

목표: 자연어 대화, 도구 호출, 추천 액션, 사용량 관찰을 결합한다.

포함 후보:

- LLM fallback 또는 function/tool calling
- 사용자별 대화 저장
- 실패 의도 분석 로그
- 자주 쓰는 질문 추천
- 응답 스트리밍
- 관리자용 질문 통계
- rate limit, abuse guard, 민감정보 필터링

이 단계부터는 DB 모델, 개인정보 보관 정책, 삭제 기능, 운영 모니터링이 함께 필요하다.

## 권장 아키텍처

### Backend 파일 계획

| 파일 | Phase | 책임 |
| --- | --- | --- |
| `backend/app/api/chat.py` | 1 | 챗봇 HTTP 라우터, 인증 optional 처리, 상태 코드 |
| `backend/app/services/chat_service.py` | 1 | 의도 분류, 자산 해석, 응답 조립 |
| `backend/app/services/chat_tools.py` | 1 | 내부 앱 도구 함수: asset lookup, route builder, feature help |
| `backend/app/schemas.py` | 1 | `ChatMessageRequest`, `ChatResponse`, action/card 스키마 |
| `backend/app/main.py` | 1 | `chat.router` 등록만 수행 |
| `backend/tests/test_chat_service.py` | 1 | 규칙 기반 분류와 route/action 단위 테스트 |
| `backend/tests/test_chat_api.py` | 1 | API smoke, auth optional/required 안내 테스트 |
| `backend/app/models.py` | 4 | 대화 저장 도입 시에만 모델 추가 |

`main.py`에 챗봇 로직을 직접 넣지 않는다. 현재 시장 API 일부가 `main.py`에 남아 있지만, 신규 챗봇 영역은 처음부터 `api/chat.py`와 service layer로 분리한다.

### Frontend 파일 계획

| 파일 | Phase | 책임 |
| --- | --- | --- |
| `frontend/src/components/ChatbotLauncher.jsx` | 1 | 우하단 버튼, 패널 열기/닫기 |
| `frontend/src/components/ChatbotPanel.jsx` | 1 | 패널 레이아웃, 입력폼, 전송 상태 |
| `frontend/src/components/ChatMessageList.jsx` | 1 | 사용자/assistant 메시지 목록 |
| `frontend/src/components/ChatActionCard.jsx` | 1 | navigate/candidate/login 액션 버튼 |
| `frontend/src/store/chatStore.js` | 1 | 패널 상태, 세션 메시지, pending 상태 |
| `frontend/src/utils/chatContext.js` | 1 | current path, ticker, category context 추출 |
| `frontend/src/App.jsx` | 1 | 전역 앱 셸에 launcher 추가 |
| `frontend/src/utils/apiClient.js` | 1 또는 선행 | API base URL 공통화. 챗봇 구현 중 최소 도입 권장 |

현재 프론트는 페이지별로 `http://localhost:8000`이 하드코딩되어 있다. 챗봇만이라도 `apiClient`를 쓰고, 기존 페이지 전체 공통화는 별도 리팩터링으로 분리하는 편이 안전하다.

## API 계약 초안

### Request

```json
{
  "message": "테슬라 보고서 보여줘",
  "current_path": "/detail/TSLA",
  "context": {
    "ticker": "TSLA",
    "category": "us_top10",
    "authenticated": true
  },
  "conversation_id": "session-local-id",
  "client_message_id": "uuid"
}
```

### Response

```json
{
  "answer": "테슬라 상세 페이지에서 가격, 차트, 최신 뉴스, AI 리포트와 커뮤니티를 확인할 수 있습니다.",
  "intent": "asset_detail_navigation",
  "confidence": 0.96,
  "actions": [
    {
      "type": "navigate",
      "label": "테슬라 상세 보기",
      "url": "/detail/TSLA",
      "reason": "테슬라를 TSLA로 해석했습니다.",
      "confidence": 0.96,
      "requires_auth": false
    }
  ],
  "cards": [
    {
      "type": "asset",
      "ticker": "TSLA",
      "name": "테슬라",
      "category": "us_top10",
      "route": "/detail/TSLA"
    }
  ],
  "requires_auth": false,
  "safe_completion": true,
  "disclaimer": "제공 정보는 투자 참고용이며 매수·매도 판단을 대신하지 않습니다."
}
```

### Pydantic 스키마 후보

```python
class ChatContext(BaseModel):
    ticker: str | None = None
    category: str | None = None
    authenticated: bool = False

class ChatMessageRequest(BaseModel):
    message: str
    current_path: str = "/"
    context: ChatContext = ChatContext()
    conversation_id: str | None = None
    client_message_id: str | None = None

class ChatAction(BaseModel):
    type: str
    label: str
    url: str | None = None
    reason: str | None = None
    confidence: float = 0
    requires_auth: bool = False

class ChatCard(BaseModel):
    type: str
    ticker: str | None = None
    name: str | None = None
    category: str | None = None
    route: str | None = None

class ChatResponse(BaseModel):
    answer: str
    intent: str
    confidence: float
    actions: list[ChatAction] = []
    cards: list[ChatCard] = []
    requires_auth: bool = False
    safe_completion: bool = True
    disclaimer: str | None = None
```

Phase 1은 DB 저장이 없으므로 `conversation_id`는 서버가 신뢰하지 않는 클라이언트 세션 식별자 정도로만 사용한다.

## 인증 정책

### 인증 optional endpoint

챗봇 API 자체는 public으로 두되, JWT가 있으면 사용자 정보를 optional로 해석한다.

계획:

- `backend/app/api/deps.py`에 `get_optional_current_user` 후보 추가
- 토큰 없음: `None`
- 토큰 유효: `User`
- 토큰 만료/오류: 챗봇 요청 전체를 401로 막기보다 `authenticated=false`로 안내할지, 기존 보호 API와 일관되게 401을 낼지 결정 필요

권장:

- Phase 1은 토큰 없음 또는 invalid token 모두 기능 안내는 가능하게 한다.
- 다만 저장 리포트 요약 같은 보호 데이터 접근은 `current_user`가 있을 때만 수행한다.

### 로그인 필요 기능 안내

로그인 필요 기능:

- 저장 AI 리포트 조회/요약
- 리포트 생성 버튼 사용
- 댓글 작성/수정/삭제/좋아요/신고
- 향후 사용자별 대화 저장 및 개인화

챗봇은 실제 protected action을 수행하기 전 `/login` 이동 버튼을 제안한다.

## 의도 분류 설계

### Intent 목록

| Intent | 설명 | 대표 액션 |
| --- | --- | --- |
| `asset_detail_navigation` | 특정 자산 상세 요청 | `/detail/:ticker` |
| `market_snapshot_navigation` | 주요 지수/환율 스냅샷 요청 | `/market/:ticker` |
| `category_navigation` | 자산군 목록 요청 | `/category/:type` |
| `report_help` | AI 리포트 조회/설명/생성 위치 문의 | 상세 페이지 또는 `/login` |
| `community_help` | 댓글/토론방/신고/좋아요 문의 | 현재 상세 페이지 또는 자산 선택 |
| `auth_help` | 로그인/권한/Google 로그인 문의 | `/login` |
| `favorite_help` | 즐겨찾기 기능 문의 | 카테고리/상세 화면 안내 |
| `market_summary` | 시장 요약/뉴스/캘린더 문의 | Phase 2 캐시 설명 |
| `current_page_help` | 현재 보고 있는 화면 설명 | current path 기반 안내 |
| `non_financial` | 금융/투자/시장/앱 기능과 무관한 질문 | 고정 안내 문구 |
| `unknown` | 모호하거나 지원 밖 요청 | 재질문 또는 후보 제시 |

### Phase 1 규칙 기반 분류 우선순위

1. 입력 정규화: 소문자화, 공백 정리, 한글/영문 별칭 dictionary lookup
2. 금융 도메인 관련성 판단:
   - 관련: 주식, 지수, 환율, 채권, 원자재, 암호화폐, 뉴스, 리포트, 차트, 가격, 시세, 로그인, 댓글, 즐겨찾기, 앱 화면 이동
   - 무관: 날씨, 요리, 여행, 코딩 일반 질문, 번역, 잡담, 역사, 연예, 게임 등 금융/앱 기능과 연결되지 않는 질문
   - 무관하다고 판단되면 `non_financial`로 종료하고 액션 없이 고정 문구를 반환한다.
3. 명시적 기능 키워드 탐지:
   - 로그인: `로그인`, `계정`, `구글`, `권한`
   - 리포트: `리포트`, `보고서`, `분석`, `AI`
   - 댓글/커뮤니티: `댓글`, `토론`, `종토방`, `신고`, `좋아요`
   - 즐겨찾기: `즐겨찾기`, `관심`, `별`
4. 자산군 키워드 탐지:
   - 미국 주식, 한국 주식, 채권, 원자재, 암호화폐, 코인, 주요 지수, 환율
5. 자산명/티커 후보 탐지
6. current path context 보정
7. confidence 산출
8. confidence가 낮으면 후보 카드 또는 재질문

### 자산 해석 규칙

자산 해석은 다음 소스를 결합한다.

- 백엔드 `market_service.py`의 `INDICES`, `BONDS`, `KR_BONDS`, `COMMODITIES`, `FX`, `US_TOP10`, `KR_TOP10`, `CRYPTOS`
- 프론트 `ASSET_NAMES`와 의미를 맞춘 한글 별칭 dictionary
- `market_cache["prices"]`의 label, payload.symbol
- ticker-like 입력 직접 매칭

예시 dictionary 후보:

| 사용자 표현 | ticker | 기본 route | 비고 |
| --- | --- | --- | --- |
| 삼성전자, 005930 | `005930.KS` | `/detail/005930.KS` | `.KS` 보정 |
| 테슬라, tsla | `TSLA` | `/detail/TSLA` | 대문자 보정 |
| 비트코인, btc | `BTC-USD` | `/detail/BTC-USD` | crypto |
| 이더리움, eth | `ETH-USD` | `/detail/ETH-USD` | crypto |
| 나스닥, 나스닥100 | `^NDX` | `/market/%5ENDX` | 주요 스냅샷 |
| S&P, 에스앤피 | `^GSPC` | `/market/%5EGSPC` | 주요 스냅샷 |
| 코스피 | `^KS11` | `/market/%5EKS11` | 주요 스냅샷 |
| 환율, 달러 | `KRW=X` | `/market/KRW%3DX` | 주요 스냅샷 |
| 금 | `XAU` 또는 `GC=F` | `/detail/XAU` | 앱 캐시 기준으로 통일 |
| 미국 10년물 | `DGS10` | `/detail/DGS10` | 채권 상세 |
| 한국 10년물 | `KTB_10Y` | `/detail/KTB_10Y` | 채권 상세 |

주요 지수/환율은 현재 홈 카드 UX와 일치하도록 `/market/:ticker`를 우선 추천한다. 일반 자산, 채권, 원자재, 암호화폐는 `/detail/:ticker`를 우선 추천한다.

### 모호성 처리

다음 경우에는 바로 이동 버튼 1개만 제안하지 않는다.

- "삼성"처럼 후보가 여러 개인 경우
- "채권 보여줘"처럼 자산군인지 특정 자산인지 불분명한 경우
- "리포트 보여줘"처럼 current ticker가 없는 경우
- route 대상이 앱 캐시에 없는 경우

응답 예:

```json
{
  "answer": "어떤 대상을 보고 싶은지 골라주세요.",
  "intent": "unknown",
  "confidence": 0.45,
  "actions": [
    { "type": "navigate", "label": "채권 목록 보기", "url": "/category/bonds", "confidence": 0.72 },
    { "type": "navigate", "label": "미국 10년물 보기", "url": "/detail/DGS10", "confidence": 0.64 },
    { "type": "navigate", "label": "한국 10년물 보기", "url": "/detail/KTB_10Y", "confidence": 0.61 }
  ]
}
```

### 비금융 질문 처리

챗봇은 금융 도메인과 앱 기능 범위 밖의 질문에 답변하지 않는다. 이 경우 `non_financial` intent를 반환하고, 액션 버튼은 제공하지 않는다.

고정 응답 문구:

```text
죄송하지만 저는 금융 데이터, 투자 리포트, 시장 정보, 그리고 Project Finance 앱 기능 안내를 돕는 챗봇입니다. 금융 관련 질문만 해주세요.
```

예시:

| 사용자 입력 | Intent | 응답 |
| --- | --- | --- |
| `오늘 저녁 뭐 먹을까?` | `non_financial` | 고정 응답 문구 |
| `파이썬 반복문 알려줘` | `non_financial` | 고정 응답 문구 |
| `서울 날씨 알려줘` | `non_financial` | 고정 응답 문구 |

경계 사례:

- `원달러 환율 때문에 여행 경비가 걱정돼`는 환율과 연결되므로 금융 관련 질문으로 처리할 수 있다.
- `테슬라 차 성능 알려줘`는 자동차 제품 질문이면 비금융으로 처리하되, `테슬라 주가/리포트` 맥락이 있으면 금융 질문으로 처리한다.
- `코딩으로 주식 데이터 가져오는 법`은 앱의 금융 데이터 사용법과 직접 연결되지 않으면 비금융으로 처리한다.

## Backend 상세 설계

### `api/chat.py`

책임:

- `POST /api/chat/message`
- request validation
- optional auth dependency 적용
- `chat_service.handle_chat_message(...)` 호출
- 응답 모델 반환

라우터 설계:

```python
router = APIRouter(prefix="/api/chat", tags=["Chat"])

@router.post("/message", response_model=ChatResponse)
async def post_chat_message(
    payload: ChatMessageRequest,
    current_user: User | None = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await handle_chat_message(payload, current_user=current_user, db=db)
```

### `services/chat_service.py`

책임:

- 입력 길이 제한과 sanitization
- intent classification
- entity extraction
- auth-aware response assembly
- 안전 문구 후처리

핵심 함수 후보:

```python
MAX_MESSAGE_LENGTH = 500

async def handle_chat_message(
    payload: ChatMessageRequest,
    current_user: User | None,
    db: AsyncSession,
) -> ChatResponse:
    ...

def classify_intent(message: str, context: ChatContext) -> IntentResult:
    ...

def build_response(intent: IntentResult, user: User | None) -> ChatResponse:
    ...
```

### `services/chat_tools.py`

책임:

- 앱 내부 route와 자산 metadata를 조회/조합한다.
- 외부 API를 직접 호출하지 않는다.
- Phase 2에서도 기존 service/cache 함수만 호출한다.

함수 후보:

```python
def normalize_query(value: str) -> str: ...
def find_asset_candidates(query: str, limit: int = 5) -> list[AssetCandidate]: ...
def route_for_asset(candidate: AssetCandidate, requested_feature: str | None = None) -> str: ...
def route_for_category(query: str) -> ChatAction | None: ...
def feature_help(feature_name: str, context: ChatContext, authenticated: bool) -> ChatResponse: ...
async def summarize_market_cache(query: str, context: ChatContext) -> ChatResponse: ...
async def summarize_saved_report(ticker: str, user: User | None, db: AsyncSession) -> ChatResponse: ...
```

### 데이터 소스 선택

Phase 1에서 asset lookup은 정적 dictionary + `market_cache["prices"]`를 사용한다.

장점:

- DB `assets`에 아직 없는 시장 캐시 자산도 찾을 수 있다.
- 외부 API를 호출하지 않는다.
- 댓글 생성 전에는 DB asset row가 없을 수 있는 현재 구조와 잘 맞는다.

Phase 3에서 저장 리포트 조회가 필요할 때만 DB를 사용한다.

### 응답 안전 후처리

모든 assistant 응답에는 다음 규칙을 적용한다.

- 추천 이동/기능 안내와 투자 판단을 분리한다.
- "매수하세요", "무조건 오릅니다" 같은 금지 표현을 생성하지 않는다.
- 데이터 설명형 응답에는 기준 시점 또는 캐시/제공자 한계를 포함한다.
- 리포트 생성 비용이 드는 액션은 자동 실행하지 않는다고 명시한다.
- 금융/투자/시장/앱 기능과 무관한 질문에는 일반 지식 답변을 생성하지 않고 `non_financial` 고정 문구만 반환한다.

## Frontend 상세 설계

### App shell 배치

`App.jsx`에서 `Header`, `Toaster`, `Routes`와 같은 레이아웃 안쪽에 `ChatbotLauncher`를 추가한다.

권장 위치:

```jsx
<main className="flex-1 pb-12">
  <Routes>...</Routes>
</main>
<ChatbotLauncher />
```

챗봇은 route 위에 고정되는 전역 overlay이므로 route별 페이지와 강하게 결합하지 않는다.

### `chatStore.js`

초기 상태 후보:

```js
{
  isOpen: false,
  messages: [],
  isSending: false,
  error: null,
  conversationId: null,
  open: () => {},
  close: () => {},
  toggle: () => {},
  addMessage: (message) => {},
  clear: () => {},
  sendMessage: async (text, context) => {}
}
```

Phase 1은 서버 저장이 없으므로 세션 메모리만 사용한다. 새로고침 후 대화가 사라져도 MVP에서는 허용한다. 필요하면 `sessionStorage` persistence는 별도 옵션으로 둔다.

### Context extraction

`frontend/src/utils/chatContext.js`는 현재 URL을 분석한다.

```js
export function buildChatContext({ location, authState }) {
  const path = location.pathname;
  const detailMatch = path.match(/^\/detail\/(.+)$/);
  const marketMatch = path.match(/^\/market\/(.+)$/);
  const categoryMatch = path.match(/^\/category\/(.+)$/);

  return {
    current_path: path,
    context: {
      ticker: detailMatch?.[1] || marketMatch?.[1] || null,
      category: categoryMatch?.[1] || null,
      authenticated: Boolean(authState.token),
    },
  };
}
```

주의: `decodeURIComponent`/`encodeURIComponent` 처리를 일관되게 해야 한다. `^NDX`, `KRW=X`처럼 URL encoding이 필요한 ticker가 있다.

### UI 구성

#### Desktop

- 우하단 fixed launcher
- 패널 크기: width 380-420px, height 560-640px
- message list scroll 영역
- 하단 input sticky
- 액션 버튼은 message 아래 compact card로 표시

#### Mobile

- launcher는 우하단 유지
- 패널은 bottom sheet 형태
- 높이는 `min(80vh, available height)`
- 입력창이 키보드에 가려지지 않도록 하단 padding

#### 상태

- empty: 추천 질문 3-4개
- sending: assistant typing row 또는 spinner
- error: "응답을 불러오지 못했습니다. 다시 시도해주세요."
- offline/API error: 재시도 버튼
- auth required: `/login` 버튼
- ambiguous: 후보 액션 카드 2-5개

추천 질문 후보:

- "삼성전자 보고서 보여줘"
- "오늘 환율 어디서 봐?"
- "미국 주식 TOP10 보여줘"
- "댓글은 어떻게 남겨?"

### Action rendering

`ChatActionCard`는 action type에 따라 동작한다.

| type | 프론트 동작 |
| --- | --- |
| `navigate` | `navigate(action.url)` |
| `login` | `navigate("/login")` |
| `candidate` | action을 버튼처럼 보여주고 클릭 시 `navigate` 또는 후속 message 전송 |
| `external` | Phase 1에서는 사용하지 않음 |

백엔드는 브라우저를 직접 이동시키지 않고, 프론트가 action을 해석한다.

## 대표 시나리오

### 1. 특정 자산 상세

입력: `삼성전자 보여줘`

처리:

- `삼성전자` -> `005930.KS`
- intent: `asset_detail_navigation`
- action: `/detail/005930.KS`

응답:

- "삼성전자는 상세 페이지에서 가격, 차트, 최신 뉴스, AI 리포트, 커뮤니티를 볼 수 있습니다."
- 버튼: "삼성전자 상세 보기"

### 2. 주요 지수/환율

입력: `나스닥 오늘 흐름`

처리:

- `나스닥` -> `^NDX`
- intent: `market_snapshot_navigation`
- action: `/market/%5ENDX`

응답:

- "나스닥 100은 홈의 주요 지수 스냅샷 화면에서 1일 흐름을 볼 수 있습니다."
- 버튼: "나스닥 100 스냅샷 보기"

### 3. 자산군 목록

입력: `코인 목록 보여줘`

처리:

- `코인` -> `cryptos`
- intent: `category_navigation`
- action: `/category/cryptos`

응답:

- "암호화폐 목록에서 비트코인과 이더리움 흐름을 볼 수 있습니다."
- 버튼: "암호화폐 목록 보기"

### 4. 로그인 필요 리포트

입력: `테슬라 리포트 보여줘`, unauthenticated

처리:

- ticker: `TSLA`
- intent: `report_help`
- route: `/detail/TSLA`
- requires_auth: true

응답:

- "테슬라 리포트는 로그인 후 상세 페이지에서 볼 수 있습니다. 챗봇은 리포트 생성을 자동 실행하지 않습니다."
- 버튼: "로그인하기"
- 버튼: "테슬라 상세 페이지 보기"

### 5. 현재 상세 페이지 맥락

현재 path: `/detail/TSLA`

입력: `이 리포트 쉽게 설명해줘`

Phase 1:

- "현재 페이지는 테슬라 상세 화면입니다. AI 리포트는 로그인 후 리포트 영역에서 확인할 수 있습니다."
- authenticated이면 "상세 페이지의 AI 분석 리포트 영역을 확인하세요." 안내

Phase 3:

- 저장 리포트 조회 후 bull/bear/risk 요약

### 6. 커뮤니티 도움

입력: `댓글 남기려면 어떻게 해?`

현재 path가 `/detail/TSLA`이면:

- "현재 자산 상세 페이지 아래 종목 토론방에서 댓글을 남길 수 있습니다. 로그인해야 작성할 수 있습니다."
- unauthenticated이면 `/login` 버튼

현재 path가 상세가 아니면:

- "먼저 댓글을 남길 자산을 선택해야 합니다."
- 후보: 미국 주식, 한국 주식, 암호화폐 목록

### 7. 비금융 질문

입력: `오늘 저녁 뭐 먹을까?`

처리:

- 금융/투자/시장/앱 기능 관련 키워드 없음
- intent: `non_financial`
- actions: 없음

응답:

- "죄송하지만 저는 금융 데이터, 투자 리포트, 시장 정보, 그리고 Project Finance 앱 기능 안내를 돕는 챗봇입니다. 금융 관련 질문만 해주세요."

## 구현 순서

### Step 0. 문서 연결

1. `docs/harness/features/chatbot-assistant.md` 생성
2. `docs/harness/feature-index.md`에 챗봇 기능 추가
3. 이 계획서 링크를 새 feature doc의 Change Records에 추가

완료 기준:

- 후속 하네스가 `feature-index.md`에서 챗봇 문서를 찾을 수 있다.

### Step 1. 백엔드 계약과 순수 서비스

1. `schemas.py`에 챗봇 request/response 스키마 추가
2. `services/chat_tools.py` 생성
3. `services/chat_service.py` 생성
4. 정적 asset/category/feature dictionary 작성
5. intent 분류와 route action 생성 단위 테스트 추가

완료 기준:

- API 없이도 `chat_service` 단위 테스트로 대표 시나리오가 통과한다.
- 외부 API/LLM/DB 없이 Phase 1 핵심 로직을 검증할 수 있다.

### Step 2. 백엔드 API 연결

1. `api/chat.py` 생성
2. optional auth dependency 추가 또는 라우터 내부에서 Bearer token optional parsing
3. `main.py`에 `app.include_router(chat.router)` 추가
4. API smoke test 추가

완료 기준:

- `POST /api/chat/message`가 정상 응답한다.
- unauthenticated 요청도 기능 안내를 받을 수 있다.
- 로그인 필요 기능은 `requires_auth`와 `/login` 액션을 반환한다.

### Step 3. 프론트 챗봇 UI

1. `chatStore.js` 생성
2. `chatContext.js` 생성
3. `ChatbotLauncher.jsx` 생성
4. `ChatbotPanel.jsx` 생성
5. `ChatMessageList.jsx` 생성
6. `ChatActionCard.jsx` 생성
7. `App.jsx`에 launcher 추가

완료 기준:

- 사용자가 패널을 열고 닫을 수 있다.
- 메시지를 보내면 assistant 응답이 표시된다.
- action 버튼 클릭 시 route 이동이 된다.

### Step 4. UX 보강

1. empty state 추천 질문
2. loading/error/retry 상태
3. 모바일 bottom sheet 레이아웃
4. action confidence가 낮은 경우 후보 UI
5. safe disclaimer 표시 규칙

완료 기준:

- 네트워크 실패 시 패널이 깨지지 않는다.
- 모바일에서 입력창과 버튼이 화면 밖으로 밀리지 않는다.

### Step 5. Phase 2 데이터 설명

1. market cache summary 함수 추가
2. current page ticker context 활용
3. latest-context 요약 연결
4. 기준 시점/source status 표시
5. provider 실패/빈 데이터 응답 테스트

완료 기준:

- "오늘 시장 요약"에 캐시 기반 답변을 제공한다.
- "이 종목 뉴스 알려줘"에 최신 컨텍스트 요약과 상세 페이지 액션을 제공한다.

### Step 6. Phase 3 저장 리포트 요약

1. authenticated user일 때만 저장 리포트 조회
2. 저장 리포트가 있으면 짧은 요약 생성
3. 저장 리포트가 없으면 자동 생성하지 않고 상세 페이지 안내
4. report metadata 한계/품질 정보 표시

완료 기준:

- 리포트 조회는 가능하지만 생성은 자동 실행되지 않는다.
- 로그인하지 않은 사용자는 `/login` 액션을 받는다.

## 테스트 계획

### Backend unit tests

대상: `backend/tests/test_chat_service.py`

필수 케이스:

- `삼성전자 보여줘` -> `asset_detail_navigation`, `/detail/005930.KS`
- `테슬라 보고서` unauthenticated -> `report_help`, `requires_auth=true`, `/login`, `/detail/TSLA`
- `나스닥` -> `market_snapshot_navigation`, `/market/%5ENDX`
- `코인 목록` -> `category_navigation`, `/category/cryptos`
- `댓글 쓰고 싶어` current `/detail/TSLA` -> `community_help`, login 안내
- `로그인 어디서 해` -> `auth_help`, `/login`
- `채권 보여줘` -> category 또는 후보 액션
- `오늘 저녁 뭐 먹을까?` -> `non_financial`, 고정 안내 문구, action 없음
- empty/too long message -> 422 또는 안전한 validation error

### Backend API tests

대상: `backend/tests/test_chat_api.py`

필수 케이스:

- public request success
- optional auth request success
- invalid payload validation
- response schema shape
- non-financial request returns `non_financial` without actions
- LLM 호출이 발생하지 않음
- report generation endpoint가 호출되지 않음

### Frontend checks

필수 케이스:

- launcher 열기/닫기
- 메시지 입력 후 전송 버튼 disabled/enabled
- sending state
- assistant response rendering
- action button navigate
- error state retry
- mobile layout
- authStore token 여부에 따른 context.authenticated 전달

현재 프론트 테스트 러너가 별도로 구성되어 있지 않으므로, 초기에는 `npm run build`와 브라우저 수동 확인을 기본 검증으로 둔다. 이후 Vitest/React Testing Library 도입은 별도 작업으로 분리한다.

### 통합 수동 시나리오

1. `/`에서 챗봇 열기
2. "삼성전자 보여줘" 입력
3. "삼성전자 상세 보기" 클릭
4. `/detail/005930.KS` 이동 확인
5. 로그아웃 상태에서 "리포트 보여줘" 입력
6. `/login` 액션 표시 확인
7. `/category/cryptos` 이동 질문 확인
8. `/market/%5ENDX` 이동 질문 확인
9. "오늘 저녁 뭐 먹을까?" 입력 시 금융 관련 질문만 해달라는 문구와 액션 없음 확인

## 검증 명령

구현 단계에서 변경 범위에 맞춰 다음을 사용한다.

Backend:

```powershell
cd backend
pytest tests/test_chat_service.py tests/test_chat_api.py
python -m compileall app
```

Frontend:

```powershell
cd frontend
npm run lint
npm run build
npm run dev
```

Cross-stack smoke:

```powershell
cd backend
uvicorn app.main:app --reload
```

```powershell
cd frontend
npm run dev
```

확인:

- `POST http://localhost:8000/api/chat/message`
- `http://localhost:5173`에서 패널 열기/전송/라우팅

## 문서 갱신 계획

구현 시작 시 반드시 갱신할 문서:

- `docs/harness/features/chatbot-assistant.md`
- `docs/harness/feature-index.md`
- `docs/harness/chatbot-feature-implementation-YYYY-MM-DD.md`

기능 문서에 포함할 내용:

- Current Behavior
- Ownership Map
- Data Flow
- Contracts
- Change Rules
- Verification
- Change Records
- Open Risks

기존 feature doc과 연결:

- frontend shell 변경: `frontend-routing-shell.md`
- market cache 활용: `market-data.md`
- AI 리포트/커뮤니티 안내: `asset-detail-ai-community.md`
- 로그인 안내/optional auth: `authentication.md`

## 위험과 대응

| 위험 | 영향 | 대응 |
| --- | --- | --- |
| LLM 비용 증가 | 운영 비용 증가 | Phase 1 규칙 기반, LLM fallback 비활성 |
| 리포트 생성 비용 증가 | OpenAI/API 사용량 증가 | 챗봇 자동 생성 금지 |
| 잘못된 투자 조언 | 제품 신뢰/규제 리스크 | 단정적 조언 금지, 안전 문구 후처리 |
| 비금융 질문에 일반 답변 생성 | 챗봇 제품 범위 이탈 | `non_financial` intent와 고정 문구 |
| 잘못된 라우팅 | 사용자 혼란 | confidence 기준, 후보 UI |
| 자산명 중복/모호성 | 오탐 라우팅 | 후보 2-5개 제시 |
| 프론트 API base URL 중복 | 유지보수 비용 | 챗봇 API부터 `apiClient` 사용 |
| current path encoding 오류 | `^NDX`, `KRW=X` 라우팅 실패 | encode/decode 테스트 |
| invalid token 처리 | UX 불안정 | optional auth 정책 명확화 |
| 대화 저장 개인정보 이슈 | 개인정보/삭제 요구 | Phase 1 서버 저장 없음 |
| 외부 provider 실패 | 빈 데이터/지연 | 기존 cache/TTL 재사용, 실패 안내 |
| `AssetDetail.jsx` 책임 과다 | 추가 복잡도 | 챗봇은 전역 컴포넌트로 분리 |

## Risky Change Confirmation Points

다음 변경은 구현 전에 사용자 확인을 받는다.

- DB에 챗봇 대화 저장 테이블 추가
- LLM fallback 또는 Responses/function calling 도입
- 챗봇에서 리포트 생성을 직접 트리거
- scheduler 빈도 변경
- API provider 추가 또는 유료 API 연결
- 인증 정책 변경으로 기존 protected endpoint 동작 변경

## MVP 완료 기준

Phase 1은 다음 조건을 만족하면 완료로 본다.

- 전역 챗봇 버튼과 패널이 모든 route에서 보인다.
- 사용자는 메시지를 입력하고 응답을 받을 수 있다.
- 최소 8개 intent를 안정적으로 분류한다.
- 주요 자산명/티커/카테고리 요청에 대해 이동 버튼을 제공한다.
- 모호한 요청에는 후보를 2-5개 보여준다.
- 로그인 필요 기능은 `/login` 액션과 함께 안내한다.
- 금융과 무관한 질문에는 고정 문구로 금융 관련 질문만 요청한다.
- 챗봇은 리포트 생성을 자동 실행하지 않는다.
- 모바일/데스크톱에서 패널이 주요 화면을 망가뜨리지 않는다.
- 백엔드 단위/API 테스트와 프론트 build 검증이 완료된다.
- 챗봇 feature doc과 change record가 갱신된다.

## 최종 권장안

첫 구현은 "전역 내비게이션 챗봇"으로 진행한다. 이 프로젝트는 이미 홈, 카테고리, 시장 스냅샷, 상세, AI 리포트, 커뮤니티, 로그인이라는 명확한 목적지가 있으므로, 챗봇이 처음부터 투자 분석을 새로 생성하기보다 사용자의 말을 앱 내부 action으로 바꾸는 역할을 맡는 것이 가장 안전하다.

구현은 백엔드의 규칙 기반 `chat_service`를 먼저 완성하고, 그 다음 프론트 전역 패널을 붙이는 순서가 좋다. 이렇게 하면 UI 구현 중에도 API 계약이 흔들리지 않고, LLM/API 비용 없이 대표 시나리오를 빠르게 검증할 수 있다.
