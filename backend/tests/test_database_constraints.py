import pytest

from decimal import Decimal

from sqlalchemy import insert, text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core.config import settings
from app.core.database import engine
from app.models import (
    User,
    Business,
    CustomerProfile,
    CreditAccount,
    LedgerEntry,
)


@pytest.fixture
def db():
    # Never allow these tests to use the main database.
    if settings.MYSQL_DATABASE != "lankapex_test_db":
        pytest.fail("Use lankapex_test_db for these tests.")

    with engine.connect() as connection:
        actual_db = connection.execute(text("SELECT DATABASE()")).scalar_one()

        if actual_db != "lankapex_test_db":
            pytest.fail("Connected to the wrong database.")

        # Foreign-key and transaction tests need InnoDB.
        for table in (
            "users",
            "businesses",
            "customer_profiles",
            "credit_accounts",
            "ledger_entries",
        ):
            result = connection.execute(
                text("""
                    SELECT ENGINE
                    FROM information_schema.TABLES
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = :table_name
                """),
                {"table_name": table},
            ).scalar_one_or_none()

            if result is None or result.upper() != "INNODB":
                pytest.fail(f"{table} must use InnoDB.")

        connection.rollback()
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()


def create_test_records(db):
    # Create a valid registered user.
    user_result = db.execute(
        insert(User).values(
            full_name="Test Customer",
            email="constraint_test@example.com",
            password_hash="test-only-not-a-real-password-hash",
            platform_role="customer",
            preferred_language="en",
            account_status="active",
        )
    )
    user_id = user_result.inserted_primary_key[0]

    # Create a valid business.
    business_result = db.execute(
        insert(Business).values(
            business_name="Test Grocery",
            business_type="retail",
            address="Jaffna, Sri Lanka",
            approval_status="approved",
        )
    )
    business_id = business_result.inserted_primary_key[0]

    # Link the customer to that business.
    profile_result = db.execute(
        insert(CustomerProfile).values(
            business_id=business_id,
            user_id=user_id,
            customer_name="Test Customer",
        )
    )
    customer_id = profile_result.inserted_primary_key[0]

    return user_id, business_id, customer_id


def create_credit_account(db):
    user_id, business_id, customer_id = create_test_records(db)

    account_result = db.execute(
        insert(CreditAccount).values(
            creditor_business_id=business_id,
            customer_id=customer_id,
            debtor_business_id=None,
            credit_limit=Decimal("10000.00"),
            payment_term_days=30,
            account_status="active",
        )
    )

    account_id = account_result.inserted_primary_key[0]

    return user_id, business_id, customer_id, account_id



def expect_rejection(db, statement, expected_mysql_codes):
    with pytest.raises((IntegrityError, OperationalError)) as exc_info:
        with db.begin_nested():
            db.execute(statement)
    assert exc_info.value.orig.args[0] in expected_mysql_codes


def test_duplicate_email_rejected(db):
    create_test_records(db)
    expect_rejection(db, insert(User).values(
        full_name="Duplicate Customer", email="constraint_test@example.com",
        password_hash="test-only-hash", platform_role="customer",
        preferred_language="en", account_status="active",
    ), {1062})


def test_negative_credit_limit_rejected(db):
    _, business, customer = create_test_records(db)
    expect_rejection(db, insert(CreditAccount).values(
        creditor_business_id=business, customer_id=customer,
        credit_limit=Decimal("-0.01"), payment_term_days=30, account_status="active",
    ), {3819})


def test_credit_account_without_debtor_rejected(db):
    _, business, _ = create_test_records(db)
    expect_rejection(db, insert(CreditAccount).values(
        creditor_business_id=business, customer_id=None, debtor_business_id=None,
        credit_limit=Decimal("100"), payment_term_days=30, account_status="active",
    ), {3819})


def test_credit_account_with_two_debtors_rejected(db):
    _, business, customer = create_test_records(db)
    expect_rejection(db, insert(CreditAccount).values(
        creditor_business_id=business, customer_id=customer, debtor_business_id=business,
        credit_limit=Decimal("100"), payment_term_days=30, account_status="active",
    ), {3819})


@pytest.mark.parametrize("amount", [Decimal("0.00"), Decimal("-500.00")])
def test_invalid_ledger_amount_rejected(db, amount):
    user, _, _, account = create_credit_account(db)
    expect_rejection(db, insert(LedgerEntry).values(
        credit_account_id=account, created_by=user, entry_type="credit_sale",
        amount=amount, idempotency_key=f"invalid-amount-{abs(amount)}",
    ), {3819})


def test_invalid_customer_foreign_key_rejected(db):
    _, business, _ = create_test_records(db)
    expect_rejection(db, insert(CreditAccount).values(
        creditor_business_id=business, customer_id=9223372036854775807,
        credit_limit=Decimal("100"), payment_term_days=30, account_status="active",
    ), {1452})
