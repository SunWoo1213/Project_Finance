from __future__ import annotations

import hashlib
import hmac
import json

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base


async def create_test_sessionmaker():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def signed_json_headers(payload: dict, secret: str) -> dict[str, str]:
    raw_body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return {"x-payment-signature": signature}
