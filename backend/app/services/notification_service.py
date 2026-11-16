"""Internal event notifications. Every write belongs to the caller's transaction.

Recipients and content come from verified database events, never API payloads.
No commits, ledger writes, user-supplied URLs, financial amounts or contact data.
"""
from datetime import datetime, timezone
from typing import get_args

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.dialects.mysql import insert

from app.models import (Business, BusinessApprovalAudit, BusinessMember, CreditAccount,
                        CustomerProfile, LedgerEntry, Notification, PaymentReminder, User, DeliveryRequest, DeliveryAssignment, DeliveryStatusEvent, Order, AdminAudit, DriverProfile)
from app.schemas.notification import NotificationResponse, NotificationType

CONTENT = {
    "driver_approved": ("Driver application approved", "Your Driver application was approved. Check your dashboard for current eligibility."),
    "driver_rejected": ("Driver application rejected", "Your Driver application was rejected. Review your application status on your dashboard."),
"order_submitted": ("Shopping order updated", "Your shopping order status is submitted."),
"order_approved": ("Shopping order updated", "Your shopping order status is approved."),
"order_rejected": ("Shopping order updated", "Your shopping order status is rejected."),
"order_processing": ("Shopping order updated", "Your shopping order status is processing."),
"order_completed": ("Shopping order updated", "Your shopping order status is completed."),
"order_cancelled": ("Shopping order updated", "Your shopping order status is cancelled."),
    "delivery_requested": ("Delivery requested", "Delivery has been requested for your order."),
    "delivery_cancelled": ("Delivery cancelled", "The delivery request has been cancelled. Order and payment records remain separate."),
    "delivery_assigned": ("Delivery assigned", "Your delivery request has been accepted by a driver."),
    "delivery_picked_up": ("Delivery picked up", "Your delivery has been picked up."),
    "delivery_in_transit": ("Delivery in transit", "Your delivery is on the way."),
    "delivery_delivered": ("Delivery marked as delivered", "Your delivery has been marked as delivered by the driver."),
    "credit_sale_recorded": ("Credit sale recorded", "A credit sale was recorded for your linked customer account."),
    "repayment_recorded": ("Repayment recorded", "A manual repayment was recorded for your linked customer account. This does not verify an electronic payment."),
    "payment_reminder_recorded": ("Payment reminder recorded", "Another owner recorded an internal payment reminder for this business. No external message was sent."),
    "business_approved": ("Business approved", "Your business registration was approved."),
    "business_rejected": ("Business rejected", "Your business registration was rejected. Review the business registration status."),
}


def utc_now():
    # Existing MySQL DATETIME columns store naive UTC with second precision.
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def notification_response(row):
    values = {key: getattr(row, key) for key in NotificationResponse.model_fields}
    for key in ("created_at", "read_at"):
        if values[key] is not None:
            values[key] = values[key].replace(tzinfo=timezone.utc)
    return NotificationResponse(**values)


def active_owners(db, business_id, actor_id):
    return list(db.scalars(select(User.user_id).join(
        BusinessMember, BusinessMember.user_id == User.user_id,
    ).where(BusinessMember.business_id == business_id,
            BusinessMember.business_role == "owner",
            BusinessMember.membership_status == "active",
            User.platform_role == "shop_owner", User.account_status == "active",
            User.user_id != actor_id).order_by(User.user_id).with_for_update(read=True)))


def current_recipient_row(db, model, row_id):
    # Recipient links/status must reflect current committed rows, rather than
    # the older MySQL REPEATABLE READ snapshot established by JWT checks.
    return db.scalar(select(model).where(
        model.__mapper__.primary_key[0] == row_id,
    ).with_for_update(read=True).execution_options(populate_existing=True))


