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
    created_at: datetime
    
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
