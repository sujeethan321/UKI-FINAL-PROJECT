# Purpose: Create public user accounts through a shared registration path with password hashing and duplicate-email handling.

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User
from app.schemas.auth import (
    CustomerRegister,
    DriverRegister,
    ShopOwnerRegister,
)


# Distinguish email already registered failures so callers can handle this condition explicitly.
class EmailAlreadyRegistered(Exception):
    pass


# Distinguish registration failed failures so callers can handle this condition explicitly.
class RegistrationFailed(Exception):
    pass


# Create user for the registration workflow.
def _create_user(
    db: Session,
    data: CustomerRegister | DriverRegister | ShopOwnerRegister,
    role: str,
) -> User:
    email = str(data.email).strip().lower()

    existing_user = db.scalar(
        select(User).where(User.email == email)
    )

    if existing_user is not None:
        raise EmailAlreadyRegistered()

    user = User(
        full_name=data.full_name.strip(),
        email=email,
        phone=data.phone,
        password_hash=hash_password(data.password),
        platform_role=role,
        preferred_language=data.preferred_language,
        account_status="active",
    )

    db.add(user)
    db.flush()

    return user



# Register user for the registration workflow.
def register_user(
    db: Session,
    data: CustomerRegister | DriverRegister | ShopOwnerRegister,
    role: str,
) -> User:
    if role not in {"shop_owner", "customer", "driver"}:
        raise ValueError("Unsupported registration role")

    try:
        user = _create_user(db, data, role)

        db.commit()
        db.refresh(user)

        return user

    except EmailAlreadyRegistered:
        db.rollback()
        raise

    except IntegrityError as exc:
        db.rollback()

        mysql_code = getattr(exc.orig, "args", [None])[0]

        if mysql_code == 1062:
            raise EmailAlreadyRegistered() from exc

        raise

    except Exception:
        db.rollback()
        raise

