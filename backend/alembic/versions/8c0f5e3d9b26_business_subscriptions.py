"""Business subscriptions and one-time approval trials; no retroactive trials.

Prepared only. MySQL DDL is not transactional: preserve partial state on failure.
"""
from alembic import op
import sqlalchemy as sa

revision = "8c0f5e3d9b26"
down_revision = "7b9e4d2c8a15"
branch_labels = None
depends_on = None


def upgrade():
    options = dict(mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci")
    op.create_table("subscription_trial_grants",
        sa.Column("business_id", sa.BigInteger(), sa.ForeignKey("businesses.business_id", ondelete="RESTRICT"), primary_key=True, autoincrement=False),
        sa.Column("grant_status", sa.String(12), nullable=False),
        sa.Column("trial_started_at", sa.DateTime(), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("grant_status IN ('GRANTED', 'EXCLUDED')", name="ck_trial_grant_status"),
        sa.CheckConstraint("(grant_status = 'GRANTED' AND trial_started_at IS NOT NULL AND trial_ends_at IS NOT NULL AND trial_ends_at > trial_started_at) OR (grant_status = 'EXCLUDED' AND trial_started_at IS NULL AND trial_ends_at IS NULL)", name="ck_trial_grant_period"), **options)
    op.create_table("business_subscriptions",
        sa.Column("business_id", sa.BigInteger(), sa.ForeignKey("businesses.business_id", ondelete="RESTRICT"), primary_key=True, autoincrement=False),
        sa.Column("plan", sa.String(12), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("billing_interval", sa.String(5), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("paid_through", sa.DateTime(), nullable=True),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        sa.Column("provider_mode", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("stripe_customer_id"), sa.UniqueConstraint("stripe_subscription_id"),
        sa.CheckConstraint("plan IN ('FREE', 'PRO', 'BUSINESS')", name="ck_subscription_plan"),
        sa.CheckConstraint("status IN ('FREE', 'TRIALING', 'ACTIVE', 'PAST_DUE', 'CANCELLED')", name="ck_subscription_status"),
        sa.CheckConstraint("billing_interval IS NULL OR billing_interval IN ('month', 'year')", name="ck_subscription_interval"),
        sa.CheckConstraint("provider_mode = 'sandbox'", name="ck_subscription_sandbox"),
        sa.CheckConstraint("paid_through IS NULL OR (started_at IS NOT NULL AND paid_through > started_at)", name="ck_subscription_paid_period"), **options)
    op.create_table("subscription_payment_events",
        sa.Column("event_id", sa.String(255), primary_key=True),
        sa.Column("business_id", sa.BigInteger(), sa.ForeignKey("businesses.business_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("provider_mode", sa.String(10), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("provider_mode = 'sandbox'", name="ck_payment_event_sandbox"),
        sa.CheckConstraint("amount_minor >= 0", name="ck_payment_event_amount"),
        sa.CheckConstraint("currency = 'lkr'", name="ck_payment_event_currency"), **options)
    op.create_index("ix_subscription_payment_events_business_id", "subscription_payment_events", ["business_id"])
    # Eligibility markers only, never a promotional entitlement or a paid record.
    # Covers legacy approved rows without audits and previously approved rows
    # that were subsequently rejected/suspended/reset to pending.
    op.execute(sa.text("""INSERT INTO subscription_trial_grants
        (business_id, grant_status, created_at)
        SELECT b.business_id, 'EXCLUDED', UTC_TIMESTAMP() FROM businesses b
        WHERE b.approval_status = 'approved' OR EXISTS
        (SELECT 1 FROM business_approval_audits a WHERE a.business_id = b.business_id AND a.decision = 'approve')"""))


def downgrade():
    raise RuntimeError("Subscription history must be preserved; destructive downgrade is not supported")
