"""Durable sandbox Checkout attempts only. Prepared; not executed."""
from alembic import op
import sqlalchemy as sa

revision = '9d1a6f4e0c37'
down_revision = '8c0f5e3d9b26'
branch_labels = depends_on = None


def upgrade():
    op.create_table('subscription_checkout_attempts',
        sa.Column('attempt_id', sa.String(36), primary_key=True),
        sa.Column('business_id', sa.BigInteger(), sa.ForeignKey('businesses.business_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('active_business_id', sa.BigInteger(), unique=True),
        sa.Column('request_key', sa.String(64), nullable=False, unique=True),
        sa.Column('plan', sa.String(12), nullable=False),
        sa.Column('billing_interval', sa.String(5), nullable=False),
        sa.Column('price_id', sa.String(255), nullable=False),
        sa.Column('return_origin', sa.String(255), nullable=False),
        sa.Column('stripe_session_id', sa.String(255), unique=True),
        sa.Column('stripe_customer_id', sa.String(255)),
        sa.Column('status', sa.String(12), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('reconciled_at', sa.DateTime()),
        sa.Column('error_code', sa.String(32)),
        sa.CheckConstraint("plan IN ('PRO', 'BUSINESS')", name='ck_checkout_plan'),
        sa.CheckConstraint("billing_interval IN ('month', 'year')", name='ck_checkout_interval'),
        sa.CheckConstraint("status IN ('CREATING', 'UNCERTAIN', 'OPEN', 'VERIFYING', 'COMPLETE', 'EXPIRED')", name='ck_checkout_status'),
        sa.CheckConstraint('active_business_id IS NULL OR active_business_id = business_id', name='ck_checkout_business'),
        sa.CheckConstraint("(status IN ('CREATING', 'UNCERTAIN', 'OPEN', 'VERIFYING') AND active_business_id IS NOT NULL) OR (status IN ('COMPLETE', 'EXPIRED') AND active_business_id IS NULL)", name='ck_checkout_active'),
        sa.CheckConstraint('expires_at > created_at', name='ck_checkout_period'),
        mysql_engine='InnoDB', mysql_charset='utf8mb4', mysql_collate='utf8mb4_unicode_ci')
    op.create_index('ix_subscription_checkout_attempts_business_id', 'subscription_checkout_attempts', ['business_id'])


def downgrade():
    raise RuntimeError('Preserve Checkout evidence; destructive downgrade is not supported')
