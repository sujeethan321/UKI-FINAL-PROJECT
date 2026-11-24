# Purpose: Map customer link invitation records to database tables so SQLAlchemy can persist and relate application data.
"""Short-lived, single-use customer credit-profile invitation."""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# Map customer link invitation to the customer_link_invitations table for ORM queries and persistence.
class CustomerLinkInvitation(Base):
    __tablename__ = "customer_link_invitations"
    __table_args__ = (
        Index("ix_customer_link_recipient_expiry", "recipient_user_id", "expires_at"),
        UniqueConstraint("code_digest", name="uq_link_invitation_code_digest"),
        {'mysql_engine':'InnoDB','mysql_charset':'utf8mb4','mysql_collate':'utf8mb4_unicode_ci'},
    )

    # Link customer id to customer_profiles.customer_id so the database enforces the record relationship.
    customer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("customer_profiles.customer_id", ondelete="RESTRICT"), primary_key=True)
    # Link business id to businesses.business_id so the database enforces the record relationship.
    business_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("businesses.business_id", ondelete="RESTRICT"), nullable=False)
    # Link recipient user id to users.user_id so the database enforces the record relationship.
    recipient_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    # Link issuer user id to users.user_id so the database enforces the record relationship.
    issuer_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    # Retain the code digest fingerprint used to compare values without persisting the corresponding raw value here.
    code_digest: Mapped[str] = mapped_column(String(64, collation="utf8mb4_bin"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
