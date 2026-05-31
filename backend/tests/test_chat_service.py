import pytest

from app.schemas import ChatContext, ChatMessageRequest
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
async def test_chat_service_routes_nasdaq_market_snapshot():
    response = await handle_chat_message(
        ChatMessageRequest(message="나스닥 오늘 흐름"),
        current_user=None,
        db=UnusedDb(),
    )

    assert response.intent == "market_snapshot_navigation"
    assert response.actions[0].url == "/market/%5ENDX"


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
