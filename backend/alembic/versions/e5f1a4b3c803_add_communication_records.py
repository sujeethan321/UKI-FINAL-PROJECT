"""Add explicit preference evidence and WhatsApp handoff request records.
Revision ID: e5f1a4b3c803
Revises: d4e0f3a2b702
"""
from alembic import op
import sqlalchemy as sa
revision = "e5f1a4b3c803"
down_revision = "d4e0f3a2b702"
branch_labels = None
depends_on = None


def fk(name, target, nullable=False):
    return sa.Column(name, sa.BigInteger(), sa.ForeignKey(target, ondelete="RESTRICT"), nullable=nullable)


def upgrade():
    op.create_table("communication_consents",
        sa.Column("consent_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        fk("business_id", "businesses.business_id"), fk("customer_id", "customer_profiles.customer_id"), fk("recorded_by", "users.user_id"),
        sa.Column("channel", sa.String(20), nullable=False), sa.Column("consent_status", sa.String(20), nullable=False),
        sa.Column("phone", sa.String(15), nullable=True), sa.Column("evidence", sa.String(500), nullable=False),
        sa.Column("idempotency_key", sa.String(100, collation="utf8mb4_bin"), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("business_id", "idempotency_key", name="uq_consent_business_key"),
        sa.CheckConstraint("channel = 'whatsapp'", name="ck_consent_channel"),
        sa.CheckConstraint("consent_status IN ('granted', 'opted_out')", name="ck_consent_status"),
        sa.CheckConstraint("consent_status = 'opted_out' OR phone IS NOT NULL", name="ck_consent_phone"))
    op.create_index("ix_consent_customer_latest", "communication_consents", ["business_id", "customer_id", "consent_id"])
    op.create_table("communication_attempts",
        sa.Column("attempt_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        fk("business_id", "businesses.business_id"), fk("customer_id", "customer_profiles.customer_id"),
        fk("reminder_id", "payment_reminders.reminder_id"), fk("consent_id", "communication_consents.consent_id"), fk("requested_by", "users.user_id"),
        sa.Column("channel", sa.String(20), nullable=False), sa.Column("phone", sa.String(15), nullable=False), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("idempotency_key", sa.String(100, collation="utf8mb4_bin"), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("business_id", "idempotency_key", name="uq_handoff_business_key"),
        sa.CheckConstraint("channel = 'whatsapp'", name="ck_handoff_channel"), sa.CheckConstraint("status = 'handoff_requested'", name="ck_handoff_status"))
    op.create_index("ix_handoff_reminder_created", "communication_attempts", ["business_id", "reminder_id", "created_at", "attempt_id"])


def downgrade():
    raise RuntimeError("Communication audit data must be preserved; use an additive forward migration")
