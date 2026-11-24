# Purpose: Implement dashboard due operations behind the HTTP layer so related business rules are shared by their callers.
"""Current unpaid due-date totals, using the approved reporting-only FIFO policy."""
from datetime import datetime
from decimal import Decimal
from fastapi import HTTPException
from app.core.config import settings
from app.services.shop_owner_aging_service import aging


# Calculate due amounts from the effective ledger for dashboard summaries.
def due_totals(entries, now, outstanding):
    unavailable = dict(due_soon_amount=None, overdue_amount=None, due_totals_status='unavailable',
                       due_date_policy='fifo_database_wall_clock_today_through_7_days')
    if not isinstance(now, datetime) or now.tzinfo is not None:
        return unavailable
    try:
        result = aging(entries, now, settings.MAX_READ_LEDGER_ENTRIES)
        if result['reconciliation'] != 'matched':
            return unavailable
        total = sum((Decimal(v) for v in result['buckets'].values()), Decimal('0.00')) + Decimal(result['unclassified'])
        if total != Decimal(outstanding):
            return unavailable
        if result['status'] != 'complete':
            return {**unavailable, 'due_totals_status': 'incomplete'}
        return {**unavailable, 'due_totals_status': 'complete',
                'due_soon_amount': result['due_soon_amount'], 'overdue_amount': result['overdue_amount']}
    except HTTPException as error:
        if error.status_code not in (409, 422):
            raise
        # Keep confirmed current balances while explicitly withholding invalid aging.
        return unavailable
