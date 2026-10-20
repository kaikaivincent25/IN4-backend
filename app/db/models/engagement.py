from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class SavedArticle(Base):
    __tablename__ = "engagements_savedarticle"
    __table_args__ = (UniqueConstraint("user_id", "article_id", name="uq_saved_article"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users_customuser.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    article_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("articles_article.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["CustomUser"] = relationship()
    article: Mapped["Article"] = relationship()


class ReadHistory(Base):
    __tablename__ = "engagements_readhistory"
    __table_args__ = (UniqueConstraint("user_id", "article_id", name="uq_readhistory_user_article"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users_customuser.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    article_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("articles_article.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["CustomUser"] = relationship()
    article: Mapped["Article"] = relationship()


class ArticleStats(Base):
    __tablename__ = "engagements_articlestats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("articles_article.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    total_saves: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_reads: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_readers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    engagement_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    article: Mapped["Article"] = relationship()
