# Purpose: Map customer join request records to database tables so SQLAlchemy can persist and relate application data.
"""One customer-initiated membership request per business and user."""
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# Map customer join request to the customer_join_requests table for ORM queries and persistence.
class CustomerJoinRequest(Base):
    __tablename__ = "customer_join_requests"
    __table_args__ = (
        UniqueConstraint("business_id", "customer_user_id", name="uq_customer_join_business_user"),
        CheckConstraint("status IN ('pending', 'approved', 'rejected', 'cancelled')", name="ck_customer_join_status"),
        Index("ix_customer_join_business_status_created", "business_id", "status", "created_at"),
        {'mysql_engine':'InnoDB','mysql_charset':'utf8mb4','mysql_collate':'utf8mb4_unicode_ci'},
    )

    # Use request id as the unique row identity for ORM lookups and related records.
    request_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Link business id to businesses.business_id so the database enforces the record relationship.
    business_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("businesses.business_id", ondelete="RESTRICT"), nullable=False)
    # Link customer user id to users.user_id so the database enforces the record relationship.
    customer_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    # Retain status so workflow checks can decide which operations are currently allowed.
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    # Retain created at for history, ordering, and time-based queries.
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Link decided by to users.user_id so the database enforces the record relationship.
    decided_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=True)
  