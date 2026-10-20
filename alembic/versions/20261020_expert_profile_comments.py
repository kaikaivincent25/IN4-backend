"""Add read-gated expert profile comments.

Revision ID: 20261020_expert_comments
Revises: 20261019_verification
Create Date: 2026-10-20
"""

from alembic import op
import sqlalchemy as sa


revision = "20261020_expert_comments"
down_revision = "20261019_profile_image"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "community_expertprofilecomment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("expert_id", sa.Integer(), sa.ForeignKey("experts_expert.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users_customuser.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.String(length=1500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("expert_id", "user_id", name="uq_expert_profile_comment_user"),
    )
    op.create_index("ix_community_expertprofilecomment_expert_id", "community_expertprofilecomment", ["expert_id"])
    op.create_index("ix_community_expertprofilecomment_user_id", "community_expertprofilecomment", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_community_expertprofilecomment_user_id", table_name="community_expertprofilecomment")
    op.drop_index("ix_community_expertprofilecomment_expert_id", table_name="community_expertprofilecomment")
    op.drop_table("community_expertprofilecomment")
