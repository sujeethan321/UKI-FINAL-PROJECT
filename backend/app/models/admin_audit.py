"""Append-only through application APIs; state and audit share a transaction."""
from datetime import datetime
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.models.catalogue import utc_now


class AdminAudit(Base):
    __tablename__ = 'admin_audits'
    __table_args__ = (
        CheckConstraint("target_type IN ('user','driver')", name='ck_admin_audit_target'),
        CheckConstraint("action IN ('driver_approved','driver_rejected','account_suspended','account_reactivated','admin_provisioned')", name='ck_admin_audit_action'),
        CheckConstraint('target_id > 0', name='ck_admin_audit_target_id'),
        Index('ix_admin_audit_created', 'created_at', 'audit_id'),
        Index('ix_admin_audit_target', 'target_type', 'target_id', 'audit_id'),
    )
    audit_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    admin_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.user_id', ondelete='RESTRICT'))
    target_type: Mapped[str] = mapped_column(String(20))
    target_id: Mapped[int] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(30))
    previous_state: Mapped[str | None] = mapped_column(String(30), nullable=True)
    new_state: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
