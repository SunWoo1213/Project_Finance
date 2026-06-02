"""add favorite notification tables

Revision ID: 20260602_0001
Revises: 20260601_0001
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa

revision = "20260602_0001"
down_revision = "20260601_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_favorite_assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=True),
        sa.Column("ticker", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("category_key", sa.String(length=80), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "ticker", name="uq_user_favorite_assets_user_ticker"),
    )
    op.create_index("ix_user_favorite_assets_id", "user_favorite_assets", ["id"])
    op.create_index("ix_user_favorite_assets_ticker", "user_favorite_assets", ["ticker"])
    op.create_index("ix_user_favorite_assets_user_id", "user_favorite_assets", ["user_id"])

    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("telegram_enabled", sa.Boolean(), nullable=False),
        sa.Column("email_enabled", sa.Boolean(), nullable=False),
        sa.Column("price_change_enabled", sa.Boolean(), nullable=False),
        sa.Column("news_enabled", sa.Boolean(), nullable=False),
        sa.Column("report_enabled", sa.Boolean(), nullable=False),
        sa.Column("daily_digest_enabled", sa.Boolean(), nullable=False),
        sa.Column("price_change_threshold_percent", sa.Float(), nullable=False),
        sa.Column("quiet_hours_start", sa.String(length=5), nullable=True),
        sa.Column("quiet_hours_end", sa.String(length=5), nullable=True),
        sa.Column("timezone", sa.String(length=80), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "notification_channel_connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=30), nullable=False),
        sa.Column("destination", sa.String(length=255), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("verification_status", sa.String(length=40), nullable=False),
        sa.Column("verification_code", sa.String(length=40), nullable=True),
        sa.Column("verification_expires_at", sa.DateTime(), nullable=True),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "channel", name="uq_notification_channel_user_channel"),
    )
    op.create_index("ix_notification_channel_connections_id", "notification_channel_connections", ["id"])
    op.create_index("ix_notification_channel_connections_user_id", "notification_channel_connections", ["user_id"])

    op.create_table(
        "notification_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=80), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("threshold_json", sa.JSON(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_rules_id", "notification_rules", ["id"])
    op.create_index("ix_notification_rules_ticker", "notification_rules", ["ticker"])
    op.create_index("ix_notification_rules_user_id", "notification_rules", ["user_id"])

    op.create_table(
        "asset_notification_snapshots",
        sa.Column("ticker", sa.String(length=80), nullable=False),
        sa.Column("last_price", sa.Float(), nullable=True),
        sa.Column("last_change_percent", sa.Float(), nullable=True),
        sa.Column("last_news_fingerprints", sa.JSON(), nullable=True),
        sa.Column("last_report_id", sa.Integer(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["last_report_id"], ["ai_reports.id"]),
        sa.PrimaryKeyConstraint("ticker"),
    )

    op.create_table(
        "notification_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=80), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("channel", sa.String(length=30), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "dedupe_key", "channel", name="uq_notification_events_user_dedupe_channel"),
    )
    op.create_index("ix_notification_events_id", "notification_events", ["id"])
    op.create_index("ix_notification_events_status", "notification_events", ["status"])
    op.create_index("ix_notification_events_ticker", "notification_events", ["ticker"])
    op.create_index("ix_notification_events_user_id", "notification_events", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_notification_events_user_id", table_name="notification_events")
    op.drop_index("ix_notification_events_ticker", table_name="notification_events")
    op.drop_index("ix_notification_events_status", table_name="notification_events")
    op.drop_index("ix_notification_events_id", table_name="notification_events")
    op.drop_table("notification_events")
    op.drop_table("asset_notification_snapshots")
    op.drop_index("ix_notification_rules_user_id", table_name="notification_rules")
    op.drop_index("ix_notification_rules_ticker", table_name="notification_rules")
    op.drop_index("ix_notification_rules_id", table_name="notification_rules")
    op.drop_table("notification_rules")
    op.drop_index("ix_notification_channel_connections_user_id", table_name="notification_channel_connections")
    op.drop_index("ix_notification_channel_connections_id", table_name="notification_channel_connections")
    op.drop_table("notification_channel_connections")
    op.drop_table("notification_preferences")
    op.drop_index("ix_user_favorite_assets_user_id", table_name="user_favorite_assets")
    op.drop_index("ix_user_favorite_assets_ticker", table_name="user_favorite_assets")
    op.drop_index("ix_user_favorite_assets_id", table_name="user_favorite_assets")
    op.drop_table("user_favorite_assets")
