# Purpose: Map subscription records to database tables so SQLAlchemy can persist and relate application data.
"""Business-owned subscriptions. All timestamps are naive UTC in MySQL."""
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# Map subscription trial grant to the subscription_trial_grants table for ORM queries and persistence.
class SubscriptionTrialGrant(Base):
    __tablename__ = "subscription_trial_grants"
    __table_args__ = (
        CheckConstraint("grant_status IN ('GRANTED', 'EXCLUDED')", name="ck_trial_grant_status"),
        CheckConstraint("(grant_status = 'GRANTED' AND trial_started_at IS NOT NULL AND trial_ends_at IS NOT NULL AND trial_ends_at > trial_started_at) OR (grant_status = 'EXCLUDED' AND trial_started_at IS NULL AND trial_ends_at IS NULL)", name="ck_trial_grant_period"),
        {'mysql_engine':'InnoDB','mysql_charset':'utf8mb4','mysql_collate':'utf8mb4_unicode_ci'},
    )
    # Link business id to businesses.business_id so the database enforces the record relationship.
    business_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("businesses.business_id", ondelete="RESTRICT"), primary_key=True, autoincrement=False)
    # Retain grant status so workflow checks can decide which operations are currently allowed.
    grant_status: Mapped[str] = mapped_column(String(12), nullable=False)
    trial_started_at: Mapped[datetime | None] = mapped_column(DateTime)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime)
    # Retain created at for history, ordering, and time-based queries.
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


# Map business subscription to the business_subscriptions table for ORM queries and persistence.
class BusinessSubscription(Base):
    __tablename__ = "business_subscriptions"
    __table_args__ = (
        CheckConstraint("plan IN ('FREE', 'PRO', 'BUSINESS')", name="ck_subscription_plan"),
        CheckConstraint("status IN ('FREE', 'TRIALING', 'ACTIVE', 'PAST_DUE', 'CANCELLED')", name="ck_subscription_status"),
        CheckConstraint("billing_interval IS NULL OR billing_interval IN ('month', 'year')", name="ck_subscription_interval"),
        CheckConstraint("provider_mode = 'sandbox'", name="ck_subscription_sandbox"),
        CheckConstraint("paid_through IS NULL OR (started_at IS NOT NULL AND paid_through > started_at)", name="ck_subscription_paid_period"),
        {'mysql_engine':'InnoDB','mysql_charset':'utf8mb4','mysql_collate':'utf8mb4_unicode_ci'},
    )
    # Link business id to businesses.business_id so the database enforces the record relationship.
    business_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("businesses.business_id", ondelete="RESTRICT"), primary_key=True, autoincrement=False)
    plan: Mapped[str] = mapped_column(String(12), nullable=False)
    # Retain status so workflow checks can decide which operations are currently allowed.
    status: Mapped[str] = mapped_column(String(12), nullable=False)
    billing_interval: Mapped[str | None] = mapped_column(String(5))
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    paid_through: Mapped[datetime | None] = mapped_column(DateTime)
    # Keep stripe customer id unique so separate rows cannot claim the same value.
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    # Keep stripe subscription id unique so separate rows cannot claim the same value.
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    provider_mode: Mapped[str] = mapped_column(String(10), nullable=False, default="sandbox")
    # Retain created at for history, ordering, and time-based queries.
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Retain updated at for history, ordering, and time-based queries.
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class SubscriptionPaymentEvent(Base):
    """Minimal verified provider receipt; never a card or raw webhook archive."""
    __tablename__ = "subscription_payment_events"
    __table_args__ = (
        CheckConstraint("provider_mode = 'sandbox'", name="ck_payment_event_sandbox"),
        CheckConstraint("amount_minor >= 0", name="ck_payment_event_amount"),
        CheckConstraint("currency = 'lkr'", name="ck_payment_event_currency"),
        {'mysql_engine':'InnoDB','mysql_charset':'utf8mb4','mysql_collate':'utf8mb4_unicode_ci'},
    )
    # Use event id as the unique row identity for ORM lookups and related records.
    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    # Link business id to businesses.business_id so the database enforces the record relationship.
    business_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("businesses.business_id", ondelete="RESTRICT"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_mode: Mapped[str] = mapped_column(String(10), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


# Map subscription checkout attempt to the subscription_checkout_attempts table for ORM queries and persistence.
class SubscriptionCheckoutAttempt(Base):
    __tablename__ = "subscription_checkout_attempts"
    __table_args__ = (
        CheckConstraint("plan IN ('PRO', 'BUSINESS')", name="ck_checkout_plan"),
        CheckConstraint("billing_interval IN ('month', 'year')", name="ck_checkout_interval"),
        CheckConstraint("status IN ('CREATING', 'UNCERTAIN', 'OPEN', 'VERIFYING', 'COMPLETE', 'EXPIRED')", name="ck_checkout_status"),
        CheckConstraint("active_business_id IS NULL OR active_business_id = business_id", name="ck_checkout_business"),
        CheckConstraint("(status IN ('CREATING', 'UNCERTAIN', 'OPEN', 'VERIFYING') AND active_business_id IS NOT NULL) OR (status IN ('COMPLETE', 'EXPIRED') AND active_business_id IS NULL)", name="ck_checkout_active"),
        CheckConstraint("expires_at > created_at", name="ck_checkout_period"),
        {'mysql_engine':'InnoDB','mysql_charset':'utf8mb4','mysql_collate':'utf8mb4_unicode_ci'},
    )
    # Use attempt id as the unique row identity for ORM lookups and related records.
    attempt_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # Link business id to businesses.business_id so the database enforces the record relationship.
    business_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("businesses.business_id", ondelete="RESTRICT"), nullable=False, index=True)
    # Nullable unique slot provides MySQL-enforced one-active-attempt per business.
    active_business_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    # Keep request key unique so separate rows cannot claim the same value.
    request_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    plan: Mapped[str] = mapped_column(String(12), nullable=False)
    billing_interval: Mapped[str] = mapped_column(String(5), nullable=False)
    price_id: Mapped[str] = mapped_column(String(255), nullable=False)
    return_origin: Mapped[str] = mapped_column(String(255), nullable=False)
    # Keep stripe session id unique so separate rows cannot claim the same value.
    stripe_session_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255))
    # Retain status so workflow checks can decide which operations are currently allowed.
    status: Mapped[str] = mapped_column(String(12), nullable=False)
    # Retain created at for history, ordering, and time-based queries.
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_code: Mapped[str | None] = mapped_column(String(32))
