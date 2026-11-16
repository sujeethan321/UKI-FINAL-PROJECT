"""Pure identity guards. Hostnames alone never establish database safety."""
import re


class MaintenanceSafetyError(ValueError):
    pass


def validate_target(environment, database, purpose='inspect'):
    if (environment == 'ai_snapshot_migration' and purpose == 'migration'
            and database == 'lankapex_ai_snapshot_test_db'):
        return database
    if environment not in {'development', 'testing'}:
        raise MaintenanceSafetyError('Local maintenance requires explicit development/testing mode')
    if not isinstance(database, str) or not re.fullmatch(r'[a-z][a-z0-9_]{2,63}', database):
        raise MaintenanceSafetyError('An exact unambiguous database name is required')
    if purpose == 'inspect':
        expected = 'lankapex_db' if environment == 'development' else 'lankapex_test_db'
        if database != expected:
            raise MaintenanceSafetyError('Inspection target does not match the selected environment')
    elif purpose in {'restore', 'migration'}:
        if environment != 'testing' or not re.fullmatch(
                rf'lankapex_{purpose}_verify_[a-z0-9]{{8,32}}', database):
            raise MaintenanceSafetyError('A separately designated isolated verification database is required')
    else:
        raise MaintenanceSafetyError('Unsupported maintenance purpose')
    return database


def verify_identity(connection, expected):
    from sqlalchemy import text
    if connection.engine.url.database != expected or connection.scalar(text('SELECT DATABASE()')) != expected:
        raise MaintenanceSafetyError('Actual database identity does not match the explicit target')


def require_empty(connection):
    from sqlalchemy import inspect
    inspector = inspect(connection)
    if inspector.get_table_names() or inspector.get_view_names():
        raise MaintenanceSafetyError('Verification target must be empty; existing data will not be replaced')
