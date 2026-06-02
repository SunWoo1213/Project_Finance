from datetime import datetime
import os

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

os.environ.setdefault("PROJECT_NAME", "test")
os.environ.setdefault("API_V1_STR", "/api")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

from app.api import community, profile
from app.models import Asset, AssetCategory, User
from billing_test_utils import create_test_sessionmaker


@pytest.mark.asyncio
async def test_profile_nickname_availability_and_update():
    engine, Session = await create_test_sessionmaker()
    async with Session() as db:
        db.add(User(email="profile@example.com", nickname="profile"))
        db.add(User(email="taken@example.com", nickname="taken"))
        await db.commit()

    async def override_db():
        async with Session() as db:
            yield db

    async def override_current_user(db=Depends(profile.get_db)):
        result = await db.execute(select(User).where(User.email == "profile@example.com"))
        return result.scalar_one()

    app = FastAPI()
    app.include_router(profile.router)
    app.dependency_overrides[profile.get_db] = override_db
    app.dependency_overrides[profile.get_current_user] = override_current_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/profile/nickname-availability", params={"nickname": "taken"})
            assert response.status_code == 200
            assert response.json()["available"] is False

            response = await client.patch("/api/profile/nickname", json={"nickname": "new profile"})
            assert response.status_code == 200
            assert response.json()["nickname_confirmed"] is True
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_comment_create_requires_confirmed_nickname():
    engine, Session = await create_test_sessionmaker()
    async with Session() as db:
        db.add(User(email="profile@example.com", nickname="profile"))
        db.add(Asset(ticker="NVDA", name="NVIDIA", category=AssetCategory.STOCK_US))
        await db.commit()

    async def override_db():
        async with Session() as db:
            yield db

    async def override_current_user_unconfirmed(db=Depends(community.get_db)):
        result = await db.execute(select(User).where(User.email == "profile@example.com"))
        return result.scalar_one()

    async def override_current_user_confirmed(db=Depends(community.get_db)):
        result = await db.execute(select(User).where(User.email == "profile@example.com"))
        user = result.scalar_one()
        user.nickname_confirmed_at = datetime.utcnow()
        await db.commit()
        await db.refresh(user)
        return user

    app = FastAPI()
    app.include_router(community.router)
    app.dependency_overrides[community.get_db] = override_db
    app.dependency_overrides[community.get_current_user] = override_current_user_unconfirmed

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/community/NVDA/comments", json={"content": "hello"})
            assert response.status_code == 403
            assert response.json()["detail"]["code"] == "NICKNAME_REQUIRED"

            app.dependency_overrides[community.get_current_user] = override_current_user_confirmed
            response = await client.post("/api/community/NVDA/comments", json={"content": "hello"})
            assert response.status_code == 200
    finally:
        await engine.dispose()
