"""Own-business delivery management on the existing Day 12 records.

Write callers commit/rollback. No payment, order, notification or ledger writes.
"""
from fastapi import HTTPException
from sqlalchemy import func, select

from app.models import BusinessMember, DeliveryRequest, DeliveryAssignment, DeliveryStatusEvent, User
from app.services import driver_service as delivery


def authorized_business(db, user_id, business_id):
    # Preserve the current Shop Owner policy: active owner membership only.
    business = delivery.requesting_business(db, user_id, business_id)
    member = db.scalar(select(BusinessMember).where(
        BusinessMember.business_id == business_id, BusinessMember.user_id == user_id,
    ).with_for_update(read=True).execution_options(populate_existing=True))
    if member is None or member.business_role != 'owner' or member.membership_status != 'active':
        raise HTTPException(404, 'Business not found')
    return business


def summary_data(row):
    return {key: getattr(row, key) for key in (
        'delivery_request_id', 'reference', 'business_id', 'pickup_area', 'delivery_area',
        'status', 'created_at', 'updated_at')}


def scoped_request(db, business_id, request_id, current=False):
    query = select(DeliveryRequest).where(
        DeliveryRequest.business_id == business_id, DeliveryRequest.delivery_request_id == request_id)
    if current:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, 'Delivery request not found')
    return row


def detail_data(db, row, current=False):
    query = select(DeliveryAssignment, User.full_name).join(
        User, User.user_id == DeliveryAssignment.driver_user_id).where(
        DeliveryAssignment.delivery_request_id == row.delivery_request_id)
    events_query = select(DeliveryStatusEvent).where(
        DeliveryStatusEvent.delivery_request_id == row.delivery_request_id).order_by(
        DeliveryStatusEvent.occurred_at, DeliveryStatusEvent.event_id)
    if current:
        query = query.with_for_update(read=True).execution_options(populate_existing=True)
        events_query = events_query.with_for_update(read=True).execution_options(populate_existing=True)
    assigned = db.execute(query).one_or_none()
    events = [dict(status='assigned', occurred_at=assigned[0].assigned_at)] if assigned else []
    events.extend(dict(status=event.status, occurred_at=event.occurred_at) for event in db.scalars(events_query))
    return dict(**summary_data(row), assigned_driver=(
        dict(full_name=assigned[1], assigned_at=assigned[0].assigned_at) if assigned else None),
        events=events, can_cancel=row.status == 'available' and assigned is None)


def create_request(db, user, business_id, payload):
    authorized_business(db, user.user_id, business_id)
    row = delivery.create_delivery(db, user.user_id, business_id, payload.pickup_area, payload.delivery_area)
    # Current response reads avoid mixing snapshots with concurrent assignment.
    row = scoped_request(db, business_id, row.delivery_request_id, current=True)
    return detail_data(db, row, current=True)


def list_requests(db, user, business_id, page, page_size, status=None):
    authorized_business(db, user.user_id, business_id)
    query = select(DeliveryRequest).where(DeliveryRequest.business_id == business_id)
    if status:
        query = query.where(DeliveryRequest.status == status)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(DeliveryRequest.created_at.desc(), DeliveryRequest.delivery_request_id.desc()).offset(
        (page - 1) * page_size).limit(page_size))
    return dict(business_id=business_id, total=total, page=page, page_size=page_size,
                deliveries=[summary_data(row) for row in rows])


def summary(db, user, business_id):
    authorized_business(db, user.user_id, business_id)
    counts = dict(db.execute(select(DeliveryRequest.status, func.count()).where(
        DeliveryRequest.business_id == business_id).group_by(DeliveryRequest.status)).all())
    return dict(business_id=business_id, total_requests_count=sum(counts.values()),
                available_requests_count=counts.get('available', 0),
                in_progress_count=sum(counts.get(status, 0) for status in delivery.ACTIVE),
                completed_count=counts.get('delivered', 0))


def request_detail(db, user, business_id, request_id):
    authorized_business(db, user.user_id, business_id)
    return detail_data(db, scoped_request(db, business_id, request_id))


def cancel_request(db, user, business_id, request_id):
    authorized_business(db, user.user_id, business_id)
    row = scoped_request(db, business_id, request_id, current=True)
    assigned = delivery.assignment(db, request_id)
    if row.status == 'cancelled' and assigned is None:
        # Safe retry: retain the original event and timestamp.
        return detail_data(db, row, current=True)
    if row.status != 'available' or assigned is not None:
        raise HTTPException(409, 'Only an unassigned available delivery request can be cancelled')
    delivery.cancel_business_delivery(db, user.user_id, business_id, request_id)
    # MySQL DATETIME stores seconds here; respond with the persisted precision
    # so the original confirmation and an idempotent retry agree exactly.
    row = scoped_request(db, business_id, request_id, current=True)
    return detail_data(db, row, current=True)
