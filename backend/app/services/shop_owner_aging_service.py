# Purpose: Implement shop owner aging operations behind the HTTP layer so related business rules are shared by their callers.
"""Bounded, reporting-only FIFO. Never persists repayment allocations."""
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from app.services.ledger_service import ZERO, account_balances, effective_entries

BUCKETS = ('current', 'days_1_30', 'days_31_60', 'days_61_90', 'days_91_plus')


# Group outstanding balances into aging buckets using effective financial records.
def aging(entries, now, max_entries):
    if len(entries) > max_entries:
        raise HTTPException(422, 'Aging exceeds the interactive ledger limit')
    originals = {e.entry_id: e for e in entries}
    seen = set()
    if len(originals) != len(entries):
        raise HTTPException(409, 'Inconsistent ledger history')
    future = False
    for e in entries:
        amount = Decimal(e.amount)
        if (not isinstance(e.recorded_at, datetime) or e.recorded_at.tzinfo is not None
                or not amount.is_finite() or amount <= ZERO
                or e.entry_type not in ('credit_sale', 'repayment', 'reversal')):
            raise HTTPException(409, 'Inconsistent ledger history')
        future |= e.recorded_at > now
        if e.entry_type == 'reversal':
            original = originals.get(e.reverses_entry_id)
            if (original is None or original.credit_account_id != e.credit_account_id
                    or original.entry_type not in ('credit_sale', 'repayment')
                    or (original.recorded_at, original.entry_id) >= (e.recorded_at, e.entry_id)
                    or e.reverses_entry_id in seen):
                raise HTTPException(409, 'Invalid ledger reversal history')
            seen.add(e.reverses_entry_id)
        elif e.reverses_entry_id is not None:
            raise HTTPException(409, 'Inconsistent ledger reference')
    if future:
        return dict(status='unavailable', reason='future_entries', reconciliation='unavailable',
                    coverage=None, buckets=None, unclassified=None, overdue_amount=None, due_soon_amount=None, as_of=now.date())
    accounts = defaultdict(list)
    for e in effective_entries(entries):
        accounts[e.credit_account_id].append(e)
    balances = account_balances(entries)
    buckets = dict.fromkeys(BUCKETS, ZERO)
    unknown = ZERO
    due_soon = ZERO
    sales_count = missing_due = invalid_due = 0
    for account_id, rows in accounts.items():
        credit = sum((Decimal(e.amount) for e in rows if e.entry_type == 'repayment'), ZERO)
        classified = ZERO
        for sale in sorted((e for e in rows if e.entry_type == 'credit_sale'), key=lambda e: (e.recorded_at, e.entry_id)):
            sales_count += 1
            used = min(credit, Decimal(sale.amount))
            credit -= used
            residual = Decimal(sale.amount) - used
            classified += residual
            due = sale.due_at
            if not isinstance(due, datetime) or due.tzinfo is not None or due < sale.recorded_at:
                missing_due += due is None
                invalid_due += due is not None
                unknown += residual
                continue
            days = (now.date() - due.date()).days
            # Today through seven calendar days ahead, inclusive; no invented terms.
            if -7 <= days <= 0:
                due_soon += residual
            key = BUCKETS[0 if days <= 0 else 1 if days <= 30 else 2 if days <= 60 else 3 if days <= 90 else 4]
            buckets[key] += residual
        if classified != max(balances.get(account_id, ZERO), ZERO):
            raise HTTPException(409, 'Aging reconciliation failed')
    total = sum((max(v, ZERO) for v in balances.values()), ZERO)
    if sum(buckets.values(), ZERO) + unknown != total:
        raise HTTPException(409, 'Aging reconciliation failed')
    return dict(status='complete' if unknown == ZERO else 'incomplete', reason=None,
                reconciliation='matched', as_of=now.date(),
                coverage=dict(effective_sales=sales_count, missing_due_dates=missing_due,
                              invalid_due_dates=invalid_due, unpaid_debt_fully_classified=unknown == ZERO),
                buckets={key: f'{value:.2f}' for key, value in buckets.items()},
                unclassified=f'{unknown:.2f}',
                due_soon_amount=f'{due_soon:.2f}' if unknown == ZERO else None,
                overdue_amount=f'{sum((buckets[k] for k in BUCKETS[1:]), ZERO):.2f}' if unknown == ZERO else None)
