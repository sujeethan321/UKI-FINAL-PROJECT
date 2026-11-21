"""Shared delivery operations. Financial posting is independent of delivery."""
from datetime import datetime, timezone
from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DriverProfile(Base):
    __tablename__ = "driver_profiles"
    __table_args__ = (
        CheckConstraint("approval_status IN ('pending','approved','rejected','suspended')", name="ck_driver_approval_status"),
        CheckConstraint("approval_status = 'pending' OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)", name="ck_driver_review_required"),
        CheckConstraint("(vehicle_type IS NULL AND registration_reference IS NULL) OR (vehicle_type IS NOT NULL AND registration_reference IS NOT NULL)", name="ck_driver_vehicle_pair"),
    )
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"), primary_key=True)
    legacy_document_exempt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text('0'))
    approval_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    vehicle_type: Mapped[str | None] = mapped_column(String(50))
    registration_reference: Mapped[str | None] = mapped_column(String(50))
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)


class DeliveryRequest(Base):
    __tablename__ = "delivery_requests"
    __table_args__ = (
        UniqueConstraint("delivery_request_id", "business_id", name="uq_delivery_id_business"),
        CheckConstraint("status IN ('available','assigned','picked_up','in_transit','delivered','cancelled')", name="ck_delivery_status"),
        Index("ix_delivery_status_created", "status", "created_at", "delivery_request_id"),
        Index("ix_delivery_business", "business_id"),
    )
    delivery_request_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    reference: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    business_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("businesses.business_id", ondelete="RESTRICT"), nullable=False)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    pickup_area: Mapped[str] = mapped_column(String(160), nullable=False)
    delivery_area: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available", server_default="available")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)


class DeliveryAssignment(Base):
    __tablename__ = "delivery_assignments"
    __table_args__ = (
        UniqueConstraint("delivery_request_id", name="uq_delivery_assignment_request"),
        Index("ix_assignment_driver_date", "driver_user_id", "assigned_at", "assignment_id"),
    )
    assignment_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    delivery_request_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("delivery_requests.delivery_request_id", ondelete="RESTRICT"), nullable=False)
    driver_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("driver_profiles.user_id", ondelete="RESTRICT"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)


class DeliveryStatusEvent(Base):
    __tablename__ = "delivery_status_events"
    __table_args__ = (
        UniqueConstraint("delivery_request_id", "status", name="uq_delivery_event_status"),
        CheckConstraint("status IN ('picked_up','in_transit','delivered','cancelled')", name="ck_delivery_event_status"),
    )
    event_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    delivery_request_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("delivery_requests.delivery_request_id", ondelete="RESTRICT"), nullable=False)
    actor_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
