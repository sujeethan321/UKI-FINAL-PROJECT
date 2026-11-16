"""Read-only identity gate before starting the separate demo API."""
from pathlib import Path
import re
import sys

# Direct script execution sets sys.path[0] to backend/scripts, not backend.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


TARGET = 'lankapex_demo_db'
REVISION = '7b9e4d2c8a15'
PASS_MESSAGE = 'PASS: demo API exact target/account, revision, 28 application tables (29 total including alembic_version), QR constraints and DML-only grant'

# Only these source-defined messages may become public diagnostic categories.
# Never emit raw driver exceptions, Settings values, grant strings or credentials.
FAILURE_CATEGORIES = {
    'Demo process environment does not name the exact runtime target': 'configured_identity_mismatch',
    'Unsafe effective demo configuration': 'unsafe_effective_configuration',
    'Demo schema requires the reviewed QR revision': 'schema_revision_mismatch',
    'Demo schema table inventory differs from the approved model': 'schema_inventory_mismatch',
    'QR table columns differ from reviewed schema': 'qr_columns_mismatch',
    'Required QR uniqueness constraint missing or misplaced': 'qr_unique_constraint_mismatch',
    'QR business primary key differs': 'qr_business_primary_key_mismatch',
    'QR request primary key differs': 'qr_request_primary_key_mismatch',
    'Required QR request index missing': 'qr_index_missing',
    'Required QR status constraint differs': 'qr_status_constraint_mismatch',
    'Required QR foreign key differs': 'qr_foreign_key_mismatch',
    'Actual demo database/account identity differs': 'runtime_identity_mismatch',
    'Unexpected runtime grant format or scope': 'runtime_grant_format_mismatch',
    'Runtime grant is broader than exact demo schema': 'runtime_grant_scope_mismatch',
    'Runtime grant is missing a required privilege or includes extra rights': 'runtime_privileges_mismatch',
    'Active runtime role privileges require review': 'active_runtime_roles',
}


def failure_category(error):
    if isinstance(error, ModuleNotFoundError):
        return 'required_module_unavailable'
    if isinstance(error, RuntimeError) and str(error) in FAILURE_CATEGORIES:
        return FAILURE_CATEGORIES[str(error)]
    original = getattr(error, 'orig', None)
    arguments = getattr(original, 'args', ())
    code = arguments[0] if arguments else None
    return {
        1044: 'database_access_denied', 1045: 'authentication_failed',
        1049: 'database_missing', 1142: 'metadata_access_denied',
        1146: 'required_table_missing', 2003: 'mysql_connection_failed',
        2026: 'tls_connection_failed',
    }.get(code, 'unclassified_preflight_failure') if type(code) is int else 'unclassified_preflight_failure'


def validate_configuration(settings, url):
    if (settings.APP_ENV != 'development' or settings.MYSQL_DATABASE != TARGET
            or settings.MYSQL_USER != 'lankapex_demo_app'
            or settings.MYSQL_HOST != 'localhost' or settings.MYSQL_PORT != 3306
            or url.database != TARGET or url.username != 'lankapex_demo_app'
            or url.host != 'localhost' or url.port != 3306):
        raise RuntimeError('Demo process environment does not name the exact runtime target')
    if (settings.AI_ENABLED is not False or settings.APP_DEBUG is not False
            or settings.LOG_LEVEL != 'WARNING' or settings.RATE_LIMIT_MODE != 'local'
            or settings.CORS_ALLOWED_ORIGINS != ['http://127.0.0.1:5173']
            or settings.ALLOWED_HOSTS != ['127.0.0.1', 'localhost']):
        raise RuntimeError('Unsafe effective demo configuration')


