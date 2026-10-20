from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.db.models.category import Category
    from app.db.models.user import CustomUser


class ArticleRevisionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ArticleStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Article(Base):
    __tablename__ = "articles_article"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users_customuser.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("categories_category.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    featured_image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ArticleStatus.DRAFT.value, index=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    save_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reading_time: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    author: Mapped["CustomUser"] = relationship(back_populates="articles")
    category: Mapped["Category"] = relationship(back_populates="articles")
    drafts: Mapped[list["ArticleDraft"]] = relationship(back_populates="article")


class ArticleDraft(Base):
    __tablename__ = "articles_articledraft"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users_customuser.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    article_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("articles_article.id", ondelete="SET NULL"),
        unique=True,
        nullable=True,
    )
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("categories_category.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    featured_image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_auto_saved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_auto_save: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    author: Mapped["CustomUser"] = relationship(back_populates="drafts")
    article: Mapped["Article | None"] = relationship(back_populates="drafts")
    category: Mapped["Category | None"] = relationship(back_populates="drafts")


class ArticleRevision(Base):
    __tablename__ = "articles_articlerevision"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles_article.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users_customuser.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users_customuser.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ArticleRevisionStatus.PENDING.value, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories_category.id", ondelete="RESTRICT"), nullable=False)
    featured_image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    change_note: Mapped[str] = mapped_column(Text, nullable=False)
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    previous_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    previous_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_category_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    previous_featured_image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    article: Mapped["Article"] = relationship()
    author: Mapped["CustomUser"] = relationship(foreign_keys=[author_id])
    reviewer: Mapped["CustomUser | None"] = relationship(foreign_keys=[reviewer_id])
    category: Mapped["Category"] = relationship()
