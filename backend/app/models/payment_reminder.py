"""Internal reminder snapshots; recording never implies external delivery."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PaymentReminder(Base):
    __tablename__ = "payment_reminders"
    __table_args__ = (
        UniqueConstraint("business_id", "idempotency_key", name="uq_reminder_business_key"),
        CheckConstraint("outstanding_amount > 0", name="ck_reminder_positive_amount"),
        CheckConstraint("status = 'recorded'", name="ck_reminder_recorded_status"),
        CheckConstraint("currency = 'LKR'", name="ck_reminder_currency"),
        CheckConstraint("language IN ('en', 'ta')", name="ck_reminder_language"),
        CheckConstraint("channel IN ('internal', 'copy', 'whatsapp', 'sms')", name="ck_reminder_channel"),
        Index("ix_reminder_business_created", "business_id", "created_at", "reminder_id"),
        Index("ix_reminder_customer_created", "business_id", "customer_id", "created_at"),
    )
    reminder_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("businesses.business_id", ondelete="RESTRICT"))
    customer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("customer_profiles.customer_id", ondelete="RESTRICT"))
    credit_account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("credit_accounts.credit_account_id", ondelete="RESTRICT"))
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"))
    outstanding_amount: Mapped[Decimal] = mapped_column(Numeric(24, 2))
    currency: Mapped[str] = mapped_column(String(3), default="LKR")
    channel: Mapped[str] = mapped_column(String(20))
    language: Mapped[str] = mapped_column(String(2))
    template_version: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="recorded")
    idempotency_key: Mapped[str] = mapped_column(String(100, collation="utf8mb4_bin"))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
