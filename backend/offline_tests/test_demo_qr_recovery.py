"""Pure recovery contract tests; never import DB-connected pytest fixtures."""
import copy
from datetime import datetime, timezone
from decimal import Decimal
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
from io import StringIO
from contextlib import redirect_stdout
from types import SimpleNamespace

MODULE = Path(__file__).resolve().parents[1] / 'scripts/demo_qr_recovery.py'
spec = importlib.util.spec_from_file_location('recovery', MODULE)
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
H = 'a' * 64
FINANCIAL = '''signed_account_balances ledger_type_totals credit_accounts ledger_entries
customer_profiles business_members orders order_items delivery_requests delivery_assignments
delivery_status_events payment_reminders'''.split()


def snapshot(database=r.SOURCE):
    return dict(database=database, account=r.SOURCE_ACCOUNT if database == r.SOURCE else r.RESTORE_ACCOUNT,
                host='localhost', port=3306, revision=r.REVISION,
                tables={name: dict(schema_sha256=H, rows=2, sha256=H) for name in r.TABLES},
                stored_objects=0, non_innodb=0, active_roles='NONE', global_usage_only=True,
                database_defaults={'charset': 'utf8mb4', 'collation': 'utf8mb4_unicode_ci'},
                privileges=['SELECT', 'INSERT', 'UPDATE', 'DELETE'] if database == r.SOURCE else
                ['SELECT', 'INSERT', 'CREATE', 'ALTER', 'INDEX', 'REFERENCES'], grant_scope=database,
                duplicate_profiles=0, foreign_key_orphans={'synthetic_fk': 0},
                financial_fingerprints={name: H for name in FINANCIAL},
                source_hashes={name: H for name in r.BOUND_SOURCES},
                versions={'mysql': '8.0.46', 'sqlalchemy': 'reviewed', 'pymysql': 'reviewed'})


class FakeAdapter:
    def __init__(self):
        self.calls = []
        self.files = {}
        self.failure = None
        self.before = snapshot()
        self.after = snapshot()
        self.restored = snapshot(r.RESTORE)

    def event(self, name):
        self.calls.append(name)
        if self.failure == name:
            raise r.RecoveryStop('synthetic_failure')

    def validate_private_paths(self, paths, **_kwargs):
        self.event('private_paths')
        if paths['restore'] in self.files or paths['dump'] in self.files and not _kwargs.get('restore'):
            raise r.RecoveryStop('existing_artifact')

    def snapshot(self, database):
        self.event('snapshot')
        return copy.deepcopy(self.restored if database == r.RESTORE else
                             self.before if self.calls.count('snapshot') == 1 else self.after)

    def write_exclusive(self, path, value):
        self.event('write')
        if path in self.files:
            raise r.RecoveryStop('existing_artifact')
        self.files[path] = copy.deepcopy(value)

    def dump_exclusive(self, path, _args):
        self.event('dump')
        self.write_exclusive(path, 'synthetic protected dump; never actual records')

    def inspect_dump(self, *_args):
        self.event('inspect_dump')
        return dict(validated_grammar=True, tables=27, revision=r.REVISION, size_bytes=10, sha256=H)

    def read_backup(self, paths):
        self.event('read_backup')
        return self.files[paths['before']], self.files[paths['backup']]

    def current_source_hashes(self):
        return self.before['source_hashes']

    def assert_empty_isolated_target(self, database, account):
        self.event('empty_target')
        assert (database, account) == (r.RESTORE, r.RESTORE_ACCOUNT)

    def restore_once(self, *_args):
        self.event('restore')


