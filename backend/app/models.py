import enum
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import List

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
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    nickname: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # 양방향 관계 맵핑
    comments: Mapped[List["Comment"]] = relationship("Comment", back_populates="user", cascade="all, delete-orphan")
    liked_comments: Mapped[List["CommentLike"]] = relationship("CommentLike", back_populates="user", cascade="all, delete-orphan")


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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # 양방향 관계 맵핑
    asset: Mapped["Asset"] = relationship("Asset", back_populates="reports")


class Comment(Base):
    """
    Comment 테이블.
    사용자가 특정 자산(종목)의 토론방(종토방)에 작성하는 댓글(게시글) 정보를 담는 모델.
    - 관계(N:1): Comment 생성자는 특정 User이며, 대상 종목은 특정 Asset입니다.
    - 관계(1:N): 하나의 Comment는 여러 명의 사용자가 남긴 CommentLike들을 가집니다.
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
