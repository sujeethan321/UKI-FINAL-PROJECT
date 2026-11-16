"""JWT-identity scoped reads and transactional delivery operations.

Write callers commit on success and roll back on failure. Driver writes lock
user/profile before the delivery; business checks use shared locks.
"""
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import exists, func, select
from app.models import User, Business, BusinessMember, DriverProfile, DeliveryRequest, DeliveryAssignment, DeliveryStatusEvent, Order
from app.models.delivery import utc_now

ACTIVE = ("assigned", "picked_up", "in_transit")
TRANSITIONS = {
    "available": {"assigned", "cancelled"}, "assigned": {"picked_up", "cancelled"},
    "picked_up": {"in_transit"}, "in_transit": {"delivered"}, "delivered": set(), "cancelled": set(),
}


def actor(db, user_id, role, lock=False, exclusive=False):
    query = select(User).where(User.user_id == user_id)
    if lock:
        query = query.with_for_update(read=not exclusive).execution_options(populate_existing=True)
    user = db.scalar(query)
    if user is None or user.platform_role != role or user.account_status != "active":
        raise HTTPException(403, "This operation is not permitted for this account")
    return user


def profile_row(db, user_id, lock=False):
    query = select(DriverProfile).where(DriverProfile.user_id == user_id)
    if lock:
        query = query.with_for_update(read=True).execution_options(populate_existing=True)
    return db.scalar(query)


def eligibility(profile):
    if profile is None:
        return False, "profile_required"
    if profile.approval_status != "approved":
        return False, "approval_" + profile.approval_status
    if not profile.vehicle_type or not profile.registration_reference:
        return False, "vehicle_required"
    return True, "eligible"


def driver_profile(db, user):
    profile = profile_row(db, user.user_id)
    eligible, reason = eligibility(profile)
    return dict(driver_user_id=user.user_id, full_name=user.full_name, account_status=user.account_status,
                approval_status=profile.approval_status if profile else "not_submitted",
                eligible_for_jobs=eligible, eligibility_reason=reason,
                vehicle=dict(vehicle_type=profile.vehicle_type, registration_reference=profile.registration_reference)
                if profile and profile.vehicle_type and profile.registration_reference else None)


def unassigned_available():
    assigned = exists(select(1).where(DeliveryAssignment.delivery_request_id == DeliveryRequest.delivery_request_id))
    return select(DeliveryRequest.delivery_request_id).join(Business, Business.business_id == DeliveryRequest.business_id).where(
        DeliveryRequest.status == "available", Business.approval_status == "approved", ~assigned)


def summary(db, user):
    eligible, _ = eligibility(profile_row(db, user.user_id))
    available = db.scalar(select(func.count()).select_from(unassigned_available().subquery())) if eligible else 0
    query = select(DeliveryRequest.status, func.count()).join(
        DeliveryAssignment, DeliveryAssignment.delivery_request_id == DeliveryRequest.delivery_request_id,
    ).where(DeliveryAssignment.driver_user_id == user.user_id).group_by(DeliveryRequest.status)
    counts = dict(db.execute(query).all())
    return dict(driver_user_id=user.user_id, available_jobs_count=available,
                active_deliveries_count=sum(counts.get(status, 0) for status in ACTIVE),
                completed_deliveries_count=counts.get("delivered", 0))


def assigned_deliveries(db, user, page, page_size, status=None, history=False):
    query = select(DeliveryRequest, DeliveryAssignment.assigned_at, Business.business_name).join(
        DeliveryAssignment, DeliveryAssignment.delivery_request_id == DeliveryRequest.delivery_request_id,
    ).join(Business, Business.business_id == DeliveryRequest.business_id).where(
        DeliveryAssignment.driver_user_id == user.user_id,
        DeliveryRequest.status.in_(("delivered", "cancelled") if history else ACTIVE))
    if status:
        query = query.where(DeliveryRequest.status == status)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.order_by(DeliveryAssignment.assigned_at.desc(), DeliveryAssignment.assignment_id.desc()).offset(
        (page - 1) * page_size).limit(page_size))
    return dict(driver_user_id=user.user_id, total=total, page=page, page_size=page_size,
                deliveries=[dict(delivery_request_id=row.delivery_request_id, reference=row.reference,
                    business_name=business_name, pickup_area=row.pickup_area, delivery_area=row.delivery_area,
                    status=row.status, assigned_at=assigned_at,
                    finished_at=recorded_finish(db, row)) for row, assigned_at, business_name in rows])


def create_profile(db, user_id, vehicle_type=None, registration_reference=None):
    # Serialize first-time submissions on an existing row, before probing the
    # missing profile key. Shared locks permit competing insert/gap deadlocks.
    actor(db, user_id, "driver", lock=True, exclusive=True)
    if profile_row(db, user_id, lock=True) is not None:
        raise HTTPException(409, "Driver profile already exists")
    if (vehicle_type is None) != (registration_reference is None):
        raise HTTPException(422, "Provide both vehicle fields")
    if vehicle_type is not None:
        vehicle_type, registration_reference = vehicle_type.strip(), registration_reference.strip()
        if not vehicle_type or not registration_reference or len(vehicle_type) > 50 or len(registration_reference) > 50:
            raise HTTPException(422, "Invalid vehicle fields")
    profile = DriverProfile(user_id=user_id, vehicle_type=vehicle_type, registration_reference=registration_reference,
                            approval_status="pending")
    db.add(profile); db.flush()
    return profile


