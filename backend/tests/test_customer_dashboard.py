"""Real-JWT, rollback-isolated customer dashboard contracts and isolation."""
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models import Business, CreditAccount, CustomerProfile, LedgerEntry, User
from app.services.ledger_service import account_balances, load_ledger_entries
from test_shop_owner_dashboard import db, make_business, make_entry

ROOT = "/api/v1/customer"
PATHS = ["/dashboard/summary", "/shops", "/credit-accounts", "/transactions"]


@pytest.fixture
def api(db):
    def user(role="customer", status="active"):
        row = User(full_name="Dashboard fixture", email=f"customer-dashboard-{uuid4().hex}@example.com",
                   password_hash="not-a-login-fixture", platform_role=role, account_status=status, preferred_language="en", phone="0771234567")
        db.add(row); db.flush()
        return row
    customer = user()
    other = user()
    def profile(business_id, owner=customer, account=True, limit="1000.00"):
        row = CustomerProfile(business_id=business_id, user_id=owner.user_id if owner else None,
                              customer_name="Dashboard fixture", phone="0771234567", address="Private address")
        db.add(row); db.flush()
        credit = None
        if account:
            credit = CreditAccount(creditor_business_id=business_id, customer_id=row.customer_id,
                                   credit_limit=Decimal(limit), payment_term_days=30, account_status="active")
            db.add(credit); db.flush()
        return row, credit
    connection = db.connection()
    def request_session():
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
    previous = app.dependency_overrides.copy()
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides[get_db] = request_session
    with TestClient(app) as client:
        try:
            headers = {"Authorization": "Bearer " + create_access_token(customer.user_id)}
            yield dict(client=client, db=db, user=customer, other=other, make_user=user, profile=profile, headers=headers)
        finally:
            app.dependency_overrides.clear(); app.dependency_overrides.update(previous)


def get(api, path, **params):
    return api["client"].get(ROOT + path, params=params, headers=api["headers"])


def entry(api, account, kind, amount, reverse=None):
    return make_entry(api["db"], api["user"].user_id, account.credit_account_id, kind, amount, reverse)


def test_unlinked_user_gets_safe_empty_responses_even_with_matching_names_and_phone(api):
    shop = make_business(api["db"])
    _, hidden = api["profile"](shop, owner=None)
    entry(api, hidden, "credit_sale", "999.00")
    _, foreign = api["profile"](shop, owner=api["other"])
    entry(api, foreign, "credit_sale", "888.00")
    summary = get(api, "/dashboard/summary", user_id=api["other"].user_id).json()
    assert summary == {"currency": "LKR", "linked_shop_count": 0, "credit_account_count": 0, "total_outstanding_balance": "0.00", "recent_activity": []}
    for path, field in [("/shops", "shops"), ("/credit-accounts", "credit_accounts"), ("/transactions", "transactions")]:
        result = get(api, path, customer_id=hidden.customer_id, user_id=api["other"].user_id)
        assert result.status_code == 200
        assert result.json()["total"] == 0 and result.json()[field] == []


@pytest.mark.parametrize("repayment,expected", [("0.00", "100.25"), ("25.10", "75.15"), ("100.25", "0.00")])
def test_sales_partial_and_full_repayments_agree_with_existing_ledger(api, repayment, expected):
    shop = make_business(api["db"])
    _, account = api["profile"](shop)
    entry(api, account, "credit_sale", "100.25")
    if Decimal(repayment): entry(api, account, "repayment", repayment)
    balances = account_balances(load_ledger_entries(api["db"], [account.credit_account_id]))
    assert balances[account.credit_account_id] == Decimal(expected)
    response = get(api, "/credit-accounts")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    record = response.json()["credit_accounts"][0]
    assert record["outstanding_balance"] == expected
    assert record["available_credit"] == f"{Decimal('1000.00') - Decimal(expected):.2f}"
    summary = get(api, "/dashboard/summary").json()
    assert summary["total_outstanding_balance"] == expected
    assert summary["linked_shop_count"] == summary["credit_account_count"] == 1


