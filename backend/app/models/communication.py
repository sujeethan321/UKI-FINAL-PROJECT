"""Append-only customer preference evidence and verifiable handoff requests."""
from datetime import datetime
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class CommunicationConsent(Base):
    __tablename__ = "communication_consents"
    __table_args__ = (
        UniqueConstraint("business_id", "idempotency_key", name="uq_consent_business_key"),
        CheckConstraint("channel = 'whatsapp'", name="ck_consent_channel"),
        CheckConstraint("consent_status IN ('granted', 'opted_out')", name="ck_consent_status"),
        CheckConstraint("consent_status = 'opted_out' OR phone IS NOT NULL", name="ck_consent_phone"),
        Index("ix_consent_customer_latest", "business_id", "customer_id", "consent_id"),
    )
    consent_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("businesses.business_id", ondelete="RESTRICT"))
    customer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("customer_profiles.customer_id", ondelete="RESTRICT"))
    recorded_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"))
    channel: Mapped[str] = mapped_column(String(20))
    consent_status: Mapped[str] = mapped_column(String(20))
    phone: Mapped[str | None] = mapped_column(String(15), nullable=True)
    evidence: Mapped[str] = mapped_column(String(500))
    idempotency_key: Mapped[str] = mapped_column(String(100, collation="utf8mb4_bin"))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class CommunicationAttempt(Base):
    __tablename__ = "communication_attempts"
    __table_args__ = (
        UniqueConstraint("business_id", "idempotency_key", name="uq_handoff_business_key"),
        CheckConstraint("channel = 'whatsapp'", name="ck_handoff_channel"),
        CheckConstraint("status = 'handoff_requested'", name="ck_handoff_status"),
        Index("ix_handoff_reminder_created", "business_id", "reminder_id", "created_at", "attempt_id"),
    )
    attempt_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("businesses.business_id", ondelete="RESTRICT"))
    customer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("customer_profiles.customer_id", ondelete="RESTRICT"))
    reminder_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("payment_reminders.reminder_id", ondelete="RESTRICT"))
    consent_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("communication_consents.consent_id", ondelete="RESTRICT"))
    requested_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"))
    channel: Mapped[str] = mapped_column(String(20))
    phone: Mapped[str] = mapped_column(String(15))
    status: Mapped[str] = mapped_column(String(30))
    idempotency_key: Mapped[str] = mapped_column(String(100, collation="utf8mb4_bin"))
    created_at: Mapped[datetime] = mapped_column(DateTime)
