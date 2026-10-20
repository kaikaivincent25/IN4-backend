"""Add moderated article revision history.

Revision ID: 20261018_article_revisions
Revises: 20241016_initial_schema
Create Date: 2026-10-18
"""

from alembic import op
import sqlalchemy as sa


revision = "20261018_article_revisions"
down_revision = "20241016_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "articles_articlerevision",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles_article.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users_customuser.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("users_customuser.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories_category.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("featured_image", sa.String(length=500), nullable=True),
        sa.Column("change_note", sa.Text(), nullable=False),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.Column("previous_title", sa.String(length=200), nullable=True),
        sa.Column("previous_summary", sa.String(length=500), nullable=True),
        sa.Column("previous_body", sa.Text(), nullable=True),
        sa.Column("previous_category_id", sa.Integer(), nullable=True),
        sa.Column("previous_featured_image", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_articles_articlerevision_article_id", "articles_articlerevision", ["article_id"])
    op.create_index("ix_articles_articlerevision_author_id", "articles_articlerevision", ["author_id"])
    op.create_index("ix_articles_articlerevision_status", "articles_articlerevision", ["status"])


def downgrade() -> None:
    op.drop_index("ix_articles_articlerevision_status", table_name="articles_articlerevision")
    op.drop_index("ix_articles_articlerevision_author_id", table_name="articles_articlerevision")
    op.drop_index("ix_articles_articlerevision_article_id", table_name="articles_articlerevision")
    op.drop_table("articles_articlerevision")
