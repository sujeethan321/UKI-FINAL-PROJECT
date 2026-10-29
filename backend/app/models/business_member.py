
from sqlalchemy import (
    BigInteger,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BusinessMember(Base):
    __tablename__ = "business_members"

    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "user_id",
            name="uq_business_member_business_user",
        ),
    )

    membership_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    business_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "businesses.business_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "users.user_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    business_role: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="owner",
        server_default="owner",
    )

    membership_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
        server_default="active",
    )
