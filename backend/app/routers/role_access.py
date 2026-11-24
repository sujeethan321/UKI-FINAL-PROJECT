# Purpose: Expose role access HTTP endpoints and connect request validation and dependencies to the application services.

from fastapi import APIRouter, Depends

from app.core.auth_dependencies import require_roles
from app.models import User


router = APIRouter(
    prefix="/access",
    tags=["Role Access Testing"],
)


# Handle GET /shop-owner through the declared request and dependency contract.
@router.get("/shop-owner")
def shop_owner_access(
    current_user: User = Depends(
        require_roles("shop_owner")
    ),
):
    return {
        "message": "Shop Owner access granted",
        "user_id": current_user.user_id,
    }


# Handle GET /customer through the declared request and dependency contract.
@router.get("/customer")
def customer_access(
    current_user: User = Depends(
        require_roles("customer")
    ),
):
    return {
        "message": "Customer access granted",
        "user_id": current_user.user_id,
    }


# Handle GET /driver through the declared request and dependency contract.
@router.get("/driver")
def driver_access(
    current_user: User = Depends(
        require_roles("driver")
    ),
):
    return {
        "message": "Driver access granted",
        "user_id": current_user.user_id,
    }


# Handle GET /admin through the declared request and dependency contract.
@router.get("/admin")
def admin_access(
    current_user: User = Depends(
        require_roles("admin")
    ),
):
    return {
        "message": "Administrator access granted",
        "user_id": current_user.user_id,
    }
