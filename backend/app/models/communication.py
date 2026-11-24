# Purpose: Map communication records to database tables so SQLAlchemy can persist and relate application data.
"""Append-only customer preference evidence and verifiable handoff requests."""
from datetime import datetime
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


# Map communication consent to the communication_consents table for ORM queries and persistence.
class CommunicationConsent(Base):
    __tablename__ = "communication_consents"
    __table_args__ = (
        UniqueConstraint("business_id", "idempotency_key", name="uq_consent_business_key"),
        CheckConstraint("channel = 'whatsapp'", name="ck_consent_channel"),
        CheckConstraint("consent_status IN ('granted', 'opted_out')", name="ck_consent_status"),
        CheckConstraint("consent_status = 'opted_out' OR phone IS NOT NULL", name="ck_consent_phone"),
        Index("ix_consent_customer_latest", "business_id", "customer_id", "consent_id"),
    )
    # Use consent id as the unique row identity for ORM lookups and related records.
    consent_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Link business id to businesses.business_id so the database enforces the record relationship.
    business_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("businesses.business_id", ondelete="RESTRICT"))
    # Link customer id to customer_profiles.customer_id so the database enforces the record relationship.
    customer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("customer_profiles.customer_id", ondelete="RESTRICT"))
    # Link recorded by to users.user_id so the database enforces the record relationship.
    recorded_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"))
    channel: Mapped[str] = mapped_column(String(20))
    # Retain consent status so workflow checks can decide which operations are currently allowed.
    consent_status: Mapped[str] = mapped_column(String(20))
    phone: Mapped[str | None] = mapped_column(String(15), nullable=True)
    evidence: Mapped[str] = mapped_column(String(500))
    # Identify a logical request so retries can be checked against the original operation.
    idempotency_key: Mapped[str] = mapped_column(String(100, collation="utf8mb4_bin"))
    # Retain created at for history, ordering, and time-based queries.
    created_at: Mapped[datetime] = mapped_column(DateTime)


# Map communication attempt to the communication_attempts table for ORM queries and persistence.
class CommunicationAttempt(Base):
    __tablename__ = "communication_attempts"
    __table_args__ = (
        UniqueConstraint("business_id", "idempotency_key", name="uq_handoff_business_key"),
        CheckConstraint("channel = 'whatsapp'", name="ck_handoff_channel"),
        CheckConstraint("status = 'handoff_requested'", name="ck_handoff_status"),
        Index("ix_handoff_reminder_created", "business_id", "reminder_id", "created_at", "attempt_id"),
    )
    # Use attempt id as the unique row identity for ORM lookups and related records.
    attempt_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Link business id to businesses.business_id so the database enforces the record relationship.
    business_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("businesses.business_id", ondelete="RESTRICT"))
    # Link customer id to customer_profiles.customer_id so the database enforces the record relationship.
    customer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("customer_profiles.customer_id", ondelete="RESTRICT"))
    # Link reminder id to payment_reminders.reminder_id so the database enforces the record relationship.
    reminder_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("payment_reminders.reminder_id", ondelete="RESTRICT"))
    # Link consent id to communication_consents.consent_id so the database enforces the record relationship.
    consent_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("communication_consents.consent_id", ondelete="RESTRICT"))
    # Link requested by to users.user_id so the database enforces the record relationship.
    requested_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"))
    channel: Mapped[str] = mapped_column(String(20))
    phone: Mapped[str] = mapped_column(String(15))
    # Retain status so workflow checks can decide which operations are currently allowed.
    status: Mapped[str] = mapped_column(String(30))
    # Identify a logical request so retries can be checked against the original operation.
    idempotency_key: Mapped[str] = mapped_column(String(100, collation="utf8mb4_bin"))
    # Retain created at for history, ordering, and time-based queries.
    created_at: Mapped[datetime] = mapped_column(DateTime)
