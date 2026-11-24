"""Read-only receipts, temporal statements and effective outstanding positions."""
from datetime import datetime
from decimal import Decimal
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models import Business, BusinessMember, CreditAccount, CustomerProfile, LedgerEntry
from app.routers import shop_owner
from test_day7_integration import integration_api
from test_shop_owner_dashboard import db, make_entry
from test_shop_owner_credit_sales import sale_api, post_sale, details
from test_shop_owner_repayments import repay
from test_credit_sales_concurrency import committed_sales


@pytest.fixture
def document_api(sale_api):
    ctx = sale_api
    assert post_sale(ctx, amount="600.30").status_code == 201
    response = repay(ctx, amount="100.10")
    assert response.status_code == 201
    ctx["repayment"] = response.json()
    return ctx


def read(ctx, kind, **params):
    paths = {"receipt": f"repayments/{ctx.get('repayment', {}).get('entry_id', 99999999)}/receipt",
             "statement": f"customers/{ctx['customer']}/statement", "outstanding": "outstanding-payments"}
    query = {"business_id": ctx["business"]}
    if kind == "statement":
        query.update(start_date="2026-01-01", end_date="2026-12-31")
    query.update(params)
    return ctx["client"].get(f"/api/v1/shop-owner/{paths[kind]}", params=query)


def test_receipt_is_stable_scoped_and_read_only(document_api):
    ctx = document_api
    before = [(e.entry_id, e.receipt_number, e.amount) for e in ctx["db"].scalars(select(LedgerEntry).where(LedgerEntry.credit_account_id == ctx["account"]))]
    first, second = read(ctx, "receipt"), read(ctx, "receipt")
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    data = first.json()
    assert data["receipt_number"] == ctx["repayment"]["receipt_number"]
    assert data["receipt_identifier"] == f"ledger-repayment:{ctx['repayment']['entry_id']}"
    assert data["amount"] == "100.10" and data["currency"] == "LKR"
    assert data["payment_method"] == "cash" and data["status"] == "recorded"
    assert data["business"]["business_id"] == ctx["business"] and data["customer"]["customer_id"] == ctx["customer"]
    assert first.headers["Cache-Control"] == "no-store"
    assert [(e.entry_id, e.receipt_number, e.amount) for e in ctx["db"].scalars(select(LedgerEntry).where(LedgerEntry.credit_account_id == ctx["account"]))] == before


def test_legacy_missing_number_uses_stable_pk_without_mutation(sale_api):
    ctx = sale_api
    entry_id = make_entry(ctx["db"], ctx["owner"].user_id, ctx["account"], "repayment", "1.20")
    ctx["db"].commit(); ctx["repayment"] = {"entry_id": entry_id}
    a, b = read(ctx, "receipt").json(), read(ctx, "receipt").json()
    assert a == b and a["receipt_number"] is None
    assert a["reference"] == f"Ledger repayment #{entry_id}"
    assert ctx["db"].get(LedgerEntry, entry_id).receipt_number is None


def test_reversed_receipt_retains_original_identity_and_marks_void(document_api):
    ctx = document_api
    before = read(ctx, "receipt").json()
    reversal = make_entry(ctx["db"], ctx["owner"].user_id, ctx["account"], "reversal", "100.10", ctx["repayment"]["entry_id"])
    ctx["db"].commit()
    data = read(ctx, "receipt").json()
    assert data["status"] == "reversed" and data["reversal_entry_id"] == reversal and data["reversed_at"]
    for field in ("receipt_number", "receipt_identifier", "reference", "amount"):
        assert data[field] == before[field]
    ctx["repayment"] = {"entry_id": reversal}
    assert read(ctx, "receipt").status_code == 404


def test_sale_or_missing_receipt_cannot_be_fabricated(sale_api):
    response = post_sale(sale_api)
    for entry_id in (response.json()["entry_id"], 9223372036854775807):
        sale_api["repayment"] = {"entry_id": entry_id}
        assert read(sale_api, "receipt").status_code == 404