def review_profile(db, admin_id, driver_id, decision):
    actor(db, admin_id, "admin", lock=True)
    actor(db, driver_id, "driver", lock=True)
    if decision not in {"approved", "rejected", "suspended"}:
        raise HTTPException(422, "Invalid review decision")
    profile = db.scalar(select(DriverProfile).where(DriverProfile.user_id == driver_id).with_for_update().execution_options(populate_existing=True))
    if profile is None:
        raise HTTPException(404, "Driver profile not found")
    profile.approval_status = decision; profile.reviewed_by = admin_id; profile.reviewed_at = utc_now()
    db.flush()
    return profile


def requesting_business(db, user_id, business_id):
    actor(db, user_id, "shop_owner", lock=True)
    member = db.scalar(select(BusinessMember).where(BusinessMember.user_id == user_id,
        BusinessMember.business_id == business_id, BusinessMember.membership_status == "active").with_for_update(read=True))
    business = db.scalar(select(Business).where(Business.business_id == business_id).with_for_update(read=True).execution_options(populate_existing=True))
    if member is None or business is None:
        raise HTTPException(404, "Business not found")
    if business.approval_status != "approved":
        raise HTTPException(403, "Business is not eligible for delivery requests")
    return business


def create_delivery(db, owner_id, business_id, pickup_area, delivery_area):
    requesting_business(db, owner_id, business_id)
    if any(not isinstance(value, str) or not value.strip() or len(value.strip()) > 160 for value in [pickup_area, delivery_area]):
        raise HTTPException(422, "Provide valid pickup and delivery areas")
    row = DeliveryRequest(reference="DR-" + uuid4().hex, business_id=business_id, created_by=owner_id,
                          pickup_area=pickup_area.strip(), delivery_area=delivery_area.strip(), status="available")
    db.add(row); db.flush()
    return row


def eligible_driver(db, driver_id):
    actor(db, driver_id, "driver", lock=True)
    profile = profile_row(db, driver_id, lock=True)
    if not eligibility(profile)[0]:
        raise HTTPException(403, "Driver is not eligible to accept or update deliveries")


def lock_linked_order(db, request_id):
    return db.scalar(select(Order).where(Order.delivery_request_id == request_id)
        .with_for_update(read=True).execution_options(populate_existing=True))


def locked_delivery(db, request_id):
    lock_linked_order(db, request_id)
    row = db.scalar(select(DeliveryRequest).where(DeliveryRequest.delivery_request_id == request_id).with_for_update().execution_options(populate_existing=True))
    if row is None:
        raise HTTPException(404, "Delivery not found")
    return row


def assignment(db, request_id):
    # A locking/current read is essential after waiting on the request row:
    # ordinary SELECT could still use an earlier MySQL REPEATABLE READ snapshot.
    return db.scalar(select(DeliveryAssignment).where(DeliveryAssignment.delivery_request_id == request_id).with_for_update().execution_options(populate_existing=True))


def accept_delivery(db, driver_id, request_id):
    eligible_driver(db, driver_id)
    row = locked_delivery(db, request_id)
    prior = assignment(db, request_id)
    if prior is not None and prior.driver_user_id == driver_id and row.status in ACTIVE:
        return prior
    business = db.scalar(select(Business).where(Business.business_id == row.business_id).with_for_update(read=True).execution_options(populate_existing=True))
    if row.status != "available" or prior is not None or business is None or business.approval_status != "approved":
        raise HTTPException(409, "Delivery is no longer available")
    result = DeliveryAssignment(delivery_request_id=row.delivery_request_id, driver_user_id=driver_id)
    db.add(result); row.status = "assigned"; row.updated_at = utc_now(); db.flush()
    from app.services.notification_service import notify_event
    notify_event(db, "delivery_assigned", request_id)
    return result


def transition_delivery(db, driver_id, request_id, next_status, expected_status=None):
    eligible_driver(db, driver_id)
    row = locked_delivery(db, request_id); assigned = assignment(db, request_id)
    if assigned is None or assigned.driver_user_id != driver_id:
        raise HTTPException(404, "Delivery not found")
    if expected_status is not None and row.status != expected_status:
        raise HTTPException(409, "Delivery changed. Refresh before updating its status.")
    if next_status not in TRANSITIONS.get(row.status, set()) or next_status == "assigned":
        raise HTTPException(409, "Delivery status transition is not permitted")
    row.status = next_status; row.updated_at = utc_now()
    db.add(DeliveryStatusEvent(delivery_request_id=request_id, actor_user_id=driver_id,
                              status=next_status, occurred_at=row.updated_at))
    db.flush()
    from app.services.notification_service import notify_event
    if next_status in {"picked_up", "in_transit", "delivered", "cancelled"}:
        notify_event(db, "delivery_" + next_status, request_id)
    return row


