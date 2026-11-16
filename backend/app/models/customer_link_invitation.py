"""Short-lived, single-use customer credit-profile invitation."""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CustomerLinkInvitation(Base):
    __tablename__ = "customer_link_invitations"
    __table_args__ = (
        Index("ix_customer_link_recipient_expiry", "recipient_user_id", "expires_at"),
        UniqueConstraint("code_digest", name="uq_link_invitation_code_digest"),
    )

    customer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("customer_profiles.customer_id", ondelete="RESTRICT"), primary_key=True)
    business_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("businesses.business_id", ondelete="RESTRICT"), nullable=False)
    recipient_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    issuer_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    code_digest: Mapped[str] = mapped_column(String(64, collation="utf8mb4_bin"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
