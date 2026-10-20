"""Add article comments and reader expert conversations.

Revision ID: 20261018_community_features
Revises: 20261018_article_revisions
Create Date: 2026-10-18
"""

from alembic import op
import sqlalchemy as sa


revision = "20261018_community_features"
down_revision = "20261018_article_revisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "community_articlecomment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles_article.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users_customuser.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_community_articlecomment_article_id", "community_articlecomment", ["article_id"])
    op.create_index("ix_community_articlecomment_user_id", "community_articlecomment", ["user_id"])

    op.create_table(
        "community_conversation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles_article.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reader_id", sa.Integer(), sa.ForeignKey("users_customuser.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expert_id", sa.Integer(), sa.ForeignKey("users_customuser.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("article_id", "reader_id", "expert_id", name="uq_article_reader_expert_conversation"),
    )
    op.create_index("ix_community_conversation_article_id", "community_conversation", ["article_id"])
    op.create_index("ix_community_conversation_reader_id", "community_conversation", ["reader_id"])
    op.create_index("ix_community_conversation_expert_id", "community_conversation", ["expert_id"])

    op.create_table(
        "community_conversationmessage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("community_conversation.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users_customuser.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.String(length=4000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_community_conversationmessage_conversation_id", "community_conversationmessage", ["conversation_id"])
    op.create_index("ix_community_conversationmessage_sender_id", "community_conversationmessage", ["sender_id"])


def downgrade() -> None:
    op.drop_index("ix_community_conversationmessage_sender_id", table_name="community_conversationmessage")
    op.drop_index("ix_community_conversationmessage_conversation_id", table_name="community_conversationmessage")
    op.drop_table("community_conversationmessage")
    op.drop_index("ix_community_conversation_expert_id", table_name="community_conversation")
    op.drop_index("ix_community_conversation_reader_id", table_name="community_conversation")
    op.drop_index("ix_community_conversation_article_id", table_name="community_conversation")
    op.drop_table("community_conversation")
    op.drop_index("ix_community_articlecomment_user_id", table_name="community_articlecomment")
    op.drop_index("ix_community_articlecomment_article_id", table_name="community_articlecomment")
    op.drop_table("community_articlecomment")
