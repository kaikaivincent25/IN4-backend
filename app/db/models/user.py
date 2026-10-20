from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from .article import Article
    from .expert import Expert


class CustomUser(Base):
    __tablename__ = "users_customuser"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    profile_image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_consumer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_provider: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_staff: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    articles: Mapped[list["Article"]] = relationship(back_populates="author")
    drafts: Mapped[list] = relationship("ArticleDraft", back_populates="author")
    expert_profile: Mapped["Expert | None"] = relationship(
        back_populates="user",
        foreign_keys="Expert.user_id",
        uselist=False,
    )
