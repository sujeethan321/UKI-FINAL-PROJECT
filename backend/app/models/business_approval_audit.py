# Purpose: Map business approval audit records to database tables so SQLAlchemy can persist and relate application data.

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# Map business approval audit to the business_approval_audits table for ORM queries and persistence.
class BusinessApprovalAudit(Base):
    __tablename__ = "business_approval_audits"

    # Use audit id as the unique row identity for ORM lookups and related records.
    audit_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    # Link business id to businesses.business_id so the database enforces the record relationship.
    business_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "businesses.business_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    # Link admin user id to users.user_id so the database enforces the record relationship.
    admin_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "users.user_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    decision: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # Retain previous status so workflow checks can decide which operations are currently allowed.
    previous_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    # Retain new status so workflow checks can decide which operations are currently allowed.
    new_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    review_note: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Retain created at for history, ordering, and time-based queries.
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
