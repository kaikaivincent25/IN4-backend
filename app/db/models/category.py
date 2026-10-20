from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ContentType(str, Enum):
    MEDICAL = "medical"
    LEGAL = "legal"
    FINANCIAL = "financial"
    TECHNOLOGY = "technology"
    MENTAL = "mental"
    AGRICULTURE = "agriculture"
    GENERAL = "general"


class Category(Base):
    __tablename__ = "categories_category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False, default=ContentType.GENERAL.value)
    icon_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    color_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    articles: Mapped[list["Article"]] = relationship(back_populates="category")
    drafts: Mapped[list["ArticleDraft"]] = relationship(back_populates="category")
    template: Mapped["CategoryTemplate | None"] = relationship(back_populates="category", uselist=False)


class CategoryTemplate(Base):
    __tablename__ = "categories_categorytemplate"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("categories_category.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    template_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    category: Mapped[Category] = relationship(back_populates="template")
