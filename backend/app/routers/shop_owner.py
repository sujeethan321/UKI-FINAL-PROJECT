
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth_dependencies import require_roles
from app.core.database import get_db
from app.models import Business, BusinessMember, User
from app.schemas.business import (
    BusinessCreate,
    BusinessCreateResponse,
)
from app.services.shop_owner_customer_service import (
    list_business_customers,
)
from app.services.shop_owner_dashboard_service import (
    get_dashboard_summary,
    get_recent_credit_transactions,
)
from app.schemas.customer import (
    CustomerCreate,
    CustomerCreateResponse,
)

from app.services.shop_owner_customer_create_service import (
    create_business_customer,
)


router = APIRouter(
    prefix="/shop-owner",
    tags=["Shop Owner"],
)


# ---------------------------------------------------
# Helper: Check for duplicate business registration
# ---------------------------------------------------

def find_duplicate_owned_business(
    db: Session,
    user_id: int,
    payload: BusinessCreate,
) -> Business | None:
    """
    Check whether the authenticated Shop Owner already
    has an active owner membership for a business with
    matching registration details.

    Different businesses are allowed.
    """

    def normalized_match(column, value):
        if value is None:
            return column.is_(None)

        return (
            func.lower(func.trim(column))
            == value.strip().lower()
        )

    statement = (
        select(Business)
        .join(
            BusinessMember,
            BusinessMember.business_id == Business.business_id,
        )
        .where(
            BusinessMember.user_id == user_id,
            BusinessMember.business_role == "owner",
            BusinessMember.membership_status == "active",
            normalized_match(
                Business.business_name,
                payload.business_name,
            ),
            Business.business_type == payload.business_type,
            normalized_match(
                Business.registration_number,
                payload.registration_number,
            ),
            normalized_match(
                Business.phone,
                payload.phone,
            ),
            normalized_match(
                Business.address,
                payload.address,
            ),
        )
        .limit(1)
    )

    return db.scalar(statement)


# ---------------------------------------------------
# POST: Register a new Shop Owner business
# ---------------------------------------------------

@router.post(
    "/businesses",
    response_model=BusinessCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_shop_owner_business(
    payload: BusinessCreate,
    current_user: User = Depends(
        require_roles("shop_owner")
    ),
    db: Session = Depends(get_db),
):
    """
    Create a pending business and link the authenticated
    Shop Owner in a single database transaction.
    """

    duplicate = find_duplicate_owned_business(
        db=db,
        user_id=current_user.user_id,
        payload=payload,
    )

    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This business is already registered under "
                "your account. Check your dashboard before "
                "submitting again."
            ),
        )

    business = Business(
        business_name=payload.business_name,
        business_type=payload.business_type,
        registration_number=payload.registration_number,
        phone=payload.phone,
        address=payload.address,
        approval_status="pending",
    )

    try:
        db.add(business)

        # Obtain the new business ID before committing.
        db.flush()

        membership = BusinessMember(
            business_id=business.business_id,
            user_id=current_user.user_id,
            business_role="owner",
            membership_status="active",
        )

        db.add(membership)

        # Save business and membership together.
        db.commit()
        db.refresh(business)

    except SQLAlchemyError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to register business",
        ) from None

    return BusinessCreateResponse(
        business_id=business.business_id,
        business_name=business.business_name,
        business_type=business.business_type,
        approval_status=business.approval_status,
        message="Business submitted for admin approval",
    )


# ---------------------------------------------------
# Helper: Verify approved business ownership
# ---------------------------------------------------

def get_approved_owned_business(
    db: Session,
    current_user: User,
    business_id: int,
) -> Business:
    """
    Allow financial access only when:
    - User is an active business owner.
    - Business exists.
    - Business is approved.
    """

    membership = db.scalar(
        select(BusinessMember).where(
            BusinessMember.business_id == business_id,
            BusinessMember.user_id == current_user.user_id,
            BusinessMember.business_role == "owner",
            BusinessMember.membership_status == "active",
        )
    )

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot access this business",
        )

    business = db.get(Business, business_id)

    if business is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )

    if business.approval_status != "approved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Business approval is required "
                "to access financial data"
            ),
        )

    return business