def test_multiple_shops_profiles_accounts_do_not_duplicate_or_net_away_debt(api):
    first, second, advance_shop, empty_shop = (make_business(api["db"]) for _ in range(4))
    _, a = api["profile"](first); _, b = api["profile"](second); _, c = api["profile"](advance_shop)
    api["profile"](empty_shop, account=False)
    entry(api, a, "credit_sale", "100.00")
    entry(api, b, "credit_sale", "200.00")
    entry(api, c, "repayment", "50.00")  # legacy advance must not offset another account's debt
    summary = get(api, "/dashboard/summary").json()
    assert summary["linked_shop_count"] == 4 and summary["credit_account_count"] == 3
    assert summary["total_outstanding_balance"] == "300.00"
    shops = get(api, "/shops").json()
    assert shops["total"] == 4
    assert {r["business_id"]: (r["credit_account_count"], r["outstanding_balance"]) for r in shops["shops"]} == {
        first: (1, "100.00"), second: (1, "200.00"), advance_shop: (1, "0.00"), empty_shop: (0, "0.00")}
    accounts = get(api, "/credit-accounts").json()["credit_accounts"]
    advance = next(r for r in accounts if r["credit_account_id"] == c.credit_account_id)
    assert advance["advance_balance"] == "50.00" and advance["available_credit"] == "1000.00"


def test_shop_without_credit_account_and_account_without_transactions(api):
    first, second = make_business(api["db"]), make_business(api["db"])
    api["profile"](first, account=False); _, account = api["profile"](second)
    summary = get(api, "/dashboard/summary").json()
    assert summary["linked_shop_count"] == 2 and summary["credit_account_count"] == 1
    assert summary["recent_activity"] == []
    assert get(api, "/transactions", credit_account_id=account.credit_account_id).json()["transactions"] == []


@pytest.mark.parametrize("path", PATHS)
def test_authentication_and_roles_are_enforced(api, path):
    assert api["client"].get(ROOT + path).status_code == 401
    for role in ["shop_owner", "driver", "admin", "unsupported"]:
        user = api["make_user"](role)
        response = api["client"].get(ROOT + path, headers={"Authorization": "Bearer " + create_access_token(user.user_id)})
        assert response.status_code == 403
    suspended = api["make_user"](status="suspended")
    assert api["client"].get(ROOT + path, headers={"Authorization": "Bearer " + create_access_token(suspended.user_id)}).status_code == 403


def test_cross_customer_unlinked_pending_and_malformed_business_accounts_remain_hidden(api):
    shop, foreign_shop, pending_shop = make_business(api["db"]), make_business(api["db"]), make_business(api["db"], "pending")
    _, own = api["profile"](shop); _, other = api["profile"](shop, api["other"])
    _, unlinked = api["profile"](shop, owner=None); _, pending = api["profile"](pending_shop)
    _, malformed = api["profile"](foreign_shop)
    malformed.creditor_business_id = shop  # account and profile business disagree
    api["db"].flush()
    for account in [own, other, unlinked, pending, malformed]: entry(api, account, "credit_sale", "17.01")
    summary = get(api, "/dashboard/summary").json()
    assert summary["total_outstanding_balance"] == "17.01" and summary["credit_account_count"] == 1
    assert {r["credit_account_id"] for r in get(api, "/transactions").json()["transactions"]} == {own.credit_account_id}
    for account in [other, unlinked, pending, malformed]:
        assert get(api, "/transactions", credit_account_id=account.credit_account_id).status_code == 404
    assert get(api, "/transactions", credit_account_id=9223372036854775807).status_code == 404


@pytest.mark.parametrize("kind", ["credit_sale", "repayment"])
def test_reversals_cancel_full_original_and_keep_customer_history_interpretable(api, kind):
    shop = make_business(api["db"]); _, account = api["profile"](shop)
    entry(api, account, "credit_sale", "200.00")
    original = entry(api, account, kind, "100.25")
    reversal = entry(api, account, "reversal", "1.00", original)  # legacy descriptive amount differs
    expected = account_balances(load_ledger_entries(api["db"], [account.credit_account_id]))[account.credit_account_id]
    assert get(api, "/dashboard/summary").json()["total_outstanding_balance"] == f"{expected:.2f}"
    history = get(api, "/transactions").json()["transactions"]
    assert next(r for r in history if r["entry_id"] == original)["status"] == "reversed"
    row = next(r for r in history if r["entry_id"] == reversal)
    assert row["amount"] == "1.00" and row["balance_delta"] == ("-100.25" if kind == "credit_sale" else "100.25")


