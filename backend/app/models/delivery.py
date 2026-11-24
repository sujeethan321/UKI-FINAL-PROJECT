# Purpose: Map delivery records to database tables so SQLAlchemy can persist and relate application data.
"""Shared delivery operations. Financial posting is independent of delivery."""
from datetime import datetime, timezone
from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


# Use timezone-aware UTC timestamps so application comparisons share one time reference.
def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Map driver profile to the driver_profiles table for ORM queries and persistence.
class DriverProfile(Base):
    __tablename__ = "driver_profiles"
    __table_args__ = (
        CheckConstraint("approval_status IN ('pending','approved','rejected','suspended')", name="ck_driver_approval_status"),
        CheckConstraint("approval_status = 'pending' OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)", name="ck_driver_review_required"),
        CheckConstraint("(vehicle_type IS NULL AND registration_reference IS NULL) OR (vehicle_type IS NOT NULL AND registration_reference IS NOT NULL)", name="ck_driver_vehicle_pair"),
    )
    # Link user id to users.user_id so the database enforces the record relationship.
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"), primary_key=True)
    legacy_document_exempt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text('0'))
    # Retain approval status so workflow checks can decide which operations are currently allowed.
    approval_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    vehicle_type: Mapped[str | None] = mapped_column(String(50))
    registration_reference: Mapped[str | None] = mapped_column(String(50))
    # Link reviewed by to users.user_id so the database enforces the record relationship.
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    # Retain created at for history, ordering, and time-based queries.
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)


# Map delivery request to the delivery_requests table for ORM queries and persistence.
class DeliveryRequest(Base):
    __tablename__ = "delivery_requests"
    __table_args__ = (
        UniqueConstraint('delivery_request_id','status',name='uq_delivery_completion_state'),
        UniqueConstraint("delivery_request_id", "business_id", name="uq_delivery_id_business"),
        CheckConstraint("status IN ('available','assigned','picked_up','in_transit','delivered','cancelled')", name="ck_delivery_status"),
        Index("ix_delivery_status_created", "status", "created_at", "delivery_request_id"),
        Index("ix_delivery_business", "business_id"),
    )
    # Use delivery request id as the unique row identity for ORM lookups and related records.
    delivery_request_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Keep reference unique so separate rows cannot claim the same value.
    reference: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    # Link business id to businesses.business_id so the database enforces the record relationship.
    business_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("businesses.business_id", ondelete="RESTRICT"), nullable=False)
    # Link created by to users.user_id so the database enforces the record relationship.
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    pickup_area: Mapped[str] = mapped_column(String(160), nullable=False)
    delivery_area: Mapped[str] = mapped_column(String(160), nullable=False)
    # Retain status so workflow checks can decide which operations are currently allowed.
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available", server_default="available")
    # Retain created at for history, ordering, and time-based queries.
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    # Retain updated at for history, ordering, and time-based queries.
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)


# Map delivery assignment to the delivery_assignments table for ORM queries and persistence.
class DeliveryAssignment(Base):
    __tablename__ = "delivery_assignments"
    __table_args__ = (
        UniqueConstraint('assignment_id','delivery_request_id','driver_user_id',name='uq_assignment_provenance'),
        UniqueConstraint("delivery_request_id", name="uq_delivery_assignment_request"),
        Index("ix_assignment_driver_date", "driver_user_id", "assigned_at", "assignment_id"),
    )
    # Use assignment id as the unique row identity for ORM lookups and related records.
    assignment_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Link delivery request id to delivery_requests.delivery_request_id so the database enforces the record relationship.
    delivery_request_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("delivery_requests.delivery_request_id", ondelete="RESTRICT"), nullable=False)
    # Link driver user id to driver_profiles.user_id so the database enforces the record relationship.
    driver_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("driver_profiles.user_id", ondelete="RESTRICT"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)


# Map delivery status event to the delivery_status_events table for ORM queries and persistence.
class DeliveryStatusEvent(Base):
    __tablename__ = "delivery_status_events"
    __table_args__ = (
        UniqueConstraint('event_id','delivery_request_id','actor_user_id','status',name='uq_completion_provenance'),
        UniqueConstraint("delivery_request_id", "status", name="uq_delivery_event_status"),
        CheckConstraint("status IN ('picked_up','in_transit','delivered','cancelled')", name="ck_delivery_event_status"),
    )
    # Use event id as the unique row identity for ORM lookups and related records.
    event_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Link delivery request id to delivery_requests.delivery_request_id so the database enforces the record relationship.
    delivery_request_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("delivery_requests.delivery_request_id", ondelete="RESTRICT"), nullable=False)
    # Link actor user id to users.user_id so the database enforces the record relationship.
    actor_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    # Retain status so workflow checks can decide which operations are currently allowed.
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
