# Purpose: Map business records to database tables so SQLAlchemy can persist and relate application data.

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# Map business to the businesses table for ORM queries and persistence.
class Business(Base):
    __tablename__ = "businesses"

    # Use business id as the unique row identity for ORM lookups and related records.
    business_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    business_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    business_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    registration_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    address: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Retain approval status so workflow checks can decide which operations are currently allowed.
    approval_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    # Retain created at for history, ordering, and time-based queries.
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