def test_balances_use_complete_history_not_page_and_recent_activity_is_bounded(api):
    shop = make_business(api["db"]); _, account = api["profile"](shop)
    ids = [entry(api, account, "credit_sale", "0.01") for _ in range(8)]
    for row in api["db"].scalars(select(LedgerEntry).where(LedgerEntry.entry_id.in_(ids))): row.recorded_at = datetime(2026, 1, 1, 12)
    api["db"].flush()
    one = get(api, "/transactions", page=1, page_size=3).json()
    two = get(api, "/transactions", page=2, page_size=3).json()
    assert one["total"] == two["total"] == 8
    assert [r["entry_id"] for r in one["transactions"]] == list(reversed(ids))[:3]
    assert [r["entry_id"] for r in two["transactions"]] == list(reversed(ids))[3:6]
    assert get(api, "/transactions", page=9).json()["transactions"] == []
    summary = get(api, "/dashboard/summary").json()
    assert summary["total_outstanding_balance"] == "0.08" and len(summary["recent_activity"]) == 5


@pytest.mark.parametrize("path", ["/shops", "/credit-accounts", "/transactions"])
@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 101}, {"page_size": 0}, {"page": 1000001}])
def test_safe_pagination_bounds(api, path, params):
    assert get(api, path, **params).status_code == 422


@pytest.mark.parametrize("value", [0, -1, "invalid"])
def test_invalid_account_identifier_is_rejected(api, value):
    assert get(api, "/transactions", credit_account_id=value).status_code == 422


def test_response_fields_are_minimal_and_gets_do_not_mutate(api):
    shop = make_business(api["db"]); _, account = api["profile"](shop)
    ident = entry(api, account, "credit_sale", "10.00")
    row = api["db"].get(LedgerEntry, ident); row.notes = "Shop-private internal note"; api["db"].flush()
    before = {m.__tablename__: api["db"].scalar(select(func.count()).select_from(m)) for m in [User, Business, CustomerProfile, CreditAccount, LedgerEntry]}
    for path in PATHS:
        result = get(api, path)
        assert result.status_code == 200
        assert result.json()["currency"] == "LKR"
        for forbidden in ["password_hash", "access_token", "created_by", "user_id", "customer_id", "idempotency_key", "notes", "private internal note", "phone", "address"]:
            assert forbidden not in result.text
    after = {m.__tablename__: api["db"].scalar(select(func.count()).select_from(m)) for m in [User, Business, CustomerProfile, CreditAccount, LedgerEntry]}
    assert before == after
    api["db"].refresh(row)
    assert row.notes == "Shop-private internal note" and row.receipt_number is None and row.amount == Decimal("10.00")


def test_account_and_shop_lists_have_stable_pagination(api):
    for _ in range(4): api["profile"](make_business(api["db"]))
    for path, field, key in [("/shops", "shops", "business_id"), ("/credit-accounts", "credit_accounts", "credit_account_id")]:
        first = get(api, path, page=1, page_size=2).json(); second = get(api, path, page=2, page_size=2).json()
        assert first["total"] == second["total"] == 4
        assert len(first[field]) == len(second[field]) == 2
        assert not {r[key] for r in first[field]} & {r[key] for r in second[field]}


def test_database_errors_are_sanitized(api, monkeypatch):
    from app.services import customer_dashboard_service
    def fail(*args): raise SQLAlchemyError("private database detail")
    monkeypatch.setattr(customer_dashboard_service, "dashboard_summary", fail)
    response = get(api, "/dashboard/summary")
    assert response.status_code == 500 and response.json() == {"detail": "Unable to load customer information"}


