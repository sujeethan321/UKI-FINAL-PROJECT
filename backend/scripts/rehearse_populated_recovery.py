"""Exact-target populated recovery rehearsal. Default is read-only preflight.

Restore and upgrade are separate, explicitly confirmed invocations. Never retry,
reset, downgrade, stamp, seed, or clean up a failed partial target automatically.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PROFILES = {
    'lankapex_migration_verify_recovery20261109': (
        'lankapex_db_20261109T001844+0530.sql',
        '9253fd3577d5c2bff37a4e5a08d08d5d6112190cd74775fe6d7aa8d6345477be'),
    'lankapex_migration_verify_recovery20261109b': (
        'lankapex_db_20261109T105502+0530.sql',
        '1588a78f4e5b5e95d9556233d79241991ea063224fd6e73da363ae545e78245e'),
}
TARGET = 'lankapex_migration_verify_recovery20261109'
SOURCE = 'c9d5e8f7a237'
HEAD = '14c0d3e2f782'
TAIL = ['d0e6f9a8b348', 'e1f7a0b9c459', 'f2a8b1c0d560',
        '03b9c2d1e671', HEAD]
BACKUP = ROOT / '.server-logs/private-backups/lankapex_db_20261109T001844+0530.sql'
MANIFEST = BACKUP.with_suffix('.manifest.json')
VALIDATION = BACKUP.with_suffix('.validation.json')
SHA256 = '9253fd3577d5c2bff37a4e5a08d08d5d6112190cd74775fe6d7aa8d6345477be'
MYSQL = Path(r'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe')


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def quote_option(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r') + '"'


def inspect_dump():
    """Review this pinned dump's statement forms without reporting row contents."""
    raw = BACKUP.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == SHA256, 'Backup bytes changed')
    sql = raw.decode('utf-8')
    # Ignore ordinary comments and string/quoted-identifier bodies while preserving
    # SQL keywords, identifiers, and executable MySQL versioned comments.
    clean = []
    i = 0
    while i < len(sql):
        if sql.startswith('-- ', i) or sql.startswith('#', i):
            end = sql.find('\n', i)
            i = len(sql) if end < 0 else end
        elif sql.startswith('/*', i) and not sql.startswith('/*!', i):
            end = sql.find('*/', i + 2)
            require(end >= 0, 'Unclosed SQL comment')
            i = end + 2
        elif sql[i] in "'\"`":
            quote = sql[i]
            clean.append(quote)
            i += 1
            while i < len(sql):
                if sql[i] == '\\':
                    i += 2
                elif sql[i] == quote:
                    if i + 1 < len(sql) and sql[i + 1] == quote:
                        i += 2
                    else:
                        i += 1
                        break
                else:
                    i += 1
            else:
                raise RuntimeError('Unclosed SQL quote')
            clean.append(quote)
        else:
            clean.append(sql[i])
            i += 1
    text = ''.join(clean)
    require(not re.search(r'\b(?:CREATE|ALTER|DROP)\s+DATABASE\b|\bUSE\s+|\bDEFINER\b|'
                          r'\b(?:GRANT|REVOKE|TRUNCATE|LOAD\s+DATA|SET\s+GLOBAL)\b|'
                          r'\b(?:lankapex_db|lankapex_test_db)\s*\.', text, re.I),
            'Dump contains a database-switching, privileged or cross-database statement')
    require(not re.search(r'(?i)\b(?:CREATE\s+(?:USER|TRIGGER|EVENT|PROCEDURE|FUNCTION|VIEW)|'
                          r'DROP\s+TABLE|INSERT\s+INTO\s+`?[^`\s;]+`?\s*\.)', text),
            'Dump contains an unexpected stored object or qualified write')
    require(len(re.findall(r'(?m)^CREATE TABLE `[^`]+` \(', sql)) == 18,
            'Expected 18 CREATE TABLE statements')
    require(len(re.findall(r'(?m)^INSERT INTO `ledger_entries` ', sql)) == 6,
            'Expected six ledger rows in backup')
    require(len(re.findall(r'(?m)^INSERT INTO `alembic_version` ', sql)) == 1,
            'Expected one Alembic row in backup')
    return raw