@pytest.mark.parametrize("kind", ["receipt", "statement", "outstanding"])
@pytest.mark.parametrize("identity", ["anonymous", "invalid_token", "customer", "driver", "admin", "inactive_user", "pending", "inactive_member", "staff", "unowned"])
def test_financial_document_security(document_api, kind, identity):
    ctx = document_api; business = ctx["business"]
    if identity == "anonymous": ctx["client"].headers.pop("Authorization")
    elif identity == "invalid_token": ctx["client"].headers["Authorization"] = "Bearer invalid"
    elif identity in ("customer", "driver", "admin"): ctx["owner"].platform_role = identity
    elif identity == "inactive_user": ctx["owner"].account_status = "suspended"
    elif identity == "pending": ctx["db"].get(Business, business).approval_status = "pending"
    elif identity in ("inactive_member", "staff"):
        member = ctx["db"].scalar(select(BusinessMember).where(BusinessMember.business_id == business))
        if identity == "inactive_member": member.membership_status = "inactive"
        else: member.business_role = "staff"
    else: business = ctx["other_business"]
    ctx["db"].commit()
    response = read(ctx, kind, business_id=business)
    assert response.status_code == (401 if identity in ("anonymous", "invalid_token") else 403)
    assert "Private customer" not in response.text and ctx["repayment"]["reference"] not in response.text


def test_owned_other_business_still_cannot_read_foreign_receipt_or_statement(document_api):
    ctx = document_api
    ctx["db"].add(BusinessMember(business_id=ctx["other_business"], user_id=ctx["owner"].user_id, business_role="owner", membership_status="active"))
    ctx["db"].commit()
    assert read(ctx, "receipt", business_id=ctx["other_business"]).status_code == 404
    assert read(ctx, "statement", business_id=ctx["other_business"]).status_code == 404
    assert read(ctx, "outstanding", business_id=ctx["other_business"]).json()["total_outstanding"] == "0.00"


def event(ctx, kind, amount, when, original=None):
    row = LedgerEntry(credit_account_id=ctx["account"], created_by=ctx["owner"].user_id,
        entry_type=kind, amount=Decimal(amount), recorded_at=datetime.fromisoformat(when),
        reverses_entry_id=original, idempotency_key=f"statement-{uuid4().hex}")
    ctx["db"].add(row); ctx["db"].flush(); return row.entry_id


def test_statement_opening_closing_partial_payment_and_later_reversals(sale_api):
    ctx = sale_api
    sale = event(ctx, "credit_sale", "100.10", "2026-01-01T09:00:00")
    payment = event(ctx, "repayment", "30.05", "2026-02-01T00:00:00")
    event(ctx, "credit_sale", "20.20", "2026-02-28T23:59:59")
    event(ctx, "reversal", "30.05", "2026-03-01T00:00:00", payment)
    event(ctx, "reversal", "100.10", "2026-03-03T10:00:00", sale)
    ctx["db"].commit()
    feb = read(ctx, "statement", start_date="2026-02-01", end_date="2026-02-28").json()
    assert feb["opening_balance"] == "100.10" and feb["closing_balance"] == "90.25"
    assert feb["total_credit_sales"] == "20.20" and feb["total_repayments"] == "30.05" and feb["reversal_impact"] == "0.00"
    assert [t["running_balance"] for t in feb["transactions"]] == ["70.05", "90.25"]
    assert feb["transactions"][0]["status"] == "recorded"  # future reversal is not retroactive
    march = read(ctx, "statement", start_date="2026-03-01", end_date="2026-03-31").json()
    assert march["opening_balance"] == "90.25" and march["closing_balance"] == "20.20" and march["reversal_impact"] == "-70.05"
    assert [t["debit"] for t in march["transactions"]] == ["30.05", "0.00"]
    assert [t["credit"] for t in march["transactions"]] == ["0.00", "100.10"]
    all_rows = read(ctx, "statement").json()
    assert all_rows["closing_balance"] == details(ctx)["outstanding_balance"] == "20.20"
    assert [t["status"] for t in all_rows["transactions"][:2]] == ["reversed", "reversed"]
    assert len(all_rows["transactions"]) == 5


