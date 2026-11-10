"""Add M-Pesa payment attempts for expert verification.

Revision ID: 20261104_expert_payment
Revises: 20261020_expert_comments
Create Date: 2026-11-04
"""

from alembic import op
import sqlalchemy as sa


revision = "20261104_expert_payment"
down_revision = "20261020_expert_comments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "experts_verificationpayment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "expert_id",
            sa.Integer(),
            sa.ForeignKey("experts_expert.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="KES"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="initiating"),
        sa.Column("merchant_request_id", sa.String(length=100), nullable=True),
        sa.Column("checkout_request_id", sa.String(length=100), nullable=True),
        sa.Column("receipt_number", sa.String(length=32), nullable=True),
        sa.Column("result_code", sa.Integer(), nullable=True),
        sa.Column("result_description", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("checkout_request_id", name="uq_experts_verificationpayment_checkout"),
        sa.UniqueConstraint("receipt_number", name="uq_experts_verificationpayment_receipt"),
    )
    op.create_index(
        "ix_experts_verificationpayment_expert_id",
        "experts_verificationpayment",
        ["expert_id"],
    )
    op.create_index(
        "ix_experts_verificationpayment_status",
        "experts_verificationpayment",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_experts_verificationpayment_status", table_name="experts_verificationpayment")
    op.drop_index("ix_experts_verificationpayment_expert_id", table_name="experts_verificationpayment")
    op.drop_table("experts_verificationpayment")