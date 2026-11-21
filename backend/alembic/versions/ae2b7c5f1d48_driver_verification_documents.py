"""Private Driver document foundations only. Prepared, never auto-applied."""
from alembic import op
import sqlalchemy as sa

revision = 'ae2b7c5f1d48'
down_revision = '9d1a6f4e0c37'
branch_labels = depends_on = None


def upgrade():
    op.add_column('driver_profiles', sa.Column('legacy_document_exempt', sa.Boolean(), nullable=False, server_default=sa.text('0')))
    # Exemption is not document verification. No approval/reviewer fields change.
    op.execute(sa.text("UPDATE driver_profiles SET legacy_document_exempt=1 WHERE approval_status='approved'"))
    op.create_table('driver_verification_documents',
        sa.Column('document_id',sa.String(36),primary_key=True),
        sa.Column('driver_user_id',sa.BigInteger(),sa.ForeignKey('driver_profiles.user_id',ondelete='RESTRICT'),nullable=False),
        sa.Column('document_type',sa.String(32),nullable=False),
        sa.Column('version',sa.Integer(),nullable=False),
        sa.Column('current_slot',sa.Integer()),
        sa.Column('supersedes_id',sa.String(36)),
        sa.Column('storage_key',sa.String(64),nullable=False,unique=True),
        sa.Column('content_sha256',sa.String(64),nullable=False),
        sa.Column('media_type',sa.String(32),nullable=False),
        sa.Column('size_bytes',sa.BigInteger(),nullable=False),
        sa.Column('created_at',sa.DateTime(),nullable=False),
        sa.Column('validated_at',sa.DateTime(),nullable=False),
        sa.Column('review_status',sa.String(12),nullable=False),
        sa.Column('reviewed_by',sa.BigInteger(),sa.ForeignKey('users.user_id',ondelete='RESTRICT')),
        sa.Column('reviewed_at',sa.DateTime()),
        sa.Column('rejection_code',sa.String(32)),
        sa.CheckConstraint("document_type IN ('DRIVING_LICENCE','VEHICLE_OWNERSHIP_PROOF')",name='ck_driver_doc_type'),
        sa.CheckConstraint("media_type IN ('image/jpeg','image/png','application/pdf')",name='ck_driver_doc_media'),
        sa.CheckConstraint('size_bytes > 0 AND size_bytes <= 5242880',name='ck_driver_doc_size'),
        sa.CheckConstraint('version > 0',name='ck_driver_doc_version'),
        sa.CheckConstraint('current_slot IS NULL OR current_slot = 1',name='ck_driver_doc_current'),
        sa.CheckConstraint("review_status IN ('PENDING','APPROVED','REJECTED')",name='ck_driver_doc_review'),
        sa.CheckConstraint("(review_status='PENDING' AND reviewed_by IS NULL AND reviewed_at IS NULL AND rejection_code IS NULL) OR (review_status='APPROVED' AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL AND rejection_code IS NULL) OR (review_status='REJECTED' AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL AND rejection_code IS NOT NULL)",name='ck_driver_doc_review_fields'),
        sa.UniqueConstraint('driver_user_id','document_type','current_slot',name='uq_driver_doc_current'),
        sa.UniqueConstraint('driver_user_id','document_type','version',name='uq_driver_doc_version'),
        sa.UniqueConstraint('document_id','driver_user_id','document_type',name='uq_driver_doc_identity'),
        sa.UniqueConstraint('supersedes_id',name='uq_driver_doc_successor'),
        sa.ForeignKeyConstraint(['supersedes_id','driver_user_id','document_type'],['driver_verification_documents.document_id','driver_verification_documents.driver_user_id','driver_verification_documents.document_type'],name='fk_driver_doc_previous',ondelete='RESTRICT'),
        mysql_engine='InnoDB',mysql_charset='utf8mb4',mysql_collate='utf8mb4_unicode_ci')
    op.create_index('ix_driver_doc_review','driver_verification_documents',['review_status','created_at'])
    op.create_table('driver_document_audits',
        sa.Column('audit_id',sa.String(36),primary_key=True),
        sa.Column('document_id',sa.String(36),sa.ForeignKey('driver_verification_documents.document_id',ondelete='RESTRICT'),nullable=False),
        sa.Column('actor_user_id',sa.BigInteger(),sa.ForeignKey('users.user_id',ondelete='RESTRICT'),nullable=False),
        sa.Column('action',sa.String(16),nullable=False),
        sa.Column('outcome',sa.String(8),nullable=False),
        sa.Column('created_at',sa.DateTime(),nullable=False),
        sa.CheckConstraint("action IN ('SUBMITTED','REPLACED','REVIEWED','PREVIEWED','DOWNLOADED')",name='ck_driver_doc_audit_action'),
        sa.CheckConstraint("outcome IN ('SUCCESS','DENIED','FAILED')",name='ck_driver_doc_audit_outcome'),
        mysql_engine='InnoDB',mysql_charset='utf8mb4',mysql_collate='utf8mb4_unicode_ci')
    op.create_index('ix_driver_doc_audit_document','driver_document_audits',['document_id','created_at'])


def downgrade():
    raise RuntimeError('Preserve identity-document evidence; destructive downgrade is not supported')
