import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api import chat


async def override_db():
    yield object()


@pytest.mark.asyncio
async def test_chat_api_requires_authentication():
    app = FastAPI()
    app.include_router(chat.router)
    app.dependency_overrides[chat.get_db] = override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/chat/message", json={"message": "삼성전자 보여줘"})

    assert response.status_code == 401


async def override_pro_user():
    return object()


@pytest.mark.asyncio
async def test_chat_api_pro_request_success():
    app = FastAPI()
    app.include_router(chat.router)
    app.dependency_overrides[chat.get_db] = override_db
    app.dependency_overrides[chat.require_chatbot_access] = override_pro_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/chat/message", json={"message": "삼성전자 보여줘"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "asset_detail_navigation"
    assert payload["actions"][0]["url"] == "/detail/005930.KS"


@pytest.mark.asyncio
async def test_chat_api_non_financial_response_has_no_actions():
    app = FastAPI()
    app.include_router(chat.router)
    app.dependency_overrides[chat.get_db] = override_db
    app.dependency_overrides[chat.require_chatbot_access] = override_pro_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/chat/message", json={"message": "서울 날씨 알려줘"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "non_financial"
    assert payload["actions"] == []


@pytest.mark.asyncio
async def test_chat_api_invalid_payload_validation():
    app = FastAPI()
    app.include_router(chat.router)
    app.dependency_overrides[chat.get_db] = override_db
    app.dependency_overrides[chat.require_chatbot_access] = override_pro_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/chat/message", json={"message": ""})

    assert response.status_code == 422
