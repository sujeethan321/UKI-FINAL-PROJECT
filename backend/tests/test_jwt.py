
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from jwt.exceptions import ExpiredSignatureError, InvalidSignatureError

from app.core.config import settings
from app.core.security import (
    JWT_ALGORITHM,
    create_access_token,
)


def test_access_token_created():
    token = create_access_token(user_id=10)

    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[JWT_ALGORITHM],
    )

    assert payload["sub"] == "10"
    assert payload["type"] == "access"
    assert "exp" in payload


def test_expired_token_rejected():
    payload = {
        "sub": "10",
        "type": "access",
        "iat": datetime.now(timezone.utc)
               - timedelta(hours=2),
        "exp": datetime.now(timezone.utc)
               - timedelta(hours=1),
    }

    token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )

    with pytest.raises(ExpiredSignatureError):
        jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
        )


def test_tampered_token_rejected():
    token = create_access_token(user_id=10)

    with pytest.raises(InvalidSignatureError):
        jwt.decode(
            token,
            "different-secret-key",
            algorithms=[JWT_ALGORITHM],
        )
