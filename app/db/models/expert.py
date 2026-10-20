from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ExpertStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class ExpertBadgeTier(str, Enum):
    VERIFIED = "verified"
    CREDENTIALLED = "credentialed"
    INSTITUTIONAL = "institutional"


class Expert(Base):
    __tablename__ = "experts_expert"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users_customuser.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    profession: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    license_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    license_issuer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    expertise_areas: Mapped[str | None] = mapped_column(Text, nullable=True)
    organization: Mapped[str | None] = mapped_column(String(200), nullable=True)
    location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    languages: Mapped[str | None] = mapped_column(String(255), nullable=True)
    consultation_methods: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ExpertStatus.PENDING.value, index=True)
    badge_tier: Mapped[str] = mapped_column(String(30), nullable=False, default=ExpertBadgeTier.VERIFIED.value)
    verified_by_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users_customuser.id", ondelete="SET NULL"),
        nullable=True,
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    slug: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["CustomUser"] = relationship(
        back_populates="expert_profile",
        foreign_keys=[user_id],
    )
    verified_by: Mapped["CustomUser | None"] = relationship(foreign_keys=[verified_by_id])
