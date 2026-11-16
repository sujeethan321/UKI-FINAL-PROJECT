"""Current-demo backup/recovery contracts and operator plans; no I/O at import.

No provisioning, existing ACL changes, migration or implicit live operation.
The logical archive is deliberately NOT an executable SQL file.
"""
import argparse
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import sys

SOURCE = 'lankapex_demo_db'
REVISION = '6e3f2c1a9b04'
RESTORE = 'lankapex_demo_qr_rehearsal_20261115'
SOURCE_ACCOUNT = 'lankapex_demo_app@localhost'
RESTORE_ACCOUNT = 'lankapex_demo_qr_restore@localhost'
EXISTING_RESTORE = 'lankapex_demo_restore_verify_20261116'
QR_TABLES = frozenset({'business_join_links', 'customer_join_requests'})
TABLES = frozenset('''users businesses business_members customer_profiles
credit_accounts ledger_entries business_approval_audits payment_reminders
notifications communication_consents communication_attempts driver_profiles
delivery_requests delivery_assignments delivery_status_events product_categories
products orders order_items admin_audits customer_addresses user_preferences
business_settings vehicles vehicle_documents customer_link_invitations
alembic_version'''.split())
ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / '.server-logs/private-demo-qr-migration'
BOUND_SOURCES = (
    'backend/scripts/demo_qr_recovery.py',
    'backend/scripts/demo_qr_preservation.py',
    'backend/scripts/inventory_demo_database.py',
    'backend/scripts/demo_qr_migration_guard.py',
    'backend/scripts/upgrade_populated_demo_qr.py',
    'backend/scripts/upgrade_populated_demo_qr.ps1',
    'backend/scripts/check_demo_qr_private_path.ps1',
    'backend/scripts/tamil_ai_private_acl.ps1',
    'backend/scripts/demo_qr_credential_storage.ps1',
    'backend/scripts/check_demo_backend.py',
    'backend/alembic/versions/7b9e4d2c8a15_customer_qr_join.py',
)


class RecoveryStop(ValueError):
    """Messages are fixed categories, never raw connector/record content."""


def require(condition, category):
    if not condition:
        raise RecoveryStop(category)


def typed(value):
    """Unambiguous full-row encoding, including private fields; hash only output."""
    if value is None:
        return ['null']
    if isinstance(value, bool):
        return ['bool', value]
    if isinstance(value, int):
        return ['int', str(value)]
    if isinstance(value, Decimal):
        require(value.is_finite(), 'unsupported_value')
        return ['decimal', str(value)]
    if isinstance(value, str):
        return ['text', value]
    if isinstance(value, bytes):
        return ['bytes', value.hex()]
    if isinstance(value, (datetime, date, time)):
        return [type(value).__name__, value.isoformat()]
    if isinstance(value, timedelta):
        return ['timedelta', str(value.days), str(value.seconds), str(value.microseconds)]
    require(False, 'unsupported_value')  # No lossy float/currency conversion.


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode('utf-8')).hexdigest()


def row_fingerprint(rows):
    """Rows must be streamed in the verified primary-key order by the adapter."""
    result = hashlib.sha256()
    count = 0
    for row in rows:
        result.update(json.dumps([typed(value) for value in row], ensure_ascii=False,
                                 separators=(',', ':')).encode('utf-8') + b'\n')
        count += 1
    return {'rows': count, 'sha256': result.hexdigest()}


def artifact_paths(artifact_id):
    require(isinstance(artifact_id, str) and re.fullmatch('[0-9a-f]{32}', artifact_id),
            'artifact_identity')
    return {kind: PRIVATE / f'{prefix}-{artifact_id}.{suffix}' for kind, prefix, suffix in (
        ('dump', 'source', 'lpx'), ('before', 'backup-before', 'json'),
        ('after', 'backup-after', 'json'), ('backup', 'recovery-backup', 'json'),
        ('restore', 'restore-proof', 'json'))}


def validate_snapshot(snapshot, database=SOURCE):
    require(database in (SOURCE, RESTORE), 'target')
    account = SOURCE_ACCOUNT if database == SOURCE else RESTORE_ACCOUNT
    privileges = {'SELECT', 'INSERT', 'UPDATE', 'DELETE'} if database == SOURCE else {
        'SELECT', 'INSERT', 'CREATE', 'ALTER', 'INDEX', 'REFERENCES'}
    validate_inventory_snapshot(snapshot, database, account, privileges, REVISION, TABLES)


def validate_inventory_snapshot(snapshot, database, account, privileges, revision, tables):
    """Pure snapshot checks; callers independently establish exact connection policy."""
    require((snapshot.get('database'), snapshot.get('account'), snapshot.get('host'),
             snapshot.get('port')) == (database, account, 'localhost', 3306), 'identity')
    require(snapshot.get('revision') == revision, 'revision')
    require(set(snapshot.get('tables', {})) == tables, 'inventory')
    require(snapshot.get('stored_objects') == 0 and snapshot.get('non_innodb') == 0,
            'unsupported_schema')
    defaults = snapshot.get('database_defaults')
    require(isinstance(defaults, dict) and set(defaults) == {'charset', 'collation'}
            and all(isinstance(v, str) and re.fullmatch('[A-Za-z0-9_]+', v)
                    for v in defaults.values()), 'database_defaults')
    require(snapshot.get('active_roles') == 'NONE', 'roles')
    require(snapshot.get('global_usage_only') is True
            and set(snapshot.get('privileges', [])) == privileges
            and snapshot.get('grant_scope') == database, 'grants')
    require(snapshot.get('duplicate_profiles') == 0, 'duplicate_profiles')
    require(snapshot.get('foreign_key_orphans') and all(
        type(value) is int and value == 0 for value in snapshot['foreign_key_orphans'].values()),
        'foreign_keys')
    for table in snapshot['tables'].values():
        require(set(table) == {'schema_sha256', 'rows', 'sha256'}, 'table_evidence')
        require(type(table['rows']) is int and table['rows'] >= 0, 'table_evidence')
        for field in ('schema_sha256', 'sha256'):
            require(isinstance(table[field], str) and re.fullmatch('[0-9a-f]{64}', table[field]),
                    'table_evidence')
    for field in ('financial_fingerprints', 'source_hashes', 'versions'):
        require(isinstance(snapshot.get(field), dict) and snapshot[field], 'evidence_incomplete')
    require(set(snapshot['financial_fingerprints']) == {
        'signed_account_balances', 'ledger_type_totals', 'credit_accounts', 'ledger_entries',
        'customer_profiles', 'business_members', 'orders', 'order_items', 'delivery_requests',
        'delivery_assignments', 'delivery_status_events', 'payment_reminders'}, 'financial_inventory')
    for value in (*snapshot['financial_fingerprints'].values(), *snapshot['source_hashes'].values()):
        require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value), 'fingerprint')
    require(set(snapshot['source_hashes']) == set(BOUND_SOURCES), 'source_binding')


def compare(before, after, restored=False):
    validate_snapshot(before)
    validate_snapshot(after, RESTORE if restored else SOURCE)
    # Identity is checked independently, never rewritten to fake a source snapshot.
    for key in ('revision', 'tables', 'financial_fingerprints', 'foreign_key_orphans',
                'duplicate_profiles', 'source_hashes', 'versions', 'database_defaults'):
        require(before[key] == after[key], 'preservation_mismatch')


