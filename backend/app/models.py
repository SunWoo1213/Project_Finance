import enum
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import Boolean, Column, Float, Integer, JSON, String, Text, DateTime, ForeignKey, Enum as SQLEnum, Index, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import List, Optional

from .db.base import Base  # Assuming this exists at backend/app/db/base.py


def get_kst_now() -> datetime:
    return datetime.now(ZoneInfo("Asia/Seoul"))

class AssetCategory(enum.Enum):
    """자산 군(Category) 열거형. 자산의 종류를 필터링하는 데 사용됩니다."""
    INDEX = "INDEX"
    BOND_US = "BOND_US"
    BOND_KR = "BOND_KR"
    STOCK_US = "STOCK_US"
    STOCK_KR = "STOCK_KR"
    COMMODITY = "COMMODITY"
    CRYPTO = "CRYPTO"


class User(Base):
    """
    User 테이블.
    사용자 인증 및 커뮤니티 활동(댓글 작성, 좋아요 등)을 위한 기본 모델.
    - 관계(1:N): User는 여러 Comment와 CommentLike를 가집니다.
    """
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    google_sub: Mapped[Optional[str]] = mapped_column(String, unique=True, index=True, nullable=True)
    nickname: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    nickname_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # 양방향 관계 맵핑
    comments: Mapped[List["Comment"]] = relationship("Comment", back_populates="user", cascade="all, delete-orphan")
    liked_comments: Mapped[List["CommentLike"]] = relationship("CommentLike", back_populates="user", cascade="all, delete-orphan")
    reported_comments: Mapped[List["CommentReport"]] = relationship("CommentReport", back_populates="user", cascade="all, delete-orphan")
    subscriptions: Mapped[List["Subscription"]] = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    billing_events: Mapped[List["BillingEvent"]] = relationship("BillingEvent", back_populates="user")
    favorite_assets: Mapped[List["UserFavoriteAsset"]] = relationship("UserFavoriteAsset", back_populates="user", cascade="all, delete-orphan")
    notification_preferences: Mapped[Optional["NotificationPreference"]] = relationship(
        "NotificationPreference",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    notification_channels: Mapped[List["NotificationChannelConnection"]] = relationship(
        "NotificationChannelConnection",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    notification_rules: Mapped[List["NotificationRule"]] = relationship(
        "NotificationRule",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    notification_events: Mapped[List["NotificationEvent"]] = relationship(
        "NotificationEvent",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Asset(Base):
    """
    Asset 테이블. (기존 유지 + category 추가)
    개별 자산(주식, 채권, 코인 등)의 메타 정보를 담는 모델.
    - 관계(1:N): 하나의 Asset은 여러 개의 AIReport 및 Comment(종토방 댓글)를 가집니다.
    """
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    category: Mapped[AssetCategory] = mapped_column(SQLEnum(AssetCategory), nullable=False)
    ticker: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)

    # 양방향 관계 맵핑
    reports: Mapped[List["AIReport"]] = relationship("AIReport", back_populates="asset", cascade="all, delete-orphan")
    comments: Mapped[List["Comment"]] = relationship("Comment", back_populates="asset", cascade="all, delete-orphan")
    favorite_links: Mapped[List["UserFavoriteAsset"]] = relationship("UserFavoriteAsset", back_populates="asset")


class AIReport(Base):
    """
    AIReport 테이블. (기존 유지)
    특정 Asset에 대해 생성된 AI 기반 투자 분석 의견(리포트)을 저장하는 모델.
    - 관계(N:1): 여러 리포트는 결국 하나의 Asset에 귀속됩니다.
    """
    __tablename__ = "ai_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    asset_id: Mapped[int] = mapped_column(Integer, ForeignKey("assets.id"), nullable=False)
    bull_summary: Mapped[str] = mapped_column(Text, nullable=True)
    bear_summary: Mapped[str] = mapped_column(Text, nullable=True)
    final_content: Mapped[str] = mapped_column(Text, nullable=False)
    quality_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    quality_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    format_check_pass: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    fact_check_pass: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    qualitative_check_pass: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    revision_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    data_as_of: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    source_summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    risk_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    analysis_framework: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # 양방향 관계 맵핑
    asset: Mapped["Asset"] = relationship("Asset", back_populates="reports")


class Comment(Base):
    """
    Comment 테이블.
    사용자가 특정 자산(종목)의 토론방(종토방)에 작성하는 댓글(게시글) 정보를 담는 모델.
    - 관계(N:1): Comment 생성자는 특정 User이며, 대상 종목은 특정 Asset입니다.
    - 관계(1:N): 하나의 Comment는 여러 명의 사용자가 남긴 CommentLike/CommentReport들을 가집니다.
    """
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    asset_id: Mapped[int] = mapped_column(Integer, ForeignKey("assets.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_kst_now)

    # 양방향 관계 맵핑
    user: Mapped["User"] = relationship("User", back_populates="comments")
    asset: Mapped["Asset"] = relationship("Asset", back_populates="comments")
    likes: Mapped[List["CommentLike"]] = relationship("CommentLike", back_populates="comment", cascade="all, delete-orphan")
    reports: Mapped[List["CommentReport"]] = relationship("CommentReport", back_populates="comment", cascade="all, delete-orphan")


class CommentLike(Base):
    """
    CommentLike 테이블. (N:M 매핑)
    어떤 사용자가 어떤 댓글에 '좋아요'를 눌렀는지 관리하는 연결 모델. 복합 키(Primary Key)를 사용.
    - 포함 관계: 특정 User와 Comment의 연결 데이터를 저장합니다.
    """
    __tablename__ = "comment_likes"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), primary_key=True)
    comment_id: Mapped[int] = mapped_column(Integer, ForeignKey("comments.id"), primary_key=True)

    # 양방향 관계 맵핑
    user: Mapped["User"] = relationship("User", back_populates="liked_comments")
    comment: Mapped["Comment"] = relationship("Comment", back_populates="likes")


class CommentReport(Base):
    """
    CommentReport 테이블.
    어떤 사용자가 어떤 댓글을 신고했는지 관리합니다. 동일 사용자의 중복 신고는 복합 키로 차단합니다.
    """
    __tablename__ = "comment_reports"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), primary_key=True)
    comment_id: Mapped[int] = mapped_column(Integer, ForeignKey("comments.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_kst_now)

    user: Mapped["User"] = relationship("User", back_populates="reported_comments")
    comment: Mapped["Comment"] = relationship("Comment", back_populates="reports")


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("ix_subscriptions_user_id", "user_id"),
        UniqueConstraint("provider", "provider_subscription_id", name="uq_subscriptions_provider_subscription"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False, default="FREE")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    provider_subscription_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    provider_plan_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    current_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    canceled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="subscriptions")
    billing_events: Mapped[List["BillingEvent"]] = relationship("BillingEvent", back_populates="subscription")


class BillingEvent(Base):
    __tablename__ = "billing_events"
    __table_args__ = (
        UniqueConstraint("provider", "provider_event_id", name="uq_billing_events_provider_event"),
        Index("ix_billing_events_subscription_id", "subscription_id"),
        Index("ix_billing_events_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    processed_status: Mapped[str] = mapped_column(String(20), nullable=False, default="received")
    subscription_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    subscription: Mapped[Optional["Subscription"]] = relationship("Subscription", back_populates="billing_events")
    user: Mapped[Optional["User"]] = relationship("User", back_populates="billing_events")


class UserFavoriteAsset(Base):
    __tablename__ = "user_favorite_assets"
    __table_args__ = (
        UniqueConstraint("user_id", "ticker", name="uq_user_favorite_assets_user_ticker"),
        Index("ix_user_favorite_assets_user_id", "user_id"),
        Index("ix_user_favorite_assets_ticker", "ticker"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    asset_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("assets.id"), nullable=True)
    ticker: Mapped[str] = mapped_column(String(80), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category_key: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="favorite_assets")
    asset: Mapped[Optional["Asset"]] = relationship("Asset", back_populates="favorite_links")


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), primary_key=True)
    telegram_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    price_change_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    news_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    report_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    daily_digest_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    price_change_threshold_percent: Mapped[float] = mapped_column(Float, nullable=False, default=3)
    quiet_hours_start: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    quiet_hours_end: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    timezone: Mapped[str] = mapped_column(String(80), nullable=False, default="Asia/Seoul")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="notification_preferences")


class NotificationChannelConnection(Base):
    __tablename__ = "notification_channel_connections"
    __table_args__ = (
        UniqueConstraint("user_id", "channel", name="uq_notification_channel_user_channel"),
        Index("ix_notification_channel_connections_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    destination: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verification_status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    verification_code: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    verification_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="notification_channels")


class NotificationRule(Base):
    __tablename__ = "notification_rules"
    __table_args__ = (
        Index("ix_notification_rules_user_id", "user_id"),
        Index("ix_notification_rules_ticker", "ticker"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    ticker: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    threshold_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="notification_rules")


class AssetNotificationSnapshot(Base):
    __tablename__ = "asset_notification_snapshots"

    ticker: Mapped[str] = mapped_column(String(80), primary_key=True)
    last_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_change_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_news_fingerprints: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    last_report_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("ai_reports.id"), nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class NotificationEvent(Base):
    __tablename__ = "notification_events"
    __table_args__ = (
        UniqueConstraint("user_id", "dedupe_key", "channel", name="uq_notification_events_user_dedupe_channel"),
        Index("ix_notification_events_user_id", "user_id"),
        Index("ix_notification_events_ticker", "ticker"),
        Index("ix_notification_events_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    ticker: Mapped[str] = mapped_column(String(80), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    channel: Mapped[str] = mapped_column(String(30), nullable=False, default="in_app")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="notification_events")
