from __future__ import annotations

from datetime import datetime
from enum import Enum

from typing import Any

from pydantic import BaseModel, EmailStr, ConfigDict, Field

from .models import AssetCategory

# -----------------
# User Schemas
# -----------------
class UserResponse(BaseModel):
    id: int
    email: EmailStr
    nickname: str
    nickname_confirmed_at: datetime | None = None
    created_at: datetime
    nickname_confirmed: bool = False
    profile_complete: bool = False
    
    # ORM 모델의 객체 인스턴스를 Pydantic 모델로 변환할 수 있도록 설정
    model_config = ConfigDict(from_attributes=True)

class GoogleLoginRequest(BaseModel):
    credential: str

class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    id: int
    email: EmailStr
    nickname: str
    nickname_confirmed: bool = False
    profile_complete: bool = False


class ProfileMeResponse(BaseModel):
    id: int
    email: EmailStr
    nickname: str
    nickname_confirmed: bool
    profile_complete: bool
    nickname_confirmed_at: datetime | None = None
    notification_preferences: dict[str, Any] | None = None


class NicknameAvailabilityResponse(BaseModel):
    nickname: str
    available: bool
    valid: bool
    message: str


class NicknameUpdateRequest(BaseModel):
    nickname: str = Field(..., min_length=1, max_length=40)


class NicknameUpdateResponse(BaseModel):
    id: int
    email: EmailStr
    nickname: str
    nickname_confirmed: bool
    profile_complete: bool
    nickname_confirmed_at: datetime


# -----------------
# Subscription / Billing Schemas
# -----------------
class SubscriptionTier(str, Enum):
    FREE = "FREE"
    PLUS = "PLUS"
    PRO = "PRO"


class SubscriptionStatus(str, Enum):
    NONE = "NONE"
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"


class BillingPlanResponse(BaseModel):
    tier: SubscriptionTier
    name: str
    monthly_price_krw: int
    billing_cycle: str
    can_view_reports: bool
    can_use_chatbot: bool
    description: str


class SubscriptionEntitlementsResponse(BaseModel):
    can_view_reports: bool
    can_use_chatbot: bool


class BillingMeResponse(BaseModel):
    tier: SubscriptionTier
    status: SubscriptionStatus
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False
    entitlements: SubscriptionEntitlementsResponse


class BillingCheckoutRequest(BaseModel):
    tier: SubscriptionTier
    success_url: str | None = None
    cancel_url: str | None = None


class BillingCheckoutResponse(BaseModel):
    checkout_url: str


class BillingCancelResponse(BaseModel):
    canceled: bool
    message: str


class BillingWebhookAckResponse(BaseModel):
    received: bool

# -----------------
# Asset Schemas
# -----------------
class AssetResponse(BaseModel):
    id: int
    ticker: str
    name: str
    category: AssetCategory

    model_config = ConfigDict(from_attributes=True)

# -----------------
# Comment Schemas
# -----------------
class CommentCreate(BaseModel):
    content: str


class CommentUpdate(BaseModel):
    content: str

class CommentResponse(BaseModel):
    id: int
    user_id: int
    asset_id: int
    content: str
    created_at: datetime
    likes_count: int = 0
    reports_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class AIReportResponse(BaseModel):
    ticker: str
    bull_summary: str | None = None
    bear_summary: str | None = None
    final_content: str
    created_at: str
    metadata: dict[str, Any] = {}

class CommentResponseWithAuthor(CommentResponse):
    author_nickname: str


# -----------------
# Chatbot Schemas
# -----------------
class ChatContext(BaseModel):
    ticker: str | None = None
    category: str | None = None
    authenticated: bool = False


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    current_path: str = "/"
    context: ChatContext = Field(default_factory=ChatContext)
    conversation_id: str | None = None
    client_message_id: str | None = None


class ChatAction(BaseModel):
    type: str
    label: str
    url: str | None = None
    reason: str | None = None
    confidence: float = 0
    requires_auth: bool = False


class ChatCard(BaseModel):
    type: str
    ticker: str | None = None
    name: str | None = None
    category: str | None = None
    route: str | None = None
    description: str | None = None


class ChatResponse(BaseModel):
    answer: str
    intent: str
    confidence: float
    actions: list[ChatAction] = Field(default_factory=list)
    cards: list[ChatCard] = Field(default_factory=list)
    requires_auth: bool = False
    safe_completion: bool = True
    disclaimer: str | None = None


# -----------------
# Favorites / Notifications Schemas
# -----------------
class FavoriteAssetCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=80)
    name: str | None = Field(default=None, max_length=255)
    categoryKey: str | None = Field(default=None, max_length=80)
    source: str = Field(default="manual", max_length=30)


class FavoriteAssetResponse(BaseModel):
    id: int
    symbol: str
    name: str
    categoryKey: str | None = None
    source: str
    created_at: datetime


class FavoriteImportRequest(BaseModel):
    favorites: list[FavoriteAssetCreate] = Field(default_factory=list)


class NotificationPreferenceResponse(BaseModel):
    telegram_enabled: bool
    email_enabled: bool
    price_change_enabled: bool
    news_enabled: bool
    report_enabled: bool
    daily_digest_enabled: bool
    price_change_threshold_percent: float
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    timezone: str
    updated_at: datetime


class NotificationPreferenceUpdate(BaseModel):
    telegram_enabled: bool | None = None
    email_enabled: bool | None = None
    price_change_enabled: bool | None = None
    news_enabled: bool | None = None
    report_enabled: bool | None = None
    daily_digest_enabled: bool | None = None
    price_change_threshold_percent: float | None = Field(default=None, ge=0.1, le=50)
    quiet_hours_start: str | None = Field(default=None, max_length=5)
    quiet_hours_end: str | None = Field(default=None, max_length=5)
    timezone: str | None = Field(default=None, max_length=80)


class NotificationChannelResponse(BaseModel):
    id: int
    channel: str
    destination: str | None = None
    verified: bool
    verification_status: str
    verified_at: datetime | None = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChannelConnectResponse(BaseModel):
    channel: str
    verification_code: str
    verification_expires_at: datetime
    message: str


class TelegramVerifyRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=40)
    chat_id: str = Field(..., min_length=1, max_length=255)


class EmailVerifyRequest(BaseModel):
    email: EmailStr | None = None


class EmailConfirmRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=40)
    email: EmailStr | None = None


class NotificationHistoryResponse(BaseModel):
    id: int
    ticker: str
    event_type: str
    severity: str
    title: str
    body: str
    channel: str
    status: str
    error_message: str | None = None
    created_at: datetime
    sent_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class NotificationTestRequest(BaseModel):
    ticker: str | None = Field(default=None, max_length=80)
    message: str | None = Field(default=None, max_length=500)


class NotificationTestResponse(BaseModel):
    created_events: int
    sent_events: int
    failed_events: int
    message: str
