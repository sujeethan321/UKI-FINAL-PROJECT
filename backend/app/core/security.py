
from pwdlib import PasswordHash
from datetime import datetime, timedelta, timezone
import jwt

from app.core.config import settings


password_hasher = PasswordHash.recommended()


def hash_password(plain_password: str) -> str:
    """Convert a plaintext password into a secure hash."""
    return password_hasher.hash(plain_password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """Check whether a password matches its stored hash."""
    return password_hasher.verify(
        plain_password,
        hashed_password,
    )
    

JWT_ALGORITHM = "HS256"


def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        ),
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )

