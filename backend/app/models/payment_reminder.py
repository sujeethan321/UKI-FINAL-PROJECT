# Purpose: Map payment reminder records to database tables so SQLAlchemy can persist and relate application data.
"""Internal reminder snapshots; recording never implies external delivery."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# Map payment reminder to the payment_reminders table for ORM queries and persistence.
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
    # Use reminder id as the unique row identity for ORM lookups and related records.
    reminder_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Link business id to businesses.business_id so the database enforces the record relationship.
    business_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("businesses.business_id", ondelete="RESTRICT"))
    # Link customer id to customer_profiles.customer_id so the database enforces the record relationship.
    customer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("customer_profiles.customer_id", ondelete="RESTRICT"))
    # Link credit account id to credit_accounts.credit_account_id so the database enforces the record relationship.
    credit_account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("credit_accounts.credit_account_id", ondelete="RESTRICT"))
    # Link created by to users.user_id so the database enforces the record relationship.
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"))
    # Store outstanding amount as an exact decimal so persisted financial values avoid binary floating-point rounding.
    outstanding_amount: Mapped[Decimal] = mapped_column(Numeric(24, 2))
    currency: Mapped[str] = mapped_column(String(3), default="LKR")
    channel: Mapped[str] = mapped_column(String(20))
    language: Mapped[str] = mapped_column(String(2))
    template_version: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # Retain status so workflow checks can decide which operations are currently allowed.
    status: Mapped[str] = mapped_column(String(20), default="recorded")
    # Identify a logical request so retries can be checked against the original operation.
    idempotency_key: Mapped[str] = mapped_column(String(100, collation="utf8mb4_bin"))
    # Retain created at for history, ordering, and time-based queries.
    created_at: Mapped[datetime] = mapped_column(DateTime)
    # Retain updated at for history, ordering, and time-based queries.
    updated_at: Mapped[datetime] = mapped_column(DateTime)
