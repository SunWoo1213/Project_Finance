import pytest

from app.core.config import settings
from app.schemas import ChatContext, ChatMessageRequest, ChatTurn
from app.services import chat_service
from app.services.chat_llm import LlmChatPlan
from app.services.chat_service import handle_chat_message


class UnusedDb:
    async def execute(self, *_args, **_kwargs):
        raise AssertionError("This scenario should not query the database")


@pytest.mark.asyncio
async def test_chat_service_routes_samsung_detail():
    response = await handle_chat_message(
        ChatMessageRequest(message="삼성전자 보여줘"),
        current_user=None,
        db=UnusedDb(),
    )

    assert response.intent == "asset_detail_navigation"
    assert response.actions[0].url == "/detail/005930.KS"


@pytest.mark.asyncio
async def test_chat_service_guides_unauthenticated_report_to_login():
    response = await handle_chat_message(
        ChatMessageRequest(message="테슬라 보고서"),
        current_user=None,
        db=UnusedDb(),
    )

    assert response.intent == "report_help"
    assert response.requires_auth is True
    assert any(action.url == "/login" for action in response.actions)
    assert any(action.url == "/detail/TSLA" for action in response.actions)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message,ticker",
    [
        ("네이버 주가 보여줘", "/detail/035420.KS"),
        ("엘지엔솔 어때", "/detail/373220.KS"),
        ("브로드컴 상세", "/detail/AVGO"),
        ("일라이릴리 보여줘", "/detail/LLY"),
        ("포스코홀딩스 보여줘", "/detail/005490.KS"),
    ],
)
async def test_chat_service_resolves_expanded_aliases(message, ticker):
    response = await handle_chat_message(
        ChatMessageRequest(message=message),
        current_user=None,
        db=UnusedDb(),
    )

    assert response.intent == "asset_detail_navigation"
    assert response.actions[0].url == ticker


@pytest.mark.asyncio
async def test_chat_service_routes_nasdaq_market_snapshot():
    response = await handle_chat_message(
        ChatMessageRequest(message="나스닥 오늘 흐름"),
        current_user=None,
        db=UnusedDb(),
    )

    assert response.intent == "market_snapshot_navigation"
    assert response.actions[0].url == "/market/%5EIXIC"


@pytest.mark.asyncio
async def test_chat_service_routes_crypto_category():
    response = await handle_chat_message(
        ChatMessageRequest(message="코인 목록 보여줘"),
        current_user=None,
        db=UnusedDb(),
    )

    assert response.intent == "category_navigation"
    assert response.actions[0].url == "/category/cryptos"


@pytest.mark.asyncio
async def test_chat_service_community_help_uses_current_detail_context():
    response = await handle_chat_message(
        ChatMessageRequest(
            message="댓글 쓰고 싶어",
            current_path="/detail/TSLA",
            context=ChatContext(ticker="TSLA", authenticated=False),
        ),
        current_user=None,
        db=UnusedDb(),
    )

    assert response.intent == "community_help"
    assert response.requires_auth is True
    assert any(action.url == "/login" for action in response.actions)
    assert any(action.url == "/detail/TSLA" for action in response.actions)


@pytest.mark.asyncio
async def test_chat_service_auth_help():
    response = await handle_chat_message(
        ChatMessageRequest(message="로그인 어디서 해"),
        current_user=None,
        db=UnusedDb(),
    )

    assert response.intent == "auth_help"
    assert response.actions[0].url == "/login"


@pytest.mark.asyncio
async def test_chat_service_ambiguous_bond_request_returns_candidates():
    response = await handle_chat_message(
        ChatMessageRequest(message="채권 보여줘"),
        current_user=None,
        db=UnusedDb(),
    )

    assert response.intent in {"category_navigation", "unknown"}
    assert any(action.url == "/category/bonds" for action in response.actions)
    assert len(response.actions) >= 2


@pytest.mark.asyncio
async def test_chat_service_rejects_non_financial_request():
    response = await handle_chat_message(
        ChatMessageRequest(message="오늘 저녁 뭐 먹을까?"),
        current_user=None,
        db=UnusedDb(),
    )

    assert response.intent == "non_financial"
    assert response.actions == []
    assert "금융 관련 질문만" in response.answer


@pytest.mark.asyncio
async def test_llm_path_maps_plan_to_response(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_LLM_CHATBOT", True)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")

    captured = {}

    async def fake_compose(*, message, history, grounding):
        captured["history"] = history
        captured["grounding"] = grounding
        return LlmChatPlan(
            answer="삼성전자는 한국 대표 반도체 기업입니다. 상세 페이지에서 시세와 리포트를 볼 수 있어요.",
            intent="asset_detail_navigation",
            confidence=0.83,
            action_indices=[0],
        )

    monkeypatch.setattr(chat_service.chat_llm, "compose_chat_answer", fake_compose)

    response = await handle_chat_message(
        ChatMessageRequest(
            message="삼성전자 요즘 어때?",
            history=[ChatTurn(role="user", content="안녕"), ChatTurn(role="assistant", content="안녕하세요")],
        ),
        current_user=None,
        db=UnusedDb(),
    )

    assert response.intent == "asset_detail_navigation"
    assert response.confidence == 0.83
    assert response.actions and response.actions[0].url == "/detail/005930.KS"
    assert response.disclaimer  # non-non_financial keeps disclaimer
    # History is forwarded to the LLM layer as plain dicts.
    assert captured["history"][0] == {"role": "user", "content": "안녕"}
    # Grounding never carries a report-generation action.
    assert all("생성" not in (a.get("label") or "") for a in captured["grounding"]["actions"])


@pytest.mark.asyncio
async def test_llm_path_falls_back_to_rules_when_plan_is_none(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_LLM_CHATBOT", True)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")

    async def fake_compose(*, message, history, grounding):
        return None

    monkeypatch.setattr(chat_service.chat_llm, "compose_chat_answer", fake_compose)

    response = await handle_chat_message(
        ChatMessageRequest(message="삼성전자 보여줘"),
        current_user=None,
        db=UnusedDb(),
    )

    # Falls back to the deterministic rule-based path.
    assert response.intent == "asset_detail_navigation"
    assert response.actions[0].url == "/detail/005930.KS"
