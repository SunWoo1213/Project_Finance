"""add subscription billing tables

Revision ID: 20260601_0001
Revises:
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa

revision = "20260601_0001"
down_revision = None
branch_labels = None
depends_on = None

asset_category_enum = sa.Enum(
    "INDEX",
    "BOND_US",
    "BOND_KR",
    "STOCK_US",
    "STOCK_KR",
    "COMMODITY",
    "CRYPTO",
    name="assetcategory",
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("google_sub", sa.String(), nullable=True),
        sa.Column("nickname", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_google_sub", "users", ["google_sub"], unique=True)
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_nickname", "users", ["nickname"], unique=True)

    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category", asset_category_enum, nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assets_id", "assets", ["id"])
    op.create_index("ix_assets_ticker", "assets", ["ticker"], unique=True)

    op.create_table(
        "ai_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("bull_summary", sa.Text(), nullable=True),
        sa.Column("bear_summary", sa.Text(), nullable=True),
        sa.Column("final_content", sa.Text(), nullable=False),
        sa.Column("quality_status", sa.String(), nullable=True),
        sa.Column("quality_feedback", sa.Text(), nullable=True),
        sa.Column("format_check_pass", sa.Boolean(), nullable=True),
        sa.Column("fact_check_pass", sa.Boolean(), nullable=True),
        sa.Column("qualitative_check_pass", sa.Boolean(), nullable=True),
        sa.Column("revision_count", sa.Integer(), nullable=True),
        sa.Column("data_as_of", sa.DateTime(), nullable=True),
        sa.Column("source_summary", sa.JSON(), nullable=True),
        sa.Column("risk_summary", sa.Text(), nullable=True),
        sa.Column("analysis_framework", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_reports_id", "ai_reports", ["id"])

    op.create_table(
        "comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_comments_id", "comments", ["id"])

    op.create_table(
        "comment_likes",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("comment_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["comment_id"], ["comments.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id", "comment_id"),
    )

    op.create_table(
        "comment_reports",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("comment_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["comment_id"], ["comments.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id", "comment_id"),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tier", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("provider_customer_id", sa.String(length=255), nullable=True),
        sa.Column("provider_subscription_id", sa.String(length=255), nullable=True),
        sa.Column("provider_plan_id", sa.String(length=255), nullable=True),
        sa.Column("current_period_start", sa.DateTime(), nullable=True),
        sa.Column("current_period_end", sa.DateTime(), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False),
        sa.Column("canceled_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_subscription_id", name="uq_subscriptions_provider_subscription"),
    )
    op.create_index("ix_subscriptions_id", "subscriptions", ["id"])
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])

    op.create_table(
        "billing_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("provider_event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("processed_status", sa.String(length=20), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("normalized_summary", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_event_id", name="uq_billing_events_provider_event"),
    )
    op.create_index("ix_billing_events_id", "billing_events", ["id"])
    op.create_index("ix_billing_events_subscription_id", "billing_events", ["subscription_id"])
    op.create_index("ix_billing_events_user_id", "billing_events", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_billing_events_user_id", table_name="billing_events")
    op.drop_index("ix_billing_events_subscription_id", table_name="billing_events")
    op.drop_index("ix_billing_events_id", table_name="billing_events")
    op.drop_table("billing_events")
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_id", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_table("comment_reports")
    op.drop_table("comment_likes")
    op.drop_index("ix_comments_id", table_name="comments")
    op.drop_table("comments")
    op.drop_index("ix_ai_reports_id", table_name="ai_reports")
    op.drop_table("ai_reports")
    op.drop_index("ix_assets_ticker", table_name="assets")
    op.drop_index("ix_assets_id", table_name="assets")
    op.drop_table("assets")
    op.drop_index("ix_users_nickname", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_index("ix_users_google_sub", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    asset_category_enum.drop(op.get_bind(), checkfirst=True)