def test_statement_reversal_uses_full_original_delta_for_legacy_amount(sale_api):
    ctx = sale_api; sale = event(ctx, "credit_sale", "100.00", "2026-01-01T00:00:00")
    event(ctx, "reversal", "1.00", "2026-02-01T00:00:00", sale); ctx["db"].commit()
    data = read(ctx, "statement").json()
    assert data["closing_balance"] == "0.00" and data["transactions"][1]["amount"] == "1.00"
    assert data["transactions"][1]["credit"] == "100.00" and details(ctx)["outstanding_balance"] == "0.00"


def test_invalid_reversal_chronology_is_disclosed_not_invented(sale_api):
    ctx = sale_api; original = event(ctx, "credit_sale", "1", "2026-03-01T00:00:00")
    event(ctx, "reversal", "1", "2026-02-01T00:00:00", original); ctx["db"].commit()
    assert read(ctx, "statement").status_code == 409


def test_statement_preserves_negative_balance_as_advance(sale_api):
    ctx = sale_api; event(ctx, "repayment", "5.15", "2026-01-01T00:00:00"); ctx["db"].commit()
    data = read(ctx, "statement", start_date="2026-02-01", end_date="2026-02-28").json()
    assert data["opening_balance"] == data["closing_balance"] == "-5.15"
    assert data["outstanding_balance"] == "0.00" and data["advance_balance"] == "5.15" and data["transactions"] == []


def test_no_account_has_empty_statement_and_outstanding_row(integration_api):
    ctx = integration_api
    response = read(ctx, "statement"); assert response.status_code == 200
    data = response.json(); assert data["credit_account_id"] is None and data["opening_balance"] == data["closing_balance"] == "0.00" and data["transactions"] == []
    data = read(ctx, "outstanding").json(); row = data["customers"][0]
    assert row["credit_limit"] is None and row["available_credit"] is None and row["account_status"] == "no_account"
    assert data["overdue_amount"] is None and row["overdue_amount"] is None
    assert read(ctx, "outstanding", outstanding_only="true").json()["customers"] == []


def test_outstanding_search_filters_pagination_and_consistency(document_api):
    ctx = document_api
    ctx["db"].add_all([CustomerProfile(business_id=ctx["business"], customer_name="No Account"), CustomerProfile(business_id=ctx["business"], customer_name="Search % literal", phone="0771112222")]); ctx["db"].commit()
    response = read(ctx, "outstanding", page_size=1); assert response.status_code == 200
    data = response.json(); assert data["total_customers"] == data["filtered_customers"] == 3
    assert data["customers_with_outstanding"] == 1 and data["total_outstanding"] == "500.20"
    assert len(data["customers"]) == 1
    filtered = read(ctx, "outstanding", outstanding_only="true").json()
    row = filtered["customers"][0]; assert row["customer_id"] == ctx["customer"] and row["outstanding_balance"] == details(ctx)["outstanding_balance"] == "500.20"
    assert row["available_credit"] == details(ctx)["available_credit"] == "499.80"
    for search in ("sEARCH", "%", "077111", " literal "):
        data = read(ctx, "outstanding", search=search).json(); assert data["filtered_customers"] == 1 and data["customers"][0]["customer_name"] == "Search % literal"
        assert data["total_outstanding"] == "500.20"  # business total independent of filters
    assert read(ctx, "outstanding", page=100).json()["customers"] == []
    assert read(ctx, "outstanding", search="no match").json()["filtered_customers"] == 0


@pytest.mark.parametrize("params", [{"start_date": "bad"}, {"start_date": "2026-03-01", "end_date": "2026-02-01"}, {"end_date": "9999-12-31"}, {"start_date": "2026-02-30"}])
def test_statement_range_validation(sale_api, params):
    assert read(sale_api, "statement", **params).status_code == 422


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 0}, {"page_size": 101}, {"search": "x" * 151}, {"business_id": 0}, {"outstanding_only": "nonsense"}])
def test_outstanding_query_validation(sale_api, params):
    assert read(sale_api, "outstanding", **params).status_code == 422


@pytest.mark.parametrize("kind", ["receipt", "statement", "outstanding"])
def test_database_errors_are_sanitized(document_api, monkeypatch, kind):
    def fail(*args, **kwargs): raise SQLAlchemyError("private database diagnostic")
    monkeypatch.setattr(shop_owner, {"receipt": "repayment_receipt", "statement": "customer_statement", "outstanding": "outstanding_payments"}[kind], fail)
    response = read(document_api, kind); assert response.status_code == 500
    assert response.json()["detail"] == "Unable to load financial document" and "private" not in response.text


