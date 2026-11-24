# Purpose: Map customer profile records to database tables so SQLAlchemy can persist and relate application data.

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# Map customer profile to the customer_profiles table for ORM queries and persistence.
class CustomerProfile(Base):
    __tablename__ = "customer_profiles"
    __table_args__ = (UniqueConstraint("business_id", "user_id", name="uq_customer_profile_business_user"),)

    # Use customer id as the unique row identity for ORM lookups and related records.
    customer_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    # Link business id to businesses.business_id so the database enforces the record relationship.
    business_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("businesses.business_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Link user id to users.user_id so the database enforces the record relationship.
    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    customer_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    address: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Retain created at for history, ordering, and time-based queries.
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    business: Mapped["Business"] = relationship(
        "Business",
    )

    user: Mapped["User | None"] = relationship(
        "User",
    )

    credit_accounts: Mapped[list["CreditAccount"]] = relationship(
        "CreditAccount",
        back_populates="customer",
    )
