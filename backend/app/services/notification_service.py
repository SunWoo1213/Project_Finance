from __future__ import annotations

import hashlib
import json
import secrets
import base64
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.cache import market_cache
from ..core.config import settings
from ..models import (
    AIReport,
    Asset,
    AssetNotificationSnapshot,
    NotificationChannelConnection,
    NotificationEvent,
    NotificationPreference,
    UserFavoriteAsset,
)


DEFAULT_CHANNELS = ("in_app",)
DELIVERY_CHANNELS = ("telegram", "email")
GMAIL_REQUIRED_SETTINGS = (
    "EMAIL_FROM_ADDRESS",
    "GMAIL_CLIENT_ID",
    "GMAIL_CLIENT_SECRET",
    "GMAIL_REFRESH_TOKEN",
)
REPORT_NOTIFICATION_TITLE = "즐겨찾기한 자산에 대한 보고서 발신입니다."
WELCOME_NOTIFICATION_TITLE = "Project Finance를 이용해주셔서 감사합니다."
WELCOME_NOTIFICATION_BODY = (
    "Project Finance를 이용해주셔서 감사합니다.\n"
    "관심 자산을 즐겨찾기하면 주요 리포트와 알림을 이 채널로 받아보실 수 있습니다.\n"
    "오늘도 좋은 하루 보내세요."
)


@dataclass
class DeliveryResult:
    success: bool
    error_message: str | None = None


@dataclass
class GmailAccessTokenResult:
    success: bool
    access_token: str | None = None
    error_message: str | None = None


def _missing_setting_names(names: tuple[str, ...]) -> list[str]:
    return [name for name in names if not getattr(settings, name)]


def get_delivery_configuration_status() -> dict[str, Any]:
    provider = (settings.EMAIL_PROVIDER or "gmail").strip().lower()
    gmail_missing = _missing_setting_names(GMAIL_REQUIRED_SETTINGS)
    telegram_missing = [] if settings.TELEGRAM_BOT_TOKEN else ["TELEGRAM_BOT_TOKEN"]
    email_configured = provider == "gmail" and not gmail_missing

    return {
        "scheduler": {
            "enabled": bool(settings.ENABLE_SCHEDULER and settings.ENABLE_NOTIFICATION_SCHEDULER),
            "enable_scheduler": bool(settings.ENABLE_SCHEDULER),
            "enable_notification_scheduler": bool(settings.ENABLE_NOTIFICATION_SCHEDULER),
        },
        "email": {
            "provider": provider,
            "configured": email_configured,
            "missing_keys": gmail_missing if provider == "gmail" else [],
            "error": None if email_configured else (
                "EMAIL_PROVIDER must be gmail."
                if provider != "gmail"
                else "Gmail email settings are incomplete."
            ),
        },
        "telegram": {
            "configured": not telegram_missing,
            "missing_keys": telegram_missing,
            "error": None if not telegram_missing else "Telegram bot token is not configured.",
            "verification_mode": "manual_chat_id",
        },
    }


def _now() -> datetime:
    return datetime.utcnow()


def _verification_code() -> str:
    return secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:10].upper()


