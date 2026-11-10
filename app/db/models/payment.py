from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class VerificationPaymentStatus(str, Enum):
    INITIATING = "initiating"
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"


class ExpertVerificationPayment(Base):
    __tablename__ = "experts_verificationpayment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    expert_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("experts_expert.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KES")
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=VerificationPaymentStatus.INITIATING.value,
        index=True,
    )
    merchant_request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    checkout_request_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    receipt_number: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    result_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    expert: Mapped["Expert"] = relationship()