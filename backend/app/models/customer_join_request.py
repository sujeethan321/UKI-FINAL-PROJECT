"""One customer-initiated membership request per business and user."""
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CustomerJoinRequest(Base):
    __tablename__ = "customer_join_requests"
    __table_args__ = (
        UniqueConstraint("business_id", "customer_user_id", name="uq_customer_join_business_user"),
        CheckConstraint("status IN ('pending', 'approved', 'rejected', 'cancelled')", name="ck_customer_join_status"),
        Index("ix_customer_join_business_status_created", "business_id", "status", "created_at"),
    )

    request_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("businesses.business_id", ondelete="RESTRICT"), nullable=False)
    customer_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decided_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=True)
