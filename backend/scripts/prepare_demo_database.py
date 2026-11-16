"""Exact-target demo migration preflight; execution needs separate approval.

This script never creates a database or account, changes grants, seeds data,
downgrades, stamps, resets, or retries a partially migrated schema.
"""
import argparse
import os
from pathlib import Path
import re
import sys

TARGET = 'lankapex_demo_db'
MIGRATOR = 'lankapex_demo_migrator@localhost'
HEAD = '14c0d3e2f782'
ROOT = Path(__file__).resolve().parents[2]
REQUIRED = {'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER',
            'INDEX', 'REFERENCES'}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def grant_scope(grants, partial_revokes):
    privileges = set()
    broad = False
    for grant in grants:
        if re.match(r'GRANT (?!USAGE\b).* ON \*\.\* TO ', grant):
            broad = True
        match = re.match(r'GRANT (.*?) ON `(.*?)`\.\* TO ', grant)
        if not match:
            continue
        scope = match[2]
        if scope.replace('\\_', '_') == TARGET:
            if not partial_revokes and re.search(r'(?<!\\)[_%]', scope):
                broad = True
            else:
                found = set(match[1].split(', '))
                if 'ALL PRIVILEGES' in found or 'GRANT OPTION' in found:
                    broad = True
                privileges |= found
        elif scope.lower().startswith('lankapex'):
            broad = True
    return privileges, broad


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True, choices=[TARGET])
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--confirm-target')
    args = parser.parse_args()
    require(not args.execute or args.confirm_target == TARGET,
            'Execution requires exact --confirm-target and separate approval')
    require(os.environ.get('APP_ENV', 'development') == 'development',
            'APP_ENV must be development')
    require(os.environ.get('MYSQL_DATABASE') == TARGET,
            'Explicit MYSQL_DATABASE=lankapex_demo_db required; normal dotenv is not edited')
    require(os.environ.get('MYSQL_USER') == 'lankapex_demo_migrator',
            'Explicit demo migrator account required')
    require(os.environ.get('MYSQL_PASSWORD'),
            'Demo migrator password must be supplied privately in process environment')
    sys.path.insert(0, str(ROOT / 'backend'))

    from sqlalchemy import event, inspect
    from sqlalchemy.engine import Engine
    from alembic import command
    from alembic.autogenerate import compare_metadata
    from alembic.config import Config
    from alembic.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from app.core.config import settings
    from app.core.database import Base, engine
    import app.models  # noqa: F401

    require(settings.APP_ENV == 'development' and settings.MYSQL_DATABASE == TARGET,
            'Effective settings do not identify demo database')
    require(settings.MYSQL_USER == 'lankapex_demo_migrator' and
            settings.MYSQL_HOST in ('localhost', '127.0.0.1', '::1') and
            engine.url.database == TARGET, 'Unexpected demo connection configuration')
    cfg = Config(str(ROOT / 'backend/alembic.ini'))
    cfg.set_main_option('script_location', str(ROOT / 'backend/alembic'))
    graph = ScriptDirectory.from_config(cfg)
    revisions = list(graph.walk_revisions())
    require(graph.get_heads() == [HEAD] and graph.get_bases() == ['79d8d51548c6']
            and len(revisions) == 14 and len(Base.metadata.tables) == 25,
            'Reviewed migration graph or models changed')

    def do_connect(dialect, record, args_, kwargs):
        require(kwargs.get('database', kwargs.get('db')) == TARGET,
                'DBAPI target differs from exact demo database')

    def engine_connect(conn):
        require(conn.engine.url.database == TARGET,
                'Connection to a non-demo database refused')

    def sql_gate(conn, cursor, statement, parameters, context, executemany):
        require(conn.engine.url.database == TARGET,
                'SQL on a non-demo engine refused')
        sql = statement.strip().upper()
        require(not re.search(r'\b(?:CREATE|ALTER|DROP)\s+DATABASE\b|'
                       r'\b(?:USE|GRANT|REVOKE|TRUNCATE|SET\s+GLOBAL)\b', sql),
                'Database/global/reset statement refused')
        require(not re.search(r'\b(?:lankapex_db|lankapex_test_db|'
                       r'lankapex_migration_verify_[a-z0-9_]+)\s*\.', statement,
                       re.IGNORECASE), 'Cross-database statement refused')
        if not args.execute:
            require(sql.startswith(('SELECT ', 'SHOW ', 'DESCRIBE ')),
                    'Preflight is read-only')

    event.listen(Engine, 'do_connect', do_connect)
    event.listen(Engine, 'engine_connect', engine_connect)
    event.listen(Engine, 'before_cursor_execute', sql_gate)
    try:
        with engine.connect() as conn:
            require(conn.exec_driver_sql('SELECT DATABASE()').scalar_one() == TARGET,
                    'SELECT DATABASE() differs from demo target')
            require(conn.exec_driver_sql('SELECT CURRENT_USER()').scalar_one() == MIGRATOR,
                    'Authenticated account differs from exact demo migrator')
            version, partial, mode, fk = conn.exec_driver_sql(
                'SELECT VERSION(), @@GLOBAL.partial_revokes, @@SESSION.sql_mode, '
                '@@SESSION.foreign_key_checks').one()
            require(str(version).startswith('8.0.') and fk == 1 and
                    'STRICT_TRANS_TABLES' in mode, 'MySQL version/mode/FK prerequisite failed')
            require(conn.exec_driver_sql('SELECT CURRENT_ROLE()').scalar_one() == 'NONE',
                    'Active role privileges require review')
            counts = conn.exec_driver_sql(
                'SELECT '
                '(SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s),'
                '(SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=%s),'
                '(SELECT COUNT(*) FROM information_schema.EVENTS WHERE EVENT_SCHEMA=%s),'
                '(SELECT COUNT(*) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=%s)',
                (TARGET, TARGET, TARGET, TARGET)).one()
            require(tuple(counts) == (0, 0, 0, 0),
                    'Demo schema has objects; no reset or retry permitted')
            grants = conn.exec_driver_sql('SHOW GRANTS FOR CURRENT_USER()').scalars().all()
            privileges, broad = grant_scope(grants, partial)
            require(not broad and REQUIRED <= privileges,
                    'Exact escaped demo-only grant with required privileges not verified')
            print('PASS: exact demo target/account, empty schema, scoped grants')
            print('PASS: MySQL 8.0 strict/FK settings, 14 revisions, 25 models; head ' + HEAD)
            if not args.execute:
                print('READ-ONLY PREFLIGHT COMPLETE; no migration executed')
                return 0
            conn.commit()
            require(conn.exec_driver_sql('SELECT GET_LOCK(%s,0)',
                ('lankapex_demo_db_migration',)).scalar_one() == 1,
                'Demo migration lock unavailable')
            try:
                require(conn.exec_driver_sql('SELECT DATABASE()').scalar_one() == TARGET and
                        not inspect(conn).get_table_names() and
                        not inspect(conn).get_view_names(),
                        'Demo target changed before migration')
                conn.commit()
                # env.py uses the normal engine. Global connection guards above
                # reject any DBAPI connection not bound to the exact demo schema.
                for revision in ('c9d5e8f7a237', 'd0e6f9a8b348',
                                 'e1f7a0b9c459', 'f2a8b1c0d560',
                                 '03b9c2d1e671', HEAD):
                    command.upgrade(cfg, revision)
                    # Each Alembic invocation uses another connection. Do not
                    # retain a REPEATABLE READ snapshot across those stages.
                    conn.commit()
                    recorded = conn.exec_driver_sql(
                        'SELECT version_num FROM alembic_version').scalars().all()
                    require(recorded == [revision],
                            'Stage revision mismatch; preserve partial schema')
                    conn.commit()
                    print('Applied demo stage: ' + revision)
                actual = set(inspect(conn).get_table_names())
                require(actual == set(Base.metadata.tables) | {'alembic_version'},
                        'Final table inventory mismatch')
                require(not compare_metadata(MigrationContext.configure(
                    conn, opts={'compare_type': True}), Base.metadata),
                    'Final model/schema comparison failed')
                for table in Base.metadata.sorted_tables:
                    require(conn.exec_driver_sql('SELECT COUNT(*) FROM `' + table.name + '`')
                            .scalar_one() == 0, 'Unexpected application rows')
                print('PASS: 25 empty application tables plus alembic_version at ' + HEAD)
            finally:
                conn.exec_driver_sql('SELECT RELEASE_LOCK(%s)',
                                     ('lankapex_demo_db_migration',))
                conn.commit()
    finally:
        event.remove(Engine, 'before_cursor_execute', sql_gate)
        event.remove(Engine, 'engine_connect', engine_connect)
        event.remove(Engine, 'do_connect', do_connect)
        engine.dispose()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        # Never print DB URLs, SQL, bound parameters, grants or credentials.
        if isinstance(exc, RuntimeError):
            print('STOP: ' + str(exc), file=sys.stderr)
        else:
            original = getattr(exc, 'orig', None)
            code = getattr(original, 'args', [None])[0]
            print('STOP: ' + type(exc).__name__ + '; MySQL code=' + str(code), file=sys.stderr)
        sys.exit(1)
