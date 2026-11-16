"""Exact-target, preflight-by-default upgrade for the isolated LankaPex test schema.

Never run --execute without separate authorization and a reviewed test backup.
No reset, downgrade, stamp, seed, cleanup or automatic retry is performed.
"""
import argparse
import os
from pathlib import Path
import re
import sys

TARGET = 'lankapex_test_db'
ACCOUNT = 'lankapex_app@localhost'
START = '03b9c2d1e671'
STAGES = ('14c0d3e2f782', '6e3f2c1a9b04')
ROOT = Path(__file__).resolve().parents[2]
ADDED = {'customer_addresses', 'vehicles', 'vehicle_documents',
         'user_preferences', 'business_settings', 'customer_link_invitations'}


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
            'Execution requires exact --confirm-target and separate approval')
    require(os.environ.get('APP_ENV') == 'testing' and os.environ.get('MYSQL_DATABASE') == TARGET,
            'Explicit testing environment and exact test database required')
    sys.path.insert(0, str(ROOT / 'backend'))

    from alembic import command
    from alembic.autogenerate import compare_metadata
    from alembic.config import Config
    from alembic.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from sqlalchemy import event, inspect
    from sqlalchemy.engine import Engine
    from app.core.config import settings
    from app.core.database import Base, engine
    import app.models  # noqa: F401

    require(settings.APP_ENV == 'testing' and settings.MYSQL_DATABASE == TARGET
            and engine.url.database == TARGET and settings.MYSQL_HOST in ('localhost', '127.0.0.1', '::1'),
            'Effective connection is not the local test schema')
    cfg = Config(str(ROOT / 'backend/alembic.ini'))
    cfg.set_main_option('script_location', str(ROOT / 'backend/alembic'))
    graph = ScriptDirectory.from_config(cfg)
    chain = list(reversed(list(graph.walk_revisions())))
    require(len(chain) == 15 and chain[0].revision == '79d8d51548c6'
            and graph.get_heads() == [STAGES[-1]] and len(Base.metadata.tables) == 26
            and [r.revision for r in chain[-3:]] == [START, *STAGES],
            'Reviewed migration chain or models changed')

    def connect_gate(dialect, record, args_, kwargs):
        require(kwargs.get('database', kwargs.get('db')) == TARGET,
                'Non-test DBAPI connection refused')

    def engine_gate(conn):
        require(conn.engine.url.database == TARGET, 'Non-test engine refused')

    def sql_gate(conn, cursor, statement, parameters, context, executemany):
        require(conn.engine is engine and conn.engine.url.database == TARGET,
                'SQL on a non-test engine refused')
        sql = statement.strip().upper()
        require(not re.search(r'\b(?:CREATE|ALTER|DROP)\s+DATABASE\b|'
                       r'\b(?:USE|GRANT|REVOKE|TRUNCATE|SET\s+GLOBAL)\b', sql),
                'Database/global/reset SQL refused')
        require(not re.search(r'\b(?:lankapex_db|lankapex_demo_db|lankapex_migration_verify_[a-z0-9_]+)\s*\.',
                              statement, re.IGNORECASE), 'Cross-database SQL refused')
        if not args.execute:
            require(sql.startswith(('SELECT ', 'SHOW ', 'DESCRIBE ')),
                    'Preflight SQL must be read-only')

    event.listen(Engine, 'do_connect', connect_gate)
    event.listen(Engine, 'engine_connect', engine_gate)
    event.listen(Engine, 'before_cursor_execute', sql_gate)
    try:
        with engine.connect() as conn:
            require(conn.exec_driver_sql('SELECT DATABASE()').scalar_one() == TARGET,
                    'Actual database identity differs')
            require(conn.exec_driver_sql('SELECT CURRENT_USER()').scalar_one() == ACCOUNT,
                    'Unexpected database account')
            version, mode, fk = conn.exec_driver_sql(
                'SELECT VERSION(), @@SESSION.sql_mode, @@SESSION.foreign_key_checks').one()
            require(str(version).startswith('8.0.') and 'STRICT_TRANS_TABLES' in mode and fk == 1,
                    'MySQL version, strict mode or foreign-key checks differ')
            require(conn.exec_driver_sql('SELECT CURRENT_ROLE()').scalar_one() == 'NONE',
                    'Active database role requires review')
            require(conn.exec_driver_sql('SELECT version_num FROM alembic_version').scalars().all() == [START],
                    'Starting Alembic revision differs')
            current = set(inspect(conn).get_table_names())
            require(current == (set(Base.metadata.tables) - ADDED) | {'alembic_version'},
                    'Existing test table inventory differs')
            for name in sorted(current - {'alembic_version'}):
                require(conn.exec_driver_sql('SELECT COUNT(*) FROM `' + name + '`').scalar_one() == 0,
                        'Test schema has application rows; backup/review required')
            grants = conn.exec_driver_sql('SHOW GRANTS FOR CURRENT_USER()').scalars().all()
            relevant = []
            for grant in grants:
                match = re.match(r'GRANT (.*?) ON `(.*?)`\.\* TO ', grant)
                if match and match[2].replace('\\_', '_') == TARGET:
                    relevant.append(grant)
            required = {'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'INDEX', 'REFERENCES'}
            privileges = set()
            for grant in relevant:
                found = set(grant.split(' ON ')[0].removeprefix('GRANT ').split(', '))
                privileges |= required if 'ALL PRIVILEGES' in found else found
            require(required <= privileges, 'Test-schema migration privileges not verified')
            print('PASS: exact test identity/account, zero application rows, starting revision and table inventory')
            print('PASS: MySQL settings, grants and 15-revision graph; pending ' + ', '.join(STAGES))
            if not args.execute:
                print('READ-ONLY PREFLIGHT COMPLETE; no migration executed')
                return 0
            conn.commit()
            require(conn.exec_driver_sql('SELECT GET_LOCK(%s,0)', (TARGET + '_invitation_upgrade',)).scalar_one() == 1,
                    'Test-schema upgrade lock unavailable')
            try:
                conn.commit()
                for revision in STAGES:
                    command.upgrade(cfg, revision)
                    conn.commit()
                    require(conn.exec_driver_sql('SELECT version_num FROM alembic_version').scalars().all() == [revision],
                            'Stage revision mismatch; preserve partial state')
                    conn.commit()
                    print('Applied test stage: ' + revision)
                require(set(inspect(conn).get_table_names()) == set(Base.metadata.tables) | {'alembic_version'},
                        'Final table inventory mismatch')
                require(not compare_metadata(MigrationContext.configure(conn, opts={'compare_type': True}), Base.metadata),
                        'Final model/schema comparison failed')
                for name in Base.metadata.tables:
                    require(conn.exec_driver_sql('SELECT COUNT(*) FROM `' + name + '`').scalar_one() == 0,
                            'Unexpected application rows after migration')
                print('PASS: 26 empty application tables plus alembic_version at ' + STAGES[-1])
            finally:
                conn.exec_driver_sql('SELECT RELEASE_LOCK(%s)', (TARGET + '_invitation_upgrade',))
                conn.commit()
    finally:
        event.remove(Engine, 'before_cursor_execute', sql_gate)
        event.remove(Engine, 'engine_connect', engine_gate)
        event.remove(Engine, 'do_connect', connect_gate)
        engine.dispose()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        if isinstance(exc, RuntimeError):
            print('STOP: ' + str(exc), file=sys.stderr)
        else:
            original = getattr(exc, 'orig', None)
            print('STOP: ' + type(exc).__name__ + '; MySQL code=' +
                  str(getattr(original, 'args', [None])[0]), file=sys.stderr)
        sys.exit(1)
