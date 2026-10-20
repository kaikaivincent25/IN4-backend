from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.db.models.article import Article
    from app.db.models.user import CustomUser


class ArticleComment(Base):
    __tablename__ = "community_articlecomment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles_article.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users_customuser.id", ondelete="CASCADE"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    article: Mapped["Article"] = relationship()
    author: Mapped["CustomUser"] = relationship()


class ExpertProfileComment(Base):
    __tablename__ = "community_expertprofilecomment"
    __table_args__ = (
        UniqueConstraint("expert_id", "user_id", name="uq_expert_profile_comment_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    expert_id: Mapped[int] = mapped_column(ForeignKey("experts_expert.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users_customuser.id", ondelete="CASCADE"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(String(1500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    expert: Mapped["Expert"] = relationship()
    author: Mapped["CustomUser"] = relationship()


class Conversation(Base):
    __tablename__ = "community_conversation"
    __table_args__ = (UniqueConstraint("article_id", "reader_id", "expert_id", name="uq_article_reader_expert_conversation"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles_article.id", ondelete="CASCADE"), nullable=False, index=True)
    reader_id: Mapped[int] = mapped_column(ForeignKey("users_customuser.id", ondelete="CASCADE"), nullable=False, index=True)
    expert_id: Mapped[int] = mapped_column(ForeignKey("users_customuser.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    article: Mapped["Article"] = relationship()
    reader: Mapped["CustomUser"] = relationship(foreign_keys=[reader_id])
    expert: Mapped["CustomUser"] = relationship(foreign_keys=[expert_id])
    messages: Mapped[list["ConversationMessage"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class ConversationMessage(Base):
    __tablename__ = "community_conversationmessage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("community_conversation.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users_customuser.id", ondelete="CASCADE"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(String(4000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    sender: Mapped["CustomUser"] = relationship()
