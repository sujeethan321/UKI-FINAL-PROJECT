# Purpose: Hash and verify passwords and sign expiring access tokens so authentication never stores plaintext passwords.

from pwdlib import PasswordHash
from datetime import datetime, timedelta, timezone
import jwt

from app.core.config import settings


# Use the library's recommended password-hashing configuration for both account creation and verification.
password_hasher = PasswordHash.recommended()
# Unknown accounts still perform password verification against this hash to reduce account-existence timing differences.
dummy_password_hash = password_hasher.hash('Non-account authentication timing comparison')


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
    

# Token creation and decoding share a fixed algorithm rather than trusting the algorithm named by an incoming token.
JWT_ALGORITHM = "HS256"


# Sign the user identifier with issued-at and expiry claims so the API can verify a time-limited session.
def create_access_token(user_id: int) -> str:
    # UTC keeps issue and expiry comparisons independent of the server's local timezone.
    now = datetime.now(timezone.utc)

    # JWT subjects are strings; the access type distinguishes these tokens from other token purposes.
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        ),
    }

    # Signing makes payload tampering detectable; it does not encrypt the claims.
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )

