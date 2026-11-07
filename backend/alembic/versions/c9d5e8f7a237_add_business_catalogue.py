"""Add business-owned product categories and products, preserving existing data."""
from alembic import op
import sqlalchemy as sa

revision = 'c9d5e8f7a237'
down_revision = 'b8c4d7e6f126'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('product_categories',
        sa.Column('category_id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('business_id', sa.BigInteger(), sa.ForeignKey('businesses.business_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('name', sa.String(100, collation='utf8mb4_unicode_ci'), nullable=False),
        sa.Column('description', sa.String(2000), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('business_id', 'name', name='uq_category_business_name'),
        sa.UniqueConstraint('category_id', 'business_id', name='uq_category_id_business'),
        sa.CheckConstraint('CHAR_LENGTH(TRIM(name)) > 0', name='ck_category_name'),
    )
    op.create_index('ix_category_business_active', 'product_categories', ['business_id','is_active','category_id'])
    op.create_table('products',
        sa.Column('product_id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('business_id', sa.BigInteger(), sa.ForeignKey('businesses.business_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('category_id', sa.BigInteger(), nullable=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.String(4000), nullable=True),
        sa.Column('unit_price', sa.Numeric(12,2), nullable=False),
        sa.Column('currency', sa.String(3), server_default='LKR', nullable=False),
        sa.Column('availability_status', sa.String(20), server_default='available', nullable=False),
        sa.Column('publication_status', sa.String(20), server_default='draft', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['category_id','business_id'], ['product_categories.category_id','product_categories.business_id'],
            name='fk_product_category_business', ondelete='RESTRICT'),
        sa.CheckConstraint('CHAR_LENGTH(TRIM(name)) > 0', name='ck_product_name'),
        sa.CheckConstraint('unit_price > 0', name='ck_product_price'),
        sa.CheckConstraint("currency = 'LKR'", name='ck_product_currency'),
        sa.CheckConstraint("availability_status IN ('available','unavailable')", name='ck_product_availability'),
        sa.CheckConstraint("publication_status IN ('draft','published','archived')", name='ck_product_publication'),
    )
    op.create_index('ix_product_business_publication', 'products', ['business_id','publication_status','product_id'])
    op.create_index('ix_product_business_category', 'products', ['category_id','business_id'])


def downgrade():
    raise RuntimeError('Preserve catalogue data; use a forward migration')
