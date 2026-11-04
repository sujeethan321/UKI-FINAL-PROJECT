"""Add recipient-owned in-app notifications.

Revision ID: d4e0f3a2b702
Revises: c3d9e2f1a601
"""
from alembic import op
import sqlalchemy as sa

revision = "d4e0f3a2b702"
down_revision = "c3d9e2f1a601"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notifications",
        sa.Column("notification_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("recipient_user_id", sa.BigInteger(), sa.ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("business_id", sa.BigInteger(), sa.ForeignKey("businesses.business_id", ondelete="RESTRICT"), nullable=True),
        sa.Column("notification_type", sa.String(40), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("message", sa.String(300), nullable=False),
        sa.Column("related_entity_type", sa.String(30), nullable=False),
        sa.Column("related_entity_id", sa.BigInteger(), nullable=False),
        sa.Column("event_key", sa.String(100, collation="utf8mb4_bin"), nullable=False),
        sa.Column("is_read", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("recipient_user_id", "event_key", name="uq_notification_recipient_event"),
        sa.CheckConstraint("notification_type IN ('credit_sale_recorded', 'repayment_recorded', 'payment_reminder_recorded', 'business_approved', 'business_rejected')", name="ck_notification_type"),
        sa.CheckConstraint("(notification_type IN ('credit_sale_recorded', 'repayment_recorded') AND related_entity_type = 'ledger_entry') OR (notification_type = 'payment_reminder_recorded' AND related_entity_type = 'payment_reminder') OR (notification_type IN ('business_approved', 'business_rejected') AND related_entity_type = 'business_approval_audit')", name="ck_notification_entity_type"),
        sa.CheckConstraint("related_entity_id > 0", name="ck_notification_entity_id"),
        sa.CheckConstraint("(is_read = 0 AND read_at IS NULL) OR (is_read = 1 AND read_at IS NOT NULL)", name="ck_notification_read_state"),
    )
    op.create_index("ix_notifications_business_id", "notifications", ["business_id"])
    op.create_index("ix_notification_recipient_created", "notifications", ["recipient_user_id", "created_at", "notification_id"])
    op.create_index("ix_notification_recipient_read_created", "notifications", ["recipient_user_id", "is_read", "created_at", "notification_id"])
    op.create_index("ix_notification_recipient_type_created", "notifications", ["recipient_user_id", "notification_type", "created_at", "notification_id"])


def downgrade():
    # Intentionally refuse data-destroying rollback. Forward migrations are additive.
    raise RuntimeError("Notification data must be preserved; use an additive forward migration")
