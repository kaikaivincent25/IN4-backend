from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class VerificationDocument(Base):
    __tablename__ = "experts_verificationdocument"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    expert_id: Mapped[int] = mapped_column(ForeignKey("experts_expert.id", ondelete="CASCADE"), nullable=False, index=True)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    expert: Mapped["Expert"] = relationship()


class ExpertVouch(Base):
    __tablename__ = "experts_expertvouch"
    __table_args__ = (UniqueConstraint("expert_id", "vouched_by_id", name="uq_expert_vouch_member"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    expert_id: Mapped[int] = mapped_column(ForeignKey("experts_expert.id", ondelete="CASCADE"), nullable=False, index=True)
    vouched_by_id: Mapped[int] = mapped_column(ForeignKey("users_customuser.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(80), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    expert: Mapped["Expert"] = relationship()
    vouched_by: Mapped["CustomUser"] = relationship()
