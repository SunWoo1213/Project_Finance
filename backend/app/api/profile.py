from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..models import User
from ..schemas import (
    NicknameAvailabilityResponse,
    NicknameUpdateRequest,
    NicknameUpdateResponse,
    ProfileMeResponse,
)
from ..services.notification_service import get_or_create_preferences
from ..services.profile_service import check_nickname_availability, update_user_nickname
from .deps import get_current_user

router = APIRouter(prefix="/api/profile", tags=["Profile"])


def _profile_complete(user: User) -> bool:
    return user.nickname_confirmed_at is not None


def _preference_payload(preference) -> dict:
    return {
        "telegram_enabled": preference.telegram_enabled,
        "email_enabled": preference.email_enabled,
        "price_change_enabled": preference.price_change_enabled,
        "news_enabled": preference.news_enabled,
        "report_enabled": preference.report_enabled,
        "daily_digest_enabled": preference.daily_digest_enabled,
        "price_change_threshold_percent": preference.price_change_threshold_percent,
        "quiet_hours_start": preference.quiet_hours_start,
        "quiet_hours_end": preference.quiet_hours_end,
        "timezone": preference.timezone,
        "updated_at": preference.updated_at,
    }


@router.get("/me", response_model=ProfileMeResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    preferences = await get_or_create_preferences(db, current_user.id)
    confirmed = _profile_complete(current_user)
    return ProfileMeResponse(
        id=current_user.id,
        email=current_user.email,
        nickname=current_user.nickname,
        nickname_confirmed=confirmed,
        profile_complete=confirmed,
        nickname_confirmed_at=current_user.nickname_confirmed_at,
        notification_preferences=_preference_payload(preferences),
    )


@router.get("/nickname-availability", response_model=NicknameAvailabilityResponse)
async def get_nickname_availability(
    nickname: str = Query(..., min_length=1, max_length=40),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await check_nickname_availability(db, nickname=nickname, current_user=current_user)


@router.patch("/nickname", response_model=NicknameUpdateResponse)
async def patch_nickname(
    payload: NicknameUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await update_user_nickname(db, current_user=current_user, nickname=payload.nickname)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return NicknameUpdateResponse(
        id=user.id,
        email=user.email,
        nickname=user.nickname,
        nickname_confirmed=True,
        profile_complete=True,
        nickname_confirmed_at=user.nickname_confirmed_at,
    )
