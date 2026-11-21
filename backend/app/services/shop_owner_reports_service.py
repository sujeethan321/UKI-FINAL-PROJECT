"""Bounded customer-credit reports in the stored ledger wall clock. No writes."""
from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from app.core.config import settings
from app.models import CreditAccount, CustomerProfile
from app.services.ledger_service import ZERO, load_ledger_entries
from app.services.shop_owner_dashboard_service import get_dashboard_summary
from app.services.shop_owner_aging_service import aging

MAX_DAYS = 366


def period(start, end, today):
    end = end or today
    if start is None:
        start = end - timedelta(days=min(29, (end - date.min).days))
    if start > end or end == date.max or (end - start).days >= MAX_DAYS:
        raise HTTPException(422, 'Choose an inclusive reporting period of 1 to 366 days')
    return start, end


def trends(entries, start, end, today):
    """Statements keep original events; a reversal negates its full original.

    Repayment reversals reduce repayment collections, rather than create sales.
    Later reversals never rewrite an earlier day's event.
    """
    days = {start + timedelta(days=i): {'credit_sales': ZERO, 'repayments': ZERO}
            for i in range((end - start).days + 1)}
    originals = {(e.credit_account_id, e.entry_id): e for e in entries}
    collected = ZERO
    for entry in entries:
        day = entry.recorded_at.date()
        if day not in days and day != today:
            continue
        original = entry
        sign = Decimal(1)
        if entry.entry_type == 'reversal':
            original = originals.get((entry.credit_account_id, entry.reverses_entry_id))
            if (original is None or original.entry_type not in ('credit_sale', 'repayment')
                or (original.recorded_at, original.entry_id) >= (entry.recorded_at, entry.entry_id)):
                raise HTTPException(409, 'Ledger reversal history cannot be reconstructed for this period')
            sign = Decimal(-1)
        if original.entry_type not in ('credit_sale', 'repayment'):
            raise HTTPException(409, 'Unsupported ledger event')
        key = 'credit_sales' if original.entry_type == 'credit_sale' else 'repayments'
        amount = sign * Decimal(original.amount)
        if day in days:
            days[day][key] += amount
        if day == today and key == 'repayments':
            collected += amount
    return ([dict(date=day.isoformat(), **{k: f'{v:.2f}' for k, v in values.items()})
             for day, values in days.items()], f'{collected:.2f}')


def report(db, business_id, start_date=None, end_date=None):
    now = db.scalar(select(func.now()))  # Same MySQL session clock as NOW()-generated ledger values.
    if not isinstance(now, datetime) or now.tzinfo is not None:
        raise HTTPException(409, 'Database reporting clock unavailable')
    start, end = period(start_date, end_date, now.date())
    account_ids = list(db.scalars(select(CreditAccount.credit_account_id).join(
        CustomerProfile, CustomerProfile.customer_id == CreditAccount.customer_id).where(
        CreditAccount.creditor_business_id == business_id, CustomerProfile.business_id == business_id,
    ).limit(settings.MAX_INTERACTIVE_CUSTOMERS + 1)))
    if len(account_ids) > settings.MAX_INTERACTIVE_CUSTOMERS:
        raise HTTPException(422, 'Report exceeds the interactive account limit')
    entries = load_ledger_entries(db, account_ids, max_entries=settings.MAX_READ_LEDGER_ENTRIES)
    aging_data = aging(entries, now, settings.MAX_READ_LEDGER_ENTRIES)
    daily, collected = trends(entries, start, end, now.date())
    summary = get_dashboard_summary(db, business_id)  # Preserve existing current-position semantics.
    summary['total_outstanding'] = f"{summary['total_outstanding']:.2f}"
    summary['collected_today'] = collected
    if aging_data['reconciliation'] == 'matched':
        aged_total = sum((Decimal(v) for v in aging_data['buckets'].values()), ZERO) + Decimal(aging_data['unclassified'])
        if aged_total != Decimal(summary['total_outstanding']):
            raise HTTPException(409, 'Current outstanding and aging do not reconcile')
    summary['overdue_amount'] = aging_data['overdue_amount']
    return dict(business_id=business_id, currency='LKR', start_date=start, end_date=end,
        database_today=now.date(), reporting_clock='database_wall_clock',
        summary=summary, daily=daily, aging=aging_data,
        totals={key: f'{sum((Decimal(day[key]) for day in daily), ZERO):.2f}'
                for key in ('credit_sales', 'repayments')})
