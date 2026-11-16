"""Add five approved storage foundations without changing existing rows.

Requires the complete existing chain through 03b9c2d1e671.
No backfill, APIs, active-vehicle columns, financial changes or optional tables.
See docs/phase3-database-enhancement-migrations.md before execution.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = '14c0d3e2f782'
down_revision = '03b9c2d1e671'
branch_labels = None
depends_on = None


def upgrade():
    # Only create new storage. No current models are imported into this revision.
    # MySQL cannot CHECK the AUTO_INCREMENT document_id: self-supersession,
    # cycles and same-type/current-tip replacement require a future write service.
    op.create_table('customer_addresses',
        sa.Column('address_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('label', sa.String(length=50), nullable=False),
        sa.Column('recipient_name', sa.String(length=150), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('address_line', sa.String(length=500), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('latitude', sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column('longitude', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('archived_at', mysql.DATETIME(fsp=6), nullable=True),
        sa.Column('created_at', mysql.DATETIME(fsp=6), server_default=sa.text('CURRENT_TIMESTAMP(6)'), nullable=False),
        sa.Column('updated_at', mysql.DATETIME(fsp=6), server_default=sa.text('CURRENT_TIMESTAMP(6)'), nullable=False),
        sa.CheckConstraint('(latitude IS NULL AND longitude IS NULL) OR (latitude IS NOT NULL AND longitude IS NOT NULL AND latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)', name='ck_address_coordinates'),
        sa.CheckConstraint('CHAR_LENGTH(TRIM(address_line)) > 0', name='ck_address_line'),
        sa.CheckConstraint('CHAR_LENGTH(TRIM(label)) > 0', name='ck_address_label'),
        sa.CheckConstraint('CHAR_LENGTH(TRIM(recipient_name)) > 0', name='ck_address_recipient'),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], name='fk_address_user', onupdate='RESTRICT', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('address_id'),
        sa.UniqueConstraint('address_id', 'user_id', name='uq_address_id_user'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
        mysql_engine='InnoDB'
    )
    op.create_index('ix_address_user_archived', 'customer_addresses', ['user_id', 'archived_at', 'address_id'], unique=False)
    op.create_table('user_preferences',
        sa.Column('user_id', sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column('theme', sa.String(length=10), server_default='system', nullable=False),
        sa.Column('in_app_notifications', sa.Boolean(), server_default=sa.text('1'), nullable=False),
        sa.Column('email_notifications', sa.Boolean(), nullable=True),
        sa.Column('preferred_address_id', sa.BigInteger(), nullable=True),
        sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('updated_at', mysql.DATETIME(fsp=6), server_default=sa.text('CURRENT_TIMESTAMP(6)'), nullable=False),
        sa.CheckConstraint("theme IN ('light','dark','system')", name='ck_preference_theme'),
        sa.CheckConstraint('email_notifications IS NULL OR email_notifications IN (0,1)', name='ck_preference_email'),
        sa.CheckConstraint('in_app_notifications IN (0,1)', name='ck_preference_in_app'),
        sa.CheckConstraint('version >= 1', name='ck_preference_version'),
        sa.ForeignKeyConstraint(['preferred_address_id', 'user_id'], ['customer_addresses.address_id', 'customer_addresses.user_id'], name='fk_preference_owned_address', onupdate='RESTRICT', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], name='fk_preference_user', onupdate='RESTRICT', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('user_id'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
        mysql_engine='InnoDB'
    )
    op.create_index('ix_preference_address_user', 'user_preferences', ['preferred_address_id', 'user_id'], unique=False)
    op.create_table('business_settings',
        sa.Column('business_id', sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column('default_credit_limit', sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column('default_payment_term_days', sa.Integer(), nullable=True),
        sa.Column('delivery_enabled', sa.Boolean(), server_default=sa.text('0'), nullable=False),
        sa.Column('delivery_radius_km', sa.Numeric(precision=7, scale=2), nullable=True),
        sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('updated_at', mysql.DATETIME(fsp=6), server_default=sa.text('CURRENT_TIMESTAMP(6)'), nullable=False),
        sa.CheckConstraint('default_credit_limit IS NULL OR default_credit_limit >= 0', name='ck_setting_credit_limit'),
        sa.CheckConstraint('default_payment_term_days IS NULL OR default_payment_term_days > 0', name='ck_setting_payment_term'),
        sa.CheckConstraint('delivery_enabled IN (0,1)', name='ck_setting_delivery_enabled'),
        sa.CheckConstraint('delivery_radius_km IS NULL OR delivery_radius_km > 0', name='ck_setting_delivery_radius'),
        sa.CheckConstraint('version >= 1', name='ck_setting_version'),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.business_id'], name='fk_setting_business', onupdate='RESTRICT', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('business_id'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
        mysql_engine='InnoDB'
    )
    op.create_table('vehicles',
        sa.Column('vehicle_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('driver_user_id', sa.BigInteger(), nullable=False),
        sa.Column('vehicle_type', sa.String(length=50), nullable=False),
        sa.Column('registration_reference', sa.String(length=50), nullable=False),
        sa.Column('make', sa.String(length=100), nullable=True),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('model_year', sa.SmallInteger(), nullable=True),
        sa.Column('image_storage_key', sa.String(length=500), nullable=True),
        sa.Column('lifecycle_status', sa.String(length=20), server_default='active', nullable=False),
        sa.Column('source', sa.String(length=20), server_default='submitted', nullable=False),
        sa.Column('created_at', mysql.DATETIME(fsp=6), server_default=sa.text('CURRENT_TIMESTAMP(6)'), nullable=False),
        sa.Column('updated_at', mysql.DATETIME(fsp=6), server_default=sa.text('CURRENT_TIMESTAMP(6)'), nullable=False),
        sa.CheckConstraint("lifecycle_status IN ('active','retired')", name='ck_vehicle_lifecycle'),
        sa.CheckConstraint("source IN ('submitted','legacy')", name='ck_vehicle_source'),
        sa.CheckConstraint('CHAR_LENGTH(TRIM(registration_reference)) > 0', name='ck_vehicle_registration'),
        sa.CheckConstraint('CHAR_LENGTH(TRIM(vehicle_type)) > 0', name='ck_vehicle_type'),
        sa.CheckConstraint('model_year IS NULL OR model_year BETWEEN 1900 AND 2100', name='ck_vehicle_year'),
        sa.ForeignKeyConstraint(['driver_user_id'], ['driver_profiles.user_id'], name='fk_vehicle_driver', onupdate='RESTRICT', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('vehicle_id'),
        sa.UniqueConstraint('vehicle_id', 'driver_user_id', name='uq_vehicle_id_driver'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
        mysql_engine='InnoDB'
    )
    op.create_index('ix_vehicle_driver_lifecycle', 'vehicles', ['driver_user_id', 'lifecycle_status', 'vehicle_id'], unique=False)
    op.create_table('vehicle_documents',
        sa.Column('document_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('vehicle_id', sa.BigInteger(), nullable=False),
        sa.Column('document_type', sa.String(length=30), nullable=False),
        sa.Column('storage_key', sa.String(length=500), nullable=False),
        sa.Column('content_sha256', mysql.CHAR(charset='ascii', length=64), nullable=False),
        sa.Column('media_type', sa.String(length=100), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('review_status', sa.String(length=20), server_default='pending', nullable=False),
        sa.Column('expires_on', sa.Date(), nullable=True),
        sa.Column('supersedes_document_id', sa.BigInteger(), nullable=True),
        sa.Column('reviewed_by', sa.BigInteger(), nullable=True),
        sa.Column('reviewed_at', mysql.DATETIME(fsp=6), nullable=True),
        sa.Column('rejection_reason', sa.String(length=500), nullable=True),
        sa.Column('created_at', mysql.DATETIME(fsp=6), server_default=sa.text('CURRENT_TIMESTAMP(6)'), nullable=False),
        sa.CheckConstraint("(review_status = 'pending' AND reviewed_by IS NULL AND reviewed_at IS NULL AND rejection_reason IS NULL) OR (review_status = 'approved' AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL AND rejection_reason IS NULL) OR (review_status = 'rejected' AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL AND rejection_reason IS NOT NULL AND CHAR_LENGTH(TRIM(rejection_reason)) > 0)", name='ck_document_review_state'),
        sa.CheckConstraint("document_type IN ('registration','insurance','revenue_license')", name='ck_document_type'),
        sa.CheckConstraint("review_status IN ('pending','approved','rejected')", name='ck_document_review_status'),
        sa.CheckConstraint('CHAR_LENGTH(TRIM(storage_key)) > 0', name='ck_document_storage'),
        sa.CheckConstraint('size_bytes > 0', name='ck_document_size'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.user_id'], name='fk_document_reviewer', onupdate='RESTRICT', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['supersedes_document_id', 'vehicle_id'], ['vehicle_documents.document_id', 'vehicle_documents.vehicle_id'], name='fk_document_superseded_vehicle', onupdate='RESTRICT', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.vehicle_id'], name='fk_document_vehicle', onupdate='RESTRICT', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('document_id'),
        sa.UniqueConstraint('document_id', 'vehicle_id', name='uq_document_id_vehicle'),
        sa.UniqueConstraint('supersedes_document_id', name='uq_document_supersedes'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
        mysql_engine='InnoDB'
    )
    op.create_index('ix_document_review_expiry', 'vehicle_documents', ['review_status', 'expires_on', 'document_id'], unique=False)
    op.create_index('ix_document_reviewer', 'vehicle_documents', ['reviewed_by'], unique=False)
    op.create_index('ix_document_supersedes_vehicle', 'vehicle_documents', ['supersedes_document_id', 'vehicle_id'], unique=False)
    op.create_index('ix_document_vehicle_type_created', 'vehicle_documents', ['vehicle_id', 'document_type', 'created_at', 'document_id'], unique=False)



def downgrade():
    # Even these non-ledger tables may contain personal data/review evidence.
    # No implicit table drops, including when an operator assumes they are empty.
    raise RuntimeError(
        'Preserve addresses, settings and vehicle review evidence; '
        'use an explicitly reviewed forward migration or approved restore'
    )
