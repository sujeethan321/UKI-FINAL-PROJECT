# Purpose: Map driver document records to database tables so SQLAlchemy can persist and relate application data.
"""Immutable private document versions; no public storage URLs."""
from datetime import datetime
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint, event, inspect
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


# Map driver verification document to the driver_verification_documents table for ORM queries and persistence.
class DriverVerificationDocument(Base):
    __tablename__ = 'driver_verification_documents'
    __table_args__ = (
        CheckConstraint("document_type IN ('DRIVING_LICENCE','VEHICLE_OWNERSHIP_PROOF')", name='ck_driver_doc_type'),
        CheckConstraint("media_type IN ('image/jpeg','image/png','application/pdf')", name='ck_driver_doc_media'),
        CheckConstraint('size_bytes > 0 AND size_bytes <= 5242880', name='ck_driver_doc_size'),
        CheckConstraint('version > 0', name='ck_driver_doc_version'),
        CheckConstraint('current_slot IS NULL OR current_slot = 1', name='ck_driver_doc_current'),
        CheckConstraint("review_status IN ('PENDING','APPROVED','REJECTED')", name='ck_driver_doc_review'),
        CheckConstraint("(review_status='PENDING' AND reviewed_by IS NULL AND reviewed_at IS NULL AND rejection_code IS NULL) OR (review_status='APPROVED' AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL AND rejection_code IS NULL) OR (review_status='REJECTED' AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL AND rejection_code IS NOT NULL)", name='ck_driver_doc_review_fields'),
        UniqueConstraint('driver_user_id','document_type','current_slot', name='uq_driver_doc_current'),
        UniqueConstraint('driver_user_id','document_type','version', name='uq_driver_doc_version'),
        UniqueConstraint('document_id','driver_user_id','document_type', name='uq_driver_doc_identity'),
        UniqueConstraint('supersedes_id', name='uq_driver_doc_successor'),
        ForeignKeyConstraint(['supersedes_id','driver_user_id','document_type'], ['driver_verification_documents.document_id','driver_verification_documents.driver_user_id','driver_verification_documents.document_type'], name='fk_driver_doc_previous', ondelete='RESTRICT'),
        Index('ix_driver_doc_review','review_status','created_at'),
        {'mysql_engine':'InnoDB','mysql_charset':'utf8mb4','mysql_collate':'utf8mb4_unicode_ci'},
    )
    # Use document id as the unique row identity for ORM lookups and related records.
    document_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # Link driver user id to driver_profiles.user_id so the database enforces the record relationship.
    driver_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('driver_profiles.user_id', ondelete='RESTRICT'), nullable=False)
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    current_slot: Mapped[int | None] = mapped_column(Integer)
    supersedes_id: Mapped[str | None] = mapped_column(String(36))
    # Keep storage key unique so separate rows cannot claim the same value.
    storage_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    media_type: Mapped[str] = mapped_column(String(32), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Retain created at for history, ordering, and time-based queries.
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    validated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Retain review status so workflow checks can decide which operations are currently allowed.
    review_status: Mapped[str] = mapped_column(String(12), nullable=False, default='PENDING')
    # Link reviewed by to users.user_id so the database enforces the record relationship.
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('users.user_id', ondelete='RESTRICT'))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    rejection_code: Mapped[str | None] = mapped_column(String(32))


# Map driver document audit to the driver_document_audits table for ORM queries and persistence.
class DriverDocumentAudit(Base):
    __tablename__ = 'driver_document_audits'
    __table_args__ = (
        CheckConstraint("action IN ('SUBMITTED','REPLACED','REVIEWED','PREVIEWED','DOWNLOADED')", name='ck_driver_doc_audit_action'),
        CheckConstraint("outcome IN ('SUCCESS','DENIED','FAILED')", name='ck_driver_doc_audit_outcome'),
        Index('ix_driver_doc_audit_document','document_id','created_at'),
        {'mysql_engine':'InnoDB','mysql_charset':'utf8mb4','mysql_collate':'utf8mb4_unicode_ci'},
    )
    # Use audit id as the unique row identity for ORM lookups and related records.
    audit_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # Link document id to driver_verification_documents.document_id so the database enforces the record relationship.
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey('driver_verification_documents.document_id', ondelete='RESTRICT'), nullable=False)
    # Link actor user id to users.user_id so the database enforces the record relationship.
    actor_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.user_id', ondelete='RESTRICT'), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    outcome: Mapped[str] = mapped_column(String(8), nullable=False)
    # Retain created at for history, ordering, and time-based queries.
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


# Reject edits to persisted document versions so replacements remain new traceable versions.
@event.listens_for(DriverVerificationDocument, 'before_update')
def immutable_version(mapper, connection, target):
    mutable = {'current_slot','review_status','reviewed_by','reviewed_at','rejection_code'}
    if any(a.history.has_changes() for a in inspect(target).attrs if a.key not in mutable):
        raise ValueError('Document versions are immutable')


# Reject document-evidence deletion through this model hook to retain the review history.
@event.listens_for(DriverVerificationDocument, 'before_delete')
@event.listens_for(DriverDocumentAudit, 'before_delete')
@event.listens_for(DriverDocumentAudit, 'before_update')
def preserve_evidence(*args):
    raise ValueError('Document evidence retention requires separate authorization')
