"""Synthetic metadata and fake subprocess/transport only. Never opens private files."""
import contextlib
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
SPEC = importlib.util.spec_from_file_location('random_provision', SCRIPTS / 'provision_demo_qr_random_password.py')
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)
SECRET = 'A' * 64  # Synthetic fixture, not an actual generated credential.
GRANTS = 'GRANT ALTER, CREATE, INDEX, INSERT, REFERENCES, SELECT, UPDATE ON `lankapex\\_demo\\_db`.* TO `lankapex_demo_qr_migrator`@`localhost`'


def snapshot():
    return dict(globals=[('general_log', 'ON'), ('slow_query_log', 'ON'), ('log_bin', 'ON'),
                         ('log_output', 'FILE'), ('binlog_format', 'ROW'),
                         ('binlog_rows_query_log_events', 'OFF'), ('performance_schema', 'ON')],
                plugins=[('caching_sha2_password', 'ACTIVE', 'AUTHENTICATION', None)],
                components=[(0,)], password_length=[(64,)],
                consumers=[(n, 'NO') for n in p.logging_gate.REQUIRED_CONSUMERS],
                instruments=[('statement/sql/create_user', 'NO')])


class RandomPasswordTests(unittest.TestCase):
    def args(self, execute=False):
        args = ['--execute' if execute else '--preflight-only', '--confirm-target', p.TARGET,
                '--confirm-account', p.ACCOUNT, '--dba-user', 'authorized_dba',
                '--confirm-dba-account', 'authorized_dba@localhost', '--tls-ca', 'synthetic-ca.pem']
        args += ['--attest-' + name.replace('_', '-') for name in p.CONTROLS]
        if execute:
            args += ['--confirm-credential-creation', '--confirm-session-length-64']
        return args

    def connection(self, changes=None):
        data = snapshot()
        data.update(changes or {})
        cursor = Mock()
        cursor.description = [(key,) for key in ('user', 'host', 'generated password', 'auth_factor')]
        cursor.last = None
        cursor.created = False

        def execute(sql, params=()):
            self.assertNotIn(SECRET, sql)
            if sql == p.CREATE:
                self.assertFalse(params)
                cursor.created = True
            if sql == p.SET_LENGTH:
                data['password_length'] = [(64,)]
            cursor.last = sql

        def fetch():
            sql = cursor.last
            if sql == p.CREATE:
                return data.get('result_rows', [(p.USER, 'localhost', SECRET, 1)])
            if sql == p.logging_gate.IDENTITY:
                return [(data.get('current_user', 'authorized_dba@localhost'), 'authorized_dba@localhost',
                         data.get('database'), data.get('port', 3306),
                         data.get('version', '8.0.46'), 'NONE', '')]
            if sql == p.PLUGIN:
                return [('caching_sha2_password',)]
            if sql == p.TLS:
                return [('Ssl_cipher', 'synthetic-cipher'), ('Ssl_version', 'TLSv1.3')]
            if sql.startswith('SELECT @@port'):
                return [(3306, 'NONE', 0, '', '8.0.46')]
            for key, query in dict(globals=p.logging_gate.GLOBALS, plugins=p.logging_gate.PLUGINS,
                                   components=p.logging_gate.COMPONENTS, consumers=p.logging_gate.CONSUMERS,
                                   instruments=p.logging_gate.INSTRUMENTS, password_length=p.LENGTH).items():
                if sql == query:
                    return data[key]
            if 'information_schema.SCHEMATA' in sql:
                return [(1,)]
            if sql.startswith('SELECT Host, account_locked'):
                return [('localhost', 'N')]
            if sql.startswith('SELECT Host'):
                return [('localhost',)] if data.get('existing') else []
            if sql.startswith('SHOW GRANTS'):
                return [(GRANTS,)]
            return [(0,)]

        cursor.execute.side_effect = execute
        cursor.fetchall.side_effect = fetch
        connection = Mock()
        connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
        connection.cursor.return_value.__exit__ = Mock(return_value=False)
        return connection, cursor

    def run_main(self, args=None, changes=None, **kwargs):
        connection, cursor = self.connection(changes)
        connector, store, prompt, storage = Mock(return_value=connection), Mock(), Mock(return_value='synthetic-dba'), Mock()
        options = dict(connector=connector, prompt=prompt, store=store, tls_check=lambda c: True,
                       check_storage=storage)
        options.update(kwargs)
        output = io.StringIO()
        with patch.object(p.ssl, 'create_default_context', return_value=Mock()), contextlib.redirect_stdout(output):
            code = p.main(self.args() if args is None else args, **options)
        self.assertNotIn(SECRET, output.getvalue())
        self.assertNotIn('synthetic-dba', output.getvalue())
        return code, output.getvalue(), connector, cursor, store, storage

    def test_default_no_io(self):
        code, _, connector, _, store, storage = self.run_main([])
        self.assertEqual(code, 0)
        connector.assert_not_called(); store.assert_not_called(); storage.assert_not_called()

    def test_readonly_complete_preflight(self):
        code, output, connector, cursor, store, _ = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn('slow_query_log status=enabled_no_plaintext_in_issued_sql', output)
        self.assertIn('running_version=8.0.46', output)
        self.assertIn('statement_capture', output)
        store.assert_not_called()
        self.assertTrue(all(call.args[0].startswith(('SELECT ', 'SHOW ', 'START TRANSACTION READ ONLY'))
                            for call in cursor.execute.call_args_list))
        self.assertEqual(connector.call_args.kwargs['host'], '127.0.0.1')

    def test_success_exact_create_and_grant_once(self):
        code, _, connector, cursor, store, _ = self.run_main(self.args(True), {'password_length': [(20,)]})
        self.assertEqual(code, 0)
        connector.assert_called_once()
        sql = [c.args[0] for c in cursor.execute.call_args_list]
        self.assertEqual(sql.count(p.CREATE), 1)
        self.assertEqual(sql.count(p.legacy.GRANT), 1)
        self.assertEqual(sql.count(p.SET_LENGTH), 1)
        store.assert_called_once_with(SECRET)

    def test_unsupported_version(self):
        self.assertIn('unreviewed_server_version', self.run_main(changes={'version': '8.0.45'})[1])

    def test_existing_account_no_create(self):
        code, _, _, cursor, store, _ = self.run_main(self.args(True), {'existing': True})
        self.assertEqual(code, 1)
        self.assertNotIn(p.CREATE, [c.args[0] for c in cursor.execute.call_args_list]); store.assert_not_called()

    def test_weak_length_preflight_stop(self):
        code, output, _, _, _, _ = self.run_main(changes={'password_length': [(20,)]})
        self.assertEqual(code, 1)
        self.assertIn('STOP_length_below_64', output)

    def test_all_noncritical_findings_reported(self):
        code, output, _, _, _, _ = self.run_main(changes={'password_length': [(20,)], 'components': [(1,)],
                                                         'consumers': None})
        self.assertEqual(code, 1)
        for key in ('components', 'statement_capture', 'password_strength', 'slow_query_log', 'raw_logging_disabled'):
            self.assertIn('check=' + key, output)

    def test_unexpected_authentication_plugin(self):
        self.assertEqual(self.run_main(changes={'plugins': [('mysql_native_password', 'ACTIVE', 'AUTHENTICATION', None)]})[0], 1)

    def test_wrong_target_account_endpoint_dba(self):
        for flag in ('--confirm-target', '--confirm-account', '--confirm-dba-account'):
            args = self.args(True); args[args.index(flag) + 1] = 'wrong'
            code, _, connector, _, _, storage = self.run_main(args)
            self.assertEqual(code, 1); connector.assert_not_called(); storage.assert_not_called()
        for flag in ('--host', '--port'):
            self.assertEqual(self.run_main(self.args() + [flag, 'wrong'])[0], 1)

    def test_missing_attestations_and_execution_confirmation(self):
        for flag in ['--attest-' + n.replace('_', '-') for n in p.CONTROLS] + ['--confirm-session-length-64', '--confirm-credential-creation']:
            args = self.args(True); args.remove(flag)
            code, _, connector, _, store, _ = self.run_main(args)
            self.assertEqual(code, 1); connector.assert_not_called(); store.assert_not_called()

    def test_unverified_tls(self):
        code, _, _, cursor, _, _ = self.run_main(tls_check=lambda c: False)
        self.assertEqual(code, 1); cursor.execute.assert_not_called()

    def test_missing_length_metadata_not_bypassed_by_execution_flag(self):
        code, _, _, cursor, _, _ = self.run_main(self.args(True), {'password_length': None})
        self.assertEqual(code, 1)
        self.assertNotIn(p.CREATE, [c.args[0] for c in cursor.execute.call_args_list])

    def test_tracing_blocks_before_storage_or_connection(self):
        with patch.object(p.sys, 'gettrace', return_value=object()):
            code, _, connector, _, _, storage = self.run_main()
        self.assertEqual(code, 1); connector.assert_not_called(); storage.assert_not_called()

    def test_missing_storage_blocks_before_connection(self):
        code, output, connector, _, _, _ = self.run_main(check_storage=Mock(side_effect=RuntimeError(SECRET)))
        self.assertEqual(code, 1); connector.assert_not_called()
        self.assertIn('stage=storage_metadata', output)

    def test_authenticated_metadata_identity_mismatch(self):
        for changes in ({'current_user': 'unexpected@localhost'}, {'port': 3307},
                        {'database': 'lankapex_db'}):
            code, _, _, cursor, store, _ = self.run_main(self.args(True), changes)
            self.assertEqual(code, 1); store.assert_not_called()
            self.assertNotIn(p.CREATE, [c.args[0] for c in cursor.execute.call_args_list])

    def test_empty_sensitive_result_leaves_committed_stop(self):
        code, output, _, cursor, store, _ = self.run_main(self.args(True), {'result_rows': []})
        self.assertEqual(code, 1); store.assert_not_called()
        self.assertIn('stage=account_committed_result_capture', output)
        self.assertEqual([c.args[0] for c in cursor.execute.call_args_list].count(p.CREATE), 1)

    def test_connector_failure_sanitized_no_retry(self):
        failing = Mock(side_effect=RuntimeError(SECRET))
        code, output, _, _, store, _ = self.run_main(connector=failing)
        self.assertEqual(code, 1); failing.assert_called_once(); store.assert_not_called()
        self.assertIn('stage=authenticated_loopback_tls', output)

    def test_storage_metadata_does_not_decrypt_or_write(self):
        runner = Mock(return_value=Mock(returncode=0, stdout='PASS: absent credential and protected storage verified', stderr=''))
        p.storage_metadata(runner)
        args = runner.call_args.args[0]
        self.assertIn('-MetadataOnly', args)
        self.assertNotIn('-StoreFromPrivatePipe', args)
        self.assertNotIn('input', runner.call_args.kwargs)

    def test_default_ps_wrapper_has_no_private_operations(self):
        source = (SCRIPTS / 'provision_demo_qr_random_password.ps1').read_text()
        self.assertLess(source.index('if (-not $Execute -and -not $PreflightOnly)'),
                        source.index('Assert-DemoQrCredentialStorage'))
        self.assertNotIn('Get-Content', source)
        self.assertNotIn('$env:', source)
        self.assertNotIn('Remove-Item', source)

    def test_storage_failure_preserves_committed_account_no_grants_retry_cleanup(self):
        failing = Mock(side_effect=RuntimeError(SECRET))
        code, output, connector, cursor, _, _ = self.run_main(self.args(True), store=failing)
        self.assertEqual(code, 1)
        self.assertIn('stage=account_committed_credential_storage', output)
        sql = [c.args[0] for c in cursor.execute.call_args_list]
        self.assertEqual(sql.count(p.CREATE), 1)
        self.assertNotIn(p.legacy.GRANT, sql)
        self.assertFalse(any(s.startswith(('DROP ', 'ALTER USER', 'DELETE ', 'RESET ')) for s in sql))
        connector.assert_called_once(); failing.assert_called_once()

    def test_result_validation(self):
        for row in ((p.USER, 'localhost', 'short', 1), ('wrong', 'localhost', SECRET, 1),
                    (p.USER, 'localhost', SECRET, 2), (p.USER, 'remote', SECRET, 1)):
            cursor = Mock(description=[(k,) for k in ('user', 'host', 'generated password', 'auth_factor')])
            cursor.fetchall.return_value = [row]
            with self.assertRaises(p.verification.Stop): p.result_password(cursor)
        with self.assertRaises(p.verification.Stop): p.result_password(Mock(description=None))

    def test_excessive_grants_still_rejected(self):
        with self.assertRaises(p.verification.Stop):
            p.verification.grants([GRANTS.replace('ALTER,', 'DROP, ALTER,')])

    def test_capture_and_plugin_states_blocked(self):
        for key, value in [('plugins', [('audit', 'ACTIVE', 'AUDIT', 'external.dll')]),
                           ('components', [(1,)]), ('consumers', [(n, 'YES') for n in p.logging_gate.REQUIRED_CONSUMERS]),
                           ('instruments', [('statement/sql/select', 'YES')])]:
            data = snapshot(); data[key] = value
            self.assertFalse(p.ready(p.assess(data, dict.fromkeys(p.CONTROLS, True))))

    def test_collection_continues_after_unavailable_surface(self):
        read = Mock(side_effect=[RuntimeError(SECRET), [], [], [], [], [(20,)]])
        result = p.collect(read)
        self.assertEqual(read.call_count, 6)
        self.assertIsNone(result['globals'])

    def test_storage_private_pipe_no_secret_arguments_or_env(self):
        runner = Mock(return_value=Mock(returncode=0, stdout='PASS: server-generated credential stored and verified\n', stderr=''))
        p.store_password(SECRET, runner)
        args, options = runner.call_args.args[0], runner.call_args.kwargs
        self.assertNotIn(SECRET, args)
        self.assertNotIn('env', options)
        self.assertEqual(options['input'], SECRET)
        self.assertTrue(options['capture_output'])

    def test_storage_raw_errors_suppressed(self):
        runner = Mock(return_value=Mock(returncode=1, stdout=SECRET, stderr=SECRET))
        with self.assertRaises(p.verification.Stop) as error: p.store_password(SECRET, runner)
        self.assertNotIn(SECRET, str(error.exception)); runner.assert_called_once()

    def test_source_storage_protections(self):
        source = (SCRIPTS / 'store_demo_qr_random_password.ps1').read_text()
        for token in ('[IO.FileMode]::CreateNew', 'SetAccessRuleProtection($true,$false)',
                      "'S-1-5-18'", 'Assert-DemoQrCredentialStorage -Mode Create',
                      '-Mode Read', 'ConvertFrom-SecureString', 'ZeroFreeBSTR', 'finally'):
            self.assertIn(token, source)
        self.assertNotIn('Set-Acl ', source)
        self.assertNotIn('Remove-Item', source)

    def test_password_free_sql_and_entropy_bound(self):
        self.assertIn('BY RANDOM PASSWORD', p.CREATE)
        self.assertNotIn('%s', p.CREATE)
        # Source mapping round(byte*(82/255)): max bucket <=4 of 256.
        import math
        from collections import Counter
        count = Counter(math.floor(byte * ((len(p.ALPHABET) - 1) / 255) + 0.5) for byte in range(256))
        self.assertLessEqual(max(count.values()), 4)
        self.assertGreaterEqual(64 * math.log2(256 / max(count.values())), 256)
        self.assertLess(20 * math.log2(len(p.ALPHABET)), 256)


if __name__ == '__main__':
    unittest.main()