def notify_event(db, notification_type: NotificationType, entity_id: int):
    """Resolve recipients for a real, flushed event and upsert once per recipient.

    Only new-event service branches call this. A replay never resolves new
    recipients. The unique index also arbitrates independent concurrent callers.
    Return notification IDs for internal callers; do not expose a create API.
    """
    if notification_type not in get_args(NotificationType):
        raise ValueError("Unsupported notification type")
    if type(entity_id) is not int or entity_id <= 0:
        raise ValueError("Invalid event identifier")
    if notification_type in {'driver_approved','driver_rejected'}:
        event=db.get(AdminAudit,entity_id)
        expected=notification_type.removeprefix('driver_')
        if event is None or event.target_type!='driver' or event.action!=notification_type or event.previous_state!='pending' or event.new_state!=expected:
            raise ValueError('Driver notification requires a persisted audit event')
        profile=current_recipient_row(db,DriverProfile,event.target_id)
        recipient=current_recipient_row(db,User,event.target_id)
        if profile is None or profile.approval_status!=expected:
            raise ValueError('Driver decision is not current')
        recipients=[recipient.user_id] if recipient and recipient.platform_role=='driver' and recipient.account_status=='active' else []
        business=None;related_type='admin_audit'
    elif notification_type.startswith("order_"):
        event = db.get(Order, entity_id)
        expected = notification_type.removeprefix("order_")
        if event is None or event.status != expected:
            raise ValueError("Order event requires a persisted transition")
        business = db.get(Business, event.business_id)
        recipient = current_recipient_row(db, User, event.customer_user_id)
        recipients = active_owners(db, event.business_id, event.customer_user_id) if expected == 'submitted' else ([recipient.user_id] if recipient and recipient.platform_role == 'customer' and recipient.account_status == 'active' else [])
        related_type = 'order'
    elif notification_type.startswith("delivery_"):
        # Writers lock the linked Order before the request, matching bridge
        # creation/replay/summary lock order and avoiding stale auth snapshots.
        linked = db.scalar(select(Order).where(Order.delivery_request_id == entity_id)
            .with_for_update(read=True).execution_options(populate_existing=True))
        event = db.get(DeliveryRequest, entity_id)
        expected = notification_type.removeprefix("delivery_")
        assigned = db.scalar(select(DeliveryAssignment).where(
            DeliveryAssignment.delivery_request_id == entity_id).with_for_update(read=True))
        persisted = assigned if expected == "assigned" else db.scalar(select(DeliveryStatusEvent).where(
            DeliveryStatusEvent.delivery_request_id == entity_id,
            DeliveryStatusEvent.status == expected).with_for_update(read=True))
        business = db.get(Business, event.business_id) if event else None
        if expected == 'requested':
            valid = event is not None and event.status == 'available' and assigned is None and linked is not None
        else:
            valid = event is not None and event.status == expected and persisted is not None
            if expected != 'cancelled':
                valid = valid and assigned is not None
        if not valid or business is None or (linked and linked.business_id != event.business_id):
            raise ValueError("Delivery notification requires a persisted transition")
        actor_id = event.created_by if expected == 'requested' else (assigned.driver_user_id if expected == 'assigned' else persisted.actor_user_id)
        recipients = [] if expected == 'requested' else active_owners(db, business.business_id, actor_id)
        related_type = "delivery_request"
        customer_id = None
        if linked is not None:
            customer = current_recipient_row(db, User, linked.customer_user_id)
            if customer and customer.platform_role == 'customer' and customer.account_status == 'active':
                customer_id = customer.user_id
                recipients.append(customer_id)
        if expected in {'assigned', 'cancelled'} and assigned is not None:
            driver = current_recipient_row(db, User, assigned.driver_user_id)
            if driver and driver.platform_role == 'driver' and driver.account_status == 'active':
                recipients.append(driver.user_id)
    elif notification_type in ("credit_sale_recorded", "repayment_recorded"):
        event = db.get(LedgerEntry, entity_id)
        expected = "credit_sale" if notification_type == "credit_sale_recorded" else "repayment"
        if event is None or event.entry_type != expected:
            raise ValueError("Notification event does not exist or has the wrong type")
        account = db.get(CreditAccount, event.credit_account_id)
        customer = current_recipient_row(db, CustomerProfile, account.customer_id) if account and account.customer_id else None
        business = db.get(Business, account.creditor_business_id) if account else None
        if customer is None or business is None or customer.business_id != business.business_id or business.approval_status != "approved":
            raise ValueError("Notification event has no valid business customer")
        # Never infer a user from names, emails, phone numbers or the actor.
        recipient = current_recipient_row(db, User, customer.user_id) if customer.user_id else None
        recipients = [recipient.user_id] if recipient and recipient.platform_role == "customer" and recipient.account_status == "active" and recipient.user_id != event.created_by else []
        related_type = "ledger_entry"
    elif notification_type == "payment_reminder_recorded":
        event = db.get(PaymentReminder, entity_id)
        if event is None or event.status != "recorded":
            raise ValueError("Notification reminder event does not exist")
        business = db.get(Business, event.business_id)
        account = db.get(CreditAccount, event.credit_account_id)
        customer = db.get(CustomerProfile, event.customer_id)
        if business is None or business.approval_status != "approved" or account is None or customer is None or customer.business_id != business.business_id or account.creditor_business_id != business.business_id or account.customer_id != customer.customer_id:
            raise ValueError("Notification reminder scope is invalid")
        # Preserve Step 9.2's internal-only policy: no customer-facing reminder
        # delivery, even when a linked customer user exists.
        recipients = active_owners(db, business.business_id, event.created_by)
        related_type = "payment_reminder"
    else:
        event = db.get(BusinessApprovalAudit, entity_id)
        expected = "approved" if notification_type == "business_approved" else "rejected"
        decision = "approve" if expected == "approved" else "reject"
        business = db.get(Business, event.business_id) if event else None
        if event is None or business is None or event.decision != decision or event.new_status != expected or event.previous_status != "pending" or business.approval_status != expected:
            raise ValueError("Notification approval event does not match a confirmed decision")
        recipients = active_owners(db, business.business_id, event.admin_user_id)
        related_type = "business_approval_audit"
    title, message = CONTENT[notification_type]
    event_key = notification_type + ":" + str(entity_id)
    ids = []
    for recipient_id in sorted(set(recipients)):
        customer_delivery = notification_type.startswith('delivery_') and recipient_id == customer_id
        statement = insert(Notification).values(
            recipient_user_id=recipient_id, business_id=business.business_id if business else None,
            notification_type=notification_type, title=title, message=message,
            related_entity_type='order' if customer_delivery else related_type,
            related_entity_id=linked.order_id if customer_delivery else entity_id,
            event_key=event_key, is_read=False, created_at=utc_now(), read_at=None,
        )
        # MySQL no-op upsert keeps the original content, timestamp and read
        # state, without rolling back the surrounding financial transaction.
        db.execute(statement.on_duplicate_key_update(notification_id=Notification.notification_id))
        ids.append(db.scalar(select(Notification.notification_id).where(
            Notification.recipient_user_id == recipient_id, Notification.event_key == event_key,
        ).with_for_update()))
    return ids