def snapshot(conn, names):
    """Private row fingerprints; never print rows or monetary values."""
    from sqlalchemy import inspect
    inspector = inspect(conn)
    quote = conn.dialect.identifier_preparer.quote
    hashes, counts = {}, {}
    for name in names:
        keys = inspector.get_pk_constraint(name)['constrained_columns']
        require(keys, 'Missing table primary key')
        rows = conn.exec_driver_sql('SELECT * FROM ' + quote(name) + ' ORDER BY ' +
                                    ','.join(quote(key) for key in keys)).all()
        counts[name] = len(rows)
        hashes[name] = hashlib.sha256(json.dumps([list(row) for row in rows],
            default=str, separators=(',', ':')).encode()).hexdigest()
    return counts, hashes


def preserved(conn, baseline):
    names = sorted(name for name in baseline['row_counts'] if name != 'alembic_version')
    counts, hashes = snapshot(conn, names)
    require(counts == {name: baseline['row_counts'][name] for name in names},
            'Restored row counts differ from protected backup baseline')
    require(hashes == {name: baseline['table_fingerprints'][name] for name in names},
            'Restored row fingerprints differ from protected backup baseline')
    require(counts['ledger_entries'] == 6, 'Six original ledger entries not preserved')
    types = dict(conn.exec_driver_sql(
        'SELECT entry_type, COUNT(*) FROM ledger_entries GROUP BY entry_type').all())
    require(types == {'credit_sale': 4, 'repayment': 2},
            'Original ledger type counts differ')
    return hashes


def restore(settings, raw):
    # The exact bytes were checked immediately before this call. Recheck after
    # opening the file to catch modification between preflight and execution.
    require(hashlib.sha256(BACKUP.read_bytes()).hexdigest() == SHA256,
            'Backup changed before restore')
    private = BACKUP.parent
    option = private / 'phase35-recovery-client.cnf'
    require(not option.exists(), 'Temporary credential file already exists')
    require(MYSQL.is_file(), 'Expected MySQL client missing')
    lines = ['[client]', 'host=' + quote_option(settings.MYSQL_HOST),
             'port=' + str(settings.MYSQL_PORT),
             'user=' + quote_option(settings.MYSQL_USER),
             'password=' + quote_option(settings.MYSQL_PASSWORD),
             'ssl-mode=' + ('VERIFY_IDENTITY' if settings.MYSQL_SSL_CA else 'PREFERRED')]
    if settings.MYSQL_SSL_CA:
        lines.append('ssl-ca=' + quote_option(settings.MYSQL_SSL_CA))
    try:
        with option.open('x', encoding='utf-8', newline='\n') as handle:
            handle.write('\n'.join(lines) + '\n')
        cmd = [str(MYSQL), '--defaults-file=' + str(option), '--binary-mode',
               '--default-character-set=utf8mb4', '--database=' + TARGET]
        with BACKUP.open('rb') as source:
            result = subprocess.run(cmd, stdin=source, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.PIPE, timeout=120, check=False)
        require(result.returncode == 0 and not result.stderr,
                'Restore client failed; preserve partial target and inspect private error')
    finally:
        option.unlink(missing_ok=True)


