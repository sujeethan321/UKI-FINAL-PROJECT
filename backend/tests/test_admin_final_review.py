"""Additional release security/financial assertions using guarded rollback fixtures."""
from datetime import datetime, timezone
import pytest
from sqlalchemy import select, event
from app.models import User, Business, BusinessMember, CreditAccount, CustomerProfile, LedgerEntry, Order, OrderItem, DeliveryRequest, DeliveryAssignment, Notification, AdminAudit
from test_admin_foundation import admin, api, db, shop, call, status, decision
from test_catalogue import request, entry
from test_order_delivery import ready


@pytest.mark.parametrize('account_state', ['deactivated', 'inactive', 'suspended'])
def test_nonactive_administrator_cannot_read_or_write(account_state, admin):
    admin['admin'].account_status = account_state; admin['db'].flush()
    for path in ['/overview', '/users', '/drivers', '/businesses', '/audit-events']:
        assert call(admin, path).status_code == 403
    assert status(admin, admin['user'], 'suspended').status_code == 403
    assert decision(admin).status_code == 403


@pytest.mark.parametrize('role', ['customer', 'shop_owner', 'driver'])
def test_detail_association_and_audit_routes_deny_other_roles(admin, role):
    actor = admin['make_user'](role)
    for path in [f"/admin/users/{admin['user'].user_id}", f"/admin/users/{admin['owner'].user_id}/businesses",
                 f"/admin/drivers/{admin['driver'].user_id}", f"/admin/businesses/{admin['business']}",
                 f"/admin/businesses/{admin['business']}/audit-history", '/admin/audit-events']:
        assert request(admin, path, actor=actor).status_code == 403


def test_account_audit_actor_target_states_timestamp_and_idempotence(admin):
    assert status(admin, admin['user'], 'suspended').status_code == 200
    assert status(admin, admin['user'], 'suspended').status_code == 200
    assert status(admin, admin['user'], 'active').status_code == 200
    records = list(admin['db'].scalars(select(AdminAudit).order_by(AdminAudit.audit_id)))
    assert len(records) == 2
    for row, old, new in zip(records, ['active', 'suspended'], ['suspended', 'active']):
        assert row.admin_user_id == admin['admin'].user_id and row.target_id == admin['user'].user_id
        assert row.target_type == 'user' and row.previous_state == old and row.new_state == new
        # MySQL DATETIME stores naive UTC, not the host's local timezone.
        assert abs((datetime.now(timezone.utc).replace(tzinfo=None) - row.created_at).total_seconds()) < 30
        assert row.reason == 'Operational review'
    for row in records:
        for method in ['patch', 'delete']:
            assert call(admin, f'/audit-events/{row.audit_id}', method).status_code in {404, 405}


@pytest.mark.parametrize('method', ['cash', 'credit'])
def test_admin_reads_and_account_changes_preserve_posted_financial_and_order_snapshots(admin, method):
    ident = ready(admin, method, 'completed')
    account = admin.get('account')
    if account is None: _, account = admin['profile'](admin['business'])
    entry(admin, account, 'credit_sale', '100.25'); entry(admin, account, 'repayment', '25.10')
    models = [BusinessMember, CustomerProfile, CreditAccount, LedgerEntry, Order, OrderItem, DeliveryRequest, DeliveryAssignment]
    def snapshot(): return [admin['db'].execute(select(model.__table__).order_by(*model.__table__.primary_key)).all() for model in models]
    admin['db'].get(Business, admin['business']).approval_status = 'pending'; admin['db'].flush()
    before = snapshot(); writes = []
    financial_tables = {'credit_accounts', 'ledger_entries', 'orders', 'order_items', 'customer_profiles', 'business_members'}
    def observe(conn, cursor, sql, parameters, context, many):
        normalized = sql.lower().strip()
        if normalized.startswith(('insert ', 'update ', 'delete ', 'replace ')) and any(table in normalized for table in financial_tables): writes.append(normalized.split()[0])
    connection = admin['db'].connection(); event.listen(connection, 'before_cursor_execute', observe)
    try:
        for path in ['/overview', '/users', '/drivers', '/businesses', '/audit-events', f"/users/{admin['owner'].user_id}/businesses"]:
            assert call(admin, path).status_code == 200
        assert call(admin, f"/businesses/{admin['business']}/decision", 'patch', {'decision': 'approve' if method == 'cash' else 'reject'}).status_code == 200
        assert decision(admin).status_code == 200
        assert status(admin, admin['user'], 'suspended').status_code == 200
        assert status(admin, admin['user'], 'active').status_code == 200
    finally: event.remove(connection, 'before_cursor_execute', observe)
    assert writes == [] and snapshot() == before
    order = admin['db'].get(Order, ident)
    assert order.status == 'completed' and order.payment_status == ('unpaid' if method == 'cash' else 'posted')
    assert call(admin, f"/users/{admin['user'].user_id}/status", 'patch', {'account_status': 'active', 'reason': 'Review', 'credit_limit': '999999.00'}).status_code == 422
    assert snapshot() == before
