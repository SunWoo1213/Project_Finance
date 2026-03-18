from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class AIReport(Base):
    __tablename__ = "ai_reports"
    __table_args__ = (Index("ix_ai_reports_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False, index=True)
    bull_summary: Mapped[str] = mapped_column(Text, nullable=False)
    bear_summary: Mapped[str] = mapped_column(Text, nullable=False)
    final_content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    asset: Mapped["Asset"] = relationship("Asset", back_populates="ai_reports")
