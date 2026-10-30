
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Business, BusinessMember, User
from app.schemas.auth import (
    CustomerRegister,
    DriverRegister,
    ShopOwnerRegister,
)


class EmailAlreadyRegistered(Exception):
    pass


class RegistrationFailed(Exception):
    pass


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


def register_user(
    db: Session,
    data: CustomerRegister | DriverRegister | ShopOwnerRegister,
    role: str,
) -> User:
    if role not in {"shop_owner", "customer", "driver"}:
        raise ValueError("Unsupported registration role")

    try:
        user = _create_user(db, data, role)

        if role == "shop_owner":
            if not isinstance(data, ShopOwnerRegister):
                raise ValueError("Shop details are required")

            business = Business(
                business_name=data.business_name.strip(),
                business_type=data.business_type.strip(),
                registration_number=data.registration_number,
                phone=data.business_phone,
                address=data.business_address.strip(),
                approval_status="pending",
            )

            db.add(business)
            db.flush()

            member = BusinessMember(
                business_id=business.business_id,
                user_id=user.user_id,
                business_role="owner",
                membership_status="active",
            )

            db.add(member)

        db.commit()
        db.refresh(user)

        return user

    except EmailAlreadyRegistered:
        db.rollback()
        raise

   
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

