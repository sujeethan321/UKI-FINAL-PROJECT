# Purpose: Implement customer join operations behind the HTTP layer so related business rules are shared by their callers.
"""Customer-initiated shop links. The ledger is deliberately untouched."""
from datetime import datetime, timezone
from secrets import token_urlsafe

from fastapi import HTTPException
from sqlalchemy import func, select

from app.models import Business, BusinessJoinLink, BusinessMember, CustomerJoinRequest, CustomerProfile, User


# Return a consistent unavailable-resource error for an inaccessible or invalid link.
def unavailable():
    return HTTPException(404, "Join resource unavailable")


# Use timezone-aware UTC timestamps so application comparisons share one time reference.
def now_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


# Resolve approved business using a row lock so the caller can coordinate concurrent changes.
def approved_business(db, business_id, lock=False):
    query = select(Business).where(Business.business_id == business_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    business = db.scalar(query)
    if business is None or business.approval_status != "approved":
        raise unavailable()
    return business


# Query owner business data for the customer join workflow.
def owner_business(db, owner, business_id, lock=False):
    business = approved_business(db, business_id, lock)
    member = db.scalar(select(BusinessMember.membership_id).where(
        BusinessMember.business_id == business_id,
        BusinessMember.user_id == owner.user_id,
        BusinessMember.business_role == "owner",
        BusinessMember.membership_status == "active",
    ))
    if owner.platform_role != "shop_owner" or owner.account_status != "active" or member is None:
        raise unavailable()
    return business


def issue_link(db, owner, business_id):
    """Business lock serializes first use, making legacy issuance idempotent."""
    owner_business(db, owner, business_id, lock=True)
    link = db.scalar(select(BusinessJoinLink).where(
        BusinessJoinLink.business_id == business_id,
    ).with_for_update().execution_options(populate_existing=True))
    if link is None:
        link = BusinessJoinLink(business_id=business_id, public_code=token_urlsafe(24))
        db.add(link)
        db.flush()
    return {"public_code": link.public_code}


# Expose only the approved business name and type for a valid public join link.
def preview(db, code):
    row = db.execute(select(Business.business_name, Business.business_type).join(
        BusinessJoinLink, BusinessJoinLink.business_id == Business.business_id,
    ).where(BusinessJoinLink.public_code == code, Business.approval_status == "approved")).first()
    if row is None:
        raise unavailable()
    return {"business_name": row.business_name, "business_type": row.business_type}


def customer_request_status(db, customer, code):
    """Read only the caller's relationship with an approved QR-linked shop."""
    business_id = db.scalar(select(BusinessJoinLink.business_id).join(
        Business, Business.business_id == BusinessJoinLink.business_id,
    ).where(BusinessJoinLink.public_code == code, Business.approval_status == "approved"))
    if business_id is None:
        raise unavailable()
    row = db.scalar(select(CustomerJoinRequest).where(
        CustomerJoinRequest.business_id == business_id,
        CustomerJoinRequest.customer_user_id == customer.user_id,
    ))
    linked = db.scalar(select(CustomerProfile.customer_id).where(
        CustomerProfile.business_id == business_id,
        CustomerProfile.user_id == customer.user_id,
    ).limit(1)) is not None
    if row is not None:
        if row.status == "approved" and not linked:
            raise HTTPException(409, "Join state is inconsistent")
        return {"request_id": row.request_id, "status": row.status}
    return {"request_id": None, "status": "already_linked" if linked else "none"}


# Resolve profile exists using a row lock so the caller can coordinate concurrent changes.
def profile_exists(db, business_id, user_id):
    return db.scalar(select(CustomerProfile.customer_id).where(
        CustomerProfile.business_id == business_id,
        CustomerProfile.user_id == user_id,
    ).limit(1).with_for_update(read=True)) is not None


# Project the join request into the fields returned by the public API contract.
def response(row, business_name, customer_name=None, customer_email=None):
    return dict(request_id=row.request_id, status=row.status, business_name=business_name,
                created_at=row.created_at, customer_name=customer_name,
                customer_email=customer_email)


# Resolve submit using a row lock so the caller can coordinate concurrent changes.
def submit(db, customer, code):
    link = db.scalar(select(BusinessJoinLink).where(BusinessJoinLink.public_code == code))
    if link is None:
        raise unavailable()
    business = approved_business(db, link.business_id, lock=True)
    current_customer = db.scalar(select(User).where(User.user_id == customer.user_id)
                                 .with_for_update(read=True).execution_options(populate_existing=True))
    if current_customer is None or current_customer.platform_role != "customer" or current_customer.account_status != "active":
        raise unavailable()
    if profile_exists(db, business.business_id, customer.user_id):
        raise HTTPException(409, "Already linked to this shop")
    row = db.scalar(select(CustomerJoinRequest).where(
        CustomerJoinRequest.business_id == business.business_id,
        CustomerJoinRequest.customer_user_id == customer.user_id,
    ).with_for_update().execution_options(populate_existing=True))
    if row is None:
        row = CustomerJoinRequest(business_id=business.business_id,
                                  customer_user_id=customer.user_id, status="pending")
        db.add(row)
    elif row.status == "approved":
        raise HTTPException(409, "Already linked to this shop")
    elif row.status in ("rejected", "cancelled"):
        # An explicit new submit is required; retain one row per pair.
        row.status = "pending"
        row.created_at = now_utc()
        row.decided_at = None
        row.decided_by = None
    db.flush()
    return response(row, business.business_name)


# Query customer requests data for the customer join workflow.
def customer_requests(db, customer, page, page_size):
    query = select(CustomerJoinRequest, Business.business_name).join(
        Business, Business.business_id == CustomerJoinRequest.business_id,
    ).where(CustomerJoinRequest.customer_user_id == customer.user_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.execute(query.order_by(CustomerJoinRequest.created_at.desc(),
                                     CustomerJoinRequest.request_id.desc())
                      .offset((page-1)*page_size).limit(page_size)).all()
    return dict(total=total, page=page, page_size=page_size,
                requests=[response(row, name) for row, name in rows])


# Query owner requests data for the customer join workflow.
def owner_requests(db, owner, business_id, page, page_size, status):
    owner_business(db, owner, business_id)
    query = select(CustomerJoinRequest, Business.business_name, User.full_name, User.email).join(
        Business, Business.business_id == CustomerJoinRequest.business_id,
    ).join(User, User.user_id == CustomerJoinRequest.customer_user_id).where(
        CustomerJoinRequest.business_id == business_id)
    if status is not None:
        query = query.where(CustomerJoinRequest.status == status)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.execute(query.order_by(CustomerJoinRequest.created_at.desc(),
                                     CustomerJoinRequest.request_id.desc())
                      .offset((page-1)*page_size).limit(page_size)).all()
    return dict(total=total, page=page, page_size=page_size,
                requests=[response(row, business_name, customer_name, customer_email)
                          for row, business_name, customer_name, customer_email in rows])


# Resolve decide using a row lock so the caller can coordinate concurrent changes.
def decide(db, owner, business_id, request_id, decision):
    business = owner_business(db, owner, business_id, lock=True)
    row = db.scalar(select(CustomerJoinRequest).where(
        CustomerJoinRequest.request_id == request_id,
        CustomerJoinRequest.business_id == business_id,
    ).with_for_update().execution_options(populate_existing=True))
    if row is None:
        raise unavailable()
    customer = db.scalar(select(User).where(User.user_id == row.customer_user_id)
                         .with_for_update().execution_options(populate_existing=True))
    if customer is None or customer.platform_role != "customer" or customer.account_status != "active":
        raise unavailable()
    expected = "approved" if decision == "approve" else "rejected"
    if row.status == expected:
        if expected == "approved" and not profile_exists(db, business_id, customer.user_id):
            raise HTTPException(409, "Join state is inconsistent")
        return response(row, business.business_name, customer.full_name, customer.email)
    if row.status != "pending":
        raise HTTPException(409, "Request is no longer pending")
    if profile_exists(db, business_id, customer.user_id):
        raise HTTPException(409, "Customer is already linked")
    if decision == "approve":
        from app.services.subscription_service import enforce_customer_capacity
        enforce_customer_capacity(db,business_id)
        db.add(CustomerProfile(business_id=business_id, user_id=customer.user_id,
                               customer_name=customer.full_name, phone=None, address=None))
    row.status = expected
    row.decided_at = now_utc()
    row.decided_by = owner.user_id
    db.flush()
    return response(row, business.business_name, customer.full_name, customer.email)


# Resolve cancel using a row lock so the caller can coordinate concurrent changes.
def cancel(db, customer, request_id):
    candidate = db.scalar(select(CustomerJoinRequest).where(
        CustomerJoinRequest.request_id == request_id,
        CustomerJoinRequest.customer_user_id == customer.user_id,
    ))
    if candidate is None:
        raise unavailable()
    business = approved_business(db, candidate.business_id, lock=True)
    row = db.scalar(select(CustomerJoinRequest).where(
        CustomerJoinRequest.request_id == request_id,
        CustomerJoinRequest.customer_user_id == customer.user_id,
    ).with_for_update().execution_options(populate_existing=True))
    if row is None:
        raise unavailable()
    if row.status == "cancelled":
        return response(row, business.business_name)
    if row.status != "pending":
        raise HTTPException(409, "Request is no longer pending")
    row.status = "cancelled"
    row.decided_at = now_utc()
    db.flush()
    return response(row, business.business_name)