def test_only_read_methods_are_exposed(api):
    for path in PATHS:
        assert api["client"].post(ROOT + path, json={}, headers=api["headers"]).status_code == 405


def test_large_decimal_totals_and_reversal_outside_current_page(api):
    first, second = make_business(api["db"]), make_business(api["db"])
    _, a = api["profile"](first, limit="999999999999.99")
    _, b = api["profile"](second, limit="999999999999.99")
    original = entry(api, a, "credit_sale", "999999999999.99")
    entry(api, b, "credit_sale", "999999999999.99")
    assert get(api, "/dashboard/summary").json()["total_outstanding_balance"] == "1999999999999.98"
    entry(api, a, "reversal", "0.01", original)
    history = get(api, "/transactions", credit_account_id=a.credit_account_id, page_size=1).json()
    assert len(history["transactions"]) == 1 and history["transactions"][0]["balance_delta"] == "-999999999999.99"
    assert get(api, "/dashboard/summary").json()["total_outstanding_balance"] == "999999999999.99"


def test_cross_account_reversal_never_cancels_another_accounts_sale(api):
    shop = make_business(api["db"])
    _, own = api["profile"](shop); _, other = api["profile"](shop, api["other"])
    original = entry(api, own, "credit_sale", "20.25")
    entry(api, other, "reversal", "20.25", original)
    summary = get(api, "/dashboard/summary")
    assert summary.status_code == 200 and summary.json()["total_outstanding_balance"] == "20.25"
    assert get(api, "/transactions").json()["transactions"][0]["status"] == "recorded"


def test_invalid_reversal_link_does_not_expose_foreign_original(api):
    shop = make_business(api["db"])
    _, own = api["profile"](shop); _, other = api["profile"](shop, api["other"])
    original = entry(api, other, "credit_sale", "777.25")
    entry(api, own, "reversal", "1.00", original)
    response = get(api, "/transactions")
    assert response.status_code == 409
    assert response.json() == {"detail": "Ledger reversal history cannot be reconstructed"}
    assert "777.25" not in response.text


def test_closed_and_suspended_credit_accounts_remain_readable_without_granting_credit(api):
    shops = [make_business(api["db"]) for _ in range(2)]
    for shop, status in zip(shops, ["closed", "suspended"]):
        _, account = api["profile"](shop)
        account.account_status = status
        entry(api, account, "credit_sale", "12.34")
    api["db"].flush()
    records = get(api, "/credit-accounts").json()["credit_accounts"]
    assert {row["account_status"] for row in records} == {"closed", "suspended"}
    assert all(row["outstanding_balance"] == "12.34" for row in records)


