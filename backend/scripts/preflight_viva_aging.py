"""Operator-only Step 378 diagnostic. No application imports, writes or retries."""
import argparse
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
import getpass
import importlib.util
import logging
from pathlib import Path
import sys
import warnings

ZERO = Decimal('0.00')
LIMIT = 100000


def assess(entries, now):
    """Pure hypothetical FIFO; tuples: id, account, type, amount, recorded, due, ref.

    No amounts or identifiers are included in the returned diagnostic.
    Invalid ledger structure blocks allocation rather than being normalized.
    """
    by_id = {e[0]: e for e in entries}
    invalid = 0
    reversed_ids = set()
    future = 0
    for e in entries:
        ident, account, kind, amount, recorded, due, ref = e
        if (not isinstance(recorded, datetime) or recorded.tzinfo is not None
                or kind not in ('credit_sale', 'repayment', 'reversal')
                or not Decimal(amount).is_finite() or Decimal(amount) <= 0):
            raise ValueError('Invalid ledger data')
        future += recorded > now
        if kind == 'reversal':
            original = by_id.get(ref)
            if (original is None or original[1] != account
                    or original[2] not in ('credit_sale', 'repayment')
                    or (original[4], original[0]) >= (recorded, ident)
                    or ref in reversed_ids):
                invalid += 1
            reversed_ids.add(ref)
        elif ref is not None:
            invalid += 1
    result = dict(invalid_reversals=invalid, future=future, reconciled=False)
    if invalid or future or len(by_id) != len(entries):
        return result
    effective = [e for e in entries if e[2] != 'reversal' and e[0] not in reversed_ids]
    accounts = defaultdict(list)
    for e in effective:
        accounts[e[1]].append(e)
    sales = [e for e in effective if e[2] == 'credit_sale']
    valid_due = lambda e: (isinstance(e[5], datetime) and e[5].tzinfo is None
                           and e[5] >= e[4])
    buckets = [ZERO] * 5
    unknown = ZERO
    reconciled = True
    for rows in accounts.values():
        credits = sum((Decimal(e[3]) for e in rows if e[2] == 'repayment'), ZERO)
        balance = sum((Decimal(e[3]) if e[2] == 'credit_sale' else -Decimal(e[3]) for e in rows), ZERO)
        allocated = ZERO
        for e in sorted((e for e in rows if e[2] == 'credit_sale'), key=lambda e: (e[4], e[0])):
            used = min(credits, Decimal(e[3]))
            credits -= used
            residual = Decimal(e[3]) - used
            allocated += residual
            if not valid_due(e):
                unknown += residual
                continue
            days = (now.date() - e[5].date()).days
            index = 0 if days <= 0 else 1 if days <= 30 else 2 if days <= 60 else 3 if days <= 90 else 4
            buckets[index] += residual
        reconciled &= allocated == max(balance, ZERO)
    result.update(reconciled=reconciled,
                  effective_sales=len(sales), valid_due=sum(valid_due(e) for e in sales),
                  missing_due=sum(e[5] is None for e in sales),
                  invalid_due=sum(e[5] is not None and not valid_due(e) for e in sales),
                  unclassified=unknown != ZERO,
                  bucket_reconciliation=sum(buckets, ZERO) + unknown == sum(
                      (max(sum((Decimal(e[3]) if e[2] == 'credit_sale' else -Decimal(e[3]) for e in rows), ZERO), ZERO)
                       for rows in accounts.values()), ZERO))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--read-only', required=True, action='store_true')
    parser.parse_args()
    logging.disable(logging.CRITICAL)
    phase = 'PRIVATE_INPUT'
    try:
        if not sys.stdin.isatty():
            raise ValueError()
        warnings.simplefilter('error', getpass.GetPassWarning)
        password = getpass.getpass('Existing viva runtime password (hidden): ')
        if not password:
            raise ValueError()
        import pymysql
        path = Path(__file__).resolve().parents[2] / 'output/step322/guarded_viva_setup.py'
        spec = importlib.util.spec_from_file_location('aging_guards', path)
        guards = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guards)
        phase = 'READ_ONLY_SNAPSHOT'
        conn = pymysql.connect(host='127.0.0.1', port=3306, database='lankapex_viva_db',
            user=guards.RUNTIME, password=password, ssl=guards.tls_context(),
            autocommit=False, connect_timeout=5, read_timeout=30, write_timeout=15)
        try:
            guards.rows(conn, 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            guards.rows(conn, 'START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY')
            guards.identity(conn, guards.RUNTIME, 'lankapex_viva_db')
            guards.require(guards.scalar(conn, 'SELECT version_num FROM alembic_version') == '9d1a6f4e0c37', 'Head differs')
            guards.require(guards.scalar(conn, "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_type='BASE TABLE'") == 33, 'Table count differs')
            # Detect inconsistent customer/business linkage; never silently omit it.
            guards.require(guards.scalar(conn, '''SELECT COUNT(*) FROM credit_accounts a
                LEFT JOIN customer_profiles c ON c.customer_id=a.customer_id
                WHERE a.customer_id IS NOT NULL AND (c.customer_id IS NULL OR c.business_id<>a.creditor_business_id)''') == 0, 'Account scope differs')
            now = guards.scalar(conn, 'SELECT NOW()')
            entries = guards.rows(conn, '''SELECT e.entry_id,e.credit_account_id,e.entry_type,e.amount,
                e.recorded_at,e.due_at,e.reverses_entry_id FROM ledger_entries e
                JOIN credit_accounts a ON a.credit_account_id=e.credit_account_id
                WHERE a.customer_id IS NOT NULL ORDER BY e.recorded_at,e.entry_id LIMIT 100001''')
            guards.require(len(entries) <= LIMIT, 'Bound exceeded')
            result = assess(entries, now)
        finally:
            conn.close()  # No commit; read-only snapshot discarded.
        print('CREDIT_SALES_DUE_DATE_COVERAGE=' + (f"EFFECTIVE={result['effective_sales']}; VALID={result['valid_due']}; MISSING={result['missing_due']}; INVALID={result['invalid_due']}" if result.get('reconciled') else 'UNVERIFIED'))
        print('INVALID_REVERSALS=' + str(result['invalid_reversals']))
        print('FUTURE_DATED_ENTRIES=' + str(result['future']))
        ready = result.get('reconciled') and result.get('bucket_reconciliation')
        print('FIFO_RECONCILIATION=' + ('MATCH_EVERY_ACCOUNT_AND_AGGREGATE' if ready else 'BLOCKED'))
        print('UNCLASSIFIED_BALANCE=' + ('PRESENT_AMOUNT_WITHHELD' if result.get('unclassified') else 'ZERO' if ready else 'UNVERIFIED'))
        print('OVERDUE_AMOUNT_READINESS=' + ('EXACT_UNDER_DISCLOSED_FIFO_POLICY' if ready and not result['unclassified'] else 'UNAVAILABLE'))
        print('STEP378_STATUS=' + ('PASS' if ready else 'BLOCKED'))
        return 0 if ready else 1
    except (Exception, KeyboardInterrupt):
        print('STEP378_STATUS=BLOCKED')
        print('DIAGNOSTIC_STAGE=' + phase)
        print('NEXT_ACTION=STOP; no retry; review privately; no exception bodies disclosed')
        return 1


if __name__ == '__main__':
    sys.exit(main())
