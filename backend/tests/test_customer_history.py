"""Customer history filters, exact statement snapshots and authorized exports."""
from datetime import date, datetime, timedelta, timezone
import jwt
from app.core.config import settings
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models import Business, LedgerEntry
from app.services.shop_owner_financial_documents_service import customer_statement
from test_customer_dashboard import api, db, entry, get, ROOT, make_business

PERIOD = dict(start_date="2026-02-01", end_date="2026-02-28")


def timed(api, account, kind, amount, when, reverse=None):
    ident = entry(api, account, kind, amount, reverse)
    api["db"].get(LedgerEntry, ident).recorded_at = datetime.fromisoformat(when)
    api["db"].flush()
    return ident


def account_fixture(api):
    shop = make_business(api["db"])
    profile, account = api["profile"](shop)
    timed(api, account, "credit_sale", "100.25", "2026-01-31T23:59:59")
    sale = timed(api, account, "credit_sale", "20.10", "2026-02-01T00:00:00")
    payment = timed(api, account, "repayment", "10.05", "2026-02-28T23:59:59")
    timed(api, account, "credit_sale", "999.99", "2026-03-01T00:00:00")
    return shop, profile, account, sale, payment


def test_history_filters_use_inclusive_database_dates_and_stable_pagination(api):
    shop, _, account, sale, payment = account_fixture(api)
    other_shop = make_business(api["db"]); _, other = api["profile"](other_shop)
    timed(api, other, "credit_sale", "3.00", "2026-02-12T10:00:00")
    result = get(api, "/transactions", business_id=shop, **PERIOD, page_size=1).json()
    assert result["total"] == 2 and result["transactions"][0]["entry_id"] == payment
    second = get(api, "/transactions", business_id=shop, **PERIOD, page_size=1, page=2).json()
    assert second["transactions"][0]["entry_id"] == sale
    assert get(api, "/transactions", **PERIOD).json()["total"] == 3
    for kind, expected in [("credit_sale", sale), ("repayment", payment)]:
        rows = get(api, "/transactions", credit_account_id=account.credit_account_id, entry_type=kind, **PERIOD).json()
        assert rows["total"] == 1 and rows["transactions"][0]["entry_id"] == expected
    assert get(api, "/transactions", business_id=shop, start_date="2025-01-01", end_date="2025-12-31").json()["total"] == 0
    assert get(api, "/transactions", business_id=other_shop, credit_account_id=account.credit_account_id).json()["total"] == 0


@pytest.mark.parametrize("params", [dict(start_date="2026-03-01", end_date="2026-02-01"), dict(start_date="2026-02-30"), dict(end_date="9999-12-31"), dict(entry_type="payment"), dict(business_id=0)])
def test_history_invalid_filters_are_rejected(api, params):
    assert get(api, "/transactions", **params).status_code == 422


def test_shop_filter_cannot_select_foreign_or_pending_business(api):
    for shop in [make_business(api["db"]), make_business(api["db"], "pending")]:
        api["profile"](shop, api["other"])
        assert get(api, "/transactions", business_id=shop).status_code == 404
    assert get(api, "/transactions", business_id=9223372036854775807).status_code == 404


def test_customer_statement_reuses_trusted_full_history_decimal_calculation(api):
    shop, profile, account, _, _ = account_fixture(api)
    result = get(api, f"/credit-accounts/{account.credit_account_id}/statement", **PERIOD)
    assert result.status_code == 200 and result.headers["cache-control"] == "no-store"
    data = result.json()
    assert [data[key] for key in ["opening_balance", "total_credit_sales", "total_repayments", "reversal_impact", "closing_balance"]] == ["100.25", "20.10", "10.05", "0.00", "110.30"]
    business = api["db"].get(Business, shop)
    trusted = customer_statement(api["db"], business, profile.customer_id, date(2026,2,1),date(2026,2,28))
    for key in ["opening_balance", "total_credit_sales", "total_repayments", "reversal_impact", "closing_balance"]: assert data[key] == trusted[key]
    assert len(data["transactions"]) == 2 and data["transactions"][-1]["running_balance"] == "110.30"
    assert Decimal(data["opening_balance"])+Decimal(data["total_credit_sales"])-Decimal(data["total_repayments"])+Decimal(data["reversal_impact"]) == Decimal(data["closing_balance"])
    for forbidden in ["customer_id", "user_id", "created_by", "notes", "phone", "address", "payment_method", "idempotency_key", "reverses_entry_id"]: assert forbidden not in result.text


def test_statement_reversals_post_full_original_on_recorded_date_and_as_of_status(api):
    shop = make_business(api["db"]); _, account = api["profile"](shop)
    sale = timed(api, account, "credit_sale", "100.25", "2026-01-01T12:00:00")
    timed(api, account, "reversal", "0.01", "2026-02-01T12:00:00", sale)
    payment = timed(api, account, "repayment", "20.10", "2026-02-02T12:00:00")
    timed(api, account, "reversal", "0.01", "2026-03-01T12:00:00", payment)
    result = get(api, f"/credit-accounts/{account.credit_account_id}/statement", **PERIOD).json()
    assert result["opening_balance"] == "100.25" and result["reversal_impact"] == "-100.25"
    assert result["closing_balance"] == "-20.10" and result["advance_balance"] == "20.10"
    assert result["transactions"][-1]["status"] == "recorded"


