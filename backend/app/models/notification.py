"""Minimal recipient-owned in-app event records. No external delivery state."""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("recipient_user_id", "event_key", name="uq_notification_recipient_event"),
        CheckConstraint("notification_type IN ('credit_sale_recorded', 'repayment_recorded', 'payment_reminder_recorded', 'business_approved', 'business_rejected')", name="ck_notification_type"),
        CheckConstraint("(notification_type IN ('credit_sale_recorded', 'repayment_recorded') AND related_entity_type = 'ledger_entry') OR (notification_type = 'payment_reminder_recorded' AND related_entity_type = 'payment_reminder') OR (notification_type IN ('business_approved', 'business_rejected') AND related_entity_type = 'business_approval_audit')", name="ck_notification_entity_type"),
        CheckConstraint("related_entity_id > 0", name="ck_notification_entity_id"),
        CheckConstraint("(is_read = 0 AND read_at IS NULL) OR (is_read = 1 AND read_at IS NOT NULL)", name="ck_notification_read_state"),
        Index("ix_notification_recipient_created", "recipient_user_id", "created_at", "notification_id"),
        Index("ix_notification_recipient_read_created", "recipient_user_id", "is_read", "created_at", "notification_id"),
        Index("ix_notification_recipient_type_created", "recipient_user_id", "notification_type", "created_at", "notification_id"),
    )
    notification_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    recipient_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"))
    business_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("businesses.business_id", ondelete="RESTRICT"), nullable=True, index=True)
    notification_type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(120))
    message: Mapped[str] = mapped_column(String(300))
    related_entity_type: Mapped[str] = mapped_column(String(30))
    related_entity_id: Mapped[int] = mapped_column(BigInteger)
    event_key: Mapped[str] = mapped_column(String(100, collation="utf8mb4_bin"))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
