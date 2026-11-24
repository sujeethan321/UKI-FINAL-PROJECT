# Purpose: Map user records to database tables so SQLAlchemy can persist and relate application data.

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# Map user to the users table for ORM queries and persistence.
class User(Base):
    __tablename__ = "users"

    # Use user id as the unique row identity for ORM lookups and related records.
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    # Keep a required display name for account screens and user-facing record labels.
    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    # Allow accounts without a contact number; workflows that need a phone perform their own eligibility checks.
    phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    # Keep email unique so separate rows cannot claim the same value.
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    # Store the password hash used for verification; the account record must never contain the plaintext password.
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Store the platform role checked by authorization dependencies and role-specific application routes.
    platform_role: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    # Retain the account language preference used by localized application workflows.
    preferred_language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
    )

    # Store account lifecycle state so suspended or inactive records can be rejected by the relevant workflows.
    account_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
    )

    # Retain created at for history, ordering, and time-based queries.
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
