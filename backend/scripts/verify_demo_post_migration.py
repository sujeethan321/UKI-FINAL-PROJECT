"""Read-only integrity check of the exact upgraded demo database."""
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = (ROOT / '.server-logs' / 'private-demo-backups').resolve()
TARGET = 'lankapex_demo_db'
ACCOUNT = 'lankapex_demo_app@localhost'
OLD = '14c0d3e2f782'
HEAD = '6e3f2c1a9b04'
NEW = 'customer_link_invitations'
MANIFEST = 'lankapex_demo_db_20261109T175450Z_a7ace782.backup.json'
DUMP = 'lankapex_demo_db_20261109T175450Z_a7ace782.sql'
SHA256 = 'ede32b514a47efb4b3b06a206596ff8d23a03f9779cafc39e32099b5a654e685'
FIELDS = ('row_counts', 'table_fingerprints',
          'financial_relationship_fingerprints', 'foreign_key_orphans')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_only_sql(statement):
    sql = statement.strip().upper()
    if re.search(r'\bLANKAPEX_[A-Z0-9_]+\s*\.', sql):
        return False
    return sql.startswith(('SELECT ', 'SHOW ', 'DESCRIBE ')) or sql in {
        'SET SESSION TRANSACTION READ ONLY',
        'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ',
        'START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY',
    }


def private_json(name):
    path = (PRIVATE / name).resolve()
    require(path.parent == PRIVATE and path.suffix == '.json' and path.is_file(),
            'private evidence missing or out of scope')
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ValueError('private evidence format differs') from None


def pinned_baseline():
    manifest = private_json(MANIFEST)
    require(manifest.get('database') == TARGET and manifest.get('revision') == OLD
            and manifest.get('dump_filename') == DUMP and manifest.get('sha256') == SHA256
            and type(manifest.get('size_bytes')) is int
            and isinstance(manifest.get('before_manifest'), str)
            and isinstance(manifest.get('after_manifest'), str),
            'pinned backup identity differs')
    dump = (PRIVATE / DUMP).resolve()
    require(dump.parent == PRIVATE and dump.is_file()
            and dump.stat().st_size == manifest['size_bytes'], 'pinned backup size differs')
    with dump.open('rb') as source:
        require(hashlib.file_digest(source, 'sha256').hexdigest() == SHA256,
                'pinned backup checksum differs')
    before_name, after_name = manifest['before_manifest'], manifest['after_manifest']
    require(before_name.endswith('.before.json') and after_name.endswith('.after.json')
            and before_name != after_name, 'pinned baseline names differ')
    before, after = private_json(before_name), private_json(after_name)
    for baseline in (before, after):
        require(baseline.get('database') == TARGET
                and baseline.get('account') == 'lankapex_demo_migrator@localhost'
                and baseline.get('revision') == OLD, 'pinned baseline identity differs')
        require(all(isinstance(baseline.get(field), dict) for field in FIELDS),
                'pinned baseline fields missing')
        require(len(baseline['row_counts']) == 26
                and baseline['row_counts'].keys() == baseline['table_fingerprints'].keys()
                and len(baseline['financial_relationship_fingerprints']) == 4
                and len(baseline['foreign_key_orphans']) == 53
                and baseline['row_counts'].get('alembic_version') == 1,
                'pinned baseline inventory differs')
        require(all(type(value) is int and value >= 0
                    for value in baseline['row_counts'].values())
                and all(type(value) is int and value == 0
                        for value in baseline['foreign_key_orphans'].values())
                and all(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value)
                        for field in ('table_fingerprints', 'financial_relationship_fingerprints')
                        for value in baseline[field].values()),
                'pinned baseline value format differs')
    require(all(before[field] == after[field] for field in FIELDS),
            'pinned before/after evidence differs')
    return before


def verify_snapshot(expected, actual):
    require(actual.get('database') == TARGET and actual.get('account') == ACCOUNT
            and actual.get('revision') == HEAD, 'post-migration identity/revision differs')
    require(actual.get('table_count') == 27 and actual.get('invitation_count') == 0,
            'post-migration table inventory or invitation count differs')
    original = set(expected['row_counts']) - {'alembic_version'}
    require(len(original) == 25, 'pinned application table inventory differs')
    for field in ('row_counts', 'table_fingerprints'):
        require(isinstance(actual.get(field), dict)
                and set(actual[field]) == original
                and actual[field] == {name: expected[field][name] for name in original},
                'original ' + field + ' differs')
    for field in ('financial_relationship_fingerprints', 'foreign_key_orphans'):
        require(isinstance(actual.get(field), dict)
                and actual[field] == expected[field], field + ' differs')
    require(len(actual['foreign_key_orphans']) == 53
            and all(type(value) is int and value == 0
                    for value in actual['foreign_key_orphans'].values()),
            'foreign-key orphan count differs')


