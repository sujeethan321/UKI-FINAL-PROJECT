"""Read-only gate for the actual VIVA application engine. Never starts services."""
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core import viva_tls
from app.core.viva_runtime_policy import ENVIRONMENT, REVISION, dotenv_disabled

TARGET = 'lankapex_viva_db'
ACCOUNT = 'lankapex_viva_runtime@127.0.0.1'
CA_SHA256 = 'BAB209850CF20A275A47818CB08F50B2CAAD24CA0A5DCDAB705E38BE294FEFA0'


class GateError(RuntimeError):
    pass


def require(ok, code):
    if not ok:
        raise GateError(code)


def validate_configuration(settings, url):
    require(dotenv_disabled(), 'ISOLATED_CONFIGURATION_REQUIRED')
    for name, expected in ENVIRONMENT.items():
        if name == 'LANKAPEX_VIVA_RUNTIME':
            continue
        value = getattr(settings, name)
        if isinstance(value, bool):
            value = str(value).lower()
        elif isinstance(value, list):
            value = ','.join(value)
        else:
            value = str(value)
        require(value == expected, 'EFFECTIVE_CONFIGURATION_MISMATCH')
    require((url.drivername, url.host, url.port, url.database, url.username) ==
            ('mysql+pymysql', '127.0.0.1', 3306, TARGET, ACCOUNT.split('@')[0]),
            'ENGINE_TARGET_MISMATCH')
    require(not url.query and url.password == settings.MYSQL_PASSWORD,
            'ENGINE_OPTIONS_MISMATCH')
    require(len(settings.JWT_SECRET_KEY) >= 64 and bool(settings.MYSQL_PASSWORD),
            'CREDENTIAL_INVALID')
    require(not settings.GROQ_API_KEY and not settings.STRIPE_TEST_SECRET_KEY
            and not settings.STRIPE_WEBHOOK_SECRET, 'INTEGRATION_CREDENTIAL_PRESENT')


def validate_identity(row):
    require(tuple(row) == (TARGET, ACCOUNT, viva_tls.SERVER_UUID, 3306, '8.0.46', 1, 0),
            'SERVER_IDENTITY_OR_GLOBAL_STATE_MISMATCH')


def validate_grants(grants, role, partial_revokes):
    require(role == 'NONE', 'ACTIVE_ROLES_REJECTED')
    require(partial_revokes in (0, 1), 'GRANT_SEMANTICS_UNKNOWN')
    rights = set()
    for grant in grants:
        require(isinstance(grant, str), 'GRANT_FORMAT_REJECTED')
        # Pin the grantee as well as scope; reject role grants, proxy, grant option,
        # table/column grants, global rights and unknown trailing clauses.
        suffix = r" TO [`']lankapex_viva_runtime[`']@[`']127\.0\.0\.1[`']"
        if re.fullmatch(r'GRANT USAGE ON \*\.\*' + suffix + r'(?: REQUIRE SSL)?', grant):
            continue
        match = re.fullmatch(r'GRANT ([A-Z, ]+) ON `([^`]+)`\.\*' + suffix, grant)
        require(match is not None, 'GRANT_SCOPE_OR_OPTION_REJECTED')
        scope = match[2]
        expected_scope = TARGET if partial_revokes == 1 else TARGET.replace('_', '\\_')
        require(scope == expected_scope, 'EXACT_SCHEMA_GRANT_REQUIRED')
        rights.update(match[1].split(', '))
    require(rights == {'SELECT', 'INSERT', 'UPDATE', 'DELETE'}, 'DML_PRIVILEGES_MISMATCH')


def expected_tables():
    contract = Path(__file__).resolve().parents[1] / 'contracts/MR07_CANONICAL_OBJECTS.json'
    names = set(json.loads(contract.read_text(encoding='utf-8'))['stages'][REVISION]['tables'])
    require(len(names) == 45 and 'alembic_version' in names, 'SOURCE_CONTRACT_INVALID')
    return names


def validate_inventory(rows, modeled_names, expected):
    require(len(rows) == 45 and {r[0] for r in rows} == expected
            and all(r[1:] == ('BASE TABLE', 'InnoDB') for r in map(tuple, rows)),
            'TABLE_INVENTORY_MISMATCH')
    require(len(modeled_names) == 44 and set(modeled_names) == expected - {'alembic_version'},
            'MODEL_INVENTORY_MISMATCH')


