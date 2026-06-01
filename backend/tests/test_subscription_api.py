from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api import billing


async def override_db():
    yield object()


async def override_current_user():
    return SimpleNamespace(id=1, email="user@example.com", nickname="tester")


@pytest.mark.asyncio
async def test_billing_plans_are_public():
    app = FastAPI()
    app.include_router(billing.router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/billing/plans")

    assert response.status_code == 200
    payload = response.json()
    assert [plan["tier"] for plan in payload] == ["FREE", "PLUS", "PRO"]


@pytest.mark.asyncio
async def test_billing_me_requires_authentication():
    app = FastAPI()
    app.include_router(billing.router)
    app.dependency_overrides[billing.get_db] = override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/billing/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_billing_me_returns_free_entitlements_until_subscription_storage_exists():
    app = FastAPI()
    app.include_router(billing.router)
    app.dependency_overrides[billing.get_db] = override_db
    app.dependency_overrides[billing.get_current_user] = override_current_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/billing/me")

    assert response.status_code == 200
    payload = response.json()
    assert payload["tier"] == "FREE"
    assert payload["status"] == "NONE"
    assert payload["entitlements"] == {
        "can_view_reports": False,
        "can_use_chatbot": False,
    }