class RecoveryTests(unittest.TestCase):
    def backup(self, adapter):
        return r.prepare_backup(adapter, execute=True, confirm_target=r.SOURCE,
                                writer_ddl_pause=True, artifact_id='1' * 32)

    def restore(self, adapter):
        return r.verify_restore(adapter, execute=True, confirm_target=r.RESTORE,
                                approved_new_target=True, artifact_id='1' * 32,
                                dump_sha256=H, baseline_sha256=r.digest(adapter.before))

    def test_default_modes_do_nothing(self):
        adapter = FakeAdapter()
        self.assertEqual(r.prepare_backup(adapter)['status'], 'OFFLINE_PREPARATION')
        self.assertEqual(r.verify_restore(adapter)['status'], 'OFFLINE_PREPARATION')
        self.assertEqual(adapter.calls, [])

    def test_exact_source_and_pause_required(self):
        for target in ('lankapex_db', r.RESTORE, 'lankapex_test_db', None):
            with self.subTest(target=target), self.assertRaises(r.RecoveryStop):
                r.prepare_backup(FakeAdapter(), execute=True, confirm_target=target)

    def test_snapshot_rejects_identity_revision_inventory_grants_and_orphans(self):
        for key, value in [('database', 'lankapex_db'), ('account', 'root@localhost'),
                           ('host', '127.0.0.1'), ('port', 3307), ('revision', '7b9e4d2c8a15'),
                           ('tables', {}), ('stored_objects', 1), ('non_innodb', 1),
                           ('active_roles', 'unexpected'), ('privileges', ['SELECT', 'DROP']),
                           ('grant_scope', 'other'), ('duplicate_profiles', 1),
                           ('foreign_key_orphans', {'fk': 1}), ('source_hashes', {}),
                           ('financial_fingerprints', {'partial': H})]:
            data = snapshot()
            data[key] = value
            with self.subTest(key=key), self.assertRaises(r.RecoveryStop):
                r.validate_snapshot(data)

    def test_no_data_or_precision_loss_in_hashing(self):
        rows = [(1, Decimal('70.10'), datetime(2026, 11, 16, tzinfo=timezone.utc), b'private')]
        self.assertEqual(r.row_fingerprint(rows), r.row_fingerprint(rows))
        self.assertNotEqual(r.row_fingerprint(rows)['sha256'], r.row_fingerprint([(1, Decimal('70.11'))])['sha256'])
        for value in (float('nan'), 70.10, Decimal('Infinity')):
            with self.subTest(value=str(value)), self.assertRaises(r.RecoveryStop):
                r.typed(value)

    def test_source_restore_and_development_targets_cannot_be_substituted(self):
        for target in (r.SOURCE, 'lankapex_db', 'lankapex_test_db', 'unapproved'):
            with self.subTest(target=target), self.assertRaises(r.RecoveryStop):
                r.verify_restore(FakeAdapter(), execute=True, confirm_target=target,
                                 approved_new_target=True, artifact_id='1' * 32)

    def test_backup_success_is_not_recoverability(self):
        adapter = FakeAdapter()
        proof = self.backup(adapter)
        self.assertFalse(proof['recoverability_verified'])
        self.assertEqual(adapter.calls.count('dump'), 1)
        self.assertNotIn('restore', adapter.calls)

    def test_failure_preserves_partial_state_without_retry(self):
        for failure in ('private_paths', 'dump', 'inspect_dump'):
            adapter = FakeAdapter()
            adapter.failure = failure
            with self.subTest(failure=failure), self.assertRaises(r.RecoveryStop):
                self.backup(adapter)
            self.assertLessEqual(adapter.calls.count('dump'), 1)
            self.assertNotIn('restore', adapter.calls)

    def test_source_drift_stops_before_backup_proof(self):
        adapter = FakeAdapter()
        adapter.after['tables']['ledger_entries']['sha256'] = 'b' * 64
        with self.assertRaises(r.RecoveryStop):
            self.backup(adapter)
        self.assertNotIn(r.artifact_paths('1' * 32)['backup'], adapter.files)
        self.assertIn(r.artifact_paths('1' * 32)['dump'], adapter.files)

    def test_duplicate_backup_refused(self):
        adapter = FakeAdapter()
        self.backup(adapter)
        with self.assertRaises(r.RecoveryStop):
            self.backup(adapter)
        self.assertEqual(adapter.calls.count('dump'), 1)

    def test_restore_only_after_proven_empty_isolated_target(self):
        adapter = FakeAdapter()
        self.backup(adapter)
        result = self.restore(adapter)
        self.assertTrue(result['restore_verified'])
        self.assertFalse(result['migration_verified'])
        self.assertLess(adapter.calls.index('empty_target'), adapter.calls.index('restore'))
        self.assertEqual(adapter.calls.count('restore'), 1)
        with self.assertRaises(r.RecoveryStop):
            self.restore(adapter)

    def test_failed_restore_or_bad_fingerprint_never_claims_success(self):
        for failure in ('empty_target', 'restore', 'fingerprint'):
            adapter = FakeAdapter()
            self.backup(adapter)
            if failure == 'fingerprint':
                adapter.restored['financial_fingerprints']['signed_account_balances'] = 'b' * 64
            else:
                adapter.failure = failure
            with self.subTest(failure=failure), self.assertRaises(r.RecoveryStop):
                self.restore(adapter)
            self.assertNotIn(r.artifact_paths('1' * 32)['restore'], adapter.files)
            self.assertLessEqual(adapter.calls.count('restore'), 1)

    def test_artifact_paths_reject_traversal(self):
        for value in ('../private', 'A' * 32, '1' * 31, None):
            with self.subTest(value=value), self.assertRaises(r.RecoveryStop):
                r.artifact_paths(value)


def archive_fixture():
    before = snapshot()
    records = {}
    for name in r.TABLES:
        column = 'version_num' if name == 'alembic_version' else 'record_id'
        ddl = f'CREATE TABLE `{name}` (`{column}` ' + ('varchar(32)' if name == 'alembic_version' else 'bigint') + ' NOT NULL, PRIMARY KEY (`' + column + '`)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4'
        values = [(r.REVISION,)] if name == 'alembic_version' else [(1,)]
        records[name] = dict(ddl=ddl, columns=[column], primary_key=[column],
                             rows=[[r.typed(value) for value in row] for row in values])
        before['tables'][name] = dict(schema_sha256=r.digest(ddl), **r.row_fingerprint(values))
    return before, dict(format='lankapex-logical-v1', database=r.SOURCE, revision=r.REVISION,
                        baseline_sha256=r.digest(before), tables=records)


class MemoryStore:
    def __init__(self):
        self.files = {}

    def check(self, path, absent=False):
        r.require((path not in self.files) if absent else (path in self.files), 'artifact_state')

    def write(self, path, value):
        self.check(path, absent=True)
        self.files[path] = r.json.dumps(value, sort_keys=True).encode('utf-8')

    def read(self, path):
        self.check(path)
        return self.files[path]

    def write_bytes(self, path, value):
        self.check(path, absent=True)
        self.files[path] = value


class MockConnection:
    def __init__(self, database=r.RESTORE, table_count=0, fail_insert=False):
        self.database, self.table_count, self.fail_insert = database, table_count, fail_insert
        self.calls = []
        self.closed = self.committed = False
        self.sql = ''

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=None):
        self.sql = sql
        self.calls.append((sql, params))
        if self.fail_insert and sql.startswith('INSERT'):
            raise RuntimeError('synthetic-secret-connector-error')

    def fetchone(self):
        if self.sql.startswith('SELECT DATABASE'):
            account = r.SOURCE_ACCOUNT if self.database == r.SOURCE else r.RESTORE_ACCOUNT
            return self.database, account, 3306, 'NONE', 0, 'STRICT_TRANS_TABLES', 1
        return (self.table_count if self.sql.startswith('SELECT COUNT(*) FROM information_schema.TABLES') else 0,)

    def fetchall(self):
        rights = 'SELECT, INSERT, UPDATE, DELETE' if self.database == r.SOURCE else 'SELECT, INSERT, CREATE, ALTER, INDEX, REFERENCES'
        scope = self.database.replace('_', '\\_')
        return [('GRANT USAGE ON *.* TO account',), (f'GRANT {rights} ON `{scope}`.* TO account',)]

    def close(self):
        self.closed = True

    def commit(self):
        self.committed = True


