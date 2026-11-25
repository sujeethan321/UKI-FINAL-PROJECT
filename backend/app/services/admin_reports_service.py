# Purpose: Implement admin reports operations behind the HTTP layer so related business rules are shared by their callers.
"""Bounded read-only platform reports. No optional document/finance-table reads.

One request Session is used throughout. MySQL must supply REPEATABLE READ;
the first authentication SELECT establishes the same consistent snapshot.
No transaction reset, write locks, DDL, financial posting or missing-table zero.
"""
from collections import Counter
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select, func
from app.core.config import settings
from app.models import (Business, BusinessApprovalAudit, User, CustomerProfile,
    CreditAccount, LedgerEntry, Order, DeliveryRequest, DeliveryAssignment, DeliveryStatusEvent)
from app.schemas.admin_reports import Overview, BusinessRow
from app.services.ledger_service import ZERO, account_balances, load_ledger_entries
from app.services.shop_owner_reports_service import period, trends
from app.services.shop_owner_aging_service import aging

MAX_ROWS = 10000
MAX_BUSINESSES = 1000
MAX_EXPORT_ROWS = 1000


# Limit the result set before building financial history so interactive requests cannot allocate unbounded records.
def bounded(db, statement, limit=MAX_ROWS):
    rows = list(db.execute(statement.limit(limit + 1)).mappings())
    if len(rows) > limit:
        raise HTTPException(422, 'Admin report exceeds the interactive dataset limit; narrow filters')
    return rows