def _news_fingerprint(item: dict[str, Any]) -> str:
    raw = "|".join(
        str(item.get(key) or "").strip()
        for key in ("title", "source", "link", "published_at")
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _find_price_payload(ticker: str) -> dict[str, Any] | None:
    for group in (market_cache.get("prices") or {}).values():
        if not isinstance(group, dict):
            continue
        for item in group.values():
            if not isinstance(item, dict):
                continue
            if item.get("symbol") == ticker:
                return item
    return None


def _build_asset_detail_url(ticker: str) -> str:
    safe_ticker = urllib.parse.quote(ticker, safe="")
    return f"{settings.FRONTEND_BASE_URL}/detail/{safe_ticker}"


def _extract_current_price(payload: dict[str, Any] | None) -> float | None:
    if not payload:
        return None
    raw_price = payload.get("currentPrice", payload.get("price"))
    if raw_price in (None, ""):
        return None
    try:
        return float(raw_price)
    except (TypeError, ValueError):
        return None


def _format_notification_price(
    ticker: str,
    favorite: UserFavoriteAsset,
    payload: dict[str, Any] | None,
) -> tuple[float | None, str, str | None]:
    price = _extract_current_price(payload)
    price_source = None
    if payload:
        price_source = str(
            payload.get("source")
            or payload.get("provider")
            or payload.get("priceSource")
            or "market_cache"
        )
    if price is None:
        return None, "확인 중", price_source

    category = (favorite.category_key or "").lower()
    upper_ticker = ticker.upper()
    if "bond" in category or upper_ticker.startswith("DGS"):
        return price, f"{price:,.2f}%", price_source
    if "kr" in category or upper_ticker.endswith(".KS") or upper_ticker.endswith(".KQ"):
        return price, f"₩{price:,.0f}", price_source
    if "crypto" in category or upper_ticker.endswith("-USD"):
        decimals = 2 if abs(price) >= 1 else 6
        return price, f"${price:,.{decimals}f}", price_source
    if "commodity" in category or "stock_us" in category or "index" in category:
        return price, f"${price:,.2f}", price_source
    return price, f"{price:,.2f}", price_source


def _build_report_notification_body(
    *,
    asset_name: str,
    ticker: str,
    detail_url: str,
    current_price_text: str,
) -> str:
    return (
        "오늘 하루도 좋은 흐름으로 보내시길 바랍니다.\n\n"
        f"즐겨찾기하신 {asset_name}({ticker}) 리포트가 준비되었습니다.\n"
        f"현재 가격: {current_price_text}\n"
        f"자산 리포트 링크: {detail_url}"
    )


def _find_news_items(ticker: str) -> list[dict[str, Any]]:
    latest_context = (market_cache.get("latest_context") or {}).get(ticker)
    if isinstance(latest_context, dict) and isinstance(latest_context.get("news"), list):
        return [item for item in latest_context["news"] if isinstance(item, dict)]

    for group in (market_cache.get("news") or {}).values():
        if not isinstance(group, dict):
            continue
        for label, payload in group.items():
            if not isinstance(payload, dict):
                continue
            if payload.get("symbol") == ticker or label == ticker:
                items = payload.get("items") or []
                return [item for item in items if isinstance(item, dict)]
    return []


async def get_or_create_preferences(db: AsyncSession, user_id: int) -> NotificationPreference:
    preference = await db.get(NotificationPreference, user_id)
    if preference is not None:
        return preference

    preference = NotificationPreference(
        user_id=user_id,
        price_change_threshold_percent=settings.NOTIFICATION_DEFAULT_PRICE_THRESHOLD_PERCENT,
    )
    db.add(preference)
    await db.commit()
    await db.refresh(preference)
    return preference


async def update_preferences(
    db: AsyncSession,
    user_id: int,
    updates: dict[str, Any],
) -> NotificationPreference:
    preference = await get_or_create_preferences(db, user_id)
    for key, value in updates.items():
        if value is not None and hasattr(preference, key):
            setattr(preference, key, value)
    await db.commit()
    await db.refresh(preference)
    return preference


async def list_channels(db: AsyncSession, user_id: int) -> list[NotificationChannelConnection]:
    result = await db.execute(
        select(NotificationChannelConnection)
        .where(NotificationChannelConnection.user_id == user_id)
        .order_by(NotificationChannelConnection.channel.asc())
    )
    return list(result.scalars().all())


async def create_channel_verification(
    db: AsyncSession,
    *,
    user_id: int,
    channel: str,
    destination: str | None = None,
) -> NotificationChannelConnection:
    result = await db.execute(
        select(NotificationChannelConnection).where(
            NotificationChannelConnection.user_id == user_id,
            NotificationChannelConnection.channel == channel,
        )
    )
    connection = result.scalar_one_or_none()
    code = _verification_code()
    expires_at = _now() + timedelta(minutes=30)

    if connection is None:
        connection = NotificationChannelConnection(
            user_id=user_id,
            channel=channel,
            destination=destination,
        )
        db.add(connection)

    connection.destination = destination or connection.destination
    connection.verified = False
    connection.verification_status = "pending"
    connection.verification_code = code
    connection.verification_expires_at = expires_at
    connection.verified_at = None

    await db.commit()
    await db.refresh(connection)
    return connection


async def verify_channel(
    db: AsyncSession,
    *,
    user_id: int,
    channel: str,
    code: str,
    destination: str,
) -> NotificationChannelConnection:
    result = await db.execute(
        select(NotificationChannelConnection).where(
            NotificationChannelConnection.user_id == user_id,
            NotificationChannelConnection.channel == channel,
        )
    )
    connection = result.scalar_one_or_none()
    if connection is None:
        raise ValueError("Verification code was not requested.")
    if connection.verification_code != code:
        connection.verification_status = "invalid_code"
        await db.commit()
        raise ValueError("Invalid verification code.")
    if connection.verification_expires_at and connection.verification_expires_at < _now():
        connection.verification_status = "expired"
        await db.commit()
        raise ValueError("Verification code expired.")

    connection.destination = destination
    connection.verified = True
    connection.verification_status = "verified"
    connection.verification_code = None
    connection.verification_expires_at = None
    connection.verified_at = _now()
    await db.commit()
    await db.refresh(connection)
    return connection


async def delete_channel(db: AsyncSession, *, user_id: int, channel: str) -> bool:
    result = await db.execute(
        select(NotificationChannelConnection).where(
            NotificationChannelConnection.user_id == user_id,
            NotificationChannelConnection.channel == channel,
        )
    )
    connection = result.scalar_one_or_none()
    if connection is None:
        return False
    await db.delete(connection)
    await db.commit()
    return True


async def list_history(
    db: AsyncSession,
    *,
    user_id: int,
    limit: int = 50,
) -> list[NotificationEvent]:
    result = await db.execute(
        select(NotificationEvent)
        .where(NotificationEvent.user_id == user_id)
        .order_by(NotificationEvent.created_at.desc(), NotificationEvent.id.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def _active_channels(
    db: AsyncSession,
    user_id: int,
    preference: NotificationPreference,
) -> list[str]:
    channels = list(DEFAULT_CHANNELS)
    result = await db.execute(
        select(NotificationChannelConnection).where(
            NotificationChannelConnection.user_id == user_id,
            NotificationChannelConnection.verified.is_(True),
        )
    )
    for connection in result.scalars().all():
        if connection.channel == "telegram" and preference.telegram_enabled:
            channels.append("telegram")
        if connection.channel == "email" and preference.email_enabled:
            channels.append("email")
    return channels


async def _already_in_cooldown(
    db: AsyncSession,
    *,
    user_id: int,
    ticker: str,
    event_type: str,
    cooldown_minutes: int,
) -> bool:
    since = _now() - timedelta(minutes=cooldown_minutes)
    result = await db.execute(
        select(NotificationEvent.id)
        .where(
            NotificationEvent.user_id == user_id,
            NotificationEvent.ticker == ticker,
            NotificationEvent.event_type == event_type,
            NotificationEvent.created_at >= since,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def create_notification_events(
    db: AsyncSession,
    *,
    user_id: int,
    ticker: str,
    event_type: str,
    title: str,
    body: str,
    payload: dict[str, Any] | None,
    dedupe_key: str,
    channels: list[str],
    severity: str = "info",
) -> int:
    created = 0
    for channel in channels:
        result = await db.execute(
            select(NotificationEvent.id).where(
                NotificationEvent.user_id == user_id,
                NotificationEvent.dedupe_key == dedupe_key,
                NotificationEvent.channel == channel,
            )
        )
        if result.scalar_one_or_none() is not None:
            continue

        event = NotificationEvent(
            user_id=user_id,
            ticker=ticker,
            event_type=event_type,
            severity=severity,
            title=title,
            body=body,
            payload_json=payload or {},
            dedupe_key=dedupe_key,
            channel=channel,
            status="sent" if channel == "in_app" else "pending",
            sent_at=_now() if channel == "in_app" else None,
        )
        db.add(event)
        created += 1

    if created:
        await db.commit()
    return created


async def create_test_notification(
    db: AsyncSession,
    *,
    user_id: int,
    ticker: str | None,
    message: str | None,
) -> tuple[int, int, int]:
    preference = await get_or_create_preferences(db, user_id)
    channels = await _active_channels(db, user_id, preference)
    target_ticker = (ticker or "TEST").strip() or "TEST"
    created = await create_notification_events(
        db,
        user_id=user_id,
        ticker=target_ticker,
        event_type="test",
        title=f"{target_ticker} 테스트 알림",
        body=message or "알림 채널이 정상적으로 연결되어 있는지 확인하는 테스트입니다.",
        payload={"manual": True},
        dedupe_key=f"test:{user_id}:{target_ticker}:{int(_now().timestamp())}",
        channels=channels,
    )
    sent, failed = await send_pending_notifications(db, limit=20)
    return created, sent, failed


async def send_welcome_notification_for_channel(
    db: AsyncSession,
    *,
    user_id: int,
    channel: str,
    destination: str | None,
) -> NotificationEvent | None:
    if channel not in DELIVERY_CHANNELS or not destination:
        return None

    dedupe_key = f"welcome:{user_id}:{channel}"
    result = await db.execute(
        select(NotificationEvent).where(
            NotificationEvent.user_id == user_id,
            NotificationEvent.dedupe_key == dedupe_key,
            NotificationEvent.channel == channel,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing

    event = NotificationEvent(
        user_id=user_id,
        ticker="SYSTEM",
        event_type="welcome",
        severity="info",
        title=WELCOME_NOTIFICATION_TITLE,
        body=WELCOME_NOTIFICATION_BODY,
        payload_json={"channel": channel},
        dedupe_key=dedupe_key,
        channel=channel,
        status="pending",
    )
    db.add(event)
    await db.flush()

    if channel == "email":
        delivery = await _send_gmail_message(destination, event.title, event.body)
    elif channel == "telegram":
        delivery = await _send_telegram(destination, event)
    else:
        delivery = DeliveryResult(success=False, error_message="Unsupported channel.")

    event.attempts = 1
    if delivery.success:
        event.status = "sent"
        event.sent_at = _now()
        event.error_message = None
    else:
        event.status = "failed"
        event.error_message = delivery.error_message

    await db.commit()
    await db.refresh(event)
    return event


async def evaluate_notifications(db: AsyncSession) -> int:
    result = await db.execute(select(UserFavoriteAsset).order_by(UserFavoriteAsset.user_id.asc()))
    favorites = list(result.scalars().all())
    created = 0

    for favorite in favorites:
        preference = await get_or_create_preferences(db, favorite.user_id)
        channels = await _active_channels(db, favorite.user_id, preference)
        snapshot = await db.get(AssetNotificationSnapshot, favorite.ticker)
        if snapshot is None:
            snapshot = AssetNotificationSnapshot(ticker=favorite.ticker)
            db.add(snapshot)

        if preference.price_change_enabled:
            created += await _evaluate_price_change(db, favorite, preference, snapshot, channels)
        if preference.news_enabled:
            created += await _evaluate_news(db, favorite, preference, snapshot, channels)
        if preference.report_enabled:
            created += await _evaluate_report(db, favorite, preference, snapshot, channels)

        snapshot.evaluated_at = _now()
        await db.commit()

    return created


async def _evaluate_price_change(
    db: AsyncSession,
    favorite: UserFavoriteAsset,
    preference: NotificationPreference,
    snapshot: AssetNotificationSnapshot,
    channels: list[str],
) -> int:
    payload = _find_price_payload(favorite.ticker)
    if payload is None:
        return 0

    price = float(payload.get("currentPrice", payload.get("price", 0)) or 0)
    change_percent = float(payload.get("changePercent", payload.get("change_pct", 0)) or 0)
    snapshot.last_price = price
    snapshot.last_change_percent = change_percent

    threshold = float(preference.price_change_threshold_percent or settings.NOTIFICATION_DEFAULT_PRICE_THRESHOLD_PERCENT)
    if abs(change_percent) < threshold:
        return 0
    if await _already_in_cooldown(
        db,
        user_id=favorite.user_id,
        ticker=favorite.ticker,
        event_type="price_change",
        cooldown_minutes=settings.NOTIFICATION_DEFAULT_COOLDOWN_MINUTES,
    ):
        return 0

    direction = "상승" if change_percent >= 0 else "하락"
    bucket = int(abs(change_percent) // max(threshold, 0.1))
    day_key = _now().strftime("%Y%m%d")
    return await create_notification_events(
        db,
        user_id=favorite.user_id,
        ticker=favorite.ticker,
        event_type="price_change",
        title=f"{favorite.display_name} {direction} 알림",
        body=f"{favorite.ticker} 변동률이 {change_percent:.2f}%로 설정 기준 {threshold:.2f}%를 넘었습니다.",
        payload={"price": price, "change_percent": change_percent, "threshold": threshold},
        dedupe_key=f"price:{favorite.ticker}:{day_key}:{bucket}",
        channels=channels,
        severity="warning" if abs(change_percent) >= threshold * 2 else "info",
    )


async def _evaluate_news(
    db: AsyncSession,
    favorite: UserFavoriteAsset,
    preference: NotificationPreference,
    snapshot: AssetNotificationSnapshot,
    channels: list[str],
) -> int:
    items = _find_news_items(favorite.ticker)
    if not items:
        return 0

    previous = set(snapshot.last_news_fingerprints or [])
    current = [_news_fingerprint(item) for item in items[:5]]
    snapshot.last_news_fingerprints = current

    new_items = [
        item for item in items[:5]
        if _news_fingerprint(item) not in previous
    ]
    if not previous or not new_items:
        return 0
    if await _already_in_cooldown(
        db,
        user_id=favorite.user_id,
        ticker=favorite.ticker,
        event_type="news",
        cooldown_minutes=settings.NOTIFICATION_DEFAULT_COOLDOWN_MINUTES,
    ):
        return 0

    first = new_items[0]
    fingerprint = _news_fingerprint(first)
    title = str(first.get("title") or f"{favorite.display_name} 새 뉴스")
    link = str(first.get("link") or "")
    return await create_notification_events(
        db,
        user_id=favorite.user_id,
        ticker=favorite.ticker,
        event_type="news",
        title=f"{favorite.display_name} 새 뉴스",
        body=f"{title}{f' ({link})' if link else ''}",
        payload={"item": first},
        dedupe_key=f"news:{favorite.ticker}:{fingerprint}",
        channels=channels,
    )


async def _evaluate_report(
    db: AsyncSession,
    favorite: UserFavoriteAsset,
    preference: NotificationPreference,
    snapshot: AssetNotificationSnapshot,
    channels: list[str],
) -> int:
    query = (
        select(AIReport, Asset)
        .join(Asset, AIReport.asset_id == Asset.id)
        .where(Asset.ticker == favorite.ticker)
        .order_by(AIReport.created_at.desc())
        .limit(1)
    )
    result = await db.execute(query)
    row = result.first()
    if row is None:
        return 0

    report, asset = row
    if snapshot.last_report_id is None:
        snapshot.last_report_id = report.id
        return 0
    if snapshot.last_report_id == report.id:
        return 0

    snapshot.last_report_id = report.id
    price_payload = _find_price_payload(favorite.ticker)
    current_price, current_price_text, price_source = _format_notification_price(
        favorite.ticker,
        favorite,
        price_payload,
    )
    detail_url = _build_asset_detail_url(asset.ticker)
    created_at = report.created_at.isoformat()
    return await create_notification_events(
        db,
        user_id=favorite.user_id,
        ticker=favorite.ticker,
        event_type="report",
        title=REPORT_NOTIFICATION_TITLE,
        body=_build_report_notification_body(
            asset_name=asset.name,
            ticker=asset.ticker,
            detail_url=detail_url,
            current_price_text=current_price_text,
        ),
        payload={
            "report_id": report.id,
            "created_at": created_at,
            "detail_url": detail_url,
            "current_price": current_price,
            "current_price_text": current_price_text,
            "price_source": price_source,
        },
        dedupe_key=f"report:{asset.ticker}:{report.id}",
        channels=channels,
    )


async def send_pending_notifications(db: AsyncSession, *, limit: int = 50) -> tuple[int, int]:
    now = _now()
    result = await db.execute(
        select(NotificationEvent)
        .where(
            NotificationEvent.status == "pending",
            NotificationEvent.channel.in_(DELIVERY_CHANNELS),
            or_(NotificationEvent.next_attempt_at.is_(None), NotificationEvent.next_attempt_at <= now),
        )
        .order_by(NotificationEvent.created_at.asc())
        .limit(limit)
    )
    events = list(result.scalars().all())

    sent = 0
    failed = 0
    for event in events:
        channel_result = await db.execute(
            select(NotificationChannelConnection).where(
                NotificationChannelConnection.user_id == event.user_id,
                NotificationChannelConnection.channel == event.channel,
                NotificationChannelConnection.verified.is_(True),
            )
        )
        connection = channel_result.scalar_one_or_none()
        if connection is None or not connection.destination:
            event.status = "failed"
            event.error_message = "Notification channel is not verified."
            event.attempts += 1
            failed += 1
            continue

        if event.channel == "telegram":
            delivery = await _send_telegram(connection.destination, event)
        elif event.channel == "email":
            delivery = await _send_email(connection.destination, event)
        else:
            delivery = DeliveryResult(success=False, error_message="Unsupported channel.")

        event.attempts += 1
        if delivery.success:
            event.status = "sent"
            event.sent_at = _now()
            event.error_message = None
            sent += 1
        else:
            failed += 1
            event.error_message = delivery.error_message
            if event.attempts >= 3:
                event.status = "failed"
            else:
                event.next_attempt_at = _now() + timedelta(minutes=2 ** event.attempts)

    if events:
        await db.commit()
    return sent, failed


async def _send_telegram(chat_id: str, event: NotificationEvent) -> DeliveryResult:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return DeliveryResult(success=False, error_message="Telegram bot token is not configured.")

    text = f"{event.title}\n\n{event.body}"
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            if 200 <= response.status < 300:
                return DeliveryResult(success=True)
            return DeliveryResult(success=False, error_message=f"Telegram returned HTTP {response.status}.")
    except urllib.error.HTTPError as exc:
        return DeliveryResult(success=False, error_message=_http_error_message("Telegram", exc))
    except (urllib.error.URLError, TimeoutError) as exc:
        return DeliveryResult(success=False, error_message=str(exc))


async def send_email_verification_code(
    db: AsyncSession,
    connection: NotificationChannelConnection,
) -> DeliveryResult:
    if not connection.destination or not connection.verification_code:
        return DeliveryResult(success=False, error_message="Email verification destination or code is missing.")

    body = (
        "Project Finance 알림 이메일 확인 코드입니다.\n\n"
        f"확인 코드: {connection.verification_code}\n\n"
        "이 코드는 30분 동안 유효합니다. 본인이 요청하지 않았다면 이 메일을 무시하세요."
    )
    delivery = await _send_gmail_message(
        connection.destination,
        "Project Finance 이메일 확인 코드",
        body,
    )
    if not delivery.success:
        connection.verification_status = "delivery_failed"
        await db.commit()
    return delivery


async def _send_email(destination: str, event: NotificationEvent) -> DeliveryResult:
    return await _send_gmail_message(destination, event.title, event.body)


async def _send_gmail_message(destination: str, subject: str, body: str) -> DeliveryResult:
    provider = (settings.EMAIL_PROVIDER or "gmail").strip().lower()
    if provider != "gmail":
        return DeliveryResult(success=False, error_message="EMAIL_PROVIDER must be gmail.")
    missing_settings = _missing_setting_names(GMAIL_REQUIRED_SETTINGS)
    if missing_settings:
        missing_names = ", ".join(missing_settings)
        return DeliveryResult(success=False, error_message=f"Gmail email settings are incomplete: {missing_names}.")

    access_token = _refresh_gmail_access_token()
    if not access_token.success:
        return DeliveryResult(success=False, error_message=access_token.error_message)

    message = EmailMessage()
    message["From"] = settings.EMAIL_FROM_ADDRESS
    message["To"] = destination
    message["Subject"] = subject
    message.set_content(body)

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    request = urllib.request.Request(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        data=json.dumps({"raw": raw_message}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {access_token.access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            if 200 <= response.status < 300:
                return DeliveryResult(success=True)
            return DeliveryResult(success=False, error_message=f"Gmail returned HTTP {response.status}.")
    except urllib.error.HTTPError as exc:
        return DeliveryResult(success=False, error_message=_http_error_message("Gmail", exc))
    except (urllib.error.URLError, TimeoutError) as exc:
        return DeliveryResult(success=False, error_message=str(exc))


def _refresh_gmail_access_token() -> GmailAccessTokenResult:
    data = urllib.parse.urlencode(
        {
            "client_id": settings.GMAIL_CLIENT_ID,
            "client_secret": settings.GMAIL_CLIENT_SECRET,
            "refresh_token": settings.GMAIL_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return GmailAccessTokenResult(success=False, error_message=_http_error_message("Gmail OAuth", exc))
    except (json.JSONDecodeError, urllib.error.URLError, TimeoutError) as exc:
        return GmailAccessTokenResult(success=False, error_message=str(exc))

    token = payload.get("access_token")
    if not token:
        return GmailAccessTokenResult(success=False, error_message="Gmail OAuth response did not include an access token.")
    return GmailAccessTokenResult(success=True, access_token=str(token))


def _http_error_message(provider: str, exc: urllib.error.HTTPError) -> str:
    try:
        payload = json.loads(exc.read().decode("utf-8"))
    except Exception:
        payload = {}
    detail = _safe_error_detail(payload, exc.reason)
    return f"{provider} returned HTTP {exc.code}: {detail}"


def _safe_error_detail(payload: dict[str, Any], fallback: Any) -> str:
    detail = payload.get("error_description")
    error = payload.get("error")
    if not detail and isinstance(error, dict):
        status = error.get("status")
        code = error.get("code")
        message = error.get("message")
        parts = [str(part) for part in (status, code, message) if part]
        detail = " - ".join(parts)
    elif not detail and error:
        detail = str(error)
    if not detail:
        detail = str(fallback or "unknown_error")
    return detail[:300]