# ---------------------------------------------------
# GET: Shop Owner business context
# ---------------------------------------------------

@router.get("/business-context")
def get_business_context(
    current_user: User = Depends(
        require_roles("shop_owner")
    ),
    db: Session = Depends(get_db),
):
    statement = (
        select(Business, BusinessMember)
        .join(
            BusinessMember,
            BusinessMember.business_id == Business.business_id,
        )
        .where(
            BusinessMember.user_id == current_user.user_id,
            BusinessMember.business_role == "owner",
            BusinessMember.membership_status == "active",
        )
        .order_by(Business.business_id)
    )

    results = db.execute(statement).all()

    businesses = [
        {
            "business_id": business.business_id,
            "business_name": business.business_name,
            "business_type": business.business_type,
            "approval_status": business.approval_status,
        }
        for business, membership in results
    ]

    return {
        "user_id": current_user.user_id,
        "full_name": current_user.full_name,
        "has_business": len(businesses) > 0,
        "businesses": businesses,
    }


# ---------------------------------------------------
# GET: Shop Owner dashboard summary
# ---------------------------------------------------

@router.get("/dashboard/summary")
def read_dashboard_summary(
    business_id: int,
    current_user: User = Depends(
        require_roles("shop_owner")
    ),
    db: Session = Depends(get_db),
):
    get_approved_owned_business(
        db=db,
        current_user=current_user,
        business_id=business_id,
    )

    return get_dashboard_summary(
        db=db,
        business_id=business_id,
    )


# ---------------------------------------------------
# GET: Recent credit transactions
# ---------------------------------------------------

@router.get("/dashboard/recent-transactions")
def read_recent_transactions(
    business_id: int,
    current_user: User = Depends(
        require_roles("shop_owner")
    ),
    db: Session = Depends(get_db),
):
    get_approved_owned_business(
        db=db,
        current_user=current_user,
        business_id=business_id,
    )

    transactions = get_recent_credit_transactions(
        db=db,
        business_id=business_id,
        limit=5,
    )

    return {
        "business_id": business_id,
        "transactions": transactions,
    }


# ---------------------------------------------------
# Day 7 Step 7.1A - Shop Owner Customer List
# ---------------------------------------------------

@router.get("/customers")
def read_shop_owner_customers(
    business_id: int,
    current_user: User = Depends(
        require_roles("shop_owner")
    ),
    db: Session = Depends(get_db),
):
    # Reuse our existing ownership and approval checks.
    get_approved_owned_business(
        db=db,
        current_user=current_user,
        business_id=business_id,
    )

    customers = list_business_customers(
        db=db,
        business_id=business_id,
    )

    return {
        "business_id": business_id,
        "currency": "LKR",
        "total_customers": len(customers),
        "customers": customers,
    }


# --------------------------------------------------
# Day 7 Step 7.2A - Add Customer
# --------------------------------------------------


@router.post(
    "/customers",
    response_model=CustomerCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_shop_owner_customer(
    business_id: int,
    payload: CustomerCreate,
    current_user: User = Depends(
        require_roles("shop_owner")
    ),
    db: Session = Depends(get_db),
):
    get_approved_owned_business(
        db=db,
        current_user=current_user,
        business_id=business_id,
    )

    try:
        customer = create_business_customer(
            db=db,
            business_id=business_id,
            payload=payload,
        )

        result = CustomerCreateResponse(
            customer_id=customer.customer_id,
            business_id=customer.business_id,
            customer_name=customer.customer_name,
            phone=customer.phone,
            address=customer.address,
            message="Customer created successfully",
        )

        db.commit()
        return result

    except HTTPException:
        db.rollback()
        raise

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to create customer",
        ) from None
