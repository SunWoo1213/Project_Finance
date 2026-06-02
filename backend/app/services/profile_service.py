from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User

NICKNAME_PATTERN = re.compile(r"^[0-9A-Za-z가-힣 _-]+$")
MIN_NICKNAME_LENGTH = 2
MAX_NICKNAME_LENGTH = 20


def normalize_nickname(value: str | None) -> str:
    nickname = re.sub(r"\s+", " ", str(value or "").strip())
    return nickname


def validate_nickname(value: str | None) -> tuple[bool, str, str]:
    nickname = normalize_nickname(value)
    if len(nickname) < MIN_NICKNAME_LENGTH:
        return False, nickname, "닉네임은 2자 이상이어야 합니다."
    if len(nickname) > MAX_NICKNAME_LENGTH:
        return False, nickname, "닉네임은 20자 이하로 입력해주세요."
    if not NICKNAME_PATTERN.fullmatch(nickname):
        return False, nickname, "닉네임은 한글, 영문, 숫자, 공백, _, -만 사용할 수 있습니다."
    return True, nickname, "사용할 수 있는 닉네임입니다."


async def find_user_by_nickname(db: AsyncSession, nickname: str) -> User | None:
    result = await db.execute(
        select(User).where(func.lower(User.nickname) == nickname.lower())
    )
    return result.scalar_one_or_none()


async def check_nickname_availability(
    db: AsyncSession,
    *,
    nickname: str | None,
    current_user: User,
) -> dict:
    valid, normalized, message = validate_nickname(nickname)
    if not valid:
        return {
            "nickname": normalized,
            "available": False,
            "valid": False,
            "message": message,
        }

    existing = await find_user_by_nickname(db, normalized)
    available = existing is None or existing.id == current_user.id
    return {
        "nickname": normalized,
        "available": available,
        "valid": True,
        "message": "사용할 수 있는 닉네임입니다." if available else "이미 사용 중인 닉네임입니다.",
    }


async def update_user_nickname(
    db: AsyncSession,
    *,
    current_user: User,
    nickname: str | None,
) -> User:
    availability = await check_nickname_availability(db, nickname=nickname, current_user=current_user)
    if not availability["valid"] or not availability["available"]:
        raise ValueError(availability["message"])

    current_user.nickname = availability["nickname"]
    current_user.nickname_confirmed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(current_user)
    return current_user
