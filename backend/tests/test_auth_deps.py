import pytest
from fastapi import HTTPException
from jose import jwt

from app.api.deps import get_current_user
from app.core.config import settings


class FailingDb:
    async def execute(self, *_args, **_kwargs):
        raise AssertionError("DB should not be queried for an invalid JWT subject")


@pytest.mark.asyncio
async def test_get_current_user_rejects_non_numeric_subject():
    token = jwt.encode({"sub": "not-a-number"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token, db=FailingDb())

    assert exc_info.value.status_code == 401
