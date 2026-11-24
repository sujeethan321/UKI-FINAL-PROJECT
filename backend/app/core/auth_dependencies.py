# Purpose: Resolve the signed-in database user and enforce account status and platform roles before protected endpoints run.

import jwt

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import JWT_ALGORITHM
from app.models import User


# Extract a bearer token and advertise the login endpoint in the generated API security documentation.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login"
)


# Build a consistent bearer-token rejection so all invalid credential paths return the same authentication challenge.
def credentials_error():
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


# Verify token claims, reload the user, and reject inactive accounts before applying the authenticated request budget.
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    request: Request = None,
) -> User:
    try:
        # Restrict the accepted algorithm and require identity and lifetime claims before trusting the payload.
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "exp", "iat"]},
        )

        # A correctly signed token for another purpose must not authorize API access.
        if payload.get("type") != "access":
            raise credentials_error()

        user_id = int(payload["sub"])

    except (InvalidTokenError, ValueError, TypeError):
        raise credentials_error() from None

    # Reload current account state so a token cannot bypass deletion or later account suspension.
    user = db.get(User, user_id)

    if user is None:
        raise credentials_error()

    # A known but inactive account is forbidden even when its token remains cryptographically valid.
    if user.account_status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active",
        )

    from app.core.rate_limit import authenticated_limit
    authenticated_limit(request, user.user_id)
    return user



def require_roles(*allowed_roles: str):
    """
    Allow access only to users with specified roles.
    """

    allowed = frozenset(allowed_roles)

    if not allowed:
        raise ValueError("At least one role is required")

    # Reject a valid session with an unauthorized role before the endpoint can access protected resources.
    def check_role(
        current_user: User = Depends(get_current_user),
    ) -> User:

        if current_user.platform_role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource",
            )

        return current_user

    return check_role


# One centralized dependency for the existing platform Administrator role.
require_admin = require_roles("admin")
