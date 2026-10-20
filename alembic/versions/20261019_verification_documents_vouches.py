"""Add private verification evidence and member vouches.

Revision ID: 20261019_verification
Revises: 20261018_community_features
Create Date: 2026-10-19
"""

from alembic import op
import sqlalchemy as sa

revision = "20261019_verification"
down_revision = "20261018_community_features"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("experts_expert", sa.Column("location", sa.String(160), nullable=True))
    op.add_column("experts_expert", sa.Column("languages", sa.String(255), nullable=True))
    op.add_column("experts_expert", sa.Column("consultation_methods", sa.String(255), nullable=True))
    op.create_table(
        "experts_verificationdocument",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("expert_id", sa.Integer(), sa.ForeignKey("experts_expert.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("storage_key", sa.String(80), nullable=False, unique=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_experts_verificationdocument_expert_id", "experts_verificationdocument", ["expert_id"])
    op.create_table(
        "experts_expertvouch",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("expert_id", sa.Integer(), sa.ForeignKey("experts_expert.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vouched_by_id", sa.Integer(), sa.ForeignKey("users_customuser.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relationship_type", sa.String(80), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("expert_id", "vouched_by_id", name="uq_expert_vouch_member"),
    )
    op.create_index("ix_experts_expertvouch_expert_id", "experts_expertvouch", ["expert_id"])
    op.create_index("ix_experts_expertvouch_vouched_by_id", "experts_expertvouch", ["vouched_by_id"])


def downgrade() -> None:
    op.drop_table("experts_expertvouch")
    op.drop_table("experts_verificationdocument")
    op.drop_column("experts_expert", "consultation_methods")
    op.drop_column("experts_expert", "languages")
    op.drop_column("experts_expert", "location")
