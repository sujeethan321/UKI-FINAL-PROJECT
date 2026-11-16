"""Read-only post-upgrade verification of the exact development database.

Requires the fresh, writer-paused baseline captured before migration. Prints no
financial amounts, customer rows, connection URLs or credentials.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE = 'c9d5e8f7a237'
HEAD = '14c0d3e2f782'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True, choices=['lankapex_db'])
    parser.add_argument('--baseline', required=True, type=Path)
    args = parser.parse_args()
    require(os.environ.get('APP_ENV') != 'production', 'Production mode refused')
    os.environ['APP_ENV'] = 'development'
    sys.path.insert(0, str(ROOT / 'backend'))
    from sqlalchemy import event, inspect, select
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import Session
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from app.core.config import settings
    from app.core.database import Base, engine
    from app.models import LedgerEntry
    from app.services.ledger_service import account_balances
    import app.models  # noqa: F401

    require(settings.APP_ENV == 'development' and settings.MYSQL_DATABASE == 'lankapex_db'
            and engine.url.database == 'lankapex_db'
            and engine.url.host in ('localhost', '127.0.0.1', '::1'),
            'Exact local development connection required')
    baseline = json.loads(args.baseline.read_text(encoding='utf-8'))
    require(baseline['database'] == 'lankapex_db' and baseline['revision'] == [SOURCE]
            and len(baseline['schema']) == 18 and
            baseline['schema']['ledger_entries']['rows'] == 6,
            'Fresh baseline identity or source state differs')

    def connect_gate(dialect, record, positional, keyword):
        require(keyword.get('database', keyword.get('db')) == 'lankapex_db',
                'Different DBAPI target refused')
    def sql_gate(conn, cursor, statement, parameters, context, many):
        require(conn.engine is engine and conn.engine.url.database == 'lankapex_db',
                'Different engine refused')
        sql = statement.strip().upper()
        require(sql.startswith(('SELECT ', 'SHOW ', 'DESCRIBE ')) or sql in (
                'SET SESSION TRANSACTION READ ONLY',
                'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ',
                'START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY'),
                'Write refused in post-upgrade verifier')
    event.listen(Engine, 'do_connect', connect_gate)
    event.listen(engine, 'before_cursor_execute', sql_gate)
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql('SET SESSION TRANSACTION READ ONLY')
            conn.commit()
            conn.exec_driver_sql('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            conn.exec_driver_sql('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY')
            require(conn.exec_driver_sql('SELECT DATABASE()').scalar_one() == 'lankapex_db',
                    'Actual development database differs')
            require(conn.exec_driver_sql('SELECT version_num FROM alembic_version').scalars().all()
                    == [HEAD], 'Final revision differs')
            inspector = inspect(conn)
            tables = set(inspector.get_table_names())
            require(tables == set(Base.metadata.tables) | {'alembic_version'} and
                    len(tables) == 26, 'Final table inventory differs')
            require(not compare_metadata(MigrationContext.configure(
                conn, opts={'compare_type': True}), Base.metadata),
                'Final model/schema comparison differs')
            quote = conn.dialect.identifier_preparer.quote
            for name, expected in baseline['table_fingerprints'].items():
                pk = inspector.get_pk_constraint(name)['constrained_columns']
                require(pk, 'Original primary key missing')
                rows = conn.exec_driver_sql('SELECT * FROM ' + quote(name) +
                    ' ORDER BY ' + ','.join(quote(key) for key in pk)).all()
                fingerprint = hashlib.sha256(json.dumps([list(row) for row in rows],
                    default=str, separators=(',', ':')).encode()).hexdigest()
                require(len(rows) == baseline['schema'][name]['rows'] and
                        fingerprint == expected, 'Original rows or structure changed')
            new_tables = set(Base.metadata.tables) - set(baseline['table_fingerprints'])
            require(len(new_tables) == 8 and all(conn.exec_driver_sql(
                    'SELECT COUNT(*) FROM ' + quote(name)).scalar_one() == 0
                    for name in new_tables), 'New table count or empty-state mismatch')
            require(conn.exec_driver_sql('SELECT COUNT(*) FROM credit_accounts a '
                    'LEFT JOIN customer_profiles p ON p.customer_id=a.customer_id '
                    'LEFT JOIN businesses b ON b.business_id=a.creditor_business_id '
                    'WHERE p.customer_id IS NULL OR b.business_id IS NULL').scalar_one() == 0,
                    'Credit account ownership relationship differs')
            require(conn.exec_driver_sql('SELECT COUNT(*) FROM ledger_entries l '
                    'LEFT JOIN credit_accounts a ON a.credit_account_id=l.credit_account_id '
                    'WHERE a.credit_account_id IS NULL').scalar_one() == 0,
                    'Ledger/account relationship differs')
            types = dict(conn.exec_driver_sql('SELECT entry_type, COUNT(*) FROM '
                'ledger_entries GROUP BY entry_type').all())
            require(types == baseline['ledger_types'] and sum(types.values()) == 6,
                    'Original ledger type/count differs')
            with Session(bind=conn, join_transaction_mode='rollback_only') as session:
                entries = list(session.scalars(select(LedgerEntry).order_by(LedgerEntry.entry_id)))
                balances = account_balances(entries)
                ledger_hash = hashlib.sha256(json.dumps([
                    [item.entry_id, item.credit_account_id, item.entry_type,
                     str(item.amount), item.reverses_entry_id, item.order_id,
                     item.idempotency_key, item.receipt_number] for item in entries],
                    separators=(',', ':')).encode()).hexdigest()
                balance_hash = hashlib.sha256(json.dumps([
                    [key, str(value)] for key, value in sorted(balances.items())],
                    separators=(',', ':')).encode()).hexdigest()
            require(ledger_hash == baseline['ledger_fingerprint'] and
                    balance_hash == baseline['balance_fingerprint'],
                    'Financial ledger or effective balance changed')
            conn.rollback()
        print('PASS: 26 tables, head revision, model parity, original rows, six ledger entries, balances and ownership')
    finally:
        engine.dispose()
        event.remove(Engine, 'do_connect', connect_gate)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        code = getattr(getattr(error, 'orig', None), 'args', [None])[0]
        print('STOP: ' + type(error).__name__ + '; MySQL code=' + str(code), file=sys.stderr)
        sys.exit(1)
