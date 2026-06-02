from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..models import User
from ..schemas import (
    ChannelConnectResponse,
    EmailConfirmRequest,
    EmailVerifyRequest,
    NotificationChannelResponse,
    NotificationHistoryResponse,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
    NotificationTestRequest,
    NotificationTestResponse,
    TelegramVerifyRequest,
)
from ..services.notification_service import (
    create_channel_verification,
    create_test_notification,
    delete_channel,
    get_or_create_preferences,
    list_channels,
    list_history,
    update_preferences,
    verify_channel,
)
from .deps import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


def _preference_response(preference) -> NotificationPreferenceResponse:
    return NotificationPreferenceResponse(
        telegram_enabled=preference.telegram_enabled,
        email_enabled=preference.email_enabled,
        price_change_enabled=preference.price_change_enabled,
        news_enabled=preference.news_enabled,
        report_enabled=preference.report_enabled,
        daily_digest_enabled=preference.daily_digest_enabled,
        price_change_threshold_percent=preference.price_change_threshold_percent,
        quiet_hours_start=preference.quiet_hours_start,
        quiet_hours_end=preference.quiet_hours_end,
        timezone=preference.timezone,
        updated_at=preference.updated_at,
    )


@router.get("/preferences", response_model=NotificationPreferenceResponse)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    preference = await get_or_create_preferences(db, current_user.id)
    return _preference_response(preference)


@router.put("/preferences", response_model=NotificationPreferenceResponse)
async def put_preferences(
    payload: NotificationPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    preference = await update_preferences(
        db,
        current_user.id,
        payload.model_dump(exclude_unset=True),
    )
    return _preference_response(preference)


@router.get("/channels", response_model=list[NotificationChannelResponse])
async def get_channels(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_channels(db, current_user.id)


@router.post("/channels/telegram/connect", response_model=ChannelConnectResponse)
async def connect_telegram(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    connection = await create_channel_verification(
        db,
        user_id=current_user.id,
        channel="telegram",
    )
    return ChannelConnectResponse(
        channel="telegram",
        verification_code=connection.verification_code or "",
        verification_expires_at=connection.verification_expires_at,
        message="Telegram bot에 /start <code> 형식으로 코드를 전달한 뒤 verify를 호출하세요.",
    )


@router.post("/channels/telegram/verify", response_model=NotificationChannelResponse)
async def verify_telegram(
    payload: TelegramVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        connection = await verify_channel(
            db,
            user_id=current_user.id,
            channel="telegram",
            code=payload.code,
            destination=payload.chat_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return connection


@router.delete("/channels/telegram", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_telegram(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await delete_channel(db, user_id=current_user.id, channel="telegram")


@router.post("/channels/email/verify", response_model=ChannelConnectResponse)
async def request_email_verification(
    payload: EmailVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    destination = str(payload.email or current_user.email).lower()
    connection = await create_channel_verification(
        db,
        user_id=current_user.id,
        channel="email",
        destination=destination,
    )
    return ChannelConnectResponse(
        channel="email",
        verification_code=connection.verification_code or "",
        verification_expires_at=connection.verification_expires_at,
        message="프로토타입에서는 확인 코드를 응답으로 반환합니다. 운영 발송은 email provider 설정 후 연결하세요.",
    )


@router.post("/channels/email/confirm", response_model=NotificationChannelResponse)
async def confirm_email(
    payload: EmailConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    destination = str(payload.email or current_user.email).lower()
    try:
        connection = await verify_channel(
            db,
            user_id=current_user.id,
            channel="email",
            code=payload.code,
            destination=destination,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return connection


@router.delete("/channels/email", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_email(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await delete_channel(db, user_id=current_user.id, channel="email")


@router.get("/history", response_model=list[NotificationHistoryResponse])
async def get_history(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_history(db, user_id=current_user.id, limit=limit)


@router.post("/test", response_model=NotificationTestResponse)
async def send_test_notification(
    payload: NotificationTestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    created, sent, failed = await create_test_notification(
        db,
        user_id=current_user.id,
        ticker=payload.ticker,
        message=payload.message,
    )
    return NotificationTestResponse(
        created_events=created,
        sent_events=sent,
        failed_events=failed,
        message="테스트 알림 처리가 완료되었습니다.",
    )