def prepare_backup(adapter, *, execute=False, confirm_target=None, writer_ddl_pause=False,
                   artifact_id=None):
    """One execution only; adapter methods are security contracts, not CLI bypasses.

    Protected exclusive output creation and consistent read-only snapshots use
    explicit non-application connections; no subprocess carries credentials.
    """
    if not execute:
        return {'status': 'OFFLINE_PREPARATION', 'database_changed': False}
    require(confirm_target == SOURCE and writer_ddl_pause is True, 'confirmation')
    paths = artifact_paths(artifact_id)
    adapter.validate_private_paths(paths, all_absent=True)
    before = adapter.snapshot(SOURCE)
    validate_snapshot(before)
    adapter.write_exclusive(paths['before'], before)
    # Full typed archive and single-table DDL are validated before any restore;
    # no executable dump or native client command stream is accepted.
    adapter.dump_exclusive(paths['dump'], None)
    integrity = adapter.inspect_dump(paths['dump'], before)
    require(integrity.get('validated_grammar') is True
            and integrity.get('tables') == 27 and integrity.get('revision') == REVISION
            and type(integrity.get('size_bytes')) is int and integrity['size_bytes'] > 0
            and re.fullmatch('[0-9a-f]{64}', integrity.get('sha256', '')), 'dump_integrity')
    after = adapter.snapshot(SOURCE)
    compare(before, after)
    adapter.write_exclusive(paths['after'], after)
    proof = {'format': 1, 'database': SOURCE, 'revision': REVISION, 'total_tables': 27,
             'dump_sha256': integrity['sha256'], 'size_bytes': integrity['size_bytes'],
             'baseline_sha256': digest(before), 'source_hashes': before['source_hashes'],
             'created_utc': datetime.now(timezone.utc).isoformat(),
             'archive_format': 'lankapex-logical-v1', 'recoverability_verified': False,
             'migration_runner_compatible': False}
    adapter.write_exclusive(paths['backup'], proof)
    return proof


def verify_restore(adapter, *, execute=False, confirm_target=None, approved_new_target=False,
                   artifact_id=None, dump_sha256=None, baseline_sha256=None):
    if not execute:
        return {'status': 'OFFLINE_PREPARATION', 'database_changed': False}
    require(confirm_target == RESTORE and approved_new_target is True, 'restore_confirmation')
    paths = artifact_paths(artifact_id)
    adapter.validate_private_paths(paths, restore=True)
    before, proof = adapter.read_backup(paths)
    validate_snapshot(before)
    require(digest(before) == baseline_sha256 == proof.get('baseline_sha256')
            and proof.get('dump_sha256') == dump_sha256, 'backup_binding')
    require(proof.get('database') == SOURCE and proof.get('revision') == REVISION
            and proof.get('total_tables') == 27 and proof.get('source_hashes') == before['source_hashes']
            and proof.get('recoverability_verified') is False, 'backup_proof')
    require(adapter.current_source_hashes() == before['source_hashes'], 'source_binding')
    integrity = adapter.inspect_dump(paths['dump'], before)
    require(integrity.get('validated_grammar') is True
            and integrity.get('sha256') == dump_sha256
            and integrity.get('size_bytes') == proof.get('size_bytes'), 'dump_integrity')
    adapter.assert_empty_isolated_target(RESTORE, RESTORE_ACCOUNT)
    adapter.restore_once(paths['dump'], None)
    after = adapter.snapshot(RESTORE)
    compare(before, after, restored=True)
    result = {'format': 1, 'database': RESTORE, 'source_database': SOURCE,
              'revision': REVISION, 'dump_sha256': dump_sha256,
              'baseline_sha256': baseline_sha256, 'source_hashes': before['source_hashes'],
              'verified_utc': datetime.now(timezone.utc).isoformat(),
              'restore_verified': True, 'migration_verified': False,
              'migration_runner_compatible': False}
    adapter.write_exclusive(paths['restore'], result)
    return result


MAX_ARCHIVE = 256 * 1024 * 1024


def identifier(value):
    require(isinstance(value, str) and re.fullmatch('[A-Za-z_][A-Za-z0-9_]*', value), 'identifier')
    return '`' + value + '`'


def untyped(value):
    require(isinstance(value, list) and value, 'archive_value')
    kind = value[0]
    try:
        if kind == 'null' and len(value) == 1:
            return None
        require(len(value) == (4 if kind == 'timedelta' else 2), 'archive_value')
        if kind == 'text' and isinstance(value[1], str):
            result = value[1]
        elif kind == 'bool' and type(value[1]) is bool:
            result = value[1]
        elif kind == 'int':
            result = int(value[1])
        elif kind == 'decimal':
            result = Decimal(value[1])
        elif kind == 'bytes':
            result = bytes.fromhex(value[1])
        elif kind in ('datetime', 'date', 'time'):
            result = {'datetime': datetime, 'date': date, 'time': time}[kind].fromisoformat(value[1])
        elif kind == 'timedelta':
            result = timedelta(days=int(value[1]), seconds=int(value[2]), microseconds=int(value[3]))
        else:
            raise RecoveryStop('archive_value')
        require(typed(result) == value, 'archive_value')
        return result
    except (ValueError, TypeError, OverflowError):
        raise RecoveryStop('archive_value') from None


def validate_ddl(table, ddl, allowed_tables=TABLES):
    """Single CREATE TABLE only. Quoted literals are lexed, not regex-stripped.

    Archive data never becomes SQL: restored values use DBAPI parameters.
    Qualified references, comments, extra statements and executable objects stop.
    """
    require(allowed_tables in (TABLES, TABLES | QR_TABLES), 'archive_schema')
    require(table in allowed_tables and isinstance(ddl, str), 'archive_schema')
    require(ddl.startswith('CREATE TABLE ' + identifier(table) + ' ('), 'archive_schema')
    tokens, index = [], 0
    while index < len(ddl):
        char = ddl[index]
        if char in "'\"`":
            quote, end = char, index + 1
            while end < len(ddl):
                if ddl[end] == '\\' and quote != '`':
                    end += 2
                elif ddl[end] == quote:
                    if end + 1 < len(ddl) and ddl[end + 1] == quote:
                        end += 2
                    else:
                        break
                else:
                    end += 1
            require(end < len(ddl), 'archive_schema')
            tokens.append(' ID ' if quote == '`' else ' LITERAL ')
            index = end + 1
        else:
            tokens.append(char)
            index += 1
    code = ''.join(tokens)
    code = re.sub(r'\bON\s+(?:DELETE|UPDATE)\s+(?:RESTRICT|CASCADE|NO\s+ACTION|SET\s+NULL)\b',
                  ' FK_ACTION ', code, flags=re.I)
    code = re.sub(r'\bON\s+UPDATE\s+CURRENT_TIMESTAMP(?:\(\d*\))?',
                  ' UPDATE_DEFAULT ', code, flags=re.I)
    require(not re.search(r';|/\*|\*/|--|#|\b(?:SELECT|INSERT|UPDATE|DELETE|DROP|TRUNCATE|'
                          r'DATABASE|SCHEMA|DEFINER|TRIGGER|PROCEDURE|FUNCTION|EVENT|'
                          r'PREPARE|EXECUTE|OUTFILE|INFILE|LOAD|GRANT|REVOKE|CALL|'
                          r'TABLESPACE|DIRECTORY|CONNECTION|SERVER|UNION)\b',
                          code, re.I), 'archive_schema')
    require(not re.search(r'\b[A-Za-z_]\w*\s*\.\s*[A-Za-z_]\w*\b', code), 'archive_schema')
    require(len(re.findall(r'\bCREATE\b', code, re.I)) == 1
            and re.search(r'\bENGINE=InnoDB\b', code), 'archive_schema')
    # REFERENCES may only name known tables; names cannot be schema-qualified.
    refs = re.findall(r'\bREFERENCES\s+`([A-Za-z_][A-Za-z0-9_]*)`', ddl, re.I)
    require(all(name in allowed_tables for name in refs), 'archive_schema')
    return ddl