def test_uncommitted_and_failed_payment_is_not_receiptable(committed_sales):
    ctx = committed_sales
    with Session(engine) as session:
        owner = session.scalar(select(BusinessMember.user_id).where(BusinessMember.business_id == ctx["business"]))
        row = LedgerEntry(credit_account_id=ctx["accounts"][0], created_by=owner, entry_type="repayment", amount=Decimal("1.00"), idempotency_key=f"uncommitted-{uuid4().hex}")
        session.add(row); session.flush(); entry_id = row.entry_id
        response = ctx["client"].get(f"/api/v1/shop-owner/repayments/{entry_id}/receipt", params={"business_id": ctx["business"]}, headers=ctx["headers"])
        assert response.status_code == 404
        session.rollback()
    assert ctx["client"].get(f"/api/v1/shop-owner/repayments/{entry_id}/receipt", params={"business_id": ctx["business"]}, headers=ctx["headers"]).status_code == 404


def test_existing_database_unique_receipt_constraint(document_api):
    ctx = document_api
    with pytest.raises(IntegrityError):
        with ctx["db"].begin_nested():
            ctx["db"].add(LedgerEntry(credit_account_id=ctx["account"], created_by=ctx["owner"].user_id, entry_type="repayment", amount=Decimal("1"), idempotency_key=f"duplicate-{uuid4().hex}", receipt_number=ctx["repayment"]["receipt_number"]))
            ctx["db"].flush()
    assert read(ctx, "receipt").json()["receipt_number"] == ctx["repayment"]["receipt_number"]


def test_concurrent_receipt_reads_preserve_numbered_and_legacy_identifiers(committed_sales):
    ctx = committed_sales
    with Session(engine) as session:
        owner = session.scalar(select(BusinessMember.user_id).where(BusinessMember.business_id == ctx["business"]))
        rows = [LedgerEntry(credit_account_id=ctx["accounts"][0], created_by=owner, entry_type="repayment", amount=Decimal("1.00"), idempotency_key=f"read-{uuid4().hex}", receipt_number=number)
                for number in (None, f"BANK-{uuid4().hex}")]
        session.add_all(rows); session.commit()
        entry_ids = [row.entry_id for row in rows]
    def fetch(entry_id):
        response = ctx["client"].get(f"/api/v1/shop-owner/repayments/{entry_id}/receipt", params={"business_id": ctx["business"]}, headers=ctx["headers"])
        assert response.status_code == 200
        return response.json()
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(fetch, [entry_ids[0], entry_ids[0], entry_ids[1], entry_ids[1]]))
    assert responses[0] == responses[1] and responses[2] == responses[3]
    assert responses[0]["receipt_identifier"] != responses[2]["receipt_identifier"]
    with Session(engine) as session:
        assert session.get(LedgerEntry, entry_ids[0]).receipt_number is None


def test_multiple_debtors_totals_do_not_offset_with_another_customer_advance(document_api):
    ctx = document_api
    for name, kind, value in [("Second debtor", "credit_sale", "25.25"), ("Advance holder", "repayment", "10.00")]:
        customer = CustomerProfile(business_id=ctx["business"], customer_name=name); ctx["db"].add(customer); ctx["db"].flush()
        account = CreditAccount(creditor_business_id=ctx["business"], customer_id=customer.customer_id, credit_limit=Decimal("100.00"), payment_term_days=30, account_status="suspended")
        ctx["db"].add(account); ctx["db"].flush()
        make_entry(ctx["db"], ctx["owner"].user_id, account.credit_account_id, kind, value)
    ctx["db"].commit()
    data = read(ctx, "outstanding", outstanding_only="true").json()
    assert data["total_outstanding"] == "525.45" and data["customers_with_outstanding"] == 2
    assert data["filtered_customers"] == 2
    assert next(row for row in data["customers"] if row["customer_name"] == "Second debtor")["available_credit"] == "74.75"
