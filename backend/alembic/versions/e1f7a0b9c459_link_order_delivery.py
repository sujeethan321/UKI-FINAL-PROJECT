"""Link one delivery per order with database-enforced business consistency."""
from alembic import op
import sqlalchemy as sa

revision = 'e1f7a0b9c459'
down_revision = 'd0e6f9a8b348'
branch_labels = None
depends_on = None


def upgrade():
    # Legacy requests and orders stay untouched; null means no delivery linked.
    op.create_unique_constraint('uq_delivery_id_business', 'delivery_requests',
                                ['delivery_request_id', 'business_id'])
    op.add_column('orders', sa.Column('delivery_request_id', sa.BigInteger(), nullable=True))
    op.create_unique_constraint('uq_order_delivery_request', 'orders', ['delivery_request_id'])
    op.create_foreign_key('fk_order_delivery_business', 'orders', 'delivery_requests',
                          ['delivery_request_id', 'business_id'],
                          ['delivery_request_id', 'business_id'], ondelete='RESTRICT')


def downgrade():
    raise RuntimeError('Preserve order delivery relationships; use a forward migration')