class AdapterTests(unittest.TestCase):
    def adapter(self, connection=None):
        store = MemoryStore()
        conn = connection or MockConnection()
        return r.LiveRecoveryAdapter(store, lambda *_args: conn, lambda: 'synthetic-secret', Path('public-ca.pem'))

    def test_archive_roundtrip_and_integrity(self):
        before, archive = archive_fixture()
        adapter = self.adapter()
        adapter.cached[r.SOURCE] = (before, archive['tables'])
        path = r.artifact_paths('2' * 32)['dump']
        adapter.dump_exclusive(path, None)
        result = adapter.inspect_dump(path, before)
        self.assertTrue(result['validated_grammar'])
        self.assertEqual(result['tables'], 27)
        self.assertEqual(result['sha256'], r.hashlib.sha256(adapter.store.files[path]).hexdigest())
        with self.assertRaises(r.RecoveryStop):
            adapter.dump_exclusive(path, None)
        adapter.store.files[path] = b'{}'
        with self.assertRaises(r.RecoveryStop):
            adapter.inspect_dump(path, before)

    def test_archive_rejects_bad_source_revision_rows_and_schema(self):
        before, archive = archive_fixture()
        for mutation in ('source', 'revision', 'row', 'ddl', 'table_count'):
            value = copy.deepcopy(archive)
            if mutation == 'source':
                value['database'] = 'lankapex_db'
            elif mutation == 'revision':
                value['revision'] = '7b9e4d2c8a15'
            elif mutation == 'row':
                value['tables']['users']['rows'][0][0] = ['int', '999']
            elif mutation == 'table_count':
                del value['tables']['users']
            else:
                value['tables']['users']['ddl'] += '; DROP DATABASE lankapex_demo_db'
            with self.subTest(mutation=mutation), self.assertRaises(r.RecoveryStop):
                r.validate_archive(value, before)

    def test_schema_lexer_preserves_fk_actions_and_quoted_data_but_rejects_extra_sql(self):
        ddl = "CREATE TABLE `users` (`user_id` bigint NOT NULL, `note` varchar(40) DEFAULT ';DELETE', PRIMARY KEY (`user_id`), CONSTRAINT `fk` FOREIGN KEY (`user_id`) REFERENCES `businesses` (`business_id`) ON DELETE RESTRICT ON UPDATE CASCADE) ENGINE=InnoDB"
        self.assertEqual(r.validate_ddl('users', ddl), ddl)
        for extra in ('; SELECT 1', ' /* comment */', ' AS SELECT 1', '; DROP TABLE `users`'):
            with self.subTest(extra=extra), self.assertRaises(r.RecoveryStop):
                r.validate_ddl('users', ddl + extra)
        with self.assertRaises(r.RecoveryStop):
            r.validate_ddl('users', ddl.replace('REFERENCES `businesses`', 'REFERENCES `lankapex_demo_db`.`businesses`'))

    def test_restore_rechecks_empty_target_and_parameterizes_records(self):
        conn = MockConnection()
        adapter = self.adapter(conn)
        _, adapter.archive = archive_fixture()
        adapter.assert_empty_isolated_target(r.RESTORE, r.RESTORE_ACCOUNT)
        adapter.restore_once(None, None)
        self.assertTrue(conn.closed and conn.committed)
        self.assertEqual(sum(sql.startswith('CREATE TABLE') for sql, _ in conn.calls), 27)
        inserts = [(sql, values) for sql, values in conn.calls if sql.startswith('INSERT')]
        self.assertEqual(len(inserts), 27)
        self.assertTrue(all('%s' in sql and isinstance(values, tuple) for sql, values in inserts))
        self.assertFalse(any('DROP' in sql or 'TRUNCATE' in sql or 'GLOBAL foreign' in sql for sql, _ in conn.calls))

    def test_nonempty_and_partial_restore_fail_without_commit_or_cleanup(self):
        for count, fail in ((1, False), (0, True)):
            conn = MockConnection(table_count=count, fail_insert=fail)
            adapter = self.adapter(conn)
            _, adapter.archive = archive_fixture()
            with self.subTest(count=count, fail=fail), self.assertRaises((r.RecoveryStop, RuntimeError)):
                adapter.restore_once(None, None)
            self.assertFalse(conn.committed)
            self.assertTrue(conn.closed)
            self.assertEqual(sum(sql.startswith('CREATE TABLE') for sql, _ in conn.calls), 0 if count else 27)

    def test_wrong_actual_account_scope_or_roles_stop(self):
        for identity in [('lankapex_db', r.RESTORE_ACCOUNT, 3306, 'NONE', 0, 'STRICT_TRANS_TABLES', 1),
                         (r.RESTORE, 'root@localhost', 3306, 'NONE', 0, 'STRICT_TRANS_TABLES', 1),
                         (r.RESTORE, r.RESTORE_ACCOUNT, 3306, 'role', 0, 'STRICT_TRANS_TABLES', 1)]:
            conn = MockConnection()
            adapter = self.adapter(conn)
            with patch.object(conn, 'fetchone', return_value=identity), self.assertRaises(r.RecoveryStop):
                adapter.assert_empty_isolated_target(r.RESTORE, r.RESTORE_ACCOUNT)

    def test_credential_failure_does_not_connect_and_password_never_enters_arguments(self):
        calls = []
        adapter = r.LiveRecoveryAdapter(MemoryStore(), lambda *args: calls.append(args),
                                       lambda: (_ for _ in ()).throw(r.RecoveryStop('credential_unavailable')), None)
        with self.assertRaises(r.RecoveryStop):
            adapter._connection(r.SOURCE)
        self.assertEqual(calls, [])
        with self.assertRaises(r.RecoveryStop):
            adapter._connection('lankapex_db')

    def test_typed_roundtrip_is_exact_and_rejects_noncanonical_input(self):
        for value in (None, True, 7, Decimal('70.10'), 'தமிழ்', b'\x00\xff',
                      datetime(2026, 11, 16, tzinfo=timezone.utc)):
            self.assertEqual(r.untyped(r.typed(value)), value)
        for value in (['int', '01'], ['decimal', 'NaN'], ['bytes', 'not hex'], ['unknown', 'private']):
            with self.subTest(value=value), self.assertRaises(r.RecoveryStop):
                r.untyped(value)

    def test_missing_backup_evidence_and_source_changes_block_restore(self):
        adapter = FakeAdapter()
        with self.assertRaises(KeyError):
            r.verify_restore(adapter, execute=True, confirm_target=r.RESTORE, approved_new_target=True,
                             artifact_id='1' * 32, dump_sha256=H, baseline_sha256=H)
        adapter = FakeAdapter()
        RecoveryTests().backup(adapter)
        with patch.object(adapter, 'current_source_hashes', return_value={}):
            with self.assertRaises(r.RecoveryStop):
                RecoveryTests().restore(adapter)
        self.assertNotIn('restore', adapter.calls)

    def test_cli_default_has_no_file_credential_or_database_access(self):
        output = StringIO()
        with (patch.object(r, 'WindowsPrivateStore', side_effect=AssertionError('must not access')),
              redirect_stdout(output)):
            self.assertEqual(r.main([]), 0)
        self.assertIn('PASS: offline recovery preparation', output.getvalue())

    def test_private_file_creation_uses_protected_dacl_and_create_new_without_real_io(self):
        import ctypes
        import msvcrt
        import os
        from ctypes import wintypes
        store = r.WindowsPrivateStore()
        store.ct, store.wt, store.sid = ctypes, wintypes, 'S-1-5-21-100'
        stages = []
        def descriptor(sddl, *_args):
            self.assertEqual(sddl, 'O:S-1-5-21-100D:P(A;;FA;;;S-1-5-21-100)(A;;FA;;;SY)')
            stages.append('security')
            return 1
        store.advapi = SimpleNamespace(ConvertStringSecurityDescriptorToSecurityDescriptorW=descriptor)
        store.kernel = SimpleNamespace(LocalFree=lambda *_args: stages.append('free'),
                                       CloseHandle=lambda *_args: stages.append('close'))
        def create(_path, access, share, disposition, flags, _security):
            self.assertEqual((access, share, disposition, flags), (0x40000000, 0, 1, 0x80))
            stages.append('create_new')
            return 77
        stream = SimpleNamespace(write=lambda _value: stages.append('write'), flush=lambda: None,
                                 fileno=lambda: 11)
        class Context:
            def __enter__(self): return stream
            def __exit__(self, *_args): return False
        with (patch.object(store, '_open', side_effect=create),
              patch.object(store, '_identity'), patch.object(store, '_acl', side_effect=lambda *_args: stages.append('verify_acl')),
              patch.object(msvcrt, 'open_osfhandle', return_value=11),
              patch.object(os, 'fdopen', return_value=Context()), patch.object(os, 'fsync')):
            store.write(r.artifact_paths('3' * 32)['backup'], {'synthetic': True})
        self.assertLess(stages.index('security'), stages.index('create_new'))
        self.assertLess(stages.index('create_new'), stages.index('write'))
        self.assertIn('verify_acl', stages)
        with (patch.object(store, '_open', side_effect=r.RecoveryStop('private_file_open')) as create,
              self.assertRaises(r.RecoveryStop)):
            store.write(r.artifact_paths('3' * 32)['backup'], {'synthetic': True})
        self.assertEqual(create.call_count, 1)

    def test_tls_is_required_before_authentication_no_network(self):
        import ssl
        import pymysql
        context = SimpleNamespace(check_hostname=True, verify_mode=ssl.CERT_REQUIRED)
        class Socket:
            def version(self): return 'TLSv1.3'
            def getpeername(self): return ('127.0.0.1', 3306)
        connection = SimpleNamespace(ssl=True, _ssl_required=True, ctx=context, _sock=Socket(),
                                     connect=lambda: None, close=lambda: None)
        with (patch.object(ssl, 'create_default_context', return_value=context),
              patch.object(ssl, 'SSLSocket', Socket),
              patch.object(pymysql, 'connect', return_value=connection) as create):
            self.assertIs(r.connect_mysql(r.SOURCE, 'lankapex_demo_app', 'synthetic-secret', 'public-ca'), connection)
            self.assertTrue(create.call_args.kwargs['defer_connect'])
            self.assertFalse(create.call_args.kwargs['local_infile'])
            self.assertEqual(create.call_args.kwargs['host'], '127.0.0.1')
            connection._ssl_required = False
            with patch.object(connection, 'connect') as authenticate, self.assertRaises(r.RecoveryStop):
                r.connect_mysql(r.SOURCE, 'lankapex_demo_app', 'synthetic-secret', 'public-ca')
            authenticate.assert_not_called()

    def test_cli_suppresses_raw_connection_errors(self):
        output = StringIO()
        with (patch.object(r, 'WindowsPrivateStore', side_effect=RuntimeError('password=synthetic-secret')),
              patch.object(Path, 'is_file', return_value=True),
              patch.object(Path, 'lstat', return_value=SimpleNamespace(st_file_attributes=0)),
              patch.object(Path, 'is_symlink', return_value=False), redirect_stdout(output)):
            status = r.main(['--execute', '--confirm-target', r.SOURCE, '--confirm-writer-ddl-pause',
                             '--confirm-private-console', '--confirm-dba-stored-object-review',
                             '--artifact-id', '1' * 32, '--tls-ca', str(MODULE)])
        self.assertEqual(status, 1)
        self.assertNotIn('synthetic-secret', output.getvalue())
        self.assertIn('category=operation_failed', output.getvalue())

    def test_full_capture_uses_consistent_readonly_boundary_and_closes_engine(self):
        import sqlalchemy
        native = MockConnection(database=r.SOURCE)
        calls = []
        before, archive = archive_fixture()
        class Result:
            def __init__(self, rows): self.rows = rows
            def __iter__(self): return iter(self.rows)
            def one(self): return self.rows[0]
            def scalar_one(self): return self.rows[0][0]
            def scalars(self): return SimpleNamespace(all=lambda: [row[0] for row in self.rows])
            def close(self): pass
        class Connection:
            connection = SimpleNamespace(driver_connection=native)
            def __enter__(self): return self
            def __exit__(self, *_args): pass
            def rollback(self): calls.append('ROLLBACK')
            def execution_options(self, **_kwargs): return self
            def exec_driver_sql(self, sql):
                calls.append(sql)
                if sql.startswith('SHOW CREATE TABLE'):
                    name = sql.split('`')[1]
                    return Result([(name, archive['tables'][name]['ddl'])])
                if sql.startswith('SELECT version_num'):
                    return Result([(r.REVISION,)])
                if sql == 'SELECT VERSION()': return Result([('8.0.46',)])
                if sql.startswith('SELECT DEFAULT_CHARACTER'): return Result([('utf8mb4', 'utf8mb4_unicode_ci')])
                if sql.startswith('SELECT COUNT') or 'information_schema.ROUTINES' in sql: return Result([(0,)])
                if 'FROM `alembic_version`' in sql: return Result([(r.REVISION,)])
                return Result([(1,)])
        connection = Connection()
        disposed = []
        engine = SimpleNamespace(connect=lambda: connection, dispose=lambda: disposed.append(True))
        inspector = SimpleNamespace(
            get_table_names=lambda: sorted(r.TABLES), get_view_names=lambda: [],
            get_columns=lambda name: [{'name': archive['tables'][name]['columns'][0]}],
            get_pk_constraint=lambda name: {'constrained_columns': archive['tables'][name]['primary_key']},
            get_foreign_keys=lambda name: [{'name': 'fk_synthetic', 'constrained_columns': ['record_id'],
                'referred_columns': ['record_id'], 'referred_table': 'businesses', 'referred_schema': None}] if name == 'users' else [])
        inventory = SimpleNamespace(PROJECTIONS={name: 'record_id' for name in FINANCIAL
                                                if name not in ('signed_account_balances', 'ledger_type_totals')},
                                    BALANCES='SELECT synthetic_balance', LEDGER_TOTALS='SELECT synthetic_totals',
                                    DUPLICATES='SELECT COUNT(*) FROM synthetic_duplicate_audit',
                                    fingerprint=r.row_fingerprint)
        adapter = self.adapter()
        with (patch.object(sqlalchemy, 'create_engine', return_value=engine),
              patch.object(sqlalchemy, 'inspect', return_value=inspector),
              patch.dict(r.sys.modules, {'inventory_demo_database': inventory}),
              patch.object(adapter, 'current_source_hashes', return_value=before['source_hashes'])):
            report, records = adapter._capture(r.SOURCE)
        self.assertEqual(set(records), r.TABLES)
        self.assertEqual(len(report['tables']), 27)
        self.assertIn('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY', calls)
        self.assertGreaterEqual(calls.count('ROLLBACK'), 2)
        self.assertEqual(disposed, [True])
        self.assertFalse(native.committed)
        self.assertFalse(any(sql.startswith(('INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER')) for sql in calls))


