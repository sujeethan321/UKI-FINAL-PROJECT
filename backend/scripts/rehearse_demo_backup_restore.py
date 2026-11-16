"""Exact-target demo-backup restore rehearsal; read-only unless separately authorized."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = (ROOT / '.server-logs' / 'private-demo-backups').resolve()
TARGET = 'lankapex_demo_restore_verify_20261110b'
ACCOUNT = 'lankapex_demo_restore_b@localhost'
REQUIRED_RIGHTS = {'SELECT', 'INSERT', 'CREATE', 'INDEX', 'REFERENCES', 'ALTER', 'LOCK TABLES'}
PINNED_MANIFEST = 'lankapex_demo_db_20261109T175450Z_a7ace782.backup.json'
PINNED_DUMP = 'lankapex_demo_db_20261109T175450Z_a7ace782.sql'
PINNED_SHA256 = 'ede32b514a47efb4b3b06a206596ff8d23a03f9779cafc39e32099b5a654e685'
MYSQL = Path(r'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe')


def require(value, message):
    if not value:
        raise RuntimeError(message)


def option(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r') + '"'


def checksum(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def sanitized_mysql_failure(stderr, returncode):
    """Report only a numeric client error and a controlled category, never SQL or secrets."""
    output = stderr.decode('utf-8', errors='replace') if isinstance(stderr, bytes) else (stderr or '')
    match = re.search(r'\bERROR\s+(\d{3,5})\s*\(([A-Z0-9]{5})\)', output)
    code = match.group(1) if match else 'unavailable'
    state = match.group(2) if match else 'unavailable'
    categories = {'1044': 'database-access-denied', '1045': 'authentication-denied',
                  '1142': 'table-privilege-denied', '1227': 'privilege-denied',
                  '1064': 'sql-syntax-error', '1452': 'foreign-key-error',
                  '2002': 'connection-error', '2003': 'connection-error'}
    category = categories.get(code, 'mysql-client-error')
    return (f'Restore failed (mysql_exit={returncode}, error={code}, '
            f'sqlstate={state}, category={category}); preserve partial target')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True, choices=[TARGET])
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--confirm-target')
    parser.add_argument('--diagnose', action='store_true',
                        help='read-only inventory of a failed partial target')
    args = parser.parse_args()
    require(not (args.execute and args.diagnose), 'Diagnosis cannot execute a restore')
    require(not args.execute or args.confirm_target == TARGET,
            'Restore execution needs exact --confirm-target and separate authorization')
    require(os.environ.get('APP_ENV') == 'development'
            and os.environ.get('MYSQL_DATABASE') == TARGET
            and os.environ.get('MYSQL_USER') == 'lankapex_demo_restore_b'
            and os.environ.get('MYSQL_HOST') in ('localhost', '127.0.0.1', '::1')
            and os.environ.get('MYSQL_PASSWORD'),
            'Private exact-target restore environment required')
    manifest_path = Path(args.manifest).resolve()
    require(manifest_path.parent == PRIVATE and manifest_path.name == PINNED_MANIFEST,
            'Pinned manifest must be in operator-private demo backup directory')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    require(manifest['database'] == 'lankapex_demo_db'
            and manifest['revision'] == '14c0d3e2f782'
            and manifest['dump_filename'] == PINNED_DUMP
            and manifest['sha256'] == PINNED_SHA256
            and manifest['restored_and_compared'] is False,
            'Unexpected source backup manifest')
    dump = (PRIVATE / manifest['dump_filename']).resolve()
    baseline = (PRIVATE / manifest['before_manifest']).resolve()
    require(dump.parent == PRIVATE and baseline.parent == PRIVATE
            and dump.is_file() and baseline.is_file(), 'Pinned private files missing')
    require(dump.stat().st_size == manifest['size_bytes']
            and checksum(dump) == manifest['sha256'], 'Backup size/checksum differs')
    expected = json.loads(baseline.read_text(encoding='utf-8'))
    require(expected['database'] == 'lankapex_demo_db'
            and expected['revision'] == '14c0d3e2f782'
            and len(expected['row_counts']) == 26, 'Source row baseline differs')
    sql = dump.read_text(encoding='utf-8')
    require(len(re.findall(r'(?m)^CREATE TABLE `[^`]+` \(', sql)) == 26,
            'Backup table-definition count differs')
    require(not re.search(r'(?im)^\s*(?:CREATE|ALTER|DROP)\s+DATABASE\b|^\s*USE\s+|'
                          r'^\s*DROP\s+TABLE\b|\bDEFINER\s*=|'
                          r'\b(?:lankapex_db|lankapex_test_db|lankapex_demo_db)\s*\.', sql),
            'Backup contains target-switching, destructive or cross-schema SQL')
    require(not re.search(r'(?im)^\s*(?:CREATE\s+(?:VIEW|TRIGGER|PROCEDURE|FUNCTION|EVENT)|'
                          r'DROP|REPLACE|UPDATE|DELETE|LOAD\s+DATA|GRANT|REVOKE|'
                          r'SET\s+GLOBAL)\b', sql), 'Backup has unreviewed restore operations')
    require(len(re.findall(r'(?m)^LOCK TABLES\b', sql)) == 26
            and len(re.findall(r'(?m)^UNLOCK TABLES\b', sql)) == 26,
            'Backup lock statement inventory differs')
    for table, count in expected['row_counts'].items():
        require(len(re.findall(r'(?m)^INSERT INTO `' + re.escape(table) + r'` ', sql)) == count,
                'Backup row count differs for ' + table)
    sys.path.insert(0, str(ROOT / 'backend'))
    from sqlalchemy import inspect
    from app.core.config import settings
    from app.core.database import engine
    require(settings.APP_ENV == 'development' and settings.MYSQL_DATABASE == TARGET
            and settings.MYSQL_USER == 'lankapex_demo_restore_b'
            and engine.url.database == TARGET, 'Effective restore target differs')
    try:
        with engine.connect() as conn:
            require(conn.exec_driver_sql('SELECT DATABASE()').scalar_one() == TARGET
                    and conn.exec_driver_sql('SELECT CURRENT_USER()').scalar_one() == ACCOUNT,
                    'Actual restore target/account differs')
            objects = conn.exec_driver_sql(
                'SELECT '
                '(SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s),'
                '(SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=%s),'
                '(SELECT COUNT(*) FROM information_schema.EVENTS WHERE EVENT_SCHEMA=%s),'
                '(SELECT COUNT(*) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=%s)',
                (TARGET, TARGET, TARGET, TARGET)).one()
            if not args.diagnose:
                require(tuple(objects) == (0, 0, 0, 0), 'Restore target is not empty')
            require(conn.exec_driver_sql('SELECT CURRENT_ROLE()').scalar_one() == 'NONE',
                    'Active restore account role requires review')
            grants = conn.exec_driver_sql('SHOW GRANTS FOR CURRENT_USER()').scalars().all()
            rights = set()
            for grant in grants:
                require(not re.match(r'GRANT (?!USAGE\b).* ON \*\.\* TO ', grant),
                        'Global restore privilege refused')
                match = re.match(r'GRANT (.*?) ON `(.*?)`\.\* TO ', grant)
                if match:
                    scope = match[2]
                    require(scope.replace('\\_', '_') == TARGET
                            and not re.search(r'(?<!\\)[_%]', scope),
                            'Restore grant scope is not exact escaped target')
                    rights |= set(match[1].split(', '))
            require(rights == REQUIRED_RIGHTS,
                    'Restore privileges differ from reviewed exact-target grant')
            if args.diagnose:
                tables = sorted(inspect(conn).get_table_names())
                print('DIAGNOSE: exact restore target; tables=' + str(len(tables))
                      + ', routines=' + str(objects[1]) + ', events=' + str(objects[2])
                      + ', triggers=' + str(objects[3]))
                print('DIAGNOSE: table names=' + ', '.join(tables))
                if 'alembic_version' in tables:
                    versions = conn.exec_driver_sql('SELECT version_num FROM alembic_version').scalars().all()
                    print('DIAGNOSE: revision=' + (versions[0] if len(versions) == 1 else 'unexpected'))
                else:
                    print('DIAGNOSE: alembic_version absent')
                print('READ-ONLY DIAGNOSIS COMPLETE; partial target preserved')
                return 0
        print('PASS: exact empty restore target/account/grant and pinned backup checksum')
        if not args.execute:
            print('READ-ONLY RESTORE PREFLIGHT COMPLETE; no restore executed')
            return 0
        require(MYSQL.is_file(), 'MySQL client missing')
        # Recheck immediately before spawning the MySQL restore client. The
        # dedicated account cannot operate on the source or unrelated schemas.
        with engine.connect() as conn:
            require(conn.exec_driver_sql('SELECT DATABASE()').scalar_one() == TARGET
                    and conn.exec_driver_sql('SELECT CURRENT_USER()').scalar_one() == ACCOUNT,
                    'Restore connection identity changed before execution')
            require(not inspect(conn).get_table_names() and not inspect(conn).get_view_names(),
                    'Restore target changed after preflight')
        option_file = PRIVATE / (manifest_path.stem + '.restore-client.cnf')
        require(not option_file.exists(), 'Temporary restore option file already exists')
        try:
            with option_file.open('x', encoding='utf-8', newline='\n') as handle:
                handle.write('[client]\n')
                for key, value in (('host', settings.MYSQL_HOST), ('port', settings.MYSQL_PORT),
                                   ('user', settings.MYSQL_USER), ('password', settings.MYSQL_PASSWORD)):
                    handle.write(key + '=' + option(value) + '\n')
            require(checksum(dump) == manifest['sha256'], 'Backup changed before restore')
            with dump.open('rb') as source:
                result = subprocess.run(
                    [str(MYSQL), '--defaults-extra-file=' + str(option_file),
                     '--binary-mode', '--database=' + TARGET], stdin=source,
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            require(result.returncode == 0,
                    sanitized_mysql_failure(result.stderr, result.returncode))
        finally:
            option_file.unlink(missing_ok=True)
        with engine.connect() as conn:
            require(conn.exec_driver_sql('SELECT DATABASE()').scalar_one() == TARGET
                    and conn.exec_driver_sql('SELECT CURRENT_USER()').scalar_one() == ACCOUNT
                    and conn.exec_driver_sql('SELECT version_num FROM alembic_version').scalars().all()
                    == ['14c0d3e2f782'], 'Restored target/revision differs')
            inspector = inspect(conn)
            require(set(inspector.get_table_names()) == set(expected['row_counts']),
                    'Restored table inventory differs')
            quote = conn.dialect.identifier_preparer.quote
            for table, count in expected['row_counts'].items():
                keys = inspector.get_pk_constraint(table)['constrained_columns']
                cols = [column['name'] for column in inspector.get_columns(table)]
                require(keys, 'Restored table primary key missing')
                rows = conn.exec_driver_sql('SELECT ' + ','.join(quote(c) for c in cols)
                                            + ' FROM ' + quote(table) + ' ORDER BY '
                                            + ','.join(quote(k) for k in keys))
                digest = hashlib.sha256()
                actual = 0
                for row in rows:
                    digest.update(json.dumps(list(row), default=str,
                                             separators=(',', ':')).encode('utf-8') + b'\n')
                    actual += 1
                require(actual == count and digest.hexdigest()
                        == expected['table_fingerprints'][table],
                        'Restored row count/fingerprint differs for ' + table)
            financial = {}
            for label, sql in {
                'ledger_by_type': 'SELECT entry_type, COUNT(*), COALESCE(SUM(amount),0) FROM ledger_entries GROUP BY entry_type ORDER BY entry_type',
                'ledger_by_account': 'SELECT credit_account_id, entry_type, COUNT(*), COALESCE(SUM(amount),0) FROM ledger_entries GROUP BY credit_account_id, entry_type ORDER BY credit_account_id, entry_type',
                'customer_links': 'SELECT business_id, customer_id, user_id FROM customer_profiles ORDER BY customer_id',
                'order_financial_links': 'SELECT order_id, credit_account_id, credit_sale_id, delivery_request_id FROM orders ORDER BY order_id',
            }.items():
                digest = hashlib.sha256()
                for row in conn.exec_driver_sql(sql):
                    digest.update(json.dumps(list(row), default=str,
                                             separators=(',', ':')).encode('utf-8') + b'\n')
                financial[label] = digest.hexdigest()
            require(financial == expected['financial_relationship_fingerprints'],
                    'Restored financial/link fingerprints differ')
            orphans = {}
            for table in expected['row_counts']:
                for fk in inspector.get_foreign_keys(table):
                    source, target = fk['constrained_columns'], fk['referred_columns']
                    parent = fk['referred_table']
                    require(source and target and parent
                            and fk.get('referred_schema') in (None, TARGET),
                            'Unreviewed restored foreign-key metadata')
                    join = ' AND '.join('c.' + quote(a) + '=p.' + quote(b)
                                        for a, b in zip(source, target))
                    present = ' AND '.join('c.' + quote(a) + ' IS NOT NULL' for a in source)
                    statement = ('SELECT COUNT(*) FROM ' + quote(table) + ' c LEFT JOIN '
                                 + quote(parent) + ' p ON ' + join + ' WHERE ' + present
                                 + ' AND p.' + quote(target[0]) + ' IS NULL')
                    orphans[table + ':' + (fk.get('name') or ','.join(source))] = conn.exec_driver_sql(statement).scalar_one()
            require(orphans == expected['foreign_key_orphans']
                    and all(value == 0 for value in orphans.values()),
                    'Restored foreign-key integrity differs')
        print('PASS: 26 restored table fingerprints, financial links, FK integrity and original revision match pinned backup')
    finally:
        engine.dispose()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        if isinstance(exc, RuntimeError):
            print('STOP: ' + str(exc), file=sys.stderr)
        else:
            print('STOP: restore preflight/validation failed (' + type(exc).__name__ + ')',
                  file=sys.stderr)
        sys.exit(1)
