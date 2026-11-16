"""Dedicated-target preflight by default. --execute requires separate approval.

No pytest fixtures, normal engine connections, data seeding, reset or downgrade.
"""
import argparse
import os
from pathlib import Path
import re
import sys

TARGET = 'lankapex_migration_verify_20261107'
HEAD = '14c0d3e2f782'
ACCOUNT = 'lankapex_app@localhost'
REQUIRED = {'SELECT', 'INSERT', 'UPDATE', 'CREATE', 'ALTER', 'INDEX', 'REFERENCES'}
ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True, choices=[TARGET])
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--confirm-target')
    args = parser.parse_args()
    require(not args.execute or args.confirm_target == TARGET,
            'Execution requires the exact --confirm-target and separate user approval')
    require(os.environ.get('APP_ENV') != 'production', 'Production invocation refused')
    # Child-process only. Normal Settings remain valid; its test engine is never
    # connected. Files and the calling PowerShell environment remain untouched.
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
    from app.core.database import Base, engine as normal_engine, connection_options
    from app.core.db_maintenance import validate_target, verify_identity
    import app.models  # noqa: F401

    validate_target(settings.APP_ENV, TARGET, 'migration')
    require(settings.MYSQL_HOST in ('localhost', '127.0.0.1', '::1'), 'Local host required')
    require(normal_engine.url.database == 'lankapex_test_db', 'Unexpected normal settings')
    cfg = Config(str(ROOT / 'backend/alembic.ini'))
    cfg.set_main_option('script_location', str(ROOT / 'backend/alembic'))
    graph = ScriptDirectory.from_config(cfg)  # does not load env.py
    require(graph.get_heads() == [HEAD] and graph.get_bases() == ['79d8d51548c6'],
            'Revision graph differs from reviewed plan')
    require(len(list(graph.walk_revisions())) == 14 and len(Base.metadata.tables) == 25,
            'Reviewed revision/model count changed')

    # Globally refuse accidental fallback to the normal development/test engine.
    def connection_gate(conn):
        require(conn.engine.url.database == TARGET, 'Non-isolated connection refused')
    def before_dbapi_connect(dialect, connection_record, args, kwargs):
        require(kwargs.get('database', kwargs.get('db')) == TARGET,
                'Non-isolated DBAPI connection refused before opening')
    event.listen(Engine, 'do_connect', before_dbapi_connect)
    event.listen(Engine, 'engine_connect', connection_gate)
    isolated = create_engine(normal_engine.url.set(database=TARGET),
        hide_parameters=True, echo=False, connect_args=connection_options(settings))
    def sql_gate(conn, cursor, statement, parameters, context, executemany):
        require(conn.engine is isolated and conn.engine.url.database == TARGET,
                'SQL on a non-isolated engine refused')
        sql = statement.strip().upper()
        require(not re.search(r'\b(CREATE|DROP|ALTER)\s+DATABASE\b|\b(USE|GRANT|REVOKE|TRUNCATE)\b', sql),
                'Database/global/reset operation refused')
        require(not any(name in statement.lower() for name in ('lankapex_db', 'lankapex_test_db')),
                'Reference to an existing application database refused')
        if not args.execute:
            require(sql.startswith(('SELECT ', 'SHOW ', 'DESCRIBE ')) or
                    sql == 'SET SESSION TRANSACTION READ ONLY', 'Write refused in preflight mode')
    event.listen(isolated, 'before_cursor_execute', sql_gate)
    try:
        with isolated.connect() as conn:
            if not args.execute:
                conn.exec_driver_sql('SET SESSION TRANSACTION READ ONLY')
                conn.commit()
            verify_identity(conn, TARGET)
            require(conn.exec_driver_sql('SELECT CURRENT_USER()').scalar_one() == ACCOUNT,
                    'Unexpected authenticated account')
            version, partial, mode, fk = conn.exec_driver_sql(
                'SELECT VERSION(), @@GLOBAL.partial_revokes, @@SESSION.sql_mode, @@SESSION.foreign_key_checks').one()
            require(str(version).startswith('8.0.') and fk == 1 and 'STRICT_TRANS_TABLES' in mode,
                    'MySQL version/strict mode/FK settings require review')
            require(conn.exec_driver_sql('SELECT CURRENT_ROLE()').scalar_one() == 'NONE',
                    'Active role privileges require separate review')
            tables = conn.exec_driver_sql('SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s', (TARGET,)).scalar_one()
            routines = conn.exec_driver_sql('SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=%s', (TARGET,)).scalar_one()
            events = conn.exec_driver_sql('SELECT COUNT(*) FROM information_schema.EVENTS WHERE EVENT_SCHEMA=%s', (TARGET,)).scalar_one()
            require(tables == routines == events == 0, 'Target is not empty; no reset or rerun permitted')
            exact_privileges = set()
            broad = False
            for grant in conn.exec_driver_sql('SHOW GRANTS FOR CURRENT_USER()').scalars():
                if re.match(r'GRANT (?!USAGE\b).* ON \*\.\* TO ', grant):
                    broad = True
                match = re.match(r'GRANT (.*?) ON `(.*?)`\.\* TO ', grant)
                if match and match[2].replace('\\_', '_') == TARGET:
                    if not partial and re.search(r'(?<!\\)[_%]', match[2]):
                        broad = True
                    else:
                        privileges = set(match[1].split(', '))
                        if 'ALL PRIVILEGES' in privileges:
                            privileges |= REQUIRED
                        exact_privileges |= privileges
            print('Identity verified; target empty; MySQL ' + str(version))
            print('Graph verified: 14 revisions, head ' + HEAD + ', 25 modeled application tables')
            print('Exact-scope required privileges: ' + ('PASS' if REQUIRED <= exact_privileges else 'NOT VERIFIED'))
            print('Broad/wildcard grant review: ' + ('REQUIRED' if broad else 'PASS'))
            if not args.execute:
                print('READ-ONLY PREFLIGHT COMPLETE; execution ' +
                      ('BLOCKED by grant scope' if broad or not REQUIRED <= exact_privileges else 'AWAITING EXPLICIT APPROVAL'))
                return 2 if broad or not REQUIRED <= exact_privileges else 0
            require(not broad and REQUIRED <= exact_privileges,
                    'Exact-scope grants required before execution; ask DBA, do not change grants here')
            conn.commit()
            locked = conn.exec_driver_sql('SELECT GET_LOCK(%s,0)', ('lankapex_migration_verify_20261107_rehearsal',)).scalar_one()
            require(locked == 1, 'Another rehearsal owns the advisory lock')
            try:
                # Recheck under the advisory lock. Other DBA activity must remain quiescent.
                verify_identity(conn, TARGET)
                require(not inspect(conn).get_table_names() and not inspect(conn).get_view_names(),
                        'Target changed during preflight')
                conn.exec_driver_sql("SET SESSION time_zone = '+00:00'")
                conn.commit()
                cfg.attributes['connection'] = conn
                for revision in ('c9d5e8f7a237', 'd0e6f9a8b348', 'e1f7a0b9c459',
                                 'f2a8b1c0d560', '03b9c2d1e671', HEAD):
                    verify_identity(conn, TARGET)
                    conn.commit()
                    command.upgrade(cfg, revision)
                    conn.commit()
                    actual = conn.exec_driver_sql('SELECT version_num FROM alembic_version').scalars().all()
                    require(actual == [revision], 'Unexpected recorded revision; stop and inspect partial state')
                    print('Applied isolated stage: ' + revision)
                actual_tables = set(inspect(conn).get_table_names())
                require(actual_tables == set(Base.metadata.tables) | {'alembic_version'},
                        'Final table inventory mismatch; preserve target for investigation')
                diffs = compare_metadata(MigrationContext.configure(conn, opts={'compare_type': True}), Base.metadata)
                require(not diffs, 'Schema metadata comparison failed; preserve target for investigation')
                for name, table in Base.metadata.tables.items():
                    expected = {c.name for c in table.constraints if c.__class__.__name__ == 'CheckConstraint'}
                    found = {c['name'] for c in inspect(conn).get_check_constraints(name)}
                    require(expected <= found, 'Missing CHECK constraint in ' + name)
                print('ISOLATED CHAIN/STRUCTURAL VERIFICATION PASS: 25 application tables, revision ' + HEAD)
                print('No synthetic rows seeded. Constraint enforcement, API/security and recovery drills NOT RUN.')
            finally:
                conn.exec_driver_sql('SELECT RELEASE_LOCK(%s)', ('lankapex_migration_verify_20261107_rehearsal',))
                conn.commit()
    finally:
        isolated.dispose()
        normal_engine.dispose()
        event.remove(Engine, 'engine_connect', connection_gate)
        event.remove(Engine, 'do_connect', before_dbapi_connect)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        # Never print raw SQLAlchemy/config errors, URLs, parameters or secrets.
        if isinstance(exc, RuntimeError):
            print('STOP: ' + str(exc), file=sys.stderr)
        else:
            original = getattr(exc, 'orig', None)
            code = getattr(original, 'args', [None])[0]
            print('STOP: ' + type(exc).__name__ + '; MySQL code=' + str(code), file=sys.stderr)
        sys.exit(1)