def validate_schema(inspector, metadata):
    # FK names have three reviewed omissions. Compare relationships, not names.
    for name, table in metadata.tables.items():
        require({c['name'] for c in inspector.get_columns(name)} == set(table.columns.keys()),
                'MODEL_COLUMN_INVENTORY_MISMATCH')
        require(inspector.get_pk_constraint(name)['constrained_columns'] ==
                [c.name for c in table.primary_key.columns], 'MODEL_PRIMARY_KEY_MISMATCH')
        foreign_keys = inspector.get_foreign_keys(name)
        require(all(f.get('referred_schema') in (None, TARGET) for f in foreign_keys),
                'CROSS_SCHEMA_FOREIGN_KEY_REJECTED')
        actual = {(tuple(f['constrained_columns']), f['referred_table'],
                   tuple(f['referred_columns'])) for f in foreign_keys}
        expected = {(tuple(e.parent.name for e in f.elements),
                     f.elements[0].column.table.name,
                     tuple(e.column.name for e in f.elements)) for f in table.foreign_key_constraints}
        require(actual == expected, 'MODEL_FOREIGN_KEY_MISMATCH')


def main():
    engine = None
    stage = 'CONFIGURATION'
    result = 1
    try:
        from sqlalchemy import inspect, text
        from app.core.config import settings
        from app.core.database import Base, engine as application_engine
        engine = application_engine
        validate_configuration(settings, engine.url)
        require(hashlib.sha256(viva_tls.CA_PATH.read_bytes()).hexdigest().upper() == CA_SHA256,
                'CA_CHECKSUM_MISMATCH')
        import app.models  # noqa: F401; declarations only, no schema creation
        stage = 'READ_ONLY_CONNECTION'
        with engine.connect() as conn:
            conn.exec_driver_sql('START TRANSACTION READ ONLY')
            raw = conn.connection.driver_connection
            viva_tls.verify_socket(getattr(raw, '_sock', None))
            require(bool(raw._sock.cipher()), 'TLS_CIPHER_MISSING')
            stage = 'IDENTITY'
            validate_identity(conn.exec_driver_sql(
                'SELECT DATABASE(), CURRENT_USER(), @@server_uuid, @@port, VERSION(), '
                '@@global.log_bin, @@global.log_bin_trust_function_creators').one())
            stage = 'PRIVILEGES'
            validate_grants(conn.exec_driver_sql('SHOW GRANTS FOR CURRENT_USER()').scalars().all(),
                            conn.exec_driver_sql('SELECT CURRENT_ROLE()').scalar_one(),
                            conn.exec_driver_sql('SELECT @@global.partial_revokes').scalar_one())
            stage = 'SCHEMA'
            require(conn.exec_driver_sql('SELECT version_num FROM alembic_version').scalars().all()
                    == [REVISION], 'REVISION_MISMATCH')
            rows = conn.execute(text('SELECT TABLE_NAME, TABLE_TYPE, ENGINE FROM '
                'information_schema.TABLES WHERE TABLE_SCHEMA=:schema'), {'schema': TARGET}).all()
            validate_inventory(rows, Base.metadata.tables, expected_tables())
            validate_schema(inspect(conn), Base.metadata)
            conn.rollback()
        result = 0
    except Exception as exc:
        code = str(exc) if type(exc) is GateError else 'EXTERNAL_FAILURE_DETAILS_REDACTED'
        print('VIVA_RUNTIME_PREFLIGHT=STOP; STAGE=' + stage + '; CODE=' + code +
              '; ERROR_CLASS=' + type(exc).__name__, file=sys.stderr)
    finally:
        if engine is not None:
            try:
                engine.dispose()
            except Exception:
                print('VIVA_RUNTIME_PREFLIGHT=STOP; STAGE=DISPOSAL; '
                      'CODE=DISPOSAL_FAILED_DETAILS_REDACTED', file=sys.stderr)
                result = 1
    if result == 0:
        print('VIVA_RUNTIME_PREFLIGHT=PASS_READ_ONLY; REVISION=' + REVISION +
              '; TABLES=45; TRIGGERS=18_DBA_OPERATOR_EVIDENCE_NOT_REQUERIED; SERVICES_STARTED=no')
    return result


if __name__ == '__main__':
    sys.exit(main())
