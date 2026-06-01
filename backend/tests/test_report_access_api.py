from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app import main
from app.api import deps
from app.schemas import SubscriptionStatus, SubscriptionTier


class EmptyReportDb:
    async def execute(self, query):
        _ = query
        return self

    def first(self):
        return None


async def override_db():
    yield EmptyReportDb()


async def override_current_user():
    return SimpleNamespace(id=1, email="user@example.com", nickname="tester")


def build_report_test_app():
    app = FastAPI()
    app.get("/api/reports/{ticker}")(main.get_latest_report)
    app.dependency_overrides[main.get_db] = override_db
    return app


@pytest.mark.asyncio
async def test_report_route_requires_authentication():
    app = build_report_test_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/reports/NVDA")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_report_route_blocks_free_entitlement(monkeypatch):
    async def free_entitlements(user, db):
        _ = (user, db)
        return SimpleNamespace(
            tier=SubscriptionTier.FREE,
            status=SubscriptionStatus.NONE,
            can_view_reports=False,
            can_use_chatbot=False,
        )

    app = build_report_test_app()
    app.dependency_overrides[deps.get_current_user] = override_current_user
    monkeypatch.setattr(deps, "get_user_entitlements", free_entitlements)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/reports/NVDA")

    assert response.status_code == 403
    assert response.json()["detail"] == "AI report access requires an active Plus or Pro subscription."


@pytest.mark.asyncio
@pytest.mark.parametrize("tier", [SubscriptionTier.PLUS, SubscriptionTier.PRO])
async def test_report_route_allows_paid_entitlements_to_reach_stored_report_lookup(monkeypatch, tier):
    async def paid_entitlements(user, db):
        _ = (user, db)
        return SimpleNamespace(
            tier=tier,
            status=SubscriptionStatus.ACTIVE,
            can_view_reports=True,
            can_use_chatbot=tier == SubscriptionTier.PRO,
        )

    app = build_report_test_app()
    app.dependency_overrides[deps.get_current_user] = override_current_user
    monkeypatch.setattr(deps, "get_user_entitlements", paid_entitlements)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/reports/NVDA")

    assert response.status_code == 404
    assert response.json()["detail"] == "No report found for ticker: NVDA"
