"""Read-only, private fingerprint manifest for the exact populated demo schema."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
TARGET = 'lankapex_demo_db'
REVISION = '14c0d3e2f782'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def digest_rows(rows):
    digest = hashlib.sha256()
    count = 0
    for row in rows:
        digest.update(json.dumps(list(row), default=str, separators=(',', ':')).encode('utf-8'))
        digest.update(b'\n')
        count += 1
    return count, digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True, choices=[TARGET])
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    private = (ROOT / '.server-logs' / 'private-demo-backups').resolve()
    output = Path(args.output).resolve()
    require(output.parent == private and output.suffix == '.json' and not output.exists(),
            'Manifest must be a new private JSON file outside Git')
    require(os.environ.get('APP_ENV') == 'development'
            and os.environ.get('MYSQL_DATABASE') == TARGET
            and os.environ.get('MYSQL_USER') == 'lankapex_demo_migrator'
            and os.environ.get('MYSQL_PASSWORD'), 'Private demo migrator environment required')
    sys.path.insert(0, str(ROOT / 'backend'))
    from sqlalchemy import inspect
    from app.core.config import settings
    from app.core.database import Base, engine
    import app.models  # noqa: F401

    require(settings.APP_ENV == 'development' and settings.MYSQL_DATABASE == TARGET
            and settings.MYSQL_USER == 'lankapex_demo_migrator'
            and settings.MYSQL_HOST in ('localhost', '127.0.0.1', '::1')
            and engine.url.database == TARGET, 'Configured demo target differs')
    try:
        with engine.connect() as conn:
            require(conn.exec_driver_sql('SELECT DATABASE()').scalar_one() == TARGET
                    and conn.exec_driver_sql('SELECT CURRENT_USER()').scalar_one()
                    == 'lankapex_demo_migrator@localhost', 'Actual database/account differs')
            conn.commit()
            conn.exec_driver_sql('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            conn.exec_driver_sql('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY')
            try:
                inspector = inspect(conn)
                names = sorted(inspector.get_table_names())
                require(set(names) == (set(Base.metadata.tables) - {'customer_link_invitations'})
                        | {'alembic_version'} and len(names) == 26,
                        'Expected 26 starting demo tables')
                require(conn.exec_driver_sql('SELECT version_num FROM alembic_version').scalars().all()
                        == [REVISION], 'Demo revision differs')
                quote = conn.dialect.identifier_preparer.quote
                counts, hashes = {}, {}
                for name in names:
                    keys = inspector.get_pk_constraint(name)['constrained_columns']
                    require(keys, 'Table lacks primary key: ' + name)
                    columns = [column['name'] for column in inspector.get_columns(name)]
                    sql = ('SELECT ' + ','.join(quote(column) for column in columns)
                           + ' FROM ' + quote(name) + ' ORDER BY '
                           + ','.join(quote(key) for key in keys))
                    counts[name], hashes[name] = digest_rows(conn.exec_driver_sql(sql))
                orphans = {}
                for name in names:
                    for fk in inspector.get_foreign_keys(name):
                        source, target = fk['constrained_columns'], fk['referred_columns']
                        parent = fk['referred_table']
                        if not source or not target or not parent or fk.get('referred_schema') not in (None, TARGET):
                            raise RuntimeError('Unreviewed foreign key metadata')
                        join = ' AND '.join('c.' + quote(a) + '=p.' + quote(b)
                                            for a, b in zip(source, target))
                        present = ' AND '.join('c.' + quote(a) + ' IS NOT NULL' for a in source)
                        sql = ('SELECT COUNT(*) FROM ' + quote(name) + ' c LEFT JOIN '
                               + quote(parent) + ' p ON ' + join + ' WHERE ' + present
                               + ' AND p.' + quote(target[0]) + ' IS NULL')
                        orphans[name + ':' + (fk.get('name') or ','.join(source))] = conn.exec_driver_sql(sql).scalar_one()
                financial = {}
                for label, sql in {
                    'ledger_by_type': 'SELECT entry_type, COUNT(*), COALESCE(SUM(amount),0) FROM ledger_entries GROUP BY entry_type ORDER BY entry_type',
                    'ledger_by_account': 'SELECT credit_account_id, entry_type, COUNT(*), COALESCE(SUM(amount),0) FROM ledger_entries GROUP BY credit_account_id, entry_type ORDER BY credit_account_id, entry_type',
                    'customer_links': 'SELECT business_id, customer_id, user_id FROM customer_profiles ORDER BY customer_id',
                    'order_financial_links': 'SELECT order_id, credit_account_id, credit_sale_id, delivery_request_id FROM orders ORDER BY order_id',
                }.items():
                    _, financial[label] = digest_rows(conn.exec_driver_sql(sql))
                captured = conn.exec_driver_sql('SELECT UTC_TIMESTAMP(6)').scalar_one()
                result = {'database': TARGET, 'account': 'lankapex_demo_migrator@localhost',
                          'revision': REVISION, 'captured_utc': str(captured),
                          'row_counts': counts, 'table_fingerprints': hashes,
                          'financial_relationship_fingerprints': financial,
                          'foreign_key_orphans': orphans}
            finally:
                conn.rollback()
    finally:
        engine.dispose()
    with output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write('\n')
    print('PASS: exact demo identity/revision; 26 table counts and private fingerprints captured')
    print('PASS: foreign-key orphan counts stored privately; manifest written outside Git')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print('STOP: demo baseline failed (' + type(exc).__name__ + ')', file=sys.stderr)
        sys.exit(1)
