"""Offline only: network forbidden; no application services are started."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import socket
import ssl
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.core.viva_runtime_policy import ENVIRONMENT, dotenv_disabled

ENV = dict(ENVIRONMENT, MYSQL_PASSWORD='fictional-test-password', JWT_SECRET_KEY='a4c8' * 32)
# OpenSSL on Windows needs its OS location even in an isolated test environment.
for _name in ('SystemRoot', 'WINDIR', 'SystemDrive'):
    if _name in os.environ:
        ENV[_name] = os.environ[_name]


class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Engine construction only. Never read the operator's CA or connect.
        original_connect = socket.socket.connect
        def guarded_connect(sock, address):
            # Windows implements the event-loop self-pipe via socketpair's
            # private loopback handshake. Permit ONLY that stdlib caller,
            # never application HTTP/MySQL connections or arbitrary loopback.
            fallback = getattr(socket, '_fallback_socketpair', None)
            if (fallback is not None and sys._getframe(1).f_code is fallback.__code__
                    and address[0] in ('127.0.0.1', '::1')):
                return original_connect(sock, address)
            raise AssertionError('NETWORK_FORBIDDEN')
        cls.network = patch.object(socket.socket, 'connect', new=guarded_connect)
        cls.network.start()
        cls.network2 = patch.object(socket, 'create_connection', side_effect=AssertionError('NETWORK_FORBIDDEN'))
        cls.network2.start()
        with patch.dict(os.environ, ENV, clear=True), patch.object(Path, 'is_file', return_value=True), patch.object(ssl.SSLContext, 'load_verify_locations'):
            from app.core import config, database
            import app.models
            spec = importlib.util.spec_from_file_location('runtime_gate', BACKEND / 'scripts/check_viva_backend.py')
            cls.gate = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.gate)
            cls.config, cls.database = config, database

    @classmethod
    def tearDownClass(cls):
        cls.database.engine.dispose()
        cls.network.stop()
        cls.network2.stop()

    def setUp(self):
        self.env = patch.dict(os.environ, ENV, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        values = {k: (v == 'true' if v in ('true', 'false') else
                      v.split(',') if k in ('CORS_ALLOWED_ORIGINS', 'ALLOWED_HOSTS') else v)
                  for k, v in ENV.items() if k != 'LANKAPEX_VIVA_RUNTIME'}
        values.update(GROQ_API_KEY=None, STRIPE_TEST_SECRET_KEY=None, STRIPE_WEBHOOK_SECRET=None)
        self.settings = SimpleNamespace(**values)
        from sqlalchemy.engine import URL
        self.url = URL.create('mysql+pymysql', username='lankapex_viva_runtime', password=ENV['MYSQL_PASSWORD'],
                              host='127.0.0.1', port=3306, database='lankapex_viva_db')
        self.identity = ['lankapex_viva_db', 'lankapex_viva_runtime@127.0.0.1',
                         '7bc6e90d-aced-11f1-be0b-10e7c6704500', 3306, '8.0.46', 1, 0]
        self.grants = ["GRANT USAGE ON *.* TO `lankapex_viva_runtime`@`127.0.0.1`",
                       "GRANT SELECT, INSERT, UPDATE, DELETE ON `lankapex\\_viva\\_db`.* TO `lankapex_viva_runtime`@`127.0.0.1`"]

    def test_correct_configuration(self):
        self.gate.validate_configuration(self.settings, self.url)

    def test_cors_policy_exact_origins(self):
        self.assertEqual(ENVIRONMENT['CORS_ALLOWED_ORIGINS'].split(','),
                         ['http://127.0.0.1:5173', 'http://127.0.0.1:5176'])
        with patch.dict(os.environ, {'CORS_ALLOWED_ORIGINS': 'http://127.0.0.1:5173,http://localhost:5173'}):
            with self.assertRaises(ValueError):
                dotenv_disabled()

    def test_cors_actual_application_preflight_and_auth_post(self):
        from fastapi.testclient import TestClient
        from sqlalchemy.engine import Engine
        from app.main import app
        previous = app.dependency_overrides.copy()
        app.dependency_overrides[self.database.get_db] = lambda: Mock()
        try:
            with patch.object(Engine, 'connect', side_effect=AssertionError('DB_FORBIDDEN')):
                client = TestClient(app)
                try:
                    for origin in ('http://127.0.0.1:5173', 'http://127.0.0.1:5176'):
                        with self.subTest(origin=origin):
                            response = client.options('/api/v1/auth/login', headers={
                                'Origin': origin, 'Access-Control-Request-Method': 'POST',
                                'Access-Control-Request-Headers': 'content-type,authorization'})
                            self.assertEqual(response.status_code, 200)
                            self.assertEqual(response.headers['access-control-allow-origin'], origin)
                            self.assertIn('POST', response.headers['access-control-allow-methods'])
                            self.assertIn('OPTIONS', response.headers['access-control-allow-methods'])
                            self.assertIn('authorization', response.headers['access-control-allow-headers'].lower())
                            self.assertIn('content-type', response.headers['access-control-allow-headers'].lower())
                            self.assertNotIn('access-control-allow-credentials', response.headers)
                            # Missing credentials exercise the real auth validation response,
                            # without submitting a login or querying a database.
                            response = client.post('/api/v1/auth/login', content='', headers={
                                'Origin': origin, 'Content-Type': 'application/x-www-form-urlencoded'})
                            self.assertEqual(response.status_code, 422)
                            self.assertEqual(response.headers['access-control-allow-origin'], origin)
                finally:
                    client.close()
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(previous)

    def test_cors_unapproved_origins_rejected(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        try:
            for origin in ('http://127.0.0.1:5174', 'http://localhost:5173',
                           'https://unapproved.example', 'http://127.0.0.1:5173.evil.example'):
                with self.subTest(origin=origin):
                    response = client.options('/api/v1/auth/login', headers={
                        'Origin': origin, 'Access-Control-Request-Method': 'POST'})
                    self.assertEqual(response.status_code, 400)
                    self.assertNotIn('access-control-allow-origin', response.headers)
        finally:
            client.close()

    def test_wrong_settings(self):
        for key, value in [('MYSQL_DATABASE', 'lankapex_db'), ('MYSQL_USER', 'root'),
                           ('MYSQL_HOST', 'localhost'), ('MYSQL_PORT', 3307),
                           ('MYSQL_TLS_MODE', 'default'), ('AI_ENABLED', True), ('APP_DEBUG', True)]:
            with self.subTest(key=key):
                settings = copy.copy(self.settings)
                setattr(settings, key, value)
                with self.assertRaises(self.gate.GateError):
                    self.gate.validate_configuration(settings, self.url)

    def test_wrong_engine_targets(self):
        for key, value in [('host', 'localhost'), ('port', 3307), ('username', 'root'),
                           ('database', 'lankapex_test_db'), ('password', 'other'), ('query', {'ssl': 'false'})]:
            with self.subTest(key=key), self.assertRaises(self.gate.GateError):
                self.gate.validate_configuration(self.settings, self.url.set(**{key: value}))

    def test_isolation_absent(self):
        os.environ.pop('LANKAPEX_VIVA_RUNTIME')
        with self.assertRaises(self.gate.GateError):
            self.gate.validate_configuration(self.settings, self.url)

    def test_isolation_invalid_and_external_secrets(self):
        for key, value in [('LANKAPEX_VIVA_RUNTIME', '1'), ('GROQ_API_KEY', 'never-log-this'),
                           ('STRIPE_TEST_SECRET_KEY', 'never-log-this'), ('DATABASE_URL', 'secret-url')]:
            with self.subTest(key=key), patch.dict(os.environ, {key: value}), self.assertRaises(ValueError):
                dotenv_disabled()

    def test_actual_settings_exclude_dotenv(self):
        from pydantic_settings import DotEnvSettingsSource
        with patch.object(Path, 'is_file', return_value=True), patch.object(DotEnvSettingsSource, '__call__', side_effect=AssertionError('DOTENV_READ')):
            settings = self.config.Settings()
            self.assertEqual(settings.MYSQL_DATABASE, 'lankapex_viva_db')
            self.assertTrue(settings.ADDRESS_CHECKOUT_ENABLED)
            self.assertIsNone(settings.GROQ_API_KEY)

    def test_other_modes_unchanged(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(dotenv_disabled())

    def test_identity_valid(self):
        self.gate.validate_identity(self.identity)

    def test_identity_wrong_each_field(self):
        for index, value in enumerate(['other', 'root@localhost', 'other-uuid', 3307, '8.0.45', 0, 1]):
            row = self.identity.copy()
            row[index] = value
            with self.subTest(index=index), self.assertRaises(self.gate.GateError):
                self.gate.validate_identity(row)

    def test_dml_grants(self):
        self.gate.validate_grants(self.grants, 'NONE', 0)
        self.gate.validate_grants([g.replace('\\_', '_') for g in self.grants], 'NONE', 1)

    def test_global_and_extra_privileges(self):
        for grant in ["GRANT SELECT ON *.* TO `lankapex_viva_runtime`@`127.0.0.1`",
                      self.grants[1].replace('DELETE', 'DELETE, TRIGGER'),
                      self.grants[1] + ' WITH GRANT OPTION', self.grants[1].replace('viva', 'test'),
                      self.grants[1].replace('runtime', 'migrator'),
                      self.grants[1].replace('\\_', '_'), "GRANT `role` TO `lankapex_viva_runtime`@`127.0.0.1`"]:
            with self.subTest(grant=grant), self.assertRaises(self.gate.GateError):
                self.gate.validate_grants([grant], 'NONE', 0)

    def test_roles_and_missing_rights(self):
        with self.assertRaises(self.gate.GateError):
            self.gate.validate_grants(self.grants, '`administrator`@`%`', 0)
        with self.assertRaises(self.gate.GateError):
            self.gate.validate_grants(self.grants[:1], 'NONE', 0)

    def test_literal_scope_under_partial_revokes(self):
        with self.assertRaises(self.gate.GateError):
            self.gate.validate_grants(self.grants, 'NONE', 1)

    def test_actual_tls_socket_policy(self):
        certificate = b'fictional-DER-for-offline-pin-test'
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.verify_flags |= ssl.VERIFY_X509_STRICT
        context.hostname_checks_common_name = False
        sock = Mock(spec=ssl.SSLSocket)
        sock.context = context
        sock.version.return_value = 'TLSv1.3'
        sock.getpeercert.return_value = certificate
        with patch.object(self.gate.viva_tls, 'CERT_SHA256', hashlib.sha256(certificate).hexdigest()):
            self.gate.viva_tls.verify_socket(sock)
            sock.version.return_value = 'TLSv1.1'
            with self.assertRaises(ValueError):
                self.gate.viva_tls.verify_socket(sock)
            sock.version.return_value = 'TLSv1.3'
            context.hostname_checks_common_name = True
            with self.assertRaises(ValueError):
                self.gate.viva_tls.verify_socket(sock)
            context.hostname_checks_common_name = False
            context.check_hostname = False
            with self.assertRaises(ValueError):
                self.gate.viva_tls.verify_socket(sock)
            context.check_hostname = True
            sock.getpeercert.return_value = b'wrong-certificate'
            with self.assertRaises(ValueError):
                self.gate.viva_tls.verify_socket(sock)

    def test_actual_model_relationships_and_schema_negatives(self):
        inspector = Mock()
        tables = self.database.Base.metadata.tables
        inspector.get_columns.side_effect = lambda n: [{'name': c.name} for c in tables[n].columns]
        inspector.get_pk_constraint.side_effect = lambda n: {'constrained_columns': [c.name for c in tables[n].primary_key.columns]}
        def keys(n):
            return [{'constrained_columns': [e.parent.name for e in f.elements],
                     'referred_schema': None, 'referred_table': f.elements[0].column.table.name,
                     'referred_columns': [e.column.name for e in f.elements]}
                    for f in tables[n].foreign_key_constraints]
        inspector.get_foreign_keys.side_effect = keys
        self.gate.validate_schema(inspector, self.database.Base.metadata)
        inspector.get_columns.side_effect = lambda n: []
        with self.assertRaises(self.gate.GateError):
            self.gate.validate_schema(inspector, self.database.Base.metadata)
        inspector.get_columns.side_effect = lambda n: [{'name': c.name} for c in tables[n].columns]
        inspector.get_foreign_keys.side_effect = lambda n: keys(n) + [{'constrained_columns': ['user_id'], 'referred_schema': 'other', 'referred_table': 'users', 'referred_columns': ['user_id']}]
        with self.assertRaises(self.gate.GateError):
            self.gate.validate_schema(inspector, self.database.Base.metadata)

    def test_inventory_and_real_model_names(self):
        expected = self.gate.expected_tables()
        rows = [(n, 'BASE TABLE', 'InnoDB') for n in expected]
        self.gate.validate_inventory(rows, self.database.Base.metadata.tables, expected)
        for bad in [rows[:-1], rows + [('extra', 'BASE TABLE', 'InnoDB')],
                    [(n, 'BASE TABLE', 'MyISAM') for n in expected]]:
            with self.assertRaises(self.gate.GateError):
                self.gate.validate_inventory(bad, self.database.Base.metadata.tables, expected)

    def mock_engine(self, revision='d15a8c902e64', error=None):
        conn = Mock()
        conn.__enter__ = Mock(return_value=conn)
        conn.__exit__ = Mock(return_value=False)
        conn.connection.driver_connection._sock.cipher.return_value = ('AES256', 'TLSv1.3', 256)
        def execute(sql):
            result = Mock()
            if error:
                raise error
            if sql.startswith('SELECT DATABASE'):
                result.one.return_value = self.identity
            elif sql.startswith('SHOW GRANTS'):
                result.scalars.return_value.all.return_value = self.grants
            elif sql == 'SELECT CURRENT_ROLE()':
                result.scalar_one.return_value = 'NONE'
            elif sql == 'SELECT @@global.partial_revokes':
                result.scalar_one.return_value = 0
            elif sql.startswith('SELECT version_num'):
                result.scalars.return_value.all.return_value = [revision]
            elif sql != 'START TRANSACTION READ ONLY':
                raise AssertionError('UNAPPROVED_SQL')
            return result
        conn.exec_driver_sql.side_effect = execute
        conn.execute.return_value.all.return_value = [(n, 'BASE TABLE', 'InnoDB') for n in self.gate.expected_tables()]
        engine = Mock(url=self.url)
        engine.connect.return_value = conn
        return engine, conn

    def run_mock(self, engine, socket_error=None):
        output = io.StringIO()
        with patch.object(self.config, 'settings', self.settings), patch.object(self.database, 'engine', engine), patch.object(Path, 'read_bytes', return_value=b'fictional-ca'), patch.object(self.gate, 'CA_SHA256', hashlib.sha256(b'fictional-ca').hexdigest().upper()), patch.object(self.gate.viva_tls, 'verify_socket', side_effect=socket_error), patch.object(self.gate, 'validate_schema'), contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            result = self.gate.main()
        engine.dispose.assert_called_once()
        return result, output.getvalue()

    def test_success_read_only_and_disposal(self):
        engine, conn = self.mock_engine()
        code, output = self.run_mock(engine)
        self.assertEqual(code, 0)
        self.assertIn('PASS_READ_ONLY', output)
        conn.rollback.assert_called_once()
        conn.commit.assert_not_called()

    def test_wrong_revision(self):
        engine, _ = self.mock_engine(revision='ae2b7c5f1d48')
        code, output = self.run_mock(engine)
        self.assertEqual(code, 1)
        self.assertIn('REVISION_MISMATCH', output)

    def test_certificate_failure_sanitized(self):
        engine, _ = self.mock_engine()
        code, output = self.run_mock(engine, ValueError('secret-certificate-details'))
        self.assertEqual(code, 1)
        self.assertNotIn('secret-certificate-details', output)

    def test_database_failure_sanitized(self):
        engine, _ = self.mock_engine(error=RuntimeError('password=secret financial customer details'))
        code, output = self.run_mock(engine)
        self.assertEqual(code, 1)
        self.assertNotIn('password=', output)
        self.assertNotIn('customer details', output)

    def test_ca_checksum_rejected_before_connection(self):
        engine, _ = self.mock_engine()
        with patch.object(self.config, 'settings', self.settings), patch.object(self.database, 'engine', engine), patch.object(Path, 'read_bytes', return_value=b'wrong-ca'), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.gate.main(), 1)
        engine.connect.assert_not_called()
        engine.dispose.assert_called_once()

    def test_application_import_has_no_database_or_service_launch(self):
        from sqlalchemy.engine import Engine
        import subprocess
        import threading
        with patch.object(Engine, 'connect', side_effect=AssertionError('DB_CONNECTION_FORBIDDEN')), patch.object(self.database.Base.metadata, 'create_all', side_effect=AssertionError('DDL_FORBIDDEN')), patch.object(subprocess, 'Popen', side_effect=AssertionError('PROCESS_FORBIDDEN')), patch.object(threading.Thread, 'start', side_effect=AssertionError('THREAD_FORBIDDEN')):
            import importlib
            application = importlib.import_module('app.main')
            self.assertIsNotNone(application.app)

    def test_disposal_failure_is_sanitized(self):
        engine, _ = self.mock_engine()
        engine.dispose.side_effect = RuntimeError('private-close-error')
        code, output = self.run_mock(engine)
        self.assertEqual(code, 1)
        self.assertIn('DISPOSAL_FAILED_DETAILS_REDACTED', output)
        self.assertNotIn('private-close-error', output)


if __name__ == '__main__':
    unittest.main()