class SqlExportTests(unittest.TestCase):
    def setUp(self):
        from test_demo_qr_preservation import reports
        self.before, self.archive = archive_fixture()
        self.report, _after = reports()
        self.before['inventory_fingerprints'] = {key: copy.deepcopy(self.report[key]) for key in (
            'preservation_fingerprints', 'signed_account_balance_fingerprint', 'ledger_type_totals_fingerprint')}
        self.before['foreign_key_orphans'] = {'customer_profiles:original': 0}
        self.report['foreign_key_orphan_counts'] = {
            'customer_profiles:' + r.hashlib.sha256(b'original').hexdigest(): 0}
        self.archive['baseline_sha256'] = r.digest(self.before)
        self.store = MemoryStore()
        self.adapter = r.LiveRecoveryAdapter(self.store, lambda *_args: self.fail('no connection allowed'),
                                            lambda: self.fail('no credential access allowed'), None)
        self.id = '4' * 32
        self.paths, self.outputs = r.artifact_paths(self.id), r.migration_paths(self.id)
        self.store.write(self.paths['before'], self.before)
        self.store.write(self.paths['dump'], self.archive)
        self.archive_sha = r.hashlib.sha256(self.store.files[self.paths['dump']]).hexdigest()
        self.store.write(self.paths['backup'], dict(format=1, database=r.SOURCE, revision=r.REVISION,
            total_tables=27, baseline_sha256=r.digest(self.before), dump_sha256=self.archive_sha,
            size_bytes=len(self.store.files[self.paths['dump']]), source_hashes=self.before['source_hashes'],
            recoverability_verified=False))
        self.metadata = {'tables': [(name, 'InnoDB', 'BASE TABLE', 'utf8mb4_unicode_ci') for name in sorted(r.TABLES)],
                         'columns': [('users', 'record_id', 'bigint', 'NO', None, 1, None, '')]}
        self.guard, self.preservation = r.migration_modules()
        self.schema_sha = self.guard.schema_digest(self.metadata)
        self.hash_patch = patch.object(self.adapter, 'current_source_hashes', return_value=self.before['source_hashes'])
        self.guard_patch = patch.object(self.guard, 'source_hashes', return_value={'synthetic/source': H})
        self.hash_patch.start()
        self.guard_patch.start()
        self.addCleanup(self.hash_patch.stop)
        self.addCleanup(self.guard_patch.stop)

    def baseline(self, report=None, live=None):
        with patch.object(self.adapter, '_capture', return_value=(
            live or self.before, self.archive['tables'], report or self.report, self.metadata)):
            return r.produce_migration_baseline(self.adapter, execute=True, artifact_id=self.id,
                archive_sha256=self.archive_sha, snapshot_digest=r.digest(self.before),
                reviewed_schema_sha256=self.schema_sha)

    def export(self, baseline_sha):
        return r.export_migration_sql(self.adapter, execute=True, artifact_id=self.id,
            archive_sha256=self.archive_sha, snapshot_digest=r.digest(self.before),
            migration_baseline_sha256=baseline_sha)

    def sql_restore_setup(self):
        binding = self.baseline()
        exported = self.export(binding['baseline_sha256'])
        after = copy.deepcopy(self.before)
        identity = snapshot(r.RESTORE)
        for key in ('database', 'account', 'privileges', 'grant_scope'):
            after[key] = identity[key]
        options = dict(execute=True, confirm_target=r.RESTORE, approved_new_target=True,
            artifact_id=self.id, archive_sha256=self.archive_sha,
            snapshot_digest=r.digest(self.before), migration_baseline_sha256=binding['baseline_sha256'],
            sql_sha256=exported['sql_sha256'], export_report_sha256=r.hashlib.sha256(
                self.store.read(self.outputs['export_report'])).hexdigest())
        return after, options

    def test_sql_restore_success_issues_exact_guard_backup_contract_after_verification(self):
        after, options = self.sql_restore_setup()
        with (patch.object(self.adapter, 'assert_empty_isolated_target') as empty,
              patch.object(self.adapter, 'restore_sql_once') as restore,
              patch.object(self.adapter, 'snapshot', return_value=after)):
            proof = r.verify_sql_restore(self.adapter, **options)
        empty.assert_called_once_with(r.RESTORE, r.RESTORE_ACCOUNT)
        restore.assert_called_once_with(self.store.read(self.outputs['sql']), self.before, r.RESTORE)
        self.assertEqual(proof['dump_sha256'], options['sql_sha256'])
        self.assertEqual(proof['baseline_sha256'], options['migration_baseline_sha256'])
        restored = r.json.loads(self.store.read(self.outputs['sql_restore_report']))
        self.assertTrue(restored['full_row_preservation_verified'])
        self.assertFalse(restored['migration_verified'])
        self.assertFalse(any(p.name.startswith('rehearsal-proof-') for p in self.store.files))
        from test_populated_demo_qr_runner import fixtures
        bundle, hashes, _live = fixtures()
        bundle['baseline'] = r.json.loads(self.store.read(self.outputs['baseline']))
        bundle['backup'] = proof
        # Rehearsal/pause remain independently supplied synthetic guard fixtures.
        bundle['baseline_sha256'] = proof['baseline_sha256']
        bundle['rehearsal']['baseline_sha256'] = proof['baseline_sha256']
        bundle['rehearsal']['backup_sha256'] = proof['dump_sha256']
        bundle['pause']['baseline_sha256'] = proof['baseline_sha256']
        self.guard.validate_evidence(bundle, hashes)
        with self.assertRaises(r.RecoveryStop):
            r.verify_sql_restore(self.adapter, **options)

    def test_sql_restore_checksum_mismatch_stops_before_connection(self):
        _after, options = self.sql_restore_setup()
        for key in ('archive_sha256', 'snapshot_digest', 'migration_baseline_sha256',
                    'sql_sha256', 'export_report_sha256'):
            with self.subTest(pin=key), self.assertRaises(r.RecoveryStop):
                r.verify_sql_restore(self.adapter, **dict(options, **{key: 'b' * 64}))
        self.assertNotIn(self.outputs['backup_proof'], self.store.files)

    def test_sql_restore_unsafe_target_and_default_never_access_adapter(self):
        self.assertEqual(r.verify_sql_restore(SimpleNamespace())['status'], 'OFFLINE_PREPARATION')
        for target in (r.SOURCE, 'lankapex_db', 'unexpected'):
            with self.subTest(target=target), self.assertRaises(r.RecoveryStop):
                r.verify_sql_restore(SimpleNamespace(), execute=True, confirm_target=target,
                                     approved_new_target=True)
        with patch.object(r, 'WindowsPrivateStore', side_effect=AssertionError('private access')), redirect_stdout(StringIO()):
            self.assertEqual(r.main(['--mode', 'verify-sql-restore']), 0)

    def test_sql_restore_partial_failure_preserves_artifacts_without_proof_or_retry(self):
        _after, options = self.sql_restore_setup()
        original = dict(self.store.files)
        with (patch.object(self.adapter, 'assert_empty_isolated_target'),
              patch.object(self.adapter, 'restore_sql_once', side_effect=RuntimeError('synthetic secret')) as restore,
              self.assertRaises(RuntimeError)):
            r.verify_sql_restore(self.adapter, **options)
        restore.assert_called_once()
        self.assertEqual(original, self.store.files)

    def test_sql_restore_modified_sql_rejected_even_with_recomputed_report_checksum(self):
        _after, options = self.sql_restore_setup()
        raw = self.store.files[self.outputs['sql']] + b' '
        self.store.files[self.outputs['sql']] = raw
        report = r.json.loads(self.store.read(self.outputs['export_report']))
        report.update(size_bytes=len(raw), sql_sha256=r.hashlib.sha256(raw).hexdigest())
        self.store.files[self.outputs['export_report']] = r.json.dumps(report).encode()
        options.update(sql_sha256=report['sql_sha256'], export_report_sha256=r.hashlib.sha256(
            self.store.read(self.outputs['export_report'])).hexdigest())
        with self.assertRaises(r.RecoveryStop):
            r.verify_sql_restore(self.adapter, **options)
        self.assertNotIn(self.outputs['backup_proof'], self.store.files)

    def test_sql_restore_source_drift_or_report_write_failure_never_issues_backup_proof(self):
        after, options = self.sql_restore_setup()
        def drift(*_args):
            self.adapter.current_source_hashes.return_value = {}
        with (patch.object(self.adapter, 'assert_empty_isolated_target'),
              patch.object(self.adapter, 'restore_sql_once', side_effect=drift),
              patch.object(self.adapter, 'snapshot', return_value=after), self.assertRaises(r.RecoveryStop)):
            r.verify_sql_restore(self.adapter, **options)
        self.adapter.current_source_hashes.return_value = self.before['source_hashes']
        with (patch.object(self.adapter, 'assert_empty_isolated_target'),
              patch.object(self.adapter, 'restore_sql_once'),
              patch.object(self.adapter, 'snapshot', return_value=after),
              patch.object(self.store, 'write', side_effect=r.RecoveryStop('artifact_write')),
              self.assertRaises(r.RecoveryStop)):
            r.verify_sql_restore(self.adapter, **options)
        self.assertNotIn(self.outputs['backup_proof'], self.store.files)

    def test_sql_restore_rejects_nonempty_target_before_sql(self):
        _after, options = self.sql_restore_setup()
        with (patch.object(self.adapter, 'assert_empty_isolated_target', side_effect=r.RecoveryStop('nonempty')),
              patch.object(self.adapter, 'restore_sql_once') as restore, self.assertRaises(r.RecoveryStop)):
            r.verify_sql_restore(self.adapter, **options)
        restore.assert_not_called()

    def test_sql_restore_all_preservation_mismatches_prevent_proof(self):
        after, options = self.sql_restore_setup()
        mutations = [lambda a: a['tables']['orders'].update(sha256='b' * 64),
                     lambda a: a['tables']['users'].update(schema_sha256='b' * 64),
                     lambda a: a['tables']['ledger_entries'].update(rows=9),
                     lambda a: a['financial_fingerprints'].update(signed_account_balances='b' * 64),
                     lambda a: a['foreign_key_orphans'].update({'customer_profiles:original': 1}),
                     lambda a: a['inventory_fingerprints'].update(signed_account_balance_fingerprint='b' * 64)]
        for index, mutate in enumerate(mutations):
            bad = copy.deepcopy(after)
            mutate(bad)
            with (self.subTest(case=index), patch.object(self.adapter, 'assert_empty_isolated_target'),
                  patch.object(self.adapter, 'restore_sql_once'), patch.object(self.adapter, 'snapshot', return_value=bad),
                  self.assertRaises(r.RecoveryStop)):
                r.verify_sql_restore(self.adapter, **options)
            self.assertNotIn(self.outputs['backup_proof'], self.store.files)

    def test_sql_restore_exact_bytes_executed_once_and_partial_failure_closed(self):
        _after, _options = self.sql_restore_setup()
        self.adapter.archive = self.archive
        raw = self.store.read(self.outputs['sql'])
        for failing in (False, True):
            connection = MockConnection(fail_insert=failing)
            with patch.object(self.adapter, '_connection', return_value=connection):
                if failing:
                    with self.assertRaises(RuntimeError):
                        self.adapter.restore_sql_once(raw, self.before, r.RESTORE)
                else:
                    self.adapter.restore_sql_once(raw, self.before, r.RESTORE)
            statements = r.split_verified_sql(raw)
            calls = [sql for sql, _params in connection.calls]
            if not failing:
                self.assertEqual([sql for sql in calls if sql in statements], statements)
            else:
                self.assertNotIn('COMMIT', calls)
            self.assertTrue(connection.closed)
        with self.assertRaises(r.RecoveryStop):
            self.adapter.restore_sql_once(raw + b' ', self.before, r.RESTORE)

    def test_sql_restore_quoted_split_and_only_exact_self_fk_normalization(self):
        raw = b"-- LankaPex isolated SQL export v1\nSET @x='a;b'; SET @y='c';\n"
        self.assertEqual(len(r.split_verified_sql(raw)), 2)
        with self.assertRaises(r.RecoveryStop):
            r.split_verified_sql(raw + b"SET @z='unterminated;")
        ddl = "CREATE TABLE `users` (`record_id` bigint, FOREIGN KEY (`record_id`) REFERENCES `" + r.RESTORE + "`.`businesses` (`record_id`)) ENGINE=InnoDB"
        normalized = r.canonical_self_references(ddl, r.RESTORE)
        r.validate_ddl('users', normalized)
        self.assertNotIn('`' + r.RESTORE + '`.', normalized)
        self.assertEqual(r.canonical_self_references(ddl, r.SOURCE), ddl)
        with self.assertRaises(r.RecoveryStop):
            r.validate_ddl('users', r.canonical_self_references(ddl.replace(r.RESTORE, 'other'), r.RESTORE))

    def test_literals_preserve_unicode_decimal_binary_null_and_reject_floats(self):
        for value in ['தமிழ் සිංහල', "'; DROP DATABASE lankapex_demo_db; --", '', '\x00\\\n']:
            literal = r.sql_literal(value)
            encoded = literal.split("'")[1]
            self.assertEqual(bytes.fromhex(encoded).decode('utf-8'), value)
            self.assertNotIn('DROP DATABASE', literal)
        for value in [Decimal('70.10'), Decimal('1E+30'), Decimal('-0.00100')]:
            self.assertEqual(Decimal(r.sql_literal(value)), value)
            self.assertNotIn('E', r.sql_literal(value))
        self.assertEqual(r.sql_literal(None), 'NULL')
        self.assertEqual(r.sql_literal(b'\x00\xff'), "X'00ff'")
        self.assertEqual(r.sql_literal(r.date(2026, 11, 16)), "'2026-11-16'")
        self.assertEqual(r.sql_literal(r.timedelta(microseconds=-1)), "'-00:00:00.000001'")
        for value in [1.2, Decimal('NaN'), Decimal('1E+1000000'), 1 << 128,
                      object(), datetime.now(timezone.utc), r.timedelta(days=100)]:
            with self.subTest(kind=type(value).__name__), self.assertRaises(r.RecoveryStop):
                r.sql_literal(value)

    def test_sql_is_deterministic_and_all_table_writes_are_isolated(self):
        raw = r.sql_export_bytes(self.archive, self.before)
        self.assertEqual(raw, r.sql_export_bytes(self.archive, self.before))
        text = raw.decode('utf-8')
        for prefix in ('CREATE TABLE ', 'INSERT INTO '):
            lines = [line for line in text.splitlines() if line.startswith(prefix)]
            self.assertEqual(len(lines), 27)
            self.assertTrue(all(line.startswith(prefix + '`' + r.RESTORE + '`.') for line in lines))
        self.assertNotIn('USE ', text)
        self.assertNotIn('CREATE DATABASE', text)
        self.assertNotIn('`lankapex_demo_db`.', text)
        self.assertNotIn('`lankapex_db`.', text)
        self.assertFalse(raw.startswith(b'\xef\xbb\xbf'))
        for target in (r.SOURCE, 'lankapex_db', 'other'):
            with self.subTest(target=target), self.assertRaises(r.RecoveryStop):
                r.sql_export_bytes(self.archive, self.before, target)

    def test_fk_qualification_does_not_rewrite_quoted_defaults(self):
        ddl = "CREATE TABLE `users` (`record_id` bigint, `note` varchar(80) DEFAULT 'REFERENCES `users`', FOREIGN KEY (`record_id`) REFERENCES `businesses` (`record_id`)) ENGINE=InnoDB"
        result = r.isolated_ddl('users', ddl)
        self.assertIn("DEFAULT 'REFERENCES `users`'", result)
        self.assertIn('REFERENCES `' + r.RESTORE + '`.`businesses`', result)
        for unsafe in [ddl + '; DROP TABLE `users`', ddl + ' /* malicious */', ddl.replace('`users` (', '`other` (', 1)]:
            with self.assertRaises(r.RecoveryStop):
                r.isolated_ddl('users', unsafe)

    def test_baseline_exact_guard_format_and_expanded_hash_convention(self):
        binding = self.baseline()
        baseline = r.json.loads(self.store.read(self.outputs['baseline']))
        self.assertEqual(set(baseline), {'format', 'schema_reviewed_for_start', 'inventory', 'full_schema_sha256'})
        self.preservation.validate(baseline['inventory'])
        self.assertEqual(baseline['full_schema_sha256'], self.guard.schema_digest(self.metadata))
        self.assertEqual(binding['baseline_sha256'], r.hashlib.sha256(self.store.read(self.outputs['baseline'])).hexdigest())
        modified = copy.deepcopy(self.metadata)
        modified['columns'][0] = (*modified['columns'][0][:-2], 'changed_default', 'changed_extra')
        self.assertNotEqual(self.guard.schema_digest(modified), baseline['full_schema_sha256'])
        self.assertNotIn(self.paths['restore'], self.store.files)

    def test_export_hashes_exact_written_bytes_and_never_issues_success_proofs(self):
        binding = self.baseline()
        report = self.export(binding['baseline_sha256'])
        raw = self.store.read(self.outputs['sql'])
        self.assertEqual(report['sql_sha256'], r.hashlib.sha256(raw).hexdigest())
        self.assertEqual(report['size_bytes'], len(raw))
        self.assertGreater(report['size_bytes'], 0)
        self.assertFalse(report['sql_restore_verified'] or report['backup_proof_issued'] or report['migration_verified'])
        self.assertFalse(any(path.name.startswith(('backup-proof-', 'rehearsal-proof-')) for path in self.store.files))
        with self.assertRaises(r.RecoveryStop):
            self.export(binding['baseline_sha256'])

    def test_tampered_archive_baseline_binding_and_source_are_rejected(self):
        binding = self.baseline()
        self.store.files[self.outputs['baseline']] += b' '
        with self.assertRaises(r.RecoveryStop):
            self.export(binding['baseline_sha256'])
        self.assertNotIn(self.outputs['sql'], self.store.files)
        self.store.files[self.paths['dump']] += b' '
        with self.assertRaises(r.RecoveryStop):
            self.adapter.validated_backup(self.paths, self.archive_sha, r.digest(self.before))

    def test_baseline_rejects_unreviewed_schema_drift_and_preservation_mismatch(self):
        with self.assertRaises(r.RecoveryStop):
            r.produce_migration_baseline(self.adapter, execute=True, artifact_id=self.id)
        bad = copy.deepcopy(self.report)
        bad['preservation_fingerprints']['ledger_entries']['sha256'] = 'b' * 64
        with self.assertRaises(r.RecoveryStop):
            self.baseline(report=bad)
        self.assertNotIn(self.outputs['baseline'], self.store.files)
        live = copy.deepcopy(self.before)
        live['tables']['orders']['sha256'] = 'b' * 64
        with self.assertRaises(r.RecoveryStop):
            self.baseline(live=live)

    def test_partial_export_keeps_sql_but_no_false_success_report(self):
        binding = self.baseline()
        real_write = self.store.write
        def fail_report(path, value):
            if path == self.outputs['export_report']:
                raise r.RecoveryStop('synthetic_failure')
            real_write(path, value)
        with patch.object(self.store, 'write', side_effect=fail_report), self.assertRaises(r.RecoveryStop):
            self.export(binding['baseline_sha256'])
        self.assertIn(self.outputs['sql'], self.store.files)
        self.assertNotIn(self.outputs['export_report'], self.store.files)

    def test_guard_accepts_baseline_shape_but_still_rejects_unverified_export_as_backup(self):
        from test_populated_demo_qr_runner import fixtures
        binding = self.baseline()
        export = self.export(binding['baseline_sha256'])
        bundle, hashes, _live = fixtures()
        bundle['baseline'] = r.json.loads(self.store.read(self.outputs['baseline']))
        # Other proofs remain synthetic fixtures, never written or issued here.
        self.guard.validate_evidence(bundle, hashes)
        bundle['backup'] = export
        with self.assertRaises(self.guard.Stop):
            self.guard.validate_evidence(bundle, hashes)

    def test_export_and_baseline_default_modes_do_not_touch_adapter(self):
        adapter = SimpleNamespace()
        self.assertEqual(r.produce_migration_baseline(adapter)['status'], 'OFFLINE_PREPARATION')
        self.assertEqual(r.export_migration_sql(adapter)['status'], 'OFFLINE_PREPARATION')
        with (patch.object(r, 'WindowsPrivateStore', side_effect=AssertionError('no private access')),
              redirect_stdout(StringIO())):
            self.assertEqual(r.main(['--mode', 'baseline']), 0)
            self.assertEqual(r.main(['--mode', 'export-sql']), 0)

    def test_source_binding_missing_baseline_and_wrong_inventory_stop_before_sql(self):
        with self.assertRaises(r.RecoveryStop):
            self.export(H)
        self.assertNotIn(self.outputs['sql'], self.store.files)
        self.baseline()
        with patch.object(self.adapter, 'current_source_hashes', return_value={}):
            with self.assertRaises(r.RecoveryStop):
                self.adapter.validated_backup(self.paths, self.archive_sha, r.digest(self.before))
        bad = r.json.loads(self.store.read(self.outputs['baseline']))
        bad['inventory']['database'] = 'lankapex_db'
        with self.assertRaises(self.preservation.PreservationStop):
            r.validate_migration_baseline(bad, self.before)

    def test_source_drift_during_export_preserves_sql_without_issuing_report(self):
        binding = self.baseline()
        write = self.store.write_bytes
        def drift(path, raw):
            write(path, raw)
            self.adapter.current_source_hashes.return_value = {}
        with patch.object(self.store, 'write_bytes', side_effect=drift), self.assertRaises(r.RecoveryStop):
            self.export(binding['baseline_sha256'])
        self.assertIn(self.outputs['sql'], self.store.files)
        self.assertNotIn(self.outputs['export_report'], self.store.files)


if __name__ == '__main__':
    unittest.main()