@pytest.mark.parametrize("suffix", ["statement", "statement.pdf"])
def test_statement_and_pdf_reject_foreign_unlinked_pending_and_inconsistent_accounts(api, suffix):
    first, second, pending = make_business(api["db"]), make_business(api["db"]), make_business(api["db"], "pending")
    _, foreign = api["profile"](first, api["other"]); _, unlinked = api["profile"](first, owner=None)
    _, blocked = api["profile"](pending); _, malformed = api["profile"](first)
    malformed.creditor_business_id = second; api["db"].flush()
    for ident in [foreign.credit_account_id, unlinked.credit_account_id, blocked.credit_account_id, malformed.credit_account_id, 9223372036854775807]:
        result = get(api, f"/credit-accounts/{ident}/{suffix}", **PERIOD, user_id=api["other"].user_id)
        assert result.status_code == 404 and result.json() == {"detail":"Credit account not found"}


@pytest.mark.parametrize("suffix", ["statement", "statement.pdf"])
@pytest.mark.parametrize("role", [None,"shop_owner","driver","admin"])
def test_statement_and_pdf_require_customer_jwt(api, suffix, role):
    headers = {} if role is None else {"Authorization":"Bearer "+create_access_token(api["make_user"](role).user_id)}
    response = api["client"].get(ROOT+f"/credit-accounts/1/{suffix}", params=PERIOD, headers=headers)
    assert response.status_code == (401 if role is None else 403)


def test_expired_jwt_denies_history_statement_and_pdf(api):
    headers = {"Authorization":"Bearer "+jwt.encode({"sub":str(api["user"].user_id),"type":"access","iat":datetime.now(timezone.utc)-timedelta(minutes=5),"exp":datetime.now(timezone.utc)-timedelta(seconds=1)},settings.JWT_SECRET_KEY,algorithm="HS256")}
    for path in ["/transactions","/credit-accounts/1/statement","/credit-accounts/1/statement.pdf"]:
        assert api["client"].get(ROOT+path,params=PERIOD,headers=headers).status_code == 401


@pytest.mark.parametrize("suffix", ["statement", "statement.pdf"])
def test_invalid_statement_periods_and_ids_are_rejected(api, suffix):
    for params in [dict(start_date="2026-03-01",end_date="2026-02-01"),dict(start_date="2026-02-30",end_date="2026-03-01"),dict(start_date="2026-01-01",end_date="9999-12-31")]:
        assert get(api,f"/credit-accounts/1/{suffix}",**params).status_code == 422
    assert get(api,f"/credit-accounts/invalid/{suffix}",**PERIOD).status_code == 422


def test_empty_and_large_precision_statements(api):
    shop=make_business(api["db"]);_,account=api["profile"](shop)
    path=f"/credit-accounts/{account.credit_account_id}/statement"
    result=get(api,path,**PERIOD).json()
    assert result["opening_balance"] == result["closing_balance"] == "0.00" and result["transactions"] == []
    timed(api,account,"credit_sale","999999999999.99","2026-02-01T12:00:00")
    timed(api,account,"repayment","0.01","2026-02-02T12:00:00")
    assert get(api,path,**PERIOD).json()["closing_balance"] == "999999999999.98"


def test_pdf_content_headers_and_read_only_behavior(api):
    _,_,account,_,_=account_fixture(api)
    result=get(api,f"/credit-accounts/{account.credit_account_id}/statement.pdf",**PERIOD)
    assert result.status_code == 200 and result.content.startswith(b"%PDF-") and len(result.content)>1000
    assert result.headers["content-type"] == "application/pdf" and result.headers["cache-control"] == "no-store"
    assert result.headers["x-content-type-options"] == "nosniff"
    assert result.headers["content-disposition"] == f'attachment; filename="LankaPex-statement-{account.credit_account_id}-2026-02-01-2026-02-28.pdf"'
    assert api["client"].post(ROOT+f"/credit-accounts/{account.credit_account_id}/statement.pdf",headers=api["headers"]).status_code == 405


def test_pdf_failures_are_sanitized(api,monkeypatch):
    _,_,account,_,_=account_fixture(api)
    def fail(data): raise ValueError("secret")
    monkeypatch.setattr("app.services.customer_statement_pdf.render_statement_pdf",fail)
    result=get(api,f"/credit-accounts/{account.credit_account_id}/statement.pdf",**PERIOD)
    assert result.status_code == 500 and result.json() == {"detail":"Unable to generate statement PDF"}


def test_statement_rejects_cross_account_reversal_without_leaking_original(api):
    shop=make_business(api["db"]);_,own=api["profile"](shop);_,foreign=api["profile"](shop,api["other"])
    sale=timed(api,foreign,"credit_sale","777.77","2026-02-01T12:00:00")
    timed(api,own,"reversal","0.01","2026-02-02T12:00:00",sale)
    result=get(api,f"/credit-accounts/{own.credit_account_id}/statement",**PERIOD)
    assert result.status_code == 409 and "777.77" not in result.text


