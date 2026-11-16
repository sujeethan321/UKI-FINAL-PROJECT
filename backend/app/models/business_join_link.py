"""Permanent, opaque public lookup for an approved business."""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BusinessJoinLink(Base):
    __tablename__ = "business_join_links"
    __table_args__ = (UniqueConstraint("public_code", name="uq_business_join_public_code"),)

    business_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("businesses.business_id", ondelete="RESTRICT"), primary_key=True)
    public_code: Mapped[str] = mapped_column(String(32, collation="utf8mb4_bin"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
