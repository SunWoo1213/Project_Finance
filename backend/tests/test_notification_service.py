import os

import pytest

os.environ.setdefault("PROJECT_NAME", "test")
os.environ.setdefault("API_V1_STR", "/api")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

from app.core.cache import market_cache
from app.models import User
from app.services.favorite_service import upsert_user_favorite
from app.services.notification_service import evaluate_notifications, list_history
from billing_test_utils import create_test_sessionmaker


@pytest.mark.asyncio
async def test_evaluate_notifications_uses_market_cache_and_dedupes_price_events():
    engine, Session = await create_test_sessionmaker()
    original_prices = market_cache.get("prices")
    market_cache["prices"] = {
        "us_top10": {
            "NVIDIA": {
                "symbol": "NVDA",
                "currentPrice": 1000,
                "changePercent": 4.2,
                "history_prices": [960, 1000],
                "marketCap": 100,
            }
        }
    }

    try:
        async with Session() as db:
            user = User(email="service@example.com", nickname="service")
            db.add(user)
            await db.flush()
            await upsert_user_favorite(
                db,
                user_id=user.id,
                ticker="NVDA",
                display_name="NVIDIA",
                category_key="us_top10",
            )

        async with Session() as db:
            created = await evaluate_notifications(db)
            assert created == 1
            created_again = await evaluate_notifications(db)
            assert created_again == 0
            history = await list_history(db, user_id=1)

        assert len(history) == 1
        assert history[0].event_type == "price_change"
        assert history[0].channel == "in_app"
        assert history[0].status == "sent"
    finally:
        market_cache["prices"] = original_prices
        await engine.dispose()
