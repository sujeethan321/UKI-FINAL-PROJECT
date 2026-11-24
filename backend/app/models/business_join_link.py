# Purpose: Map business join link records to database tables so SQLAlchemy can persist and relate application data.
"""Permanent, opaque public lookup for an approved business."""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# Map business join link to the business_join_links table for ORM queries and persistence.
class BusinessJoinLink(Base):
    __tablename__ = "business_join_links"
    __table_args__ = (UniqueConstraint("public_code", name="uq_business_join_public_code"),
        {'mysql_engine':'InnoDB','mysql_charset':'utf8mb4','mysql_collate':'utf8mb4_unicode_ci'})

    # Link business id to businesses.business_id so the database enforces the record relationship.
    business_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("businesses.business_id", ondelete="RESTRICT"), primary_key=True)
    public_code: Mapped[str] = mapped_column(String(32, collation="utf8mb4_bin"), nullable=False)
    # Retain created at for history, ordering, and time-based queries.
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