def main():
    require(os.environ.get('APP_ENV') == 'development'
            and os.environ.get('MYSQL_DATABASE') == TARGET
            and os.environ.get('MYSQL_USER') == 'lankapex_demo_app'
            and os.environ.get('MYSQL_HOST') in ('localhost', '127.0.0.1', '::1')
            and os.environ.get('MYSQL_PASSWORD'), 'exact private demo runtime environment required')
    expected = pinned_baseline()
    sys.path.insert(0, str(ROOT / 'backend'))
    from sqlalchemy import event, inspect
    from app.core.config import settings
    from app.core.database import Base, engine
    from capture_demo_baseline import digest_rows
    import app.models  # noqa: F401

    require(settings.APP_ENV == 'development' and settings.MYSQL_DATABASE == TARGET
            and settings.MYSQL_USER == 'lankapex_demo_app'
            and engine.url.database == TARGET and engine.url.host in ('localhost', '127.0.0.1', '::1'),
            'effective demo target differs')

    def sql_gate(conn, cursor, statement, parameters, context, executemany):
        require(conn.engine is engine and conn.engine.url.database == TARGET
                and read_only_sql(statement), 'write or cross-database SQL refused')

    event.listen(engine, 'before_cursor_execute', sql_gate)
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql('SET SESSION TRANSACTION READ ONLY')
            conn.commit()
            conn.exec_driver_sql('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            conn.exec_driver_sql('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY')
            try:
                require(conn.exec_driver_sql('SELECT DATABASE()').scalar_one() == TARGET
                        and conn.exec_driver_sql('SELECT CURRENT_USER()').scalar_one() == ACCOUNT,
                        'actual demo identity differs')
                require(conn.exec_driver_sql('SELECT CURRENT_ROLE()').scalar_one() == 'NONE',
                        'active runtime role differs')
                rights = set()
                for grant in conn.exec_driver_sql('SHOW GRANTS FOR CURRENT_USER()').scalars():
                    if re.match(r'GRANT USAGE ON \*\.\* TO ', grant):
                        require('GRANT OPTION' not in grant,
                                'global runtime grant differs')
                        continue
                    match = re.match(r'GRANT (.*?) ON `(.*?)`\.\* TO ', grant)
                    require(match is not None and match[2].replace('\\_', '_') == TARGET
                            and not re.search(r'(?<!\\)[_%]', match[2])
                            and 'GRANT OPTION' not in grant,
                            'runtime grant scope differs')
                    rights.update(match[1].split(', '))
                require(rights == {'SELECT', 'INSERT', 'UPDATE', 'DELETE'},
                        'runtime privilege set differs')
                revision = conn.exec_driver_sql('SELECT version_num FROM alembic_version').scalars().all()
                require(revision == [HEAD], 'post-migration revision differs')
                inspector = inspect(conn)
                names = set(inspector.get_table_names())
                require(names == set(Base.metadata.tables) | {'alembic_version'}
                        and names == set(expected['row_counts']) | {NEW}
                        and len(names) == 27, 'post-migration table inventory differs')
                invitation_count = conn.exec_driver_sql(
                    'SELECT COUNT(*) FROM customer_link_invitations').scalar_one()
                quote = conn.dialect.identifier_preparer.quote
                counts, hashes, orphans = {}, {}, {}
                for name in sorted(set(expected['row_counts']) - {'alembic_version'}):
                    keys = inspector.get_pk_constraint(name)['constrained_columns']
                    columns = [column['name'] for column in inspector.get_columns(name)]
                    require(keys and columns, 'original table metadata differs')
                    statement = ('SELECT ' + ','.join(quote(column) for column in columns)
                                 + ' FROM ' + quote(name) + ' ORDER BY '
                                 + ','.join(quote(key) for key in keys))
                    counts[name], hashes[name] = digest_rows(conn.exec_driver_sql(statement))
                for name in sorted(expected['row_counts']):
                    for fk in inspector.get_foreign_keys(name):
                        source, target = fk['constrained_columns'], fk['referred_columns']
                        parent = fk['referred_table']
                        require(source and target and parent
                                and fk.get('referred_schema') in (None, TARGET),
                                'foreign-key metadata differs')
                        join = ' AND '.join('c.' + quote(a) + '=p.' + quote(b)
                                            for a, b in zip(source, target))
                        present = ' AND '.join('c.' + quote(a) + ' IS NOT NULL' for a in source)
                        statement = ('SELECT COUNT(*) FROM ' + quote(name) + ' c LEFT JOIN '
                                     + quote(parent) + ' p ON ' + join + ' WHERE ' + present
                                     + ' AND p.' + quote(target[0]) + ' IS NULL')
                        orphans[name + ':' + (fk.get('name') or ','.join(source))] = (
                            conn.exec_driver_sql(statement).scalar_one())
                financial = {}
                for label, statement in {
                    'ledger_by_type': 'SELECT entry_type, COUNT(*), COALESCE(SUM(amount),0) FROM ledger_entries GROUP BY entry_type ORDER BY entry_type',
                    'ledger_by_account': 'SELECT credit_account_id, entry_type, COUNT(*), COALESCE(SUM(amount),0) FROM ledger_entries GROUP BY credit_account_id, entry_type ORDER BY credit_account_id, entry_type',
                    'customer_links': 'SELECT business_id, customer_id, user_id FROM customer_profiles ORDER BY customer_id',
                    'order_financial_links': 'SELECT order_id, credit_account_id, credit_sale_id, delivery_request_id FROM orders ORDER BY order_id',
                }.items():
                    _, financial[label] = digest_rows(conn.exec_driver_sql(statement))
                verify_snapshot(expected, {
                    'database': TARGET, 'account': ACCOUNT, 'revision': revision[0],
                    'table_count': len(names), 'invitation_count': invitation_count,
                    'row_counts': counts, 'table_fingerprints': hashes,
                    'financial_relationship_fingerprints': financial,
                    'foreign_key_orphans': orphans,
                })
            finally:
                conn.rollback()
    finally:
        event.remove(engine, 'before_cursor_execute', sql_gate)
        engine.dispose()
    print('PASS: exact demo target, revision, 27 tables and empty invitation table')
    print('PASS: 25 original table counts/fingerprints, four financial links and 53 zero-orphan checks match pinned backup')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print('STOP: guarded demo post-migration verification failed ('
              + (str(exc) if isinstance(exc, ValueError) else type(exc).__name__) + ')',
              file=sys.stderr)
        sys.exit(1)
