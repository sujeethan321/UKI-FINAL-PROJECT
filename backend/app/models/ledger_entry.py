
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
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="ck_ledger_entry_amount_positive",
        ),
        CheckConstraint(
            "entry_type IN ('credit_sale', 'repayment', 'reversal')",
            name="ck_ledger_entry_valid_type",
        ),
        CheckConstraint(
            "reverses_entry_id IS NULL OR entry_type = 'reversal'",
            name="ck_ledger_entry_reversal_reference",
        ),
        UniqueConstraint(
            "receipt_number",
            name="uq_ledger_entry_receipt_number",
        ),
        UniqueConstraint(
            "idempotency_key",
            name="uq_ledger_entry_idempotency_key",
        ),
        UniqueConstraint(
            "reverses_entry_id",
            name="uq_ledger_entry_single_reversal",
        ),
        Index(
            "ix_ledger_account_recorded",
            "credit_account_id",
            "recorded_at",
        ),
    )

    entry_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    credit_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "credit_accounts.credit_account_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

   
    order_id: Mapped[int | None] = mapped_column(
    BigInteger,
    nullable=True,
)

    created_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "users.user_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    reverses_entry_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "ledger_entries.entry_id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )

    entry_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )

    payment_method: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    receipt_number: Mapped[str | None] = mapped_column(
        String(60),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    due_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    credit_account: Mapped["CreditAccount"] = relationship(
        "CreditAccount",
    )

    creator: Mapped["User"] = relationship(
        "User",
    )

    reversed_entry: Mapped["LedgerEntry | None"] = relationship(
        "LedgerEntry",
        remote_side=[entry_id],
    )