def main():
    global TARGET, BACKUP, MANIFEST, VALIDATION, SHA256
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True, choices=sorted(PROFILES))
    parser.add_argument('--stage', choices=['preflight', 'restore', 'upgrade'], default='preflight')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--confirm-target')
    args = parser.parse_args()
    TARGET = args.database
    backup_name, SHA256 = PROFILES[TARGET]
    BACKUP = ROOT / '.server-logs/private-backups' / backup_name
    MANIFEST = BACKUP.with_suffix('.manifest.json')
    VALIDATION = BACKUP.with_suffix('.validation.json')
    require(args.stage == 'preflight' or (args.execute and args.confirm_target == TARGET),
            'Execution requires --execute and exact --confirm-target')
    require(args.stage != 'preflight' or not args.execute, 'Preflight must remain read-only')
    require(os.environ.get('APP_ENV') != 'production', 'Production invocation refused')
    os.environ['APP_ENV'] = 'testing'
    os.environ['MYSQL_DATABASE'] = 'lankapex_test_db'
    sys.path.insert(0, str(ROOT / 'backend'))
    from sqlalchemy import create_engine, event, inspect
    from sqlalchemy.engine import Engine
    from alembic import command
    from alembic.autogenerate import compare_metadata
    from alembic.config import Config
    from alembic.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from app.core.config import settings
    from app.core.database import Base, connection_options, engine as normal_engine
    from app.core.db_maintenance import validate_target, verify_identity
    from app.services.backup_manifest import read_manifest
    import app.models  # noqa: F401

    validate_target(settings.APP_ENV, TARGET, 'migration')
    require(settings.MYSQL_HOST in ('localhost', '127.0.0.1', '::1') and
            settings.MYSQL_USER == 'lankapex_app' and
            normal_engine.url.database == 'lankapex_test_db', 'Unexpected local configuration')
    manifest = read_manifest(MANIFEST, BACKUP)
    require(manifest['sha256'] == SHA256 and manifest['schema_revision'] == SOURCE and
            manifest['source_database'] == 'lankapex_db' and
            manifest['source_environment'] == 'development' and
            manifest['mysql_version'] == '8.0.46', 'Source backup identity differs')
    validation = json.loads(VALIDATION.read_text(encoding='utf-8'))
    baseline = validation['source_baseline']
    require(validation['status'] == 'BACKUP_FILE_VALIDATED_NOT_RESTORED' and
            baseline['revision'] == [SOURCE] and baseline['row_counts']['ledger_entries'] == 6 and
            validation['ledger_type_counts'] == {'credit_sale': 4, 'repayment': 2},
            'Protected backup baseline differs')
    raw = inspect_dump()
    cfg = Config(str(ROOT / 'backend/alembic.ini'))
    cfg.set_main_option('script_location', str(ROOT / 'backend/alembic'))
    graph = ScriptDirectory.from_config(cfg)
    require(graph.get_heads() == [HEAD] and len(list(graph.walk_revisions())) == 14 and
            [r.revision for r in reversed(list(graph.iterate_revisions(HEAD, SOURCE)))] == TAIL and
            len(Base.metadata.tables) == 25, 'Reviewed migration chain/models differ')

    def connect_gate(dialect, record, positional, keyword):
        require(keyword.get('database', keyword.get('db')) == TARGET,
                'Connection to a different database refused before DBAPI connect')
    event.listen(Engine, 'do_connect', connect_gate)
    isolated = create_engine(normal_engine.url.set(database=TARGET),
                             hide_parameters=True, echo=False,
                             connect_args=connection_options(settings))
    def sql_gate(conn, cursor, statement, parameters, context, executemany):
        require(conn.engine is isolated and conn.engine.url.database == TARGET,
                'SQL on a different engine refused')
        require(not re.search(r'\b(?:CREATE|ALTER|DROP)\s+DATABASE\b|\b(?:USE|GRANT|REVOKE|TRUNCATE)\b|'
                              r'\b(?:lankapex_db|lankapex_test_db)\s*\.', statement, re.I),
                'Database/global/cross-database SQL refused')
        if args.stage == 'preflight':
            require(statement.lstrip().upper().startswith(('SELECT ', 'SHOW ')) or
                    statement.strip().upper() == 'SET SESSION TRANSACTION READ ONLY',
                    'Write refused in read-only preflight')
    event.listen(isolated, 'before_cursor_execute', sql_gate)
    try:
        with isolated.connect() as conn:
            if args.stage == 'preflight':
                conn.exec_driver_sql('SET SESSION TRANSACTION READ ONLY')
                conn.commit()
            verify_identity(conn, TARGET)
            require(conn.exec_driver_sql('SELECT CURRENT_USER()').scalar_one() ==
                    'lankapex_app@localhost', 'Unexpected MySQL identity')
            version, mode, fk, partial = conn.exec_driver_sql(
                'SELECT VERSION(), @@SESSION.sql_mode, @@SESSION.foreign_key_checks, @@GLOBAL.partial_revokes').one()
            require(version == '8.0.46' and 'STRICT_TRANS_TABLES' in mode and fk == 1,
                    'MySQL version/mode/FK setting differs')
            require(conn.exec_driver_sql('SELECT CURRENT_ROLE()').scalar_one() == 'NONE',
                    'Active role grants require review')
            grants = conn.exec_driver_sql('SHOW GRANTS FOR CURRENT_USER()').scalars().all()
            exact = set()
            for grant in grants:
                match = re.match(r'GRANT (.*?) ON `(.*?)`\.\* TO ', grant)
                if match and match[2].replace('\\_', '_') == TARGET:
                    require(partial or not re.search(r'(?<!\\)[_%]', match[2]),
                            'Grant pattern has wildcard scope')
                    exact.update(match[1].split(', '))
            required = {'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER',
                        'DROP', 'INDEX', 'REFERENCES'}
            require(required <= exact or 'ALL PRIVILEGES' in exact,
                    'Exact target privileges insufficient')
            objects = conn.exec_driver_sql(
                'SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s', (TARGET,)).scalar_one()
            routines = conn.exec_driver_sql(
                'SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=%s', (TARGET,)).scalar_one()
            events = conn.exec_driver_sql(
                'SELECT COUNT(*) FROM information_schema.EVENTS WHERE EVENT_SCHEMA=%s', (TARGET,)).scalar_one()
            if args.stage in ('preflight', 'restore'):
                require(objects == routines == events == 0, 'Recovery target is not empty')
            if args.stage == 'preflight':
                print('PASS: exact isolated identity, empty target, grants, backup SHA/SQL and five-revision graph')
                print('READ-ONLY PREFLIGHT ONLY; no restore or migration executed')
                return
            conn.commit()
            require(conn.exec_driver_sql('SELECT GET_LOCK(%s,0)', (TARGET + '_rehearsal',)).scalar_one() == 1,
                    'Another rehearsal holds the advisory lock')
            try:
                verify_identity(conn, TARGET)
                if args.stage == 'restore':
                    require(not inspect(conn).get_table_names() and not inspect(conn).get_view_names(),
                            'Recovery target changed during preflight')
                    restore(settings, raw)
                    conn.commit()
                    require(set(inspect(conn).get_table_names()) == set(baseline['row_counts']),
                            'Restored table inventory differs')
                    require(conn.exec_driver_sql('SELECT version_num FROM alembic_version').scalars().all() == [SOURCE],
                            'Restored Alembic revision differs')
                    preserved(conn, baseline)
                    print('PASS: restored 17 application tables plus version; six ledger entries and original rows preserved')
                else:
                    require(set(inspect(conn).get_table_names()) == set(baseline['row_counts']),
                            'Legacy restored table inventory differs')
                    require(conn.exec_driver_sql('SELECT version_num FROM alembic_version').scalars().all() == [SOURCE],
                            'Expected restored source revision')
                    preserved(conn, baseline)
                    conn.exec_driver_sql("SET SESSION time_zone = '+00:00'")
                    conn.commit()
                    cfg.attributes['connection'] = conn
                    for revision in TAIL:
                        verify_identity(conn, TARGET)
                        conn.commit()
                        command.upgrade(cfg, revision)
                        conn.commit()
                        require(conn.exec_driver_sql('SELECT version_num FROM alembic_version').scalars().all() == [revision],
                                'Unexpected revision after stage; preserve partial target')
                        print('Applied isolated stage: ' + revision)
                    require(set(inspect(conn).get_table_names()) == set(Base.metadata.tables) | {'alembic_version'},
                            'Final table inventory differs')
                    require(not compare_metadata(MigrationContext.configure(conn, opts={'compare_type': True}), Base.metadata),
                            'Migration/model comparison differs')
                    preserved(conn, baseline)
                    new_names = set(Base.metadata.tables) - set(baseline['row_counts'])
                    require(all(conn.exec_driver_sql('SELECT COUNT(*) FROM `' + name + '`').scalar_one() == 0
                                for name in new_names), 'New tables contain unexpected rows')
                    print('PASS: 25 application tables, head revision, model parity and all original rows preserved')
            finally:
                conn.exec_driver_sql('SELECT RELEASE_LOCK(%s)', (TARGET + '_rehearsal',))
                conn.commit()
    finally:
        isolated.dispose()
        normal_engine.dispose()
        event.remove(Engine, 'do_connect', connect_gate)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Never display SQL, credentials, connection URLs, raw rows or client stderr.
        if isinstance(error, RuntimeError):
            print('STOP: ' + str(error), file=sys.stderr)
        else:
            original = getattr(error, 'orig', None)
            code = getattr(original, 'args', [None])[0]
            print('STOP: ' + type(error).__name__ + '; MySQL code=' + str(code), file=sys.stderr)
        sys.exit(1)
