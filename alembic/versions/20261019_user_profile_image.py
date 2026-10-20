"""Add public profile images for user accounts.

Revision ID: 20261019_profile_image
Revises: 20261019_verification
Create Date: 2026-10-19
"""

from alembic import op
import sqlalchemy as sa


revision = "20261019_profile_image"
down_revision = "20261019_verification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users_customuser", sa.Column("profile_image", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("users_customuser", "profile_image")
