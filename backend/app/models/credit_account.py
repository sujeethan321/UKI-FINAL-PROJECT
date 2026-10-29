
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CreditAccount(Base):
    __tablename__ = "credit_accounts"

    __table_args__ = (
        CheckConstraint(
            """
            (
                customer_id IS NOT NULL
                AND debtor_business_id IS NULL
            )
            OR
            (
                customer_id IS NULL
                AND debtor_business_id IS NOT NULL
            )
            """,
            name="ck_credit_account_one_debtor",
        ),
        CheckConstraint(
            "credit_limit >= 0",
            name="ck_credit_account_limit_nonnegative",
        ),
        CheckConstraint(
            "payment_term_days > 0",
            name="ck_credit_account_payment_term_positive",
        ),
        UniqueConstraint(
            "customer_id",
            name="uq_credit_account_customer",
        ),
        UniqueConstraint(
            "creditor_business_id",
            "debtor_business_id",
            name="uq_credit_account_business_pair",
        ),
        Index(
            "ix_credit_account_creditor_status",
            "creditor_business_id",
            "account_status",
        ),
    )

    credit_account_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    creditor_business_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("businesses.business_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    customer_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "customer_profiles.customer_id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )

    debtor_business_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("businesses.business_id", ondelete="RESTRICT"),
        nullable=True,
    )

    credit_limit: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    payment_term_days: Mapped[int] = mapped_column(
        nullable=False,
        default=30,
    )

    account_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
    )

    opened_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    creditor_business: Mapped["Business"] = relationship(
        "Business",
        foreign_keys=[creditor_business_id],
    )

    customer: Mapped["CustomerProfile | None"] = relationship(
        "CustomerProfile",
    )

    debtor_business: Mapped["Business | None"] = relationship(
        "Business",
        foreign_keys=[debtor_business_id],
    )