def validate_schema(inspector, revisions, modeled_names):
    if revisions != [REVISION]:
        raise RuntimeError('Demo schema requires the reviewed QR revision')
    if (len(modeled_names) != 28 or
            set(inspector.get_table_names()) != set(modeled_names) | {'alembic_version'}):
        raise RuntimeError('Demo schema table inventory differs from the approved model')
    required_columns = {
        'business_join_links': {'business_id', 'public_code', 'created_at'},
        'customer_join_requests': {'request_id', 'business_id', 'customer_user_id',
                                   'status', 'created_at', 'decided_at', 'decided_by'},
    }
    for table, columns in required_columns.items():
        if {column['name'] for column in inspector.get_columns(table)} != columns:
            raise RuntimeError('QR table columns differ from reviewed schema')
    for table, name, columns in (
        ('customer_profiles', 'uq_customer_profile_business_user', ['business_id', 'user_id']),
        ('business_join_links', 'uq_business_join_public_code', ['public_code']),
        ('customer_join_requests', 'uq_customer_join_business_user', ['business_id', 'customer_user_id']),
    ):
        if not any(c['name'] == name and c['column_names'] == columns
                   for c in inspector.get_unique_constraints(table)):
            raise RuntimeError('Required QR uniqueness constraint missing or misplaced')
    if inspector.get_pk_constraint('business_join_links')['constrained_columns'] != ['business_id']:
        raise RuntimeError('QR business primary key differs')
    if inspector.get_pk_constraint('customer_join_requests')['constrained_columns'] != ['request_id']:
        raise RuntimeError('QR request primary key differs')
    if not any(i['name'] == 'ix_customer_join_business_status_created'
               and i['column_names'] == ['business_id', 'status', 'created_at']
               for i in inspector.get_indexes('customer_join_requests')):
        raise RuntimeError('Required QR request index missing')
    checks = inspector.get_check_constraints('customer_join_requests')
    def normalized_check(value):
        return re.sub(r"[\s`()]+", '', value).lower().replace("_utf8mb4'", "'")
    expected_check = normalized_check("status IN ('pending', 'approved', 'rejected', 'cancelled')")
    if not any(c['name'] == 'ck_customer_join_status'
               and normalized_check(c['sqltext']) == expected_check for c in checks):
        raise RuntimeError('Required QR status constraint differs')
    for table, column, parent, target in (
        ('business_join_links', 'business_id', 'businesses', 'business_id'),
        ('customer_join_requests', 'business_id', 'businesses', 'business_id'),
        ('customer_join_requests', 'customer_user_id', 'users', 'user_id'),
        ('customer_join_requests', 'decided_by', 'users', 'user_id'),
    ):
        if not any(f['constrained_columns'] == [column] and f['referred_table'] == parent
                   and f['referred_columns'] == [target]
                   and f.get('referred_schema') in (None, TARGET)
                   # MySQL can omit explicit RESTRICT because it is the default.
                   and (f.get('options', {}).get('ondelete') or 'RESTRICT').upper() in ('RESTRICT', 'NO ACTION')
                   for f in inspector.get_foreign_keys(table)):
            raise RuntimeError('Required QR foreign key differs')


def validate_runtime_identity(database, account):
    if database != TARGET or account != 'lankapex_demo_app@localhost':
        raise RuntimeError('Actual demo database/account identity differs')


def main():
    from sqlalchemy import inspect, text
    from app.core.config import settings
    from app.core.database import Base, engine
    import app.models  # noqa: F401

    validate_configuration(settings, engine.url)
    with engine.connect() as conn:
        validate_runtime_identity(conn.scalar(text('SELECT DATABASE()')),
                                  conn.scalar(text('SELECT CURRENT_USER()')))
        validate_schema(inspect(conn),
                        conn.execute(text('SELECT version_num FROM alembic_version')).scalars().all(),
                        set(Base.metadata.tables))
        partial_revokes = conn.exec_driver_sql('SELECT @@GLOBAL.partial_revokes').scalar_one()
        expected = {'SELECT', 'INSERT', 'UPDATE', 'DELETE'}
        effective = set()
        for grant in conn.exec_driver_sql('SHOW GRANTS FOR CURRENT_USER()').scalars():
            if re.match(r'GRANT USAGE ON \*\.\* TO ', grant):
                continue
            match = re.match(r'GRANT (.*?) ON `(.*?)`\.\* TO ', grant)
            if not match:
                raise RuntimeError('Unexpected runtime grant format or scope')
            scope = match[2]
            if (scope.replace('\\_', '_') != 'lankapex_demo_db' or
                    (not partial_revokes and re.search(r'(?<!\\)[_%]', scope))):
                raise RuntimeError('Runtime grant is broader than exact demo schema')
            effective |= set(match[1].split(', '))
        if effective != expected:
            raise RuntimeError('Runtime grant is missing a required privilege or includes extra rights')
        if conn.exec_driver_sql('SELECT CURRENT_ROLE()').scalar_one() != 'NONE':
            raise RuntimeError('Active runtime role privileges require review')
    print(PASS_MESSAGE)


def run(check=None):
    try:
        (check or main)()
        return 0
    except Exception as exc:
        print('STOP: demo API preflight category=' + failure_category(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(run())
