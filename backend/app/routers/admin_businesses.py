
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth_dependencies import require_roles
from app.core.database import get_db
from app.core.auth_dependencies import get_current_user
from app.models import (
    Business,
    BusinessApprovalAudit,
    BusinessMember,
    User,
)


router = APIRouter(
    prefix="/admin/businesses",
    tags=["Admin - Business Management"],
    dependencies=[Depends(require_roles("admin"))],
)


class BusinessDecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    review_note: str | None = Field(
        default=None,
        max_length=500,
    )


def business_response(business: Business) -> dict:
    return {
        "business_id": business.business_id,
        "business_name": business.business_name,
        "business_type": business.business_type,
        "registration_number": business.registration_number,
        "phone": business.phone,
        "address": business.address,
        "approval_status": business.approval_status,
        "created_at": business.created_at,
    }


@router.get("")
def list_businesses(
    status: Literal[
        "pending", "approved", "rejected", "all"
    ] | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    filters = []

    if status is not None and status != "all":
        filters.append(Business.approval_status == status)

    total = db.scalar(
        select(func.count())
        .select_from(Business)
        .where(*filters)
    ) or 0

    statement = (
        select(Business)
        .where(*filters)
        .order_by(
            Business.created_at.desc(),
            Business.business_id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )

    businesses = db.scalars(statement).all()

    return {
        "businesses": [
            business_response(business)
            for business in businesses
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{business_id}")
def get_business_details(
    business_id: int,
    db: Session = Depends(get_db),
):
    business = db.get(Business, business_id)

    if business is None:
        raise HTTPException(
            status_code=404,
            detail="Business not found",
        )

    owners_statement = (
        select(User)
        .join(
            BusinessMember,
            BusinessMember.user_id == User.user_id,
        )
        .where(
            BusinessMember.business_id == business_id,
            BusinessMember.business_role == "owner",
            BusinessMember.membership_status == "active",
            User.platform_role == "shop_owner",
            User.account_status == "active",
        )
        .order_by(User.user_id)
    )

    owners = db.scalars(owners_statement).all()

    return {
        **business_response(business),
        "owners": [
            {
                "user_id": owner.user_id,
                "full_name": owner.full_name,
                "email": owner.email,
                "phone": owner.phone,
            }
            for owner in owners
        ],
    }

@router.patch("/{business_id}/decision")
def decide_business(
    business_id: int,
    payload: BusinessDecisionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        # Prevent concurrent decisions on the same business.
        business = db.scalar(
            select(Business)
            .where(
                Business.business_id == business_id
            )
            .with_for_update()
        )

        if business is None:
            raise HTTPException(
                status_code=404,
                detail="Business not found",
            )

        if business.approval_status != "pending":
            raise HTTPException(
                status_code=409,
                detail="Only pending businesses can be reviewed",
            )

        # An approved business must have an active owner.
        if payload.decision == "approve":
            owner_id = db.scalar(
                select(User.user_id)
                .join(
                    BusinessMember,
                    BusinessMember.user_id == User.user_id,
                )
                .where(
                    BusinessMember.business_id == business_id,
                    BusinessMember.business_role == "owner",
                    BusinessMember.membership_status == "active",
                    User.platform_role == "shop_owner",
                    User.account_status == "active",
                )
                .limit(1)
            )

            if owner_id is None:
                raise HTTPException(
                    status_code=409,
                    detail="Business has no active Shop Owner",
                )

        previous_status = business.approval_status

        new_status = (
            "approved"
            if payload.decision == "approve"
            else "rejected"
        )

        # Change business status.
        business.approval_status = new_status

        # Record who made the decision and when.
        audit = BusinessApprovalAudit(
            business_id=business.business_id,
            admin_user_id=current_user.user_id,
            decision=payload.decision,
            previous_status=previous_status,
            new_status=new_status,
            review_note=payload.review_note,
        )

        db.add(audit)

        # Commit the status change and audit together.
        db.commit()
        db.refresh(business)

        return {
            "message": (
                "Business approved successfully"
                if payload.decision == "approve"
                else "Business rejected successfully"
            ),
            **business_response(business),
        }

    except Exception:
        db.rollback()
        raise


@router.get("/{business_id}/audit-history")
def get_business_audit_history(
    business_id: int,
    db: Session = Depends(get_db),
):
    business = db.get(Business, business_id)

    if business is None:
        raise HTTPException(
            status_code=404,
            detail="Business not found",
        )

    statement = (
        select(
            BusinessApprovalAudit,
            User.full_name,
            User.email,
        )
        .join(
            User,
            User.user_id == BusinessApprovalAudit.admin_user_id,
        )
        .where(BusinessApprovalAudit.business_id == business_id)
        .order_by(
            BusinessApprovalAudit.created_at.desc(),
            BusinessApprovalAudit.audit_id.desc(),
        )
    )

    audits = db.execute(statement).all()

    return {
        "business_id": business_id,
        "history": [
            {
                "audit_id": audit.audit_id,
                "admin_user_id": audit.admin_user_id,
                "reviewer_name": reviewer_name,
                "reviewer_email": reviewer_email,
                "decision": audit.decision,
                "previous_status": audit.previous_status,
                "new_status": audit.new_status,
                "review_note": audit.review_note,
                "created_at": audit.created_at,
            }
            for audit, reviewer_name, reviewer_email in audits
        ],
    }
