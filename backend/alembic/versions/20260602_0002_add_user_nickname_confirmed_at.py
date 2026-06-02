"""add user nickname confirmation timestamp

Revision ID: 20260602_0002
Revises: 20260602_0001
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa

revision = "20260602_0002"
down_revision = "20260602_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("nickname_confirmed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "nickname_confirmed_at")