# Query capture data for the admin reports workflow.
def capture(db, filters):
    connection = db.connection()
    dialect = connection.dialect.name
    if dialect == 'mysql':
        if connection.get_isolation_level().upper().replace('_',' ') != 'REPEATABLE READ':
            raise HTTPException(503, 'Admin reporting requires a consistent read snapshot')
        snapshot = 'mysql_repeatable_read'
    elif dialect == 'sqlite':
        snapshot = 'sqlite_offline_test'
    else:
        raise HTTPException(503, 'Admin reporting snapshot unsupported')
    now = db.scalar(select(func.now()))
    if not isinstance(now, datetime) or now.tzinfo is not None:
        raise HTTPException(409, 'Database reporting clock unavailable')
    start, end = period(filters.start_date, filters.end_date, now.date())
    lower, upper = datetime.combine(start, datetime.min.time()), datetime.combine(end + timedelta(days=1), datetime.min.time())
    # Select timestamps inside the half-open reporting interval so adjacent report periods do not overlap.
    def inside(stamp): return lower <= stamp < upper
    business_query=select(Business.business_id, Business.business_name, Business.approval_status, Business.created_at)
    if filters.business_id is not None:
        if db.scalar(select(Business.business_id).where(Business.business_id==filters.business_id)) is None:
            raise HTTPException(404, 'Business not found')
        business_query=business_query.where(Business.business_id==filters.business_id)
    if filters.approval_status is not None: business_query=business_query.where(Business.approval_status==filters.approval_status)
    businesses = bounded(db,business_query,MAX_BUSINESSES)
    ids = [b['business_id'] for b in businesses]
    # Restrict this report query to the business identifiers selected for the captured dataset.
    def scoped(statement, column): return statement.where(column.in_(ids))
    decisions = bounded(db, scoped(select(BusinessApprovalAudit.new_status, BusinessApprovalAudit.created_at), BusinessApprovalAudit.business_id)
        .where(BusinessApprovalAudit.created_at >= lower, BusinessApprovalAudit.created_at < upper))
    # Users are platform registrations; do not confuse shop profiles/memberships with unique people.
    users = bounded(db, select(User.platform_role, User.account_status, User.created_at)
        .where(User.created_at >= lower, User.created_at < upper, User.platform_role.in_(['shop_owner','customer','driver'])))
    profiles = bounded(db, scoped(select(CustomerProfile.customer_id), CustomerProfile.business_id)
        .where(CustomerProfile.created_at >= lower, CustomerProfile.created_at < upper))
    orders_query = scoped(select(Order.order_id, Order.business_id, Order.status, Order.payment_method,
        Order.total, Order.created_at), Order.business_id).where(Order.created_at >= lower, Order.created_at < upper)
    if filters.order_status: orders_query = orders_query.where(Order.status == filters.order_status)
    orders = bounded(db, orders_query)
    deliveries = bounded(db, scoped(select(DeliveryRequest.delivery_request_id, DeliveryRequest.status, DeliveryRequest.created_at), DeliveryRequest.business_id)
        .where(DeliveryRequest.created_at >= lower, DeliveryRequest.created_at < upper))
    # Independent event queries: no fan-out join to orders/ledger/status history.
    assignments = bounded(db, select(DeliveryAssignment.delivery_request_id).join(DeliveryRequest,
        DeliveryRequest.delivery_request_id == DeliveryAssignment.delivery_request_id)
        .where(DeliveryRequest.business_id.in_(ids), DeliveryAssignment.assigned_at >= lower, DeliveryAssignment.assigned_at < upper))
    events = bounded(db, select(DeliveryStatusEvent.delivery_request_id, DeliveryStatusEvent.status, DeliveryStatusEvent.occurred_at)
        .join(DeliveryRequest, DeliveryRequest.delivery_request_id == DeliveryStatusEvent.delivery_request_id)
        .where(DeliveryRequest.business_id.in_(ids), DeliveryStatusEvent.occurred_at >= lower, DeliveryStatusEvent.occurred_at < upper))
    accounts = bounded(db, select(CreditAccount.credit_account_id, CreditAccount.creditor_business_id, CustomerProfile.business_id.label('profile_business_id'))
        .join(CustomerProfile, CustomerProfile.customer_id == CreditAccount.customer_id)
        .where(CreditAccount.creditor_business_id.in_(ids)), getattr(settings,'MAX_INTERACTIVE_CUSTOMERS',1000))
    if any(a['creditor_business_id'] != a['profile_business_id'] for a in accounts):
        raise HTTPException(409, 'Credit account business relationships cannot be reconciled')
    entries = load_ledger_entries(db, [a['credit_account_id'] for a in accounts], max_entries=getattr(settings,'MAX_READ_LEDGER_ENTRIES',5000))
    # Validate reversal references/chronology before using effective balances.
    aging_data = aging(entries, now, getattr(settings,'MAX_READ_LEDGER_ENTRIES',5000))
    if aging_data['reason'] == 'future_entries':
        raise HTTPException(409, 'Future ledger history cannot be reported as current balances')
    daily, _ = trends(entries, start, end, now.date())
    balances = account_balances(entries)
    by_account = {a['credit_account_id']:a['creditor_business_id'] for a in accounts}
    by_business = {b['business_id']:[] for b in businesses}
    for entry in entries: by_business[by_account[entry.credit_account_id]].append(entry)
    money = lambda value: f'{value:.2f}'
    total = lambda rows: sum((r['total'] for r in rows), ZERO)
    outstanding = sum((max(value,ZERO) for value in balances.values()),ZERO)
    advances = sum((max(-value,ZERO) for value in balances.values()),ZERO)
    business_days = Counter(b['created_at'].date().isoformat() for b in businesses if inside(b['created_at']))
    user_days = Counter(u['created_at'].date().isoformat() for u in users)
    order_days = Counter(o['created_at'].date().isoformat() for o in orders)
    delivery_days = Counter(d['created_at'].date().isoformat() for d in deliveries)
    # Expand daily counts across the requested dates so days without records remain explicit.
    def days(counts): return [dict(date=(start + timedelta(days=i)).isoformat(), count=counts[(start + timedelta(days=i)).isoformat()]) for i in range((end-start).days+1)]
    # Count rows for each supported status in the report projection.
    def statuses(rows, field, allowed): return {key:sum(r[field]==key for r in rows) for key in allowed}
    report = Overview.model_validate(dict(generated_at=datetime.now(timezone.utc), database_today=now.date(), start_date=start, end_date=end,
        business_id=filters.business_id, approval_status=filters.approval_status, order_status=filters.order_status,
        snapshot=snapshot, reporting_clocks={'registrations_approvals_credit':'database_wall_clock', 'orders_deliveries':'UTC'},
        coverage={'status':'complete_within_bounds','businesses':len(businesses),'credit_accounts':len(accounts),'ledger_entries':len(entries),
            'max_domain_rows':MAX_ROWS,'max_export_businesses':MAX_EXPORT_ROWS},
        limitations=['Current balances and statuses are not historical period-end positions.',
            'Orders are product value, not collected cash or platform revenue; cancelled/rejected values are separate.',
            'User registrations are platform-wide; shop customer profiles are separate business-scoped records.',
            'Credit metrics cover customer-credit accounts only; business-to-business credit is excluded.',
            'Order status filter applies only to order metrics. Business approval filter selects current business status.',
            'Database wall clock has no verified geographical timezone; UTC sections are not converted.',
            'Fresh exports may differ from an earlier screen when records change.'],
        unavailable={'driver_finance':'not_enabled' if not getattr(settings,'DRIVER_FINANCE_ENABLED',False) else 'not_included_in_core_reports',
            'platform_revenue':'no_verified_revenue_dataset','cash_collected':'order_state_does_not_verify_collection'},
        businesses={'counts':{'current_total':len(businesses),'registered_in_period':sum(inside(b['created_at']) for b in businesses),
            **{'current_'+k:v for k,v in statuses(businesses,'approval_status',['pending','approved','rejected','suspended']).items()},
            'approved_in_period':sum(d['new_status']=='approved' for d in decisions),'rejected_in_period':sum(d['new_status']=='rejected' for d in decisions)},'daily':days(business_days)},
        users={'counts':{'registered_in_period':len(users),'shop_customer_profiles_in_period':len(profiles),
            **{k:sum(u['platform_role']==k for u in users) for k in ['shop_owner','customer','driver']},
            **{'current_'+k:sum(u['account_status']==k for u in users) for k in ['active','suspended']}},'daily':days(user_days)},
        orders={'counts':{'created_in_period':len(orders),**statuses(orders,'status',['submitted','approved','rejected','processing','completed','cancelled']),
            **{k:sum(o['payment_method']==k for o in orders) for k in ['cash','credit']}},
            'amounts':{'product_order_total':money(total(orders)),'non_cancelled_product_total':money(total([o for o in orders if o['status'] not in ('rejected','cancelled')])),
                'cancelled_rejected_product_total':money(total([o for o in orders if o['status'] in ('rejected','cancelled')]))},'daily':days(order_days)},
        deliveries={'counts':{'created_in_period':len(deliveries),**{'current_'+k:v for k,v in statuses(deliveries,'status',['available','assigned','picked_up','in_transit','delivered','cancelled']).items()},
            'assigned_in_period':len({a['delivery_request_id'] for a in assignments}),'completed_in_period':len({e['delivery_request_id'] for e in events if e['status']=='delivered'}),
            'cancelled_in_period':len({e['delivery_request_id'] for e in events if e['status']=='cancelled'})},'daily':days(delivery_days)},
        credit={'counts':{'accounts':len(accounts)},'amounts':{'credit_sales':money(sum((Decimal(d['credit_sales']) for d in daily),ZERO)),
            'repayments':money(sum((Decimal(d['repayments']) for d in daily),ZERO)),'current_outstanding':money(outstanding),'current_advances':money(advances)},'daily':daily}))
    comparisons = []
    for business in businesses:
        ident = business['business_id']; own = [o for o in orders if o['business_id']==ident]
        own_days,_ = trends(by_business[ident],start,end,now.date())
        own_balances = [balance for account,balance in balances.items() if by_account[account]==ident]
        comparisons.append(BusinessRow(business_id=ident,business_name=business['business_name'],approval_status=business['approval_status'],
            orders=len(own),product_order_total=money(total(own)),credit_sales=money(sum((Decimal(d['credit_sales']) for d in own_days),ZERO)),
            repayments=money(sum((Decimal(d['repayments']) for d in own_days),ZERO)),outstanding=money(sum((max(v,ZERO) for v in own_balances),ZERO)),
            advances=money(sum((max(-v,ZERO) for v in own_balances),ZERO))))
    comparisons.sort(key=lambda row:row.business_id)
    comparisons.sort(key=lambda row: Decimal(row.outstanding) if filters.sort=='outstanding' else getattr(row,filters.sort),reverse=filters.direction=='desc')
    return report, comparisons