def list_notifications(db, user_id, filters):
    predicates = [Notification.recipient_user_id == user_id]
    if filters.unread_only or filters.is_read is not None:
        predicates.append(Notification.is_read.is_(False if filters.unread_only else filters.is_read))
    if filters.notification_type is not None:
        predicates.append(Notification.notification_type == filters.notification_type)
    total = db.scalar(select(func.count()).select_from(Notification).where(*predicates))
    rows = db.scalars(select(Notification).where(*predicates).order_by(
        Notification.created_at.desc(), Notification.notification_id.desc(),
    ).offset((filters.page - 1) * filters.page_size).limit(filters.page_size))
    return dict(page=filters.page, page_size=filters.page_size, total=total,
                notifications=[notification_response(row) for row in rows])


def unread_count(db, user_id):
    return db.scalar(select(func.count()).select_from(Notification).where(
        Notification.recipient_user_id == user_id, Notification.is_read.is_(False),
    ))


def mark_read(db, user_id, notification_id):
    db.execute(update(Notification).where(
        Notification.notification_id == notification_id,
        Notification.recipient_user_id == user_id, Notification.is_read.is_(False),
    ).values(is_read=True, read_at=utc_now()).execution_options(synchronize_session=False))
    row = db.scalar(select(Notification).where(
        Notification.notification_id == notification_id, Notification.recipient_user_id == user_id,
    ).with_for_update().execution_options(populate_existing=True))
    if row is None:
        # Same response for nonexistent and foreign-owned records.
        raise HTTPException(404, "Notification not found")
    return notification_response(row)


def mark_all_read(db, user_id):
    result = db.execute(update(Notification).where(
        Notification.recipient_user_id == user_id, Notification.is_read.is_(False),
    ).values(is_read=True, read_at=utc_now()).execution_options(synchronize_session=False))
    return result.rowcount