def validate_archive(archive, baseline):
    require(isinstance(archive, dict) and archive.get('format') == 'lankapex-logical-v1'
            and archive.get('database') == SOURCE and archive.get('revision') == REVISION,
            'archive_identity')
    require(archive.get('baseline_sha256') == digest(baseline), 'archive_binding')
    tables = archive.get('tables')
    require(isinstance(tables, dict) and set(tables) == TABLES, 'archive_inventory')
    for name, table in tables.items():
        validate_ddl(name, table['ddl'])
        require(digest(table['ddl']) == baseline['tables'][name]['schema_sha256'], 'archive_schema')
        columns, keys, rows = table['columns'], table['primary_key'], table['rows']
        require(columns and len(set(columns)) == len(columns) and keys
                and set(keys) <= set(columns), 'archive_columns')
        for column in columns:
            identifier(column)
        require(all(len(row) == len(columns) for row in rows), 'archive_rows')
        restored_rows = ((untyped(value) for value in row) for row in rows)
        require(row_fingerprint(restored_rows) == {
            key: baseline['tables'][name][key] for key in ('rows', 'sha256')}, 'archive_rows')
    require(tables['alembic_version']['columns'] == ['version_num']
            and tables['alembic_version']['rows'] == [[typed(REVISION)]], 'archive_revision')


def migration_paths(artifact_id):
    artifact_paths(artifact_id)  # Validate the immutable naming contract first.
    return {kind: PRIVATE / name for kind, name in (
        ('sql', f'source-{artifact_id}.sql'), ('baseline', f'baseline-{artifact_id}.json'),
        ('baseline_report', f'baseline-binding-{artifact_id}.json'),
        ('export_report', f'sql-export-{artifact_id}.json'),
        ('sql_restore_report', f'sql-restore-proof-{artifact_id}.json'),
        ('backup_proof', f'backup-proof-{artifact_id}.json'))}


def sql_literal(value):
    """No connection/escaping state: strings use UTF-8 hex, binary uses hex."""
    typed(value)  # Reject floats and non-finite/unsupported values.
    if value is None:
        return 'NULL'
    if isinstance(value, bool):
        return '1' if value else '0'
    if isinstance(value, int):
        require(-(1 << 63) <= value <= (1 << 64) - 1, 'sql_integer_range')
        return str(value)
    if isinstance(value, Decimal):
        parts = value.as_tuple()
        require(len(parts.digits) <= 65 and -65 <= parts.exponent <= 65, 'sql_decimal_range')
        return format(value, 'f')  # No scientific notation or float conversion.
    if isinstance(value, bytes):
        return "X'" + value.hex() + "'"
    if isinstance(value, str):
        return "CONVERT(X'" + value.encode('utf-8').hex() + "' USING utf8mb4)"
    if isinstance(value, datetime):
        require(value.tzinfo is None, 'sql_timestamp_timezone')
        return "'" + value.isoformat(sep=' ', timespec='microseconds') + "'"
    if isinstance(value, time):
        require(value.tzinfo is None, 'sql_timestamp_timezone')
        return "'" + value.isoformat(timespec='microseconds') + "'"
    if isinstance(value, date):
        return "'" + value.isoformat() + "'"
    if isinstance(value, timedelta):
        micros = ((value.days * 86400 + value.seconds) * 1_000_000 + value.microseconds)
        sign = '-' if micros < 0 else ''
        seconds, fraction = divmod(abs(micros), 1_000_000)
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        require(hours <= 838, 'sql_time_range')
        return f"'{sign}{hours:02d}:{minutes:02d}:{seconds:02d}.{fraction:06d}'"
    raise RecoveryStop('unsupported_value')


def isolated_ddl(table, ddl):
    validate_ddl(table, ddl)
    pieces, index = [], 0
    while index < len(ddl):
        if ddl[index] in "'\"`":
            quote, end = ddl[index], index + 1
            while end < len(ddl):
                if ddl[end] == '\\' and quote != '`':
                    end += 2
                elif ddl[end] == quote:
                    if end + 1 < len(ddl) and ddl[end + 1] == quote:
                        end += 2
                    else:
                        break
                else:
                    end += 1
            require(end < len(ddl), 'archive_schema')
            pieces.append(ddl[index:end + 1])
            index = end + 1
            continue
        match = re.match(r'\bREFERENCES\s+`([A-Za-z_][A-Za-z0-9_]*)`', ddl[index:], re.I)
        if match and (index == 0 or not (ddl[index - 1].isalnum() or ddl[index - 1] == '_')):
            require(match[1] in TABLES, 'archive_schema')
            pieces.append('REFERENCES ' + identifier(RESTORE) + '.' + identifier(match[1]))
            index += match.end()
        else:
            pieces.append(ddl[index])
            index += 1
    result = ''.join(pieces)
    prefix = 'CREATE TABLE ' + identifier(table)
    require(result.startswith(prefix + ' ('), 'archive_schema')
    return 'CREATE TABLE ' + identifier(RESTORE) + '.' + identifier(table) + result[len(prefix):]


def canonical_self_references(ddl, database):
    """Only normalize an explicitly verified isolated schema's self references.

    Server SHOW CREATE may retain or omit qualification. External schemas remain
    unchanged and are rejected by validate_ddl/FK metadata checks.
    """
    if database not in (RESTORE, EXISTING_RESTORE):
        return ddl
    pieces, index = [], 0
    while index < len(ddl):
        if ddl[index] in "'\"`":
            quote, end = ddl[index], index + 1
            while end < len(ddl):
                if ddl[end] == '\\' and quote != '`':
                    end += 2
                elif ddl[end] == quote:
                    if end + 1 < len(ddl) and ddl[end + 1] == quote:
                        end += 2
                    else:
                        break
                else:
                    end += 1
            require(end < len(ddl), 'archive_schema')
            pieces.append(ddl[index:end + 1])
            index = end + 1
            continue
        match = re.match(r'\bREFERENCES\s+' + re.escape(identifier(database))
                         + r'\.`([A-Za-z_][A-Za-z0-9_]*)`', ddl[index:], re.I)
        if match and (index == 0 or not (ddl[index - 1].isalnum() or ddl[index - 1] == '_')):
            require(match[1] in TABLES | QR_TABLES, 'foreign_key_scope')
            pieces.append('REFERENCES ' + identifier(match[1]))
            index += match.end()
        else:
            pieces.append(ddl[index])
            index += 1
    return ''.join(pieces)


def sql_export_bytes(archive, before, restore_target=RESTORE):
    require(restore_target == RESTORE, 'restore_target')
    validate_snapshot(before)
    validate_archive(archive, before)
    statements = ['-- LankaPex isolated SQL export v1']
    variables = ('sql_mode', 'time_zone', 'foreign_key_checks', 'character_set_client',
                 'character_set_results', 'collation_connection')
    statements += [f'SET @lpx_saved_{name}=@@SESSION.{name};' for name in variables]
    statements += ["SET SESSION sql_mode='STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION';",
                   "SET SESSION time_zone='+00:00';", 'SET NAMES utf8mb4;',
                   'SET SESSION foreign_key_checks=0;']
    for name, table in sorted(archive['tables'].items()):
        statements.append(isolated_ddl(name, table['ddl']) + ';')
    statements.append('START TRANSACTION;')
    for name, table in sorted(archive['tables'].items()):
        columns = ','.join(map(identifier, table['columns']))
        for row in table['rows']:
            values = ','.join(sql_literal(untyped(value)) for value in row)
            statements.append('INSERT INTO ' + identifier(RESTORE) + '.' + identifier(name)
                              + ' (' + columns + ') VALUES (' + values + ');')
    statements.append('COMMIT;')
    statements += [f'SET SESSION {name}=@lpx_saved_{name};' for name in reversed(variables)]
    raw = ('\n'.join(statements) + '\n').encode('utf-8')
    require(0 < len(raw) <= MAX_ARCHIVE, 'sql_export_limit')
    return raw


def migration_modules():
    if str(Path(__file__).parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).parent))
    import demo_qr_migration_guard as guard
    import demo_qr_preservation as preservation
    return guard, preservation


