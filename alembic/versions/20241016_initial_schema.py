"""Initial schema for IN4 FastAPI backend

Revision ID: 20241016_initial_schema
Revises: 
Create Date: 2026-10-16 16:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20241016_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users_customuser",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password", sa.String(length=255), nullable=False),
        sa.Column("first_name", sa.String(length=150), nullable=True),
        sa.Column("last_name", sa.String(length=150), nullable=True),
        sa.Column("is_consumer", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_provider", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_staff", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_users_customuser_email"), "users_customuser", ["email"], unique=True)
    op.create_index(op.f("ix_users_customuser_is_provider"), "users_customuser", ["is_provider"], unique=False)

    op.create_table(
        "categories_category",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("content_type", sa.String(length=32), nullable=False, server_default="general"),
        sa.Column("icon_name", sa.String(length=80), nullable=True),
        sa.Column("color_code", sa.String(length=20), nullable=True),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_categories_category_name"), "categories_category", ["name"], unique=True)
    op.create_index(op.f("ix_categories_category_slug"), "categories_category", ["slug"], unique=True)

    op.create_table(
        "categories_categorytemplate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("template_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories_category.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("category_id"),
    )
    op.create_index(op.f("ix_categories_categorytemplate_category_id"), "categories_categorytemplate", ["category_id"], unique=True)

    op.create_table(
        "experts_expert",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("profession", sa.String(length=150), nullable=False),
        sa.Column("license_number", sa.String(length=120), nullable=True),
        sa.Column("license_issuer", sa.String(length=200), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("expertise_areas", sa.Text(), nullable=True),
        sa.Column("organization", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("badge_tier", sa.String(length=30), nullable=False, server_default="verified"),
        sa.Column("verified_by_id", sa.Integer(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("slug", sa.String(length=150), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users_customuser.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verified_by_id"], ["users_customuser.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_experts_expert_profession"), "experts_expert", ["profession"], unique=False)
    op.create_index(op.f("ix_experts_expert_slug"), "experts_expert", ["slug"], unique=True)
    op.create_index(op.f("ix_experts_expert_status"), "experts_expert", ["status"], unique=False)
    op.create_index(op.f("ix_experts_expert_user_id"), "experts_expert", ["user_id"], unique=True)

    op.create_table(
        "articles_article",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("featured_image", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("save_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reading_time", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users_customuser.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories_category.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_articles_article_author_id"), "articles_article", ["author_id"], unique=False)
    op.create_index(op.f("ix_articles_article_category_id"), "articles_article", ["category_id"], unique=False)
    op.create_index(op.f("ix_articles_article_slug"), "articles_article", ["slug"], unique=True)
    op.create_index(op.f("ix_articles_article_status"), "articles_article", ["status"], unique=False)

    op.create_table(
        "articles_articledraft",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("summary", sa.String(length=500), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("featured_image", sa.String(length=500), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_auto_saved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("last_auto_save", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["article_id"], ["articles_article.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["author_id"], ["users_customuser.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories_category.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("article_id"),
    )
    op.create_index(op.f("ix_articles_articledraft_author_id"), "articles_articledraft", ["author_id"], unique=False)
    op.create_index(op.f("ix_articles_articledraft_category_id"), "articles_articledraft", ["category_id"], unique=False)

    op.create_table(
        "engagements_savedarticle",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("saved_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["articles_article.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users_customuser.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "article_id", name="uq_saved_article"),
    )
    op.create_index(op.f("ix_engagements_savedarticle_article_id"), "engagements_savedarticle", ["article_id"], unique=False)
    op.create_index(op.f("ix_engagements_savedarticle_user_id"), "engagements_savedarticle", ["user_id"], unique=False)

    op.create_table(
        "engagements_readhistory",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["articles_article.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users_customuser.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "article_id", name="uq_readhistory_user_article"),
    )
    op.create_index(op.f("ix_engagements_readhistory_article_id"), "engagements_readhistory", ["article_id"], unique=False)
    op.create_index(op.f("ix_engagements_readhistory_user_id"), "engagements_readhistory", ["user_id"], unique=False)

    op.create_table(
        "engagements_articlestats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("total_saves", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_reads", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unique_readers", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("engagement_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["articles_article.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("article_id"),
    )
    op.create_index(op.f("ix_engagements_articlestats_article_id"), "engagements_articlestats", ["article_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_engagements_articlestats_article_id"), table_name="engagements_articlestats")
    op.drop_table("engagements_articlestats")
    op.drop_index(op.f("ix_engagements_readhistory_user_id"), table_name="engagements_readhistory")
    op.drop_index(op.f("ix_engagements_readhistory_article_id"), table_name="engagements_readhistory")
    op.drop_table("engagements_readhistory")
    op.drop_index(op.f("ix_engagements_savedarticle_user_id"), table_name="engagements_savedarticle")
    op.drop_index(op.f("ix_engagements_savedarticle_article_id"), table_name="engagements_savedarticle")
    op.drop_table("engagements_savedarticle")
    op.drop_index(op.f("ix_articles_articledraft_category_id"), table_name="articles_articledraft")
    op.drop_index(op.f("ix_articles_articledraft_author_id"), table_name="articles_articledraft")
    op.drop_table("articles_articledraft")
    op.drop_index(op.f("ix_articles_article_status"), table_name="articles_article")
    op.drop_index(op.f("ix_articles_article_slug"), table_name="articles_article")
    op.drop_index(op.f("ix_articles_article_category_id"), table_name="articles_article")
    op.drop_index(op.f("ix_articles_article_author_id"), table_name="articles_article")
    op.drop_table("articles_article")
    op.drop_index(op.f("ix_experts_expert_user_id"), table_name="experts_expert")
    op.drop_index(op.f("ix_experts_expert_status"), table_name="experts_expert")
    op.drop_index(op.f("ix_experts_expert_slug"), table_name="experts_expert")
    op.drop_index(op.f("ix_experts_expert_profession"), table_name="experts_expert")
    op.drop_table("experts_expert")
    op.drop_index(op.f("ix_categories_categorytemplate_category_id"), table_name="categories_categorytemplate")
    op.drop_table("categories_categorytemplate")
    op.drop_index(op.f("ix_categories_category_slug"), table_name="categories_category")
    op.drop_index(op.f("ix_categories_category_name"), table_name="categories_category")
    op.drop_table("categories_category")
    op.drop_index(op.f("ix_users_customuser_is_provider"), table_name="users_customuser")
    op.drop_index(op.f("ix_users_customuser_email"), table_name="users_customuser")
    op.drop_table("users_customuser")
