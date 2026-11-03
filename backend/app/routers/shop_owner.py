from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.services.shop_owner_customer_details_service import get_customer_details
from app.services.shop_owner_customer_manage_service import (
    update_customer,
    manage_credit_account,
)

from app.schemas.ledger import CreditSaleCreate, CreditSaleResponse, RepaymentCreate, RepaymentResponse
from app.services.shop_owner_credit_sale_service import record_credit_sale
from app.services.shop_owner_repayment_service import record_repayment

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
    CustomerUpdate,
    CreditAccountCreate,
    CreditAccountUpdate,
)

from app.services.shop_owner_customer_create_service import (
    create_business_customer,
)

from app.schemas.financial_documents import RepaymentReceipt, CustomerStatement, OutstandingPayments
from app.services.shop_owner_financial_documents_service import (
    repayment_receipt, customer_statement, outstanding_payments,
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

        return func.lower(func.trim(column)) == value.strip().lower()

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
    current_user: User = Depends(require_roles("shop_owner")),
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
            detail=("Business approval is required " "to access financial data"),
        )

    return business


# ---------------------------------------------------
# GET: Shop Owner business context
# ---------------------------------------------------


@router.get("/business-context")
def get_business_context(
    current_user: User = Depends(require_roles("shop_owner")),
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
    current_user: User = Depends(require_roles("shop_owner")),
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
    current_user: User = Depends(require_roles("shop_owner")),
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
    current_user: User = Depends(require_roles("shop_owner")),
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
    current_user: User = Depends(require_roles("shop_owner")),
    db: Session = Depends(get_db),
):
    get_approved_owned_business(
        db=db,
        current_user=current_user,
        business_id=business_id,
    )

    try:
        db.scalar(select(Business).where(Business.business_id == business_id).with_for_update())
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


@router.get("/customers/{customer_id}")
def read_shop_owner_customer_details(
    customer_id: int,
    business_id: int,
    current_user: User = Depends(require_roles("shop_owner")),
    db: Session = Depends(get_db),
):
    get_approved_owned_business(
        db=db,
        current_user=current_user,
        business_id=business_id,
    )
    return get_customer_details(
        db=db,
        business_id=business_id,
        customer_id=customer_id,
    )


def save_customer_changes(db, business_id, customer_id, operation):
    try:
        operation()
        result = get_customer_details(db, business_id, customer_id)
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Customer or credit account conflicts with an existing record") from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(500, "Unable to save customer changes") from None


@router.patch("/customers/{customer_id}")
def edit_shop_owner_customer(
    customer_id: int, business_id: int, payload: CustomerUpdate,
    current_user: User = Depends(require_roles("shop_owner")),
    db: Session = Depends(get_db),
):
    get_approved_owned_business(db, current_user, business_id)
    return save_customer_changes(db, business_id, customer_id,
        lambda: update_customer(db, business_id, customer_id, payload))


@router.post("/customers/{customer_id}/credit-account", status_code=201)
def create_shop_owner_credit_account(
    customer_id: int, business_id: int, payload: CreditAccountCreate,
    current_user: User = Depends(require_roles("shop_owner")),
    db: Session = Depends(get_db),
):
    get_approved_owned_business(db, current_user, business_id)
    return save_customer_changes(db, business_id, customer_id,
        lambda: manage_credit_account(db, business_id, customer_id, payload, create=True))


@router.patch("/customers/{customer_id}/credit-account")
def update_shop_owner_credit_account(
    customer_id: int, business_id: int, payload: CreditAccountUpdate,
    current_user: User = Depends(require_roles("shop_owner")),
    db: Session = Depends(get_db),
):
    get_approved_owned_business(db, current_user, business_id)
    return save_customer_changes(db, business_id, customer_id,
        lambda: manage_credit_account(db, business_id, customer_id, payload))


def save_financial_operation(db, current_user, business_id, response, operation, label):
    # Both writers share retry/rollback behavior and the same account lock.
    for attempt in range(3):
        try:
            get_approved_owned_business(db, current_user, business_id)
            result = operation()
            db.commit()
            response.status_code = 200 if result.replayed else 201
            return result
        except HTTPException:
            db.rollback()
            raise
        except IntegrityError:
            # Unique indexes arbitrate cross-account key/reference races. A
            # fresh transaction can see the winning row and replay/conflict.
            db.rollback()
            if attempt == 2:
                raise HTTPException(409, f"{label.capitalize()} conflicts with an existing transaction") from None
        except OperationalError as error:
            db.rollback()
            code = error.orig.args[0] if error.orig and error.orig.args else None
            if code not in (1205, 1213) or attempt == 2:
                raise HTTPException(500, f"Unable to record {label}") from None
        except SQLAlchemyError:
            db.rollback()
            raise HTTPException(500, f"Unable to record {label}") from None


@router.post("/credit-sales", response_model=CreditSaleResponse, status_code=201)
def add_shop_owner_credit_sale(
    payload: CreditSaleCreate,
    response: Response,
    business_id: int = Query(gt=0, le=9223372036854775807),
    current_user: User = Depends(require_roles("shop_owner")),
    db: Session = Depends(get_db),
):
    return save_financial_operation(db, current_user, business_id, response,
        lambda: record_credit_sale(db, business_id, current_user.user_id, payload), "credit sale")


@router.post("/repayments", response_model=RepaymentResponse, status_code=201)
def add_shop_owner_repayment(
    payload: RepaymentCreate,
    response: Response,
    business_id: int = Query(gt=0, le=9223372036854775807),
    current_user: User = Depends(require_roles("shop_owner")),
    db: Session = Depends(get_db),
):
    return save_financial_operation(db, current_user, business_id, response,
        lambda: record_repayment(db, business_id, current_user.user_id, payload), "repayment")


def read_financial_document(db, current_user, business_id, response, operation):
    response.headers["Cache-Control"] = "no-store"
    try:
        business = get_approved_owned_business(db, current_user, business_id)
        return operation(business)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(500, "Unable to load financial document") from None


@router.get("/repayments/{repayment_id}/receipt", response_model=RepaymentReceipt)
def read_shop_owner_repayment_receipt(
    response: Response,
    repayment_id: int = Path(gt=0, le=9223372036854775807),
    business_id: int = Query(gt=0, le=9223372036854775807),
    current_user: User = Depends(require_roles("shop_owner")),
    db: Session = Depends(get_db),
):
    return read_financial_document(db, current_user, business_id, response,
        lambda business: repayment_receipt(db, business, repayment_id))


@router.get("/customers/{customer_id}/statement", response_model=CustomerStatement)
def read_shop_owner_customer_statement(
    response: Response,
    start_date: date,
    end_date: date,
    customer_id: int = Path(gt=0, le=9223372036854775807),
    business_id: int = Query(gt=0, le=9223372036854775807),
    current_user: User = Depends(require_roles("shop_owner")),
    db: Session = Depends(get_db),
):
    return read_financial_document(db, current_user, business_id, response,
        lambda business: customer_statement(db, business, customer_id, start_date, end_date))


@router.get("/outstanding-payments", response_model=OutstandingPayments)
def read_shop_owner_outstanding_payments(
    response: Response,
    business_id: int = Query(gt=0, le=9223372036854775807),
    search: str = Query(default="", max_length=150),
    outstanding_only: bool = False,
    page: int = Query(default=1, ge=1, le=1000000),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_roles("shop_owner")),
    db: Session = Depends(get_db),
):
    return read_financial_document(db, current_user, business_id, response,
        lambda business: outstanding_payments(db, business.business_id, search, outstanding_only, page, page_size))
