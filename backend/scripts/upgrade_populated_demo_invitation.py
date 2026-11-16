"""Guarded, one-revision upgrade for the populated demo database.

Default invocation is read-only. Execution needs separate authorization, a
verified backup, a maintained writer pause, and exact target confirmation.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
TARGET = 'lankapex_demo_db'
ACCOUNT = 'lankapex_demo_migrator@localhost'
START = '14c0d3e2f782'
HEAD = '6e3f2c1a9b04'
NEW_TABLE = 'customer_link_invitations'
REQUIRED = {'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'INDEX', 'REFERENCES'}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True, choices=[TARGET])
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--confirm-target')
    parser.add_argument('--backup')
    parser.add_argument('--sha256')
    parser.add_argument('--pause-verified', action='store_true')
    args = parser.parse_args()
    require(not args.execute or (args.confirm_target == TARGET and args.backup
                                  and args.sha256 and args.pause_verified),
            'Execution needs exact target, pinned backup checksum and verified writer pause')
    require(os.environ.get('APP_ENV') == 'development'
            and os.environ.get('MYSQL_DATABASE') == TARGET
            and os.environ.get('MYSQL_USER') == 'lankapex_demo_migrator'
            and os.environ.get('MYSQL_PASSWORD'),
            'Private demo migrator environment is required')
    sys.path.insert(0, str(ROOT / 'backend'))

    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from sqlalchemy import event, inspect
    from sqlalchemy.engine import Engine
    from app.core.config import settings
    from app.core.database import Base, engine
    import app.models  # noqa: F401

    require(settings.APP_ENV == 'development' and settings.MYSQL_DATABASE == TARGET
            and settings.MYSQL_USER == 'lankapex_demo_migrator'
            and settings.MYSQL_HOST in ('localhost', '127.0.0.1', '::1')
            and engine.url.database == TARGET, 'Effective connection target differs')
    cfg = Config(str(ROOT / 'backend/alembic.ini'))
    cfg.set_main_option('script_location', str(ROOT / 'backend/alembic'))
    graph = ScriptDirectory.from_config(cfg)
    chain = list(reversed(list(graph.walk_revisions())))
    require(graph.get_heads() == [HEAD] and len(chain) == 15
            and chain[-2].revision == START and chain[-1].revision == HEAD
            and len(Base.metadata.tables) == 26,
            'Reviewed migration graph or models changed')

    def dbapi_gate(dialect, record, args_, kwargs):
        require(kwargs.get('database', kwargs.get('db')) == TARGET,
                'Non-demo DBAPI target refused')

    def connection_gate(conn):
        require(conn.engine.url.database == TARGET, 'Non-demo connection refused')

    def sql_gate(conn, cursor, statement, parameters, context, executemany):
        require(conn.engine is engine and conn.engine.url.database == TARGET,
                'Non-demo SQL refused')
        sql = statement.strip().upper()
        require(not re.search(r'\b(?:CREATE|ALTER|DROP)\s+DATABASE\b|'
                       r'\b(?:USE|GRANT|REVOKE|TRUNCATE|SET\s+GLOBAL)\b', sql),
                'Database/global/reset statement refused')
        require(not re.search(r'\b(?:lankapex_db|lankapex_test_db|'
                       r'lankapex_migration_verify_[a-z0-9_]+)\s*\.', statement,
                       re.IGNORECASE), 'Cross-database SQL refused')
        if not args.execute:
            require(sql.startswith(('SELECT ', 'SHOW ', 'DESCRIBE ')),
                    'Default preflight is read-only')

    event.listen(Engine, 'do_connect', dbapi_gate)
    event.listen(Engine, 'engine_connect', connection_gate)
    event.listen(Engine, 'before_cursor_execute', sql_gate)
    try:
        with engine.connect() as conn:
            require(conn.exec_driver_sql('SELECT DATABASE()').scalar_one() == TARGET
                    and conn.exec_driver_sql('SELECT CURRENT_USER()').scalar_one() == ACCOUNT,
                    'Actual database/account identity differs')
            version, mode, fk = conn.exec_driver_sql(
                'SELECT VERSION(), @@SESSION.sql_mode, @@SESSION.foreign_key_checks').one()
            require(str(version).startswith('8.0.') and 'STRICT_TRANS_TABLES' in mode and fk == 1,
                    'MySQL version/strict/FK prerequisite differs')
            require(conn.exec_driver_sql('SELECT CURRENT_ROLE()').scalar_one() == 'NONE',
                    'Active role privileges require review')
            require(conn.exec_driver_sql('SELECT version_num FROM alembic_version').scalars().all() == [START],
                    'Starting Alembic revision differs')
            tables = set(inspect(conn).get_table_names())
            require(tables == (set(Base.metadata.tables) - {NEW_TABLE}) | {'alembic_version'},
                    'Existing populated demo table inventory differs')
            grants = conn.exec_driver_sql('SHOW GRANTS FOR CURRENT_USER()').scalars().all()
            privileges = set()
            for grant in grants:
                if re.match(r'GRANT (?!USAGE\b).* ON \*\.\* TO ', grant):
                    raise RuntimeError('Global migration privilege refused')
                match = re.match(r'GRANT (.*?) ON `(.*?)`\.\* TO ', grant)
                if match:
                    scope = match[2]
                    require(scope.replace('\\_', '_') == TARGET
                            and not re.search(r'(?<!\\)[_%]', scope),
                            'Grant scope is not exactly escaped demo database')
                    privileges |= set(match[1].split(', '))
            require(REQUIRED <= privileges and 'ALL PRIVILEGES' not in privileges
                    and 'GRANT OPTION' not in privileges,
                    'Least-privilege demo migration grant differs')
            if args.backup:
                backup = Path(args.backup).resolve()
                private_root = (ROOT / '.server-logs' / 'private-demo-backups').resolve()
                require(backup.is_file() and backup.parent == private_root,
                        'Pinned backup must be a private local file outside Git')
                with backup.open('rb') as handle:
                    digest = hashlib.file_digest(handle, 'sha256').hexdigest()
                require(args.sha256 and digest.lower() == args.sha256.lower(),
                        'Pinned backup checksum differs')
            print('PASS: exact populated demo target/account, revision, 26 starting tables, scoped grant')
            print('PASS: 15-revision chain, MySQL settings' +
                  (', pinned backup checksum' if args.backup else ''))
            if not args.execute:
                print('READ-ONLY PREFLIGHT COMPLETE; no migration executed')
                return 0
            conn.commit()
            require(conn.exec_driver_sql('SELECT GET_LOCK(%s,0)',
                                         (TARGET + '_invitation_upgrade',)).scalar_one() == 1,
                    'Demo migration lock unavailable')
            try:
                conn.commit()
                require(conn.exec_driver_sql('SELECT version_num FROM alembic_version').scalars().all() == [START]
                        and set(inspect(conn).get_table_names()) == tables,
                        'Demo schema changed after preflight')
                conn.commit()
                command.upgrade(cfg, HEAD)
                conn.commit()
                require(conn.exec_driver_sql('SELECT version_num FROM alembic_version').scalars().all() == [HEAD]
                        and set(inspect(conn).get_table_names()) == set(Base.metadata.tables) | {'alembic_version'}
                        and conn.exec_driver_sql('SELECT COUNT(*) FROM customer_link_invitations').scalar_one() == 0,
                        'Post-upgrade schema differs; preserve partial state')
                print('PASS: one demo revision applied; invitation table empty')
            finally:
                conn.exec_driver_sql('SELECT RELEASE_LOCK(%s)',
                                     (TARGET + '_invitation_upgrade',))
                conn.commit()
    finally:
        event.remove(Engine, 'before_cursor_execute', sql_gate)
        event.remove(Engine, 'engine_connect', connection_gate)
        event.remove(Engine, 'do_connect', dbapi_gate)
        engine.dispose()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        if isinstance(exc, RuntimeError):
            print('STOP: ' + str(exc), file=sys.stderr)
        else:
            print('STOP: ' + type(exc).__name__, file=sys.stderr)
        sys.exit(1)