def test_dashboard_gets_issue_no_data_mutation_sql(api):
    from sqlalchemy import event
    shop = make_business(api["db"]); _, account = api["profile"](shop)
    entry(api, account, "credit_sale", "12.34")
    mutations = []
    connection = api["db"].connection()
    def inspect_sql(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE", "REPLACE"}:
            mutations.append(statement.split()[0])
    event.listen(connection, "before_cursor_execute", inspect_sql)
    try:
        for path in PATHS: assert get(api, path).status_code == 200
    finally:
        event.remove(connection, "before_cursor_execute", inspect_sql)
    assert mutations == []


def test_owned_account_detail_is_exact_and_read_only(api):
    shop = make_business(api["db"]); _, account = api["profile"](shop)
    entry(api, account, "credit_sale", "999999999999.99")
    entry(api, account, "repayment", "0.01")
    response = get(api, f"/credit-accounts/{account.credit_account_id}")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    result = response.json()
    assert set(result) == {"currency", "account"}
    assert result["currency"] == "LKR"
    assert result["account"]["credit_account_id"] == account.credit_account_id
    assert result["account"]["outstanding_balance"] == "999999999999.98"
    assert result["account"]["available_credit"] == "0.00"
    for forbidden in ["user_id", "customer_id", "notes", "created_by", "password", "idempotency"]: assert forbidden not in response.text
    assert api["client"].post(ROOT + f"/credit-accounts/{account.credit_account_id}", headers=api["headers"]).status_code == 405


def test_shop_filter_chooses_all_owned_accounts_without_double_counting(api):
    first, second, third = (make_business(api["db"]) for _ in range(3))
    _, a = api["profile"](first); _, b = api["profile"](second); _, c = api["profile"](third)
    _, other = api["profile"](first, api["other"])
    for account, amount in [(a, "1.01"), (b, "2.02"), (c, "9.99"), (other, "55.55")]: entry(api, account, "credit_sale", amount)
    response = get(api, "/credit-accounts", business_id=first, page=1, page_size=1).json()
    another = get(api, "/credit-accounts", business_id=first, page=2, page_size=1).json()
    assert response["total"] == another["total"] == 1
    rows = response["credit_accounts"] + another["credit_accounts"]
    assert {row["credit_account_id"] for row in rows} == {a.credit_account_id}
    assert all(row["business_id"] == first for row in rows)
    assert get(api, "/credit-accounts", business_id=second).json()["credit_accounts"][0]["credit_account_id"] == b.credit_account_id
    pages = [get(api, "/credit-accounts", page=page, page_size=1).json() for page in (1, 2, 3)]
    assert all(page["total"] == 3 and len(page["credit_accounts"]) == 1 for page in pages)
    assert {page["credit_accounts"][0]["credit_account_id"] for page in pages} == {
        a.credit_account_id, b.credit_account_id, c.credit_account_id}
    summary = get(api, "/dashboard/summary").json()
    assert summary["linked_shop_count"] == 3 and summary["total_outstanding_balance"] == "13.02"


def test_linked_shop_without_account_returns_empty_filtered_list(api):
    shop = make_business(api["db"]); api["profile"](shop, account=False)
    response = get(api, "/credit-accounts", business_id=shop)
    assert response.status_code == 200 and response.json()["total"] == 0 and response.json()["credit_accounts"] == []


def test_account_detail_cannot_be_retrieved_via_id_or_user_tampering(api):
    first, second, pending = make_business(api["db"]), make_business(api["db"]), make_business(api["db"], "pending")
    _, other = api["profile"](first, api["other"]); _, unlinked = api["profile"](first, owner=None)
    _, blocked = api["profile"](pending); _, malformed = api["profile"](first)
    malformed.creditor_business_id = second; api["db"].flush()
    for account in [other, unlinked, blocked, malformed]:
        response = get(api, f"/credit-accounts/{account.credit_account_id}", user_id=api["other"].user_id)
        assert response.status_code == 404 and response.json() == {"detail": "Credit account not found"}
    response = get(api, "/credit-accounts/9223372036854775807")
    assert response.status_code == 404 and response.json() == {"detail": "Credit account not found"}
    for business in [second, pending, 9223372036854775807]: assert get(api, "/credit-accounts", business_id=business).status_code == 404


@pytest.mark.parametrize("value", [0, -1, "invalid"])
def test_detail_and_shop_filter_validate_identifiers(api, value):
    assert get(api, f"/credit-accounts/{value}").status_code == 422
    assert get(api, "/credit-accounts", business_id=value).status_code == 422


@pytest.mark.parametrize("role", [None, "shop_owner", "driver", "admin"])
def test_new_customer_detail_requires_customer_role(api, role):
    shop = make_business(api["db"]); _, account = api["profile"](shop)
    headers = {} if role is None else {"Authorization": "Bearer " + create_access_token(api["make_user"](role).user_id)}
    response = api["client"].get(ROOT + f"/credit-accounts/{account.credit_account_id}", headers=headers)
    assert response.status_code == (401 if role is None else 403)


def test_detail_preserves_zero_and_reversal_balance_rules(api):
    shop = make_business(api["db"]); _, account = api["profile"](shop)
    sale = entry(api, account, "credit_sale", "100.25")
    entry(api, account, "reversal", "0.01", sale)
    data = get(api, f"/credit-accounts/{account.credit_account_id}").json()["account"]
    assert data["outstanding_balance"] == "0.00" and data["available_credit"] == "1000.00"
    assert get(api, "/transactions", credit_account_id=account.credit_account_id).json()["total"] == 2
