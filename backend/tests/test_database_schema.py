
import pytest

from sqlalchemy import inspect

from app.core.database import engine


EXPECTED_TABLES = {
    "users",
    "businesses",
    "business_members",
    "customer_profiles",
    "credit_accounts",
    "ledger_entries",
}


@pytest.fixture(scope="module")
def inspector():
    # Reads schema information from our development MySQL database.
    return inspect(engine)


def test_all_core_tables_exist(inspector):
    actual_tables = set(inspector.get_table_names())

    assert EXPECTED_TABLES.issubset(actual_tables)


def test_user_email_is_unique(inspector):
    constraints = inspector.get_unique_constraints("users")
    indexes = inspector.get_indexes("users")

    unique_columns = [
        set(item["column_names"])
        for item in constraints
    ]

    unique_columns += [
        set(item["column_names"])
        for item in indexes
        if item.get("unique")
    ]

    assert {"email"} in unique_columns


def test_business_member_foreign_keys(inspector):
    foreign_keys = inspector.get_foreign_keys(
        "business_members"
    )

    referenced_tables = {
        fk["referred_table"]
        for fk in foreign_keys
    }

    assert "users" in referenced_tables
    assert "businesses" in referenced_tables



def test_credit_account_constraints(inspector):
    constraints = inspector.get_check_constraints(
        "credit_accounts"
    )

    names = {item["name"] for item in constraints}

    assert "ck_credit_account_one_debtor" in names
    assert "ck_credit_account_limit_nonnegative" in names
    assert "ck_credit_account_payment_term_positive" in names



def test_ledger_constraints(inspector):
    constraints = inspector.get_check_constraints(
        "ledger_entries"
    )

    names = {item["name"] for item in constraints}

    assert "ck_ledger_entry_amount_positive" in names
    assert "ck_ledger_entry_valid_type" in names
    assert "ck_ledger_entry_reversal_reference" in names


def test_ledger_foreign_keys(inspector):
    foreign_keys = inspector.get_foreign_keys(
        "ledger_entries"
    )

    referenced_tables = {
        fk["referred_table"]
        for fk in foreign_keys
    }

    assert "credit_accounts" in referenced_tables
    assert "users" in referenced_tables
    assert "ledger_entries" in referenced_tables


def test_money_columns_use_decimal(inspector):
    credit_columns = {
        column["name"]: column
        for column in inspector.get_columns("credit_accounts")
    }

    ledger_columns = {
        column["name"]: column
        for column in inspector.get_columns("ledger_entries")
    }

    assert credit_columns["credit_limit"]["type"].scale == 2
    assert ledger_columns["amount"]["type"].scale == 2