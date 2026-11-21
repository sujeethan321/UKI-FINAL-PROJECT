
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.auth import (
    CustomerRegister,
    DriverRegister,
    RegistrationResponse,
    ShopOwnerRegister,
)
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.core.auth_dependencies import get_current_user
from app.core.rate_limit import login_limit, registration_limit
from app.core.security import (
    create_access_token,
    dummy_password_hash,
    verify_password,
)
from app.models import User
from app.schemas.auth import TokenResponse, CurrentUserResponse
from app.services.registration_service import (
    EmailAlreadyRegistered,
    register_user,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])


def _register(db: Session, data, role: str):
    try:
        user = register_user(db, data, role)

    except EmailAlreadyRegistered:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email address is already registered",
        ) from None

    return RegistrationResponse(
        user_id=user.user_id,
        full_name=user.full_name,
        email=user.email,
        role=user.platform_role,
        account_status=user.account_status,
        message="Registration successful",
    )


@router.post(
    "/register/customer",
    dependencies=[Depends(registration_limit)],
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_customer(
    data: CustomerRegister,
    db: Session = Depends(get_db),
):
    return _register(db, data, "customer")


@router.post(
    "/register/shop-owner",
    dependencies=[Depends(registration_limit)],
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_shop_owner(
    data: ShopOwnerRegister,
    db: Session = Depends(get_db),
):
    return _register(db, data, "shop_owner")


@router.post(
    "/register/driver",
    dependencies=[Depends(registration_limit)],
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_driver(data: DriverRegister, db: Session = Depends(get_db)):
    return _register(db, data, "driver")


@router.post(
    "/login",
    dependencies=[Depends(login_limit)],
    response_model=TokenResponse,
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    email = form_data.username.strip().lower()

    user = db.scalar(
        select(User).where(User.email == email)
    )

    # Always return a generic login error.
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if user is None:
        # Match the password-verification work performed for existing accounts.
        verify_password(form_data.password, dummy_password_hash)
        raise invalid_credentials

    if not verify_password(
        form_data.password,
        user.password_hash,
    ):
        raise invalid_credentials

    if user.account_status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active",
        )

    token = create_access_token(user.user_id)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
    )


@router.get(
    "/me",
    response_model=CurrentUserResponse,
)
def read_current_user(
    current_user: User = Depends(get_current_user),
):
    return CurrentUserResponse(
        user_id=current_user.user_id,
        full_name=current_user.full_name,
        email=current_user.email,
        platform_role=current_user.platform_role,
        account_status=current_user.account_status,
    )