def cancel_business_delivery(db, owner_id, business_id, request_id):
    # Validate membership first, then lock the exact business-owned request.
    requesting_business(db, owner_id, business_id)
    lock_linked_order(db, request_id)
    row = db.scalar(select(DeliveryRequest).where(DeliveryRequest.delivery_request_id == request_id,
        DeliveryRequest.business_id == business_id).with_for_update().execution_options(populate_existing=True))
    if row is None:
        raise HTTPException(404, "Delivery not found")
    if row.status not in {"available", "assigned"}:
        raise HTTPException(409, "Delivery cannot be cancelled at this stage")
    row.status = "cancelled"; row.updated_at = utc_now()
    db.add(DeliveryStatusEvent(delivery_request_id=request_id, actor_user_id=owner_id,
                              status="cancelled", occurred_at=row.updated_at))
    db.flush()
    from app.services.notification_service import notify_event
    notify_event(db, "delivery_cancelled", request_id)
    return row


def job_access(db, user):
    if not eligibility(profile_row(db, user.user_id))[0]:
        raise HTTPException(403, "Driver is not eligible to view or accept available jobs")


def available_query():
    available = unassigned_available().subquery()
    return select(DeliveryRequest, Business.business_name).join(
        Business, Business.business_id == DeliveryRequest.business_id,
    ).join(available, available.c.delivery_request_id == DeliveryRequest.delivery_request_id)


def job_data(row, business_name):
    return dict(delivery_request_id=row.delivery_request_id, reference=row.reference, business_name=business_name,
                pickup_area=row.pickup_area, delivery_area=row.delivery_area, status=row.status, created_at=row.created_at)


def available_jobs(db, user, page, page_size):
    job_access(db, user)
    query = available_query()
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.order_by(DeliveryRequest.created_at.desc(), DeliveryRequest.delivery_request_id.desc()).offset(
        (page - 1) * page_size).limit(page_size))
    return dict(driver_user_id=user.user_id, total=total, page=page, page_size=page_size,
                jobs=[job_data(row, business_name) for row, business_name in rows])


def available_job_detail(db, user, request_id):
    job_access(db, user)
    result = db.execute(available_query().where(DeliveryRequest.delivery_request_id == request_id)).one_or_none()
    if result is None:
        raise HTTPException(404, "Available delivery not found")
    row, business_name = result
    return dict(driver_user_id=user.user_id, job=job_data(row, business_name))


def assigned_delivery_detail(db, user, request_id, current=False):
    query = select(DeliveryRequest, DeliveryAssignment, Business.business_name).join(
        DeliveryAssignment, DeliveryAssignment.delivery_request_id == DeliveryRequest.delivery_request_id,
    ).join(Business, Business.business_id == DeliveryRequest.business_id).where(
        DeliveryRequest.delivery_request_id == request_id, DeliveryAssignment.driver_user_id == user.user_id,
        DeliveryRequest.status.in_((*ACTIVE, "delivered", "cancelled")),
    )
    if current:
        query = query.with_for_update(read=True).execution_options(populate_existing=True)
    result = db.execute(query).one_or_none()
    if result is None:
        raise HTTPException(404, "Assigned delivery not found")
    row, assigned, business_name = result
    return dict(driver_user_id=user.user_id, assignment_id=assigned.assignment_id,
                delivery=dict(delivery_request_id=row.delivery_request_id, reference=row.reference,
                    business_name=business_name, pickup_area=row.pickup_area, delivery_area=row.delivery_area,
                    status=row.status, assigned_at=assigned.assigned_at))


def recorded_finish(db, row):
    if row.status not in {"delivered", "cancelled"}:
        return None
    return db.scalar(select(DeliveryStatusEvent.occurred_at).where(
        DeliveryStatusEvent.delivery_request_id == row.delivery_request_id,
        DeliveryStatusEvent.status == row.status))


def delivery_progress(db, user, request_id, current=False):
    result = assigned_delivery_detail(db, user, request_id, current=current)
    query = select(DeliveryStatusEvent).where(DeliveryStatusEvent.delivery_request_id == request_id).order_by(
        DeliveryStatusEvent.occurred_at, DeliveryStatusEvent.event_id)
    if current:
        query = query.with_for_update(read=True).execution_options(populate_existing=True)
    events = db.scalars(query).all()
    result["events"] = [dict(status="assigned", occurred_at=result["delivery"]["assigned_at"])] + [
        dict(status=event.status, occurred_at=event.occurred_at) for event in events]
    result["allowed_next_status"] = {"assigned": "picked_up", "picked_up": "in_transit", "in_transit": "delivered"}.get(
        result["delivery"]["status"]) if eligibility(profile_row(db, user.user_id, lock=current))[0] else None
    return result