def validate_migration_baseline(value, before):
    _guard, preservation = migration_modules()
    require(isinstance(value, dict) and value.get('format') == 1
            and value.get('schema_reviewed_for_start') is True
            and re.fullmatch('[0-9a-f]{64}', value.get('full_schema_sha256', '')),
            'migration_baseline')
    preservation.validate(value['inventory'])
    require(all(value['inventory']['row_counts'][name] == before['tables'][name]['rows']
                for name in TABLES - {'alembic_version'}), 'baseline_row_counts')
    expected = before.get('inventory_fingerprints')
    require(isinstance(expected, dict) and set(expected) == {
        'preservation_fingerprints', 'signed_account_balance_fingerprint',
        'ledger_type_totals_fingerprint'}, 'baseline_inventory_binding')
    require(all(value['inventory'][key] == fingerprints for key, fingerprints in expected.items()),
            'baseline_preservation_binding')
    orphans = {}
    for key, count in before['foreign_key_orphans'].items():
        table, name = key.split(':', 1)
        orphans[table + ':' + hashlib.sha256(name.encode()).hexdigest()] = count
    require(value['inventory']['foreign_key_orphan_counts'] == orphans, 'baseline_fk_binding')


def produce_migration_baseline(adapter, *, execute=False, artifact_id=None,
                               archive_sha256=None, snapshot_digest=None,
                               reviewed_schema_sha256=None):
    if not execute:
        return {'status': 'OFFLINE_PREPARATION'}
    require(isinstance(reviewed_schema_sha256, str)
            and re.fullmatch('[0-9a-f]{64}', reviewed_schema_sha256), 'schema_review_required')
    paths, outputs = artifact_paths(artifact_id), migration_paths(artifact_id)
    for kind in ('baseline', 'baseline_report'):
        adapter.store.check(outputs[kind], absent=True)
    before = adapter.validated_backup(paths, archive_sha256, snapshot_digest)
    guard, _preservation = migration_modules()
    migration_hashes = guard.source_hashes()
    live, _records, report, metadata = adapter._capture(SOURCE, migration=True)
    compare(before, live)
    schema_sha256 = guard.schema_digest(metadata)
    require(schema_sha256 == reviewed_schema_sha256, 'reviewed_schema_mismatch')
    baseline = dict(format=1, schema_reviewed_for_start=True, inventory=report,
                    full_schema_sha256=schema_sha256)
    validate_migration_baseline(baseline, before)
    require(adapter.current_source_hashes() == before['source_hashes']
            and guard.source_hashes() == migration_hashes, 'source_binding')
    require(len(json.dumps(baseline, ensure_ascii=False).encode('utf-8')) <= 16 * 1024 * 1024,
            'migration_baseline_limit')
    adapter.store.write(outputs['baseline'], baseline)
    raw = adapter.store.read(outputs['baseline'])
    binding = dict(format=1, database=SOURCE, revision=REVISION,
                   archive_sha256=archive_sha256, snapshot_digest=snapshot_digest,
                   baseline_sha256=hashlib.sha256(raw).hexdigest(),
                   full_schema_sha256=schema_sha256,
                   recovery_source_hashes=before['source_hashes'],
                   migration_source_hashes=migration_hashes,
                   created_utc=datetime.now(timezone.utc).isoformat())
    adapter.store.write(outputs['baseline_report'], binding)
    return binding


def export_migration_sql(adapter, *, execute=False, artifact_id=None,
                         archive_sha256=None, snapshot_digest=None,
                         migration_baseline_sha256=None):
    if not execute:
        return {'status': 'OFFLINE_PREPARATION'}
    paths, outputs = artifact_paths(artifact_id), migration_paths(artifact_id)
    for kind in ('sql', 'export_report'):
        adapter.store.check(outputs[kind], absent=True)
    before = adapter.validated_backup(paths, archive_sha256, snapshot_digest)
    baseline_raw = adapter.store.read(outputs['baseline'])
    require(hashlib.sha256(baseline_raw).hexdigest() == migration_baseline_sha256,
            'migration_baseline_checksum')
    baseline = json.loads(baseline_raw.decode('utf-8'))
    validate_migration_baseline(baseline, before)
    binding = json.loads(adapter.store.read(outputs['baseline_report']).decode('utf-8'))
    guard, _preservation = migration_modules()
    migration_hashes = guard.source_hashes()
    require(binding.get('baseline_sha256') == migration_baseline_sha256
            and binding.get('archive_sha256') == archive_sha256
            and binding.get('snapshot_digest') == snapshot_digest
            and binding.get('full_schema_sha256') == baseline['full_schema_sha256']
            and binding.get('recovery_source_hashes') == adapter.current_source_hashes()
            and binding.get('migration_source_hashes') == migration_hashes, 'baseline_binding')
    raw = sql_export_bytes(adapter.archive, before)
    adapter.store.write_bytes(outputs['sql'], raw)
    actual = adapter.store.read(outputs['sql'])
    require(actual == raw, 'sql_export_integrity')
    require(adapter.current_source_hashes() == before['source_hashes']
            and guard.source_hashes() == migration_hashes, 'source_binding')
    report = dict(format=1, database=SOURCE, revision=REVISION,
                  restore_target=RESTORE, archive_sha256=archive_sha256,
                  baseline_sha256=migration_baseline_sha256,
                  sql_sha256=hashlib.sha256(actual).hexdigest(), size_bytes=len(actual),
                  recovery_source_hashes=before['source_hashes'],
                  migration_source_hashes=migration_hashes,
                  sql_restore_verified=False, backup_proof_issued=False,
                  migration_verified=False, created_utc=datetime.now(timezone.utc).isoformat())
    adapter.store.write(outputs['export_report'], report)
    return report


def split_verified_sql(raw):
    """Split exporter bytes without treating quoted semicolons as commands.

    Caller must first establish byte-for-byte equality to the validated exporter.
    This is not a general-purpose SQL importer or client-command interpreter.
    """
    header = b'-- LankaPex isolated SQL export v1\n'
    require(isinstance(raw, bytes) and raw.startswith(header)
            and 0 < len(raw) <= MAX_ARCHIVE, 'sql_export_integrity')
    text = raw[len(header):].decode('utf-8')
    statements, start, index = [], 0, 0
    while index < len(text):
        if text[index] in "'\"`":
            quote = text[index]
            index += 1
            while index < len(text):
                if text[index] == '\\' and quote != '`':
                    index += 2
                elif text[index] == quote:
                    if index + 1 < len(text) and text[index + 1] == quote:
                        index += 2
                    else:
                        break
                else:
                    index += 1
            require(index < len(text), 'sql_statement_format')
        elif text[index] == ';':
            statement = text[start:index].strip()
            require(bool(statement), 'sql_statement_format')
            statements.append(statement)
            start = index + 1
        index += 1
    require(not text[start:].strip() and statements, 'sql_statement_format')
    return statements


