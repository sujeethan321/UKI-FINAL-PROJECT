# Purpose: Implement customer link operations behind the HTTP layer so related business rules are shared by their callers.
"""Owner invitation plus authenticated Customer consent; no contact-only linking."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from hmac import compare_digest, new as hmac_new
from secrets import randbelow

from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import settings
from app.models import Business, BusinessMember, CustomerLinkInvitation, CustomerProfile, User

CODE_LIFETIME = timedelta(minutes=15)


# Hash the invitation token so raw invitation secrets do not need to be stored for lookup.
def _digest(code):
    return hmac_new(settings.JWT_SECRET_KEY.encode(), code.encode('ascii'), sha256).hexdigest()


# Return a consistent unavailable-resource error for an inaccessible or invalid link.
def unavailable():
    return HTTPException(404, "Invitation is invalid or unavailable")


# Resolve profile within the access scope checked by this service.
def owned_profile(db, owner, business_id, customer_id):
    # Lock business first; acceptance takes the same lock before profile.
    business = db.scalar(select(Business).where(Business.business_id == business_id).with_for_update())
    membership = db.scalar(select(BusinessMember).where(
        BusinessMember.business_id == business_id,
        BusinessMember.user_id == owner.user_id,
        BusinessMember.business_role == "owner",
        BusinessMember.membership_status == "active",
    ))
    if (business is None or business.approval_status != "approved" or membership is None
            or owner.platform_role != "shop_owner" or owner.account_status != "active"):
        raise unavailable()
    profile = db.scalar(select(CustomerProfile).where(
        CustomerProfile.business_id == business_id,
        CustomerProfile.customer_id == customer_id,
    ).with_for_update())
    if profile is None or profile.user_id is not None:
        raise unavailable()
    return profile


# Query invite data for the customer link workflow.
def invite(db, owner, business_id, customer_id, recipient_email):
    owned_profile(db, owner, business_id, customer_id)
    recipient = db.scalar(select(User).where(User.email == str(recipient_email).lower()))
    if recipient is None or recipient.platform_role != "customer" or recipient.account_status != "active":
        raise HTTPException(404, "Customer account unavailable for invitation")
    row = db.get(CustomerLinkInvitation, customer_id)
    for _ in range(10):
        code = f'{randbelow(1_000_000):06d}'
        digest = _digest(code)
        collision = db.scalar(select(CustomerLinkInvitation).where(CustomerLinkInvitation.code_digest == digest))
        if collision is None or collision.customer_id == customer_id:
            break
    else:
        raise HTTPException(503, 'Invitation could not be prepared')
    if row is None:
        row = CustomerLinkInvitation(customer_id=customer_id)
        db.add(row)
    row.business_id = business_id
    row.recipient_user_id = recipient.user_id
    row.issuer_user_id = owner.user_id
    row.code_digest = digest
    row.expires_at = (datetime.now(timezone.utc) + CODE_LIFETIME).replace(tzinfo=None)
    db.flush()
    return {'invitation': code, 'expires_at': row.expires_at.replace(tzinfo=timezone.utc)}


# Resolve accept using a row lock so the caller can coordinate concurrent changes.
def accept(db, customer, invitation):
    if customer.platform_role != 'customer' or customer.account_status != 'active':
        raise unavailable()
    digest = _digest(invitation)
    candidate = db.scalar(select(CustomerLinkInvitation).where(CustomerLinkInvitation.code_digest == digest))
    if candidate is None:
        raise unavailable()
    business_id, customer_id = candidate.business_id, candidate.customer_id
    business = db.scalar(select(Business).where(Business.business_id == business_id).with_for_update())
    row = db.scalar(select(CustomerLinkInvitation).where(
        CustomerLinkInvitation.customer_id == customer_id,
    ).with_for_update())
    if (row is None or not compare_digest(row.code_digest, digest)
            or row.recipient_user_id != customer.user_id
            or row.expires_at <= datetime.now(timezone.utc).replace(tzinfo=None)):
        raise unavailable()
    if business is None or business.approval_status != "approved":
        raise unavailable()
    issuer = db.scalar(select(User).where(User.user_id == row.issuer_user_id))
    membership = db.scalar(select(BusinessMember).where(
        BusinessMember.business_id == business_id,
        BusinessMember.user_id == row.issuer_user_id,
        BusinessMember.business_role == "owner",
        BusinessMember.membership_status == "active",
    ))
    if (issuer is None or issuer.platform_role != "shop_owner" or issuer.account_status != "active"
            or membership is None):
        raise unavailable()
    profile = db.scalar(select(CustomerProfile).where(
        CustomerProfile.business_id == business_id,
        CustomerProfile.customer_id == customer_id,
    ).with_for_update())
    if profile is None or profile.user_id is not None:
        raise unavailable()
    prior = db.scalar(select(CustomerProfile.customer_id).where(
        CustomerProfile.business_id == business_id,
        CustomerProfile.user_id == customer.user_id,
    ).limit(1))
    if prior is not None:
        raise unavailable()
    profile.user_id = customer.user_id
    db.delete(row)
    db.flush()
    return {"customer_id": customer_id, "business_id": business_id, "linked": True}
