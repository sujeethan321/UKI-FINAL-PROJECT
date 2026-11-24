# Purpose: Implement shop owner customer create operations behind the HTTP layer so related business rules are shared by their callers.

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CustomerProfile
from app.schemas.customer import CustomerCreate


# Normalize phone for the shop owner customer create workflow.
def normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None

    digits = "".join(char for char in phone if char.isdigit())

    if digits.startswith("94") and len(digits) == 11:
        return "0" + digits[2:]

    return digits


# Create business customer for the shop owner customer create workflow.
def create_business_customer(
    db: Session,
    business_id: int,
    payload: CustomerCreate,
) -> CustomerProfile:
    from app.services.subscription_service import enforce_customer_capacity
    enforce_customer_capacity(db,business_id)
    normalized_phone = normalize_phone(payload.phone)

    if normalized_phone:
        existing_customers = db.scalars(
            select(CustomerProfile).where(
                CustomerProfile.business_id == business_id,
                CustomerProfile.phone.is_not(None),
            ).with_for_update()
        ).all()

        for existing in existing_customers:
            if normalize_phone(existing.phone) == normalized_phone:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "A customer with this phone number "
                        "already exists in your business"
                    ),
                )

    customer = CustomerProfile(
        business_id=business_id,
        user_id=None,
        customer_name=payload.customer_name,
        phone=normalized_phone,
        address=payload.address,
    )

    db.add(customer)
    db.flush()

    return customer