def verify_sql_restore(adapter, *, execute=False, confirm_target=None,
                       approved_new_target=False, artifact_id=None, archive_sha256=None,
                       snapshot_digest=None, migration_baseline_sha256=None,
                       sql_sha256=None, export_report_sha256=None):
    if not execute:
        return {'status': 'OFFLINE_PREPARATION'}
    require(confirm_target == RESTORE and approved_new_target is True, 'restore_confirmation')
    require(all(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value)
                for value in (archive_sha256, snapshot_digest, migration_baseline_sha256,
                              sql_sha256, export_report_sha256)), 'sql_restore_pins')
    paths, outputs = artifact_paths(artifact_id), migration_paths(artifact_id)
    for kind in ('sql_restore_report', 'backup_proof'):
        adapter.store.check(outputs[kind], absent=True)
    before = adapter.validated_backup(paths, archive_sha256, snapshot_digest)
    baseline_raw = adapter.store.read(outputs['baseline'])
    require(hashlib.sha256(baseline_raw).hexdigest() == migration_baseline_sha256,
            'migration_baseline_checksum')
    baseline = json.loads(baseline_raw.decode('utf-8'))
    validate_migration_baseline(baseline, before)
    binding = json.loads(adapter.store.read(outputs['baseline_report']).decode('utf-8'))
    report_raw = adapter.store.read(outputs['export_report'])
    require(hashlib.sha256(report_raw).hexdigest() == export_report_sha256,
            'sql_export_report_checksum')
    exported = json.loads(report_raw.decode('utf-8'))
    guard, _preservation = migration_modules()
    migration_hashes = guard.source_hashes()
    require(binding.get('baseline_sha256') == migration_baseline_sha256
            and binding.get('archive_sha256') == archive_sha256
            and binding.get('snapshot_digest') == snapshot_digest
            and binding.get('full_schema_sha256') == baseline['full_schema_sha256']
            and binding.get('recovery_source_hashes') == before['source_hashes']
            and binding.get('migration_source_hashes') == migration_hashes, 'baseline_binding')
    require(exported.get('format') == 1 and exported.get('database') == SOURCE
            and exported.get('revision') == REVISION and exported.get('restore_target') == RESTORE
            and exported.get('archive_sha256') == archive_sha256
            and exported.get('baseline_sha256') == migration_baseline_sha256
            and exported.get('sql_sha256') == sql_sha256
            and exported.get('recovery_source_hashes') == before['source_hashes']
            and exported.get('migration_source_hashes') == migration_hashes
            and exported.get('sql_restore_verified') is False
            and exported.get('backup_proof_issued') is False
            and exported.get('migration_verified') is False, 'sql_export_binding')
    raw = adapter.store.read(outputs['sql'])
    require(type(exported.get('size_bytes')) is int and len(raw) == exported['size_bytes'] > 0
            and hashlib.sha256(raw).hexdigest() == sql_sha256
            and raw == sql_export_bytes(adapter.archive, before), 'sql_export_integrity')
    require(adapter.current_source_hashes() == before['source_hashes'], 'source_binding')
    adapter.assert_empty_isolated_target(RESTORE, RESTORE_ACCOUNT)
    # Execute the checked artifact bytes, not the logical-archive restore method.
    adapter.restore_sql_once(raw, before, RESTORE)
    after = adapter.snapshot(RESTORE)
    compare(before, after, restored=True)
    require(before.get('inventory_fingerprints') == after.get('inventory_fingerprints'),
            'sql_restore_financial_preservation')
    require(adapter.current_source_hashes() == before['source_hashes']
            and guard.source_hashes() == migration_hashes, 'source_binding')
    restored = dict(format=1, database=RESTORE, account=RESTORE_ACCOUNT,
                    source_database=SOURCE, revision=REVISION,
                    archive_sha256=archive_sha256, sql_sha256=sql_sha256,
                    baseline_sha256=migration_baseline_sha256,
                    restore_verified=True, full_row_preservation_verified=True,
                    schema_verified=True, financial_preservation_verified=True,
                    foreign_keys_verified=True, migration_verified=False,
                    recovery_source_hashes=before['source_hashes'],
                    migration_source_hashes=migration_hashes, restored_snapshot=after,
                    verified_utc=datetime.now(timezone.utc).isoformat())
    adapter.store.write(outputs['sql_restore_report'], restored)
    restore_raw = adapter.store.read(outputs['sql_restore_report'])
    require(json.loads(restore_raw.decode('utf-8')) == restored, 'sql_restore_proof_integrity')
    # Exact unchanged guard backup contract. Rehearsal and pause proofs are NOT
    # produced or inferred; a populated-demo migration remains blocked.
    proof = dict(format=1, database=SOURCE, revision=REVISION, total_tables=27,
                 complete_schema_and_rows=True, stored_objects_reviewed=True,
                 baseline_sha256=migration_baseline_sha256,
                 dump_path=str(outputs['sql']), size_bytes=len(raw), dump_sha256=sql_sha256,
                 restore_database=RESTORE, restore_verified=True,
                 sql_restore_proof_sha256=hashlib.sha256(restore_raw).hexdigest(),
                 recovery_source_hashes=before['source_hashes'],
                 migration_source_hashes=migration_hashes,
                 created_utc=datetime.now(timezone.utc).isoformat())
    adapter.store.write(outputs['backup_proof'], proof)
    return proof


