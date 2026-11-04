"""Add internal payment reminder snapshots.

Revision ID: c3d9e2f1a601
Revises: b2a1c4d6e8f0
"""
from alembic import op
import sqlalchemy as sa

revision = "c3d9e2f1a601"
down_revision = "b2a1c4d6e8f0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "payment_reminders",
        sa.Column("reminder_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("business_id", sa.BigInteger(), sa.ForeignKey("businesses.business_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("customer_id", sa.BigInteger(), sa.ForeignKey("customer_profiles.customer_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("credit_account_id", sa.BigInteger(), sa.ForeignKey("credit_accounts.credit_account_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("outstanding_amount", sa.Numeric(24, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("language", sa.String(2), nullable=False),
        sa.Column("template_version", sa.String(30), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("note", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("idempotency_key", sa.String(100, collation="utf8mb4_bin"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("business_id", "idempotency_key", name="uq_reminder_business_key"),
        sa.CheckConstraint("outstanding_amount > 0", name="ck_reminder_positive_amount"),
        sa.CheckConstraint("status = 'recorded'", name="ck_reminder_recorded_status"),
        sa.CheckConstraint("currency = 'LKR'", name="ck_reminder_currency"),
        sa.CheckConstraint("language IN ('en', 'ta')", name="ck_reminder_language"),
        sa.CheckConstraint("channel IN ('internal', 'copy', 'whatsapp', 'sms')", name="ck_reminder_channel"),
    )
    op.create_index("ix_reminder_business_created", "payment_reminders", ["business_id", "created_at", "reminder_id"])
    op.create_index("ix_reminder_customer_created", "payment_reminders", ["business_id", "customer_id", "created_at"])


def downgrade():
    op.drop_table("payment_reminders")
