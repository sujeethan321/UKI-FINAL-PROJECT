"""Order-to-delivery bridge. The route owns the single commit/rollback.

MVP: one permanently retained delivery link per order, including cancellation.
No split fulfilment, implicit replacement, financial posting or order transition.
"""
from fastapi import HTTPException
from sqlalchemy import select

from app.models import (Order, User, CreditAccount, LedgerEntry, DeliveryRequest,
                        DeliveryAssignment, DeliveryStatusEvent)
from app.models.catalogue import utc_now
from app.services import order_service as orders
from app.services import shop_owner_delivery_service as deliveries


def scoped_order(db, user, order_id, business_id=None, write=False):
    preview = orders.scoped(db, user, order_id, business_id)
    if write:
        # Match order decisions: Customer user -> order -> account/ledger.
        orders.current(db, select(User).where(User.user_id == preview.customer_user_id))
    query = select(Order).where(Order.order_id == order_id)
    query = query.where(Order.business_id == business_id) if business_id is not None else query.where(
        Order.customer_user_id == user.user_id)
    row = orders.current(db, query, shared=not write)
    if row is None:
        raise HTTPException(404, 'Order not found')
    return row


def linked_delivery(db, order):
    if order.delivery_request_id is None:
        return None
    row = orders.current(db, select(DeliveryRequest).where(
        DeliveryRequest.delivery_request_id == order.delivery_request_id,
        DeliveryRequest.business_id == order.business_id))
    if row is None:
        raise HTTPException(409, 'Order delivery relationship is unavailable')
    return row


def eligible_order(db, order):
    if order.payment_method == 'cash':
        if order.status != 'processing' or order.payment_status != 'unpaid':
            raise HTTPException(409, 'Cash order must be processing before requesting delivery')
        return
    if (order.payment_method != 'credit' or order.status not in {'approved', 'processing'}
            or order.payment_status != 'posted' or order.credit_sale_id is None):
        raise HTTPException(409, 'Credit order must have completed Shop Owner approval before delivery')
    # Validate the already-posted approval. Do not require available credit a
    # second time, and do not re-post, repay or change the account balance.
    account = orders.current(db, select(CreditAccount).where(
        CreditAccount.credit_account_id == order.credit_account_id,
        CreditAccount.creditor_business_id == order.business_id))
    sale = orders.current(db, select(LedgerEntry).where(
        LedgerEntry.entry_id == order.credit_sale_id,
        LedgerEntry.order_id == order.order_id,
        LedgerEntry.credit_account_id == order.credit_account_id,
        LedgerEntry.entry_type == 'credit_sale', LedgerEntry.amount == order.total))
    reversed_sale = orders.current(db, select(LedgerEntry.entry_id).where(
        LedgerEntry.entry_type == 'reversal',
        LedgerEntry.reverses_entry_id == order.credit_sale_id))
    if account is None or sale is None or reversed_sale is not None:
        raise HTTPException(409, 'Order credit approval is no longer valid for delivery')


def owner_data(db, order, delivery):
    reason = 'This order already has a retained delivery request.' if delivery else None
    if delivery is None:
        try:
            eligible_order(db, order)
        except HTTPException as error:
            if error.status_code != 409:
                raise
            reason = error.detail
    return dict(order_id=order.order_id, delivery_requested=delivery is not None,
                can_request_delivery=reason is None, delivery_unavailable_reason=reason,
                delivery=deliveries.detail_data(db, delivery, current=True) if delivery else None)


def create(db, user, order_id, business_id, payload):
    order = scoped_order(db, user, order_id, business_id, write=True)
    existing = linked_delivery(db, order)
    if existing is not None:
        if (existing.pickup_area, existing.delivery_area) != (payload.pickup_area, payload.delivery_area):
            raise HTTPException(409, 'Order already has a delivery with different areas')
        # Replays retain the original delivery even after cancellation/completion.
        # A new request key cannot bypass this permanent one-order/one-link rule.
        return owner_data(db, order, existing)
    eligible_order(db, order)
    result = deliveries.create_request(db, user, business_id, payload, existing_order_id=order.order_id)
    order.delivery_request_id = result['delivery_request_id']
    order.updated_at = utc_now()
    db.flush()
    from app.services.notification_service import notify_event
    notify_event(db, 'delivery_requested', order.delivery_request_id)
    return owner_data(db, order, linked_delivery(db, order))


def owner_summary(db, user, order_id, business_id):
    order = scoped_order(db, user, order_id, business_id)
    return owner_data(db, order, linked_delivery(db, order))


def customer_summary(db, user, order_id):
    order = scoped_order(db, user, order_id)
    row = linked_delivery(db, order)
    data = None
    if row is not None:
        # Query only the assignment timestamp, never the Driver's identity or
        # private profile/contact fields. The request lock stabilizes progress.
        assigned_at = db.scalar(select(DeliveryAssignment.assigned_at).where(
            DeliveryAssignment.delivery_request_id == row.delivery_request_id).with_for_update(read=True))
        events = [dict(status='assigned', occurred_at=assigned_at)] if assigned_at else []
        events.extend(dict(status=event.status, occurred_at=event.occurred_at) for event in db.scalars(
            select(DeliveryStatusEvent).where(DeliveryStatusEvent.delivery_request_id == row.delivery_request_id)
            .order_by(DeliveryStatusEvent.occurred_at, DeliveryStatusEvent.event_id).with_for_update(read=True)))
        data = dict(reference=row.reference, status=row.status, created_at=row.created_at,
                    updated_at=row.updated_at, events=events)
    return dict(order_id=order.order_id, delivery_requested=row is not None, delivery=data)