class WindowsPrivateStore:
    """Hold all ancestors against rename/delete; new files have protected DACLs.

    Existing directories must already pass the reviewed metadata-only validator.
    No existing ACL, owner, credential or directory is changed.
    """
    def __init__(self):
        self.handles = []

    def __enter__(self):
        import os
        import ctypes as ct
        from ctypes import wintypes as wt
        import subprocess
        require(os.name == 'nt', 'windows_required')
        self.ct, self.wt = ct, wt
        self.kernel = ct.WinDLL('kernel32', use_last_error=True)
        self.advapi = ct.WinDLL('advapi32', use_last_error=True)
        self.kernel.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ct.c_void_p,
                                          wt.DWORD, wt.DWORD, wt.HANDLE]
        self.kernel.CreateFileW.restype = wt.HANDLE
        self.kernel.CloseHandle.argtypes = [wt.HANDLE]
        self.kernel.GetFileAttributesW.argtypes = [wt.LPCWSTR]
        self.kernel.GetFileAttributesW.restype = wt.DWORD
        self.kernel.GetFinalPathNameByHandleW.argtypes = [wt.HANDLE, wt.LPWSTR, wt.DWORD, wt.DWORD]
        self.kernel.GetFinalPathNameByHandleW.restype = wt.DWORD
        self.kernel.LocalFree.argtypes = [ct.c_void_p]
        self.advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
            wt.LPCWSTR, wt.DWORD, ct.POINTER(ct.c_void_p), ct.c_void_p]
        try:
            for part in reversed((PRIVATE, *PRIVATE.parents)):
                attributes = self.kernel.GetFileAttributesW(str(part))
                require(attributes != 0xFFFFFFFF and attributes & 0x10 and not attributes & 0x400,
                        'private_path')
                handle = self._open(part, 0x20000, 3, 3, 0x02200000, None)
                self.handles.append(handle)
                self._identity(handle, part)
            self._acl(PRIVATE)
            result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                                     '[Security.Principal.WindowsIdentity]::GetCurrent().User.Value'],
                                    capture_output=True, text=True, timeout=30, check=False)
            require(result.returncode == 0 and re.fullmatch(r'S-1-[0-9-]+', result.stdout.strip()),
                    'operator_identity')
            self.sid = result.stdout.strip()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def _open(self, path, access, share, disposition, flags, security):
        handle = self.kernel.CreateFileW(str(path), access, share, security, disposition, flags, None)
        require(handle != self.ct.c_void_p(-1).value, 'private_file_open')
        return handle

    def _identity(self, handle, path):
        buffer = self.ct.create_unicode_buffer(32768)
        length = self.kernel.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
        require(0 < length < len(buffer)
                and buffer.value.removeprefix('\\\\?\\').rstrip('\\').casefold()
                == str(path).rstrip('\\').casefold(), 'private_path_identity')

    def _acl(self, path):
        import subprocess
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-File',
                                 str(ROOT / 'backend/scripts/check_demo_qr_private_path.ps1'),
                                 '-Path', str(path)], capture_output=True, text=True,
                                timeout=30, check=False)
        require(result.returncode == 0 and result.stdout.strip() == 'PASS', 'private_acl')

    def check(self, path, absent=False):
        require(path.parent == PRIVATE, 'artifact_path')
        if absent:
            require(not path.exists() and not path.is_symlink(), 'existing_artifact')
        else:
            stat = path.lstat()
            require(path.is_file() and not getattr(stat, 'st_file_attributes', 0) & 0x400,
                    'artifact_path')
            self._acl(path)

    def write(self, path, value):
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
        self.write_bytes(path, raw)

    def write_bytes(self, path, raw):
        import msvcrt
        import os
        require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_ARCHIVE, 'archive_limit')
        ct, wt = self.ct, self.wt
        class SecurityAttributes(ct.Structure):
            _fields_ = [('length', wt.DWORD), ('descriptor', ct.c_void_p), ('inherit', wt.BOOL)]
        descriptor = ct.c_void_p()
        sddl = f'O:{self.sid}D:P(A;;FA;;;{self.sid})(A;;FA;;;SY)'
        require(self.advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl, 1, ct.byref(descriptor), None), 'private_file_security')
        handle = None
        try:
            security = SecurityAttributes(ct.sizeof(SecurityAttributes), descriptor, False)
            handle = self._open(path, 0x40000000, 0, 1, 0x80, ct.byref(security))
            self._identity(handle, path)
            fd = msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)
            handle = None  # fd now owns the native handle.
            with os.fdopen(fd, 'wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            self._acl(path)
        finally:
            if handle is not None:
                self.kernel.CloseHandle(handle)
            self.kernel.LocalFree(descriptor)

    def read(self, path):
        self.check(path)
        handle = self._open(path, 0x80000000, 1, 3, 0x00200000, None)
        # The handle denies writes/deletion until adapter context exit. The same
        # validated in-memory bytes are restored; the path is never reopened.
        self.handles.append(handle)
        self._identity(handle, path)
        duplicate = path.open('rb')
        try:
            raw = duplicate.read(MAX_ARCHIVE + 1)
        finally:
            duplicate.close()
        require(len(raw) <= MAX_ARCHIVE, 'archive_limit')
        return raw

    def __exit__(self, *_args):
        for handle in reversed(self.handles):
            self.kernel.CloseHandle(handle)
        self.handles.clear()


class LiveRecoveryAdapter:
    """Direct DBAPI logical archive; no native clients or password subprocesses."""
    def __init__(self, store, connect, password, tls_ca):
        self.store, self.connect, self.password, self.tls_ca = store, connect, password, tls_ca
        self.archive = None
        self.cached = {}
        self._secret = None

    def current_source_hashes(self):
        return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in BOUND_SOURCES}

    def validate_private_paths(self, paths, all_absent=False, restore=False):
        for kind, path in paths.items():
            self.store.check(path, absent=all_absent or kind == 'restore')

    def write_exclusive(self, path, value):
        self.store.write(path, value)

    def read_backup(self, paths):
        return tuple(json.loads(self.store.read(paths[kind]).decode('utf-8'))
                     for kind in ('before', 'backup'))

    def validated_backup(self, paths, archive_sha256, snapshot_digest):
        before, proof = self.read_backup(paths)
        validate_snapshot(before)
        require(isinstance(archive_sha256, str) and re.fullmatch('[0-9a-f]{64}', archive_sha256)
                and proof.get('format') == 1 and proof.get('recoverability_verified') is False
                and digest(before) == snapshot_digest == proof.get('baseline_sha256')
                and proof.get('database') == SOURCE and proof.get('revision') == REVISION
                and proof.get('total_tables') == 27 and proof.get('dump_sha256') == archive_sha256
                and proof.get('source_hashes') == self.current_source_hashes() == before['source_hashes'],
                'backup_binding')
        integrity = self.inspect_dump(paths['dump'], before)
        require(integrity['sha256'] == archive_sha256 and integrity['size_bytes'] == proof.get('size_bytes'),
                'dump_integrity')
        return before

    def _connection(self, database):
        require(database in (SOURCE, RESTORE), 'target')
        user = SOURCE_ACCOUNT.split('@')[0] if database == SOURCE else RESTORE_ACCOUNT.split('@')[0]
        if self._secret is None:
            self._secret = self.password()
            require(isinstance(self._secret, str) and self._secret, 'credential_unavailable')
        return self.connect(database, user, self._secret, self.tls_ca)

    def _identity(self, conn, database, empty=False):
        with conn.cursor() as cursor:
            cursor.execute('SELECT DATABASE(), CURRENT_USER(), @@port, CURRENT_ROLE(), @@GLOBAL.partial_revokes, @@SESSION.sql_mode, @@SESSION.foreign_key_checks')
            db, account, port, roles, partial, mode, checks = cursor.fetchone()
            require((db, account, port, roles) == (database, SOURCE_ACCOUNT if database == SOURCE else RESTORE_ACCOUNT, 3306, 'NONE'), 'identity')
            require(not partial and checks == 1 and 'STRICT_TRANS_TABLES' in mode.split(',')
                    and not {'NO_BACKSLASH_ESCAPES', 'ANSI_QUOTES'} & set(mode.split(',')), 'server_settings')
            cursor.execute('SHOW GRANTS FOR CURRENT_USER()')
            rights = set()
            for row in cursor.fetchall():
                grant = row[0]
                if re.fullmatch(r'GRANT USAGE ON \*\.\* TO [^ ]+', grant):
                    continue
                match = re.fullmatch(r'GRANT ([A-Z, ]+) ON `([^`]+)`\.\* TO [^ ]+', grant)
                require(match is not None and match[2] == database.replace('_', '\\_'), 'grants')
                rights.update(match[1].split(', '))
            expected = {'SELECT', 'INSERT', 'UPDATE', 'DELETE'} if database == SOURCE else {'SELECT', 'INSERT', 'CREATE', 'ALTER', 'INDEX', 'REFERENCES'}
            require(rights == expected, 'grants')
            if empty:
                cursor.execute('SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()')
                require(cursor.fetchone()[0] == 0, 'nonempty_restore_target')
                cursor.execute('SELECT (SELECT COUNT(*) FROM information_schema.ROUTINES '
                    'WHERE ROUTINE_SCHEMA=DATABASE())+(SELECT COUNT(*) FROM information_schema.EVENTS '
                    'WHERE EVENT_SCHEMA=DATABASE())')
                require(cursor.fetchone()[0] == 0, 'nonempty_restore_target')
            return sorted(rights)

    def capture_policy(self, database):
        require(database in (SOURCE, RESTORE), 'target')
        account = SOURCE_ACCOUNT if database == SOURCE else RESTORE_ACCOUNT
        rights = {'SELECT', 'INSERT', 'UPDATE', 'DELETE'} if database == SOURCE else {
            'SELECT', 'INSERT', 'CREATE', 'ALTER', 'INDEX', 'REFERENCES'}
        return account, rights, REVISION, TABLES

    def validate_capture(self, snapshot, database):
        validate_snapshot(snapshot, database)

    def enrich_capture(self, connection, inspector, result, records, database):
        """Optional metadata-only extension within the same read-only snapshot."""

    def _capture(self, database, migration=False):
        # SQLAlchemy is used for metadata inspection only, never an app engine.
        import sqlalchemy as sa
        from importlib.metadata import version
        import inventory_demo_database as inventory
        account, _rights, revision, expected_tables = self.capture_policy(database)
        engine = sa.create_engine('mysql+pymysql://', creator=lambda: self._connection(database),
                                  echo=False, hide_parameters=True, poolclass=sa.pool.NullPool)
        try:
            with engine.connect() as connection:
                native = connection.connection.driver_connection
                rights = self._identity(native, database)
                connection.exec_driver_sql("SET SESSION time_zone='+00:00'")
                connection.exec_driver_sql('SET SESSION TRANSACTION READ ONLY')
                connection.rollback()
                connection.exec_driver_sql('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
                connection.exec_driver_sql('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY')
                inspector = sa.inspect(connection)
                names = inspector.get_table_names()
                require(set(names) == expected_tables and not inspector.get_view_names(), 'inventory')
                objects = connection.exec_driver_sql('SELECT '
                    '(SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=DATABASE())+'
                    '(SELECT COUNT(*) FROM information_schema.EVENTS WHERE EVENT_SCHEMA=DATABASE())+'
                    '(SELECT COUNT(*) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=DATABASE())').scalar_one()
                require(objects == 0, 'stored_objects')
                charset, collation = connection.exec_driver_sql('SELECT DEFAULT_CHARACTER_SET_NAME, '
                    'DEFAULT_COLLATION_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=DATABASE()').one()
                require(connection.exec_driver_sql('SELECT version_num FROM alembic_version').scalars().all() == [revision], 'revision')
                records, tables, orphans = {}, {}, {}
                size = total_rows = 0
                for table in sorted(names):
                    columns = inspector.get_columns(table)
                    require(all(not c.get('computed') for c in columns), 'generated_columns')
                    cols = [c['name'] for c in columns]
                    keys = inspector.get_pk_constraint(table)['constrained_columns']
                    require(keys, 'primary_key')
                    ddl = canonical_self_references(
                        connection.exec_driver_sql('SHOW CREATE TABLE ' + identifier(table)).one()[1], database)
                    validate_ddl(table, ddl, expected_tables)
                    rows = connection.execution_options(stream_results=True).exec_driver_sql(
                        'SELECT ' + ','.join(map(identifier, cols)) + ' FROM ' + identifier(table)
                        + ' ORDER BY ' + ','.join(map(identifier, keys)))
                    encoded, full_hash = [], hashlib.sha256()
                    try:
                        for row in rows:
                            values = [typed(value) for value in row]
                            raw = json.dumps(values, ensure_ascii=False, separators=(',', ':')).encode('utf-8') + b'\n'
                            size += len(raw)
                            total_rows += 1
                            require(size <= MAX_ARCHIVE and total_rows <= 1_000_000, 'archive_limit')
                            full_hash.update(raw)
                            encoded.append(values)
                    finally:
                        rows.close()
                        connection.execution_options(stream_results=False)
                    records[table] = dict(ddl=ddl, columns=cols, primary_key=keys, rows=encoded)
                    tables[table] = dict(schema_sha256=digest(ddl), rows=len(encoded), sha256=full_hash.hexdigest())
                    for fk in inspector.get_foreign_keys(table):
                        require(fk.get('referred_schema') in (None, database) and fk['referred_table'] in expected_tables, 'foreign_key_scope')
                        child, parent = fk['constrained_columns'], fk['referred_columns']
                        require(child and len(child) == len(parent), 'foreign_key_shape')
                        join = ' AND '.join('c.' + identifier(a) + '=p.' + identifier(b) for a, b in zip(child, parent))
                        present = ' AND '.join('c.' + identifier(a) + ' IS NOT NULL' for a in child)
                        query = 'SELECT COUNT(*) FROM ' + identifier(table) + ' c LEFT JOIN ' + identifier(fk['referred_table']) + ' p ON ' + join + ' WHERE ' + present + ' AND p.' + identifier(parent[0]) + ' IS NULL'
                        orphans[table + ':' + fk['name']] = connection.exec_driver_sql(query).scalar_one()
                financial, compatible = {}, {'preservation_fingerprints': {}}
                for table, projection in inventory.PROJECTIONS.items():
                    keys = records[table]['primary_key']
                    rows = list(connection.exec_driver_sql('SELECT ' + ','.join(map(identifier, projection.split())) + ' FROM ' + identifier(table) + ' ORDER BY ' + ','.join(map(identifier, keys))))
                    financial[table] = row_fingerprint(rows)['sha256']
                    compatible['preservation_fingerprints'][table] = inventory.fingerprint(rows)
                balances = list(connection.exec_driver_sql(inventory.BALANCES))
                totals = list(connection.exec_driver_sql(inventory.LEDGER_TOTALS))
                financial['signed_account_balances'] = row_fingerprint(balances)['sha256']
                financial['ledger_type_totals'] = row_fingerprint(totals)['sha256']
                compatible['signed_account_balance_fingerprint'] = inventory.fingerprint(balances)
                compatible['ledger_type_totals_fingerprint'] = inventory.fingerprint(totals)
                result = dict(database=database, account=account,
                    host='localhost', port=3306, revision=revision, tables=tables, stored_objects=objects,
                    non_innodb=0, active_roles='NONE', global_usage_only=True, grant_scope=database,
                    privileges=rights, duplicate_profiles=connection.exec_driver_sql(inventory.DUPLICATES).scalar_one(),
                    foreign_key_orphans=orphans, financial_fingerprints=financial,
                    source_hashes=self.current_source_hashes(), versions={name: version(name) for name in ('SQLAlchemy', 'PyMySQL', 'alembic')})
                result['database_defaults'] = dict(charset=charset, collation=collation)
                result['inventory_fingerprints'] = compatible
                result['versions']['mysql'] = connection.exec_driver_sql('SELECT VERSION()').scalar_one()
                self.enrich_capture(connection, inspector, result, records, database)
                require(re.fullmatch(r'8\.0\.[0-9]+', result['versions']['mysql']) is not None,
                        'server_version')
                require(connection.exec_driver_sql('SELECT version_num FROM alembic_version').scalars().all() == [revision]
                        and set(sa.inspect(connection).get_table_names()) == expected_tables, 'schema_drift')
                for name in sorted(expected_tables):
                    current_ddl = canonical_self_references(
                        connection.exec_driver_sql('SHOW CREATE TABLE ' + identifier(name)).one()[1], database)
                    require(digest(current_ddl) == tables[name]['schema_sha256'], 'schema_drift')
                self.validate_capture(result, database)
                if migration:
                    require(database == SOURCE and revision == REVISION and expected_tables == TABLES,
                            'migration_baseline_identity')
                    guard, preservation = migration_modules()
                    report = inventory.collect(inventory.Reader(connection))
                    preservation.validate(report)
                    expanded = {key: [tuple(row) for row in connection.exec_driver_sql(query)]
                                for key, query in guard.META.items()}
                    require(all([tuple(row) for row in connection.exec_driver_sql(query)] == expanded[key]
                                for key, query in guard.META.items()), 'schema_drift')
                    require(all(digest(connection.exec_driver_sql('SHOW CREATE TABLE ' + identifier(name)).one()[1])
                                == tables[name]['schema_sha256'] for name in sorted(TABLES)), 'schema_drift')
                    connection.rollback()
                    return result, records, report, expanded
                connection.rollback()
                return result, records
        finally:
            engine.dispose()

    def snapshot(self, database):
        result, records = self._capture(database)
        self.cached[database] = (result, records)
        return result

    def dump_exclusive(self, path, _unused):
        before, records = self.cached[SOURCE]
        archive = dict(format='lankapex-logical-v1', database=SOURCE, revision=REVISION,
                       baseline_sha256=digest(before), tables=records)
        validate_archive(archive, before)
        self.store.write(path, archive)

    def inspect_dump(self, path, before):
        raw = self.store.read(path)
        archive = json.loads(raw.decode('utf-8'))
        validate_archive(archive, before)
        self.archive = archive
        return dict(validated_grammar=True, tables=27, revision=REVISION,
                    size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())

    def assert_empty_isolated_target(self, database, account):
        require((database, account) == (RESTORE, RESTORE_ACCOUNT), 'restore_target')
        conn = self._connection(database)
        try:
            self._identity(conn, database, empty=True)
        finally:
            conn.close()

    def restore_once(self, _path, _unused):
        require(self.archive is not None, 'missing_archive')
        conn = self._connection(RESTORE)
        try:
            self._identity(conn, RESTORE, empty=True)  # Repeat immediately before first DDL.
            with conn.cursor() as cursor:
                cursor.execute("SET SESSION time_zone='+00:00'")
                # Required for cyclic FKs; isolated session only. Re-enabling is
                # followed by explicit FK-orphan audits, not assumed validation.
                cursor.execute('SET SESSION foreign_key_checks=0')
                for name, table in sorted(self.archive['tables'].items()):
                    cursor.execute(validate_ddl(name, table['ddl']))
                for name, table in sorted(self.archive['tables'].items()):
                    statement = 'INSERT INTO ' + identifier(name) + ' (' + ','.join(map(identifier, table['columns'])) + ') VALUES (' + ','.join(['%s'] * len(table['columns'])) + ')'
                    for row in table['rows']:
                        cursor.execute(statement, tuple(untyped(value) for value in row))
                cursor.execute('SET SESSION foreign_key_checks=1')
            conn.commit()
        finally:
            # Closing rolls back uncommitted DML, but never assumes DDL rollback.
            conn.close()

    def restore_sql_once(self, raw, before, target):
        require(target == RESTORE and self.archive is not None, 'restore_target')
        require(raw == sql_export_bytes(self.archive, before, target), 'sql_export_integrity')
        statements = split_verified_sql(raw)
        conn = self._connection(RESTORE)
        try:
            self._identity(conn, RESTORE, empty=True)  # Last gate before the first artifact statement.
            with conn.cursor() as cursor:
                for statement in statements:
                    cursor.execute(statement)
            # COMMIT and session restoration are already in the exact artifact.
            self._identity(conn, RESTORE)
        finally:
            conn.close()  # Never retry, clean up DDL, or touch source on failure.


def secure_password():
    import getpass
    import warnings
    require(sys.stdin.isatty(), 'private_console_required')
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        value = getpass.getpass('Existing exact account password (hidden): ')
    require(bool(value), 'credential_unavailable')
    return value


def connect_mysql(database, user, password, tls_ca):
    require(database in (SOURCE, RESTORE)
            and user == (SOURCE_ACCOUNT if database == SOURCE else RESTORE_ACCOUNT).split('@')[0],
            'connection_identity')
    return connect_verified_mysql(database, user, password, tls_ca)


def connect_verified_mysql(database, user, password, tls_ca):
    """Transport shared with the exact existing-restore verifier; no app Settings."""
    import ssl
    import pymysql
    require(database in (SOURCE, RESTORE, EXISTING_RESTORE)
            and isinstance(user, str) and re.fullmatch('[A-Za-z0-9_]{1,32}', user),
            'connection_identity')
    context = ssl.create_default_context(cafile=str(tls_ca))
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    require(not pymysql.connections.DEBUG and not pymysql._auth.DEBUG, 'connector_tracing')
    connection = pymysql.connect(host='127.0.0.1', port=3306, database=database, user=user,
                           password=password, ssl=context, charset='utf8mb4', autocommit=False,
                           local_infile=False, defer_connect=True,
                           connect_timeout=5, read_timeout=60, write_timeout=60)
    try:
        # Explicit SSLContext is REQUIRED in the reviewed installed PyMySQL.
        # Refuse older/preferred-only connector implementations before authentication.
        require(connection.ssl and getattr(connection, '_ssl_required', False)
                and connection.ctx.check_hostname and connection.ctx.verify_mode == ssl.CERT_REQUIRED,
                'tls_required')
        connection.connect()
        require(isinstance(connection._sock, ssl.SSLSocket)
                and connection._sock.version() in ('TLSv1.2', 'TLSv1.3')
                and connection._sock.getpeername()[0] == '127.0.0.1', 'tls_identity')
        return connection
    except BaseException:
        connection.close()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('backup', 'restore', 'baseline', 'export-sql',
                                           'verify-sql-restore'), default='backup')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--confirm-target')
    parser.add_argument('--confirm-writer-ddl-pause', action='store_true')
    parser.add_argument('--confirm-new-isolated-target', action='store_true')
    parser.add_argument('--confirm-private-console', action='store_true')
    parser.add_argument('--confirm-dba-stored-object-review', action='store_true')
    parser.add_argument('--confirm-private-export', action='store_true')
    parser.add_argument('--artifact-id')
    parser.add_argument('--dump-sha256')
    parser.add_argument('--baseline-sha256')
    parser.add_argument('--reviewed-schema-sha256')
    parser.add_argument('--migration-baseline-sha256')
    parser.add_argument('--sql-sha256')
    parser.add_argument('--sql-export-report-sha256')
    parser.add_argument('--tls-ca', type=Path)
    args = parser.parse_args(argv)
    if not args.execute:
        print('PASS: offline recovery preparation; no credentials, files or database accessed')
        return 0
    try:
        artifact_paths(args.artifact_id)
        if args.mode == 'export-sql':
            require(args.confirm_private_export and args.confirm_target == RESTORE,
                    'export_confirmation')
            with WindowsPrivateStore() as store:
                adapter = LiveRecoveryAdapter(store, connect_mysql, secure_password, None)
                export_migration_sql(adapter, execute=True, artifact_id=args.artifact_id,
                    archive_sha256=args.dump_sha256, snapshot_digest=args.baseline_sha256,
                    migration_baseline_sha256=args.migration_baseline_sha256)
            print('PASS: private SQL export verified; SQL restore and migration proofs not issued')
            return 0
        require(args.confirm_private_console and args.confirm_dba_stored_object_review,
                'operator_confirmation')
        require(args.confirm_target == (SOURCE if args.mode in ('backup', 'baseline') else RESTORE), 'target')
        require(args.confirm_writer_ddl_pause if args.mode in ('backup', 'baseline') else args.confirm_new_isolated_target,
                'operator_confirmation')
        if args.mode == 'baseline':
            require(re.fullmatch('[0-9a-f]{64}', args.reviewed_schema_sha256 or '') is not None,
                    'schema_review_required')
        require(args.tls_ca is not None and args.tls_ca.is_absolute() and args.tls_ca.is_file(), 'tls_ca')
        for part in (args.tls_ca, *args.tls_ca.parents):
            stat = part.lstat()
            require(not part.is_symlink() and not getattr(stat, 'st_file_attributes', 0) & 0x400, 'tls_ca')
        if str(Path(__file__).parent) not in sys.path:
            sys.path.insert(0, str(Path(__file__).parent))
        with WindowsPrivateStore() as store:
            # No passwords enter command arguments/environment/files. Mutable
            # copies inside Python/connector cannot be comprehensively zeroed.
            adapter = LiveRecoveryAdapter(store, connect_mysql, secure_password, args.tls_ca)
            if args.mode == 'backup':
                prepare_backup(adapter, execute=True, confirm_target=args.confirm_target,
                               writer_ddl_pause=args.confirm_writer_ddl_pause, artifact_id=args.artifact_id)
                print('PASS: private logical backup verified; recoverability not yet established')
            elif args.mode == 'baseline':
                produce_migration_baseline(adapter, execute=True, artifact_id=args.artifact_id,
                    archive_sha256=args.dump_sha256, snapshot_digest=args.baseline_sha256,
                    reviewed_schema_sha256=args.reviewed_schema_sha256)
                print('PASS: migration-format baseline captured; SQL restore and rehearsal unverified')
            elif args.mode == 'verify-sql-restore':
                verify_sql_restore(adapter, execute=True, confirm_target=args.confirm_target,
                    approved_new_target=args.confirm_new_isolated_target, artifact_id=args.artifact_id,
                    archive_sha256=args.dump_sha256, snapshot_digest=args.baseline_sha256,
                    migration_baseline_sha256=args.migration_baseline_sha256,
                    sql_sha256=args.sql_sha256, export_report_sha256=args.sql_export_report_sha256)
                print('PASS: exact SQL restore and preservation verified; backup proof issued; QR rehearsal unverified')
            else:
                verify_restore(adapter, execute=True, confirm_target=args.confirm_target,
                               approved_new_target=args.confirm_new_isolated_target, artifact_id=args.artifact_id,
                               dump_sha256=args.dump_sha256, baseline_sha256=args.baseline_sha256)
                print('PASS: isolated restore and preservation verified; migration not authorized')
        return 0
    except RecoveryStop as error:
        # Only fixed categories from this module are emitted, never adapter data.
        category = str(error)
        print('STOP: demo recovery category=' + (category if re.fullmatch('[a-z_]+', category) else 'operation_failed'))
    except Exception:
        print('STOP: demo recovery category=operation_failed; preserve partial artifacts')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
