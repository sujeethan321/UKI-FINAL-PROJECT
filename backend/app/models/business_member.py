# Purpose: Map business member records to database tables so SQLAlchemy can persist and relate application data.

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# Map business member to the business_members table for ORM queries and persistence.
class BusinessMember(Base):
    __tablename__ = "business_members"

    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "user_id",
            name="uq_business_member_business_user",
        ),
    )

    # Use membership id as the unique row identity for ORM lookups and related records.
    membership_id: Mapped[int] = mapped_column(
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

    # Link user id to users.user_id so the database enforces the record relationship.
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "users.user_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    business_role: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="owner",
        server_default="owner",
    )

    # Retain membership status so workflow checks can decide which operations are currently allowed.
    membership_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
        server_default="active",
    )