def test_both_customer_sessions_are_isolated_across_all_customer_views(api):
    shared, own_shop, foreign_shop = [make_business(api["db"]) for _ in range(3)]
    _, a = api["profile"](shared); _, b = api["profile"](shared, api["other"])
    _, a2 = api["profile"](own_shop); _, b2 = api["profile"](foreign_shop, api["other"])
    for account, amount in [(a,"1.01"),(a2,"2.02"),(b,"8.08"),(b2,"9.09")]:
        timed(api,account,"credit_sale",amount,"2026-02-01T12:00:00")
    for user, accounts, shops, total, foreign in [
        (api["user"],[a,a2],{shared,own_shop},"3.03",b),
        (api["other"],[b,b2],{shared,foreign_shop},"17.17",a),
    ]:
        api["headers"]={"Authorization":"Bearer "+create_access_token(user.user_id)}
        ids={account.credit_account_id for account in accounts}
        summary=get(api,"/dashboard/summary",user_id=foreign.customer_id).json()
        assert summary["total_outstanding_balance"]==total and summary["linked_shop_count"]==2
        assert {row["credit_account_id"] for row in summary["recent_activity"]}==ids
        assert {row["business_id"] for row in get(api,"/shops").json()["shops"]}==shops
        assert {row["credit_account_id"] for row in get(api,"/credit-accounts").json()["credit_accounts"]}==ids
        assert {row["credit_account_id"] for row in get(api,"/transactions").json()["transactions"]}==ids
        for suffix in ["", "/statement", "/statement.pdf"]:
            response=get(api,f"/credit-accounts/{foreign.credit_account_id}{suffix}",**PERIOD)
            assert response.status_code==404 and response.json()=={"detail":"Credit account not found"}


def test_customer_totals_match_shop_owner_positions_for_the_same_authorized_accounts(api):
    from app.services.shop_owner_customer_service import list_business_customers
    shop=make_business(api["db"])
    _,first=api["profile"](shop);_,second=api["profile"](shop);_,advance=api["profile"](shop)
    _,foreign=api["profile"](shop,api["other"])
    timed(api,first,"credit_sale","100.25","2026-02-01T12:00:00")
    timed(api,first,"repayment","25.10","2026-02-02T12:00:00")
    original=timed(api,second,"credit_sale","200.20","2026-02-01T12:00:00")
    timed(api,second,"reversal","0.01","2026-02-02T12:00:00",original)
    timed(api,advance,"repayment","7.77","2026-02-01T12:00:00")
    timed(api,foreign,"credit_sale","999.99","2026-02-01T12:00:00")
    owner_rows={row["credit_account_id"]:row for row in list_business_customers(api["db"],shop)}
    rows=get(api,"/credit-accounts").json()["credit_accounts"]
    assert len(rows)==3
    for row in rows: assert Decimal(row["outstanding_balance"])==Decimal(owner_rows[row["credit_account_id"]]["outstanding_balance"])
    assert get(api,"/dashboard/summary").json()["total_outstanding_balance"]=="75.15"
    assert get(api,"/shops").json()["shops"][0]["outstanding_balance"]=="75.15"


def test_large_account_statement_is_rejected_without_truncating_history(api):
    from sqlalchemy import insert
    from uuid import uuid4
    shop=make_business(api["db"]);_,account=api["profile"](shop)
    api["db"].execute(insert(LedgerEntry),[dict(credit_account_id=account.credit_account_id,created_by=api["user"].user_id,
        entry_type="credit_sale",amount=Decimal("0.01"),recorded_at=datetime(2026,2,1,12),idempotency_key=uuid4().hex) for _ in range(5001)])
    api["db"].flush()
    for suffix in ["statement","statement.pdf"]:
        result=get(api,f"/credit-accounts/{account.credit_account_id}/{suffix}",**PERIOD)
        assert result.status_code==422 and result.json()=={"detail":"This account requires a larger statement export. Contact your shop."}
    history=get(api,"/transactions",credit_account_id=account.credit_account_id,page_size=3).json()
    assert history["total"]==5001 and len(history["transactions"])==3


def test_statement_and_pdf_issue_no_data_mutation_sql(api):
    from sqlalchemy import event
    _,_,account,_,_=account_fixture(api)
    connection=api["db"].connection();mutations=[]
    def inspect(conn,cursor,statement,parameters,context,executemany):
        if statement.lstrip().split()[0].upper() in {"INSERT","UPDATE","DELETE","REPLACE"}:mutations.append(statement)
    event.listen(connection,"before_cursor_execute",inspect)
    try:
        for suffix in ["statement","statement.pdf"]:
            assert get(api,f"/credit-accounts/{account.credit_account_id}/{suffix}",**PERIOD).status_code==200
    finally:event.remove(connection,"before_cursor_execute",inspect)
    assert mutations==[]
