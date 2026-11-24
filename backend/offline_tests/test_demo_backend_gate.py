"""Offline only: imports the gate without application configuration or DB modules."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from contextlib import redirect_stderr
from io import StringIO
import ast

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('demo_gate', ROOT / 'backend/scripts/check_demo_backend.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def config():
    return SimpleNamespace(APP_ENV='development', MYSQL_DATABASE=gate.TARGET,
        MYSQL_USER='lankapex_demo_app', MYSQL_HOST='localhost', MYSQL_PORT=3306,
        AI_ENABLED=False, APP_DEBUG=False, LOG_LEVEL='WARNING', RATE_LIMIT_MODE='local',
        CORS_ALLOWED_ORIGINS=['http://127.0.0.1:5173'], ALLOWED_HOSTS=['127.0.0.1', 'localhost'])


def url():
    return SimpleNamespace(database=gate.TARGET, username='lankapex_demo_app', host='localhost', port=3306)


def inspector():
    i = Mock()
    i.get_table_names.return_value = list(NAMES | {'alembic_version'})
    columns = {
        'business_join_links': ['business_id', 'public_code', 'created_at'],
        'customer_join_requests': ['request_id', 'business_id', 'customer_user_id', 'status', 'created_at', 'decided_at', 'decided_by'],
    }
    i.get_columns.side_effect = lambda t: [{'name': n} for n in columns[t]]
    uniques = {
        'customer_profiles': ('uq_customer_profile_business_user', ['business_id', 'user_id']),
        'business_join_links': ('uq_business_join_public_code', ['public_code']),
        'customer_join_requests': ('uq_customer_join_business_user', ['business_id', 'customer_user_id']),
    }
    i.get_unique_constraints.side_effect = lambda t: [dict(zip(('name', 'column_names'), uniques[t]))]
    i.get_pk_constraint.side_effect = lambda t: {'constrained_columns': ['business_id' if t == 'business_join_links' else 'request_id']}
    i.get_indexes.return_value = [{'name': 'ix_customer_join_business_status_created', 'column_names': ['business_id', 'status', 'created_at']}]
    i.get_check_constraints.return_value = [{'name': 'ck_customer_join_status', 'sqltext': "(`status` in ('pending','approved','rejected','cancelled'))"}]
    def fks(t):
        pairs = [('business_id', 'businesses', 'business_id')]
        if t == 'customer_join_requests':
            pairs += [('customer_user_id', 'users', 'user_id'), ('decided_by', 'users', 'user_id')]
        return [{'constrained_columns': [c], 'referred_table': p, 'referred_columns': [k], 'options': {'ondelete': 'RESTRICT'}} for c,p,k in pairs]
    i.get_foreign_keys.side_effect = fks
    return i


# Read source metadata declarations only; never import app.models or settings.
import re
NAMES = set()
for path in (ROOT / 'backend/app/models').glob('*.py'):
    NAMES.update(re.findall(r"__tablename__\s*=\s*['\"]([^'\"]+)", path.read_text(encoding='utf-8')))


class DemoGateTests(unittest.TestCase):
    def test_every_fixed_guard_error_has_allowlisted_diagnostic(self):
        tree = ast.parse((ROOT/'backend/scripts/check_demo_backend.py').read_text())
        messages = {n.exc.args[0].value for n in ast.walk(tree)
                    if isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call)
                    and isinstance(n.exc.func, ast.Name) and n.exc.func.id == 'RuntimeError'
                    and isinstance(n.exc.args[0], ast.Constant)}
        self.assertEqual(messages, set(gate.FAILURE_CATEGORIES))
        for message, category in gate.FAILURE_CATEGORIES.items():
            with self.subTest(category=category), redirect_stderr(StringIO()) as output:
                action = Mock(side_effect=RuntimeError(message))
                self.assertEqual(gate.run(action), 1)
                action.assert_called_once_with()
                self.assertEqual(output.getvalue(), 'STOP: demo API preflight category='+category+'\n')

    def test_real_revision_rejection_is_diagnosed_without_acceptance(self):
        with redirect_stderr(StringIO()) as output:
            self.assertEqual(gate.run(lambda: gate.validate_schema(inspector(), ['6e3f2c1a9b04'], NAMES)), 1)
        self.assertIn('category=schema_revision_mismatch', output.getvalue())

    def test_unknown_errors_never_print_private_details(self):
        errors = [RuntimeError('secret-password mysql://private'),
                  ModuleNotFoundError('private_path'), ValueError('private records')]
        for error in errors:
            with self.subTest(kind=type(error).__name__), redirect_stderr(StringIO()) as output:
                action = Mock(side_effect=error)
                self.assertEqual(gate.run(action), 1)
                self.assertNotIn(str(error), output.getvalue())
                action.assert_called_once_with()

    def test_database_error_code_classification_and_success(self):
        for code, expected in [(1045, 'authentication_failed'), (2003, 'mysql_connection_failed'),
                               (1142, 'metadata_access_denied'), (9999, 'unclassified_preflight_failure')]:
            error = ValueError('private')
            error.orig = Exception(code, 'secret SQL credentials')
            self.assertEqual(gate.failure_category(error), expected)
        error.orig = Exception()
        self.assertEqual(gate.failure_category(error), 'unclassified_preflight_failure')
        action = Mock()
        self.assertEqual(gate.run(action), 0)
        action.assert_called_once_with()

    def test_preflight_only_cannot_fall_through_to_server(self):
        source = (ROOT/'backend/scripts/start_demo_backend.ps1').read_text()
        self.assertIn('param([switch]$PreflightOnly)', source)
        self.assertRegex(source, r'if \(\$PreflightOnly\)\s*\{[^}]+\}\s*else\s*\{\s*& \$python -m uvicorn')
        self.assertLess(source.index('scripts/check_demo_backend.py'), source.index('if ($PreflightOnly)'))

    def test_current_schema(self):
        gate.validate_schema(inspector(), [gate.REVISION], NAMES)

    def test_old_or_multiple_revision(self):
        for revisions in ([], ['6e3f2c1a9b04'], [gate.REVISION, gate.REVISION]):
            with self.subTest(revisions=revisions), self.assertRaises(RuntimeError):
                gate.validate_schema(inspector(), revisions, NAMES)

    def test_missing_qr_tables(self):
        for table in ('business_join_links', 'customer_join_requests'):
            i = inspector(); i.get_table_names.return_value.remove(table)
            with self.subTest(table=table), self.assertRaises(RuntimeError):
                gate.validate_schema(i, [gate.REVISION], NAMES)

    def test_missing_or_wrong_unique(self):
        for constraints in ([], [{'name': 'uq_customer_profile_business_user', 'column_names': ['user_id']} ]):
            i = inspector(); i.get_unique_constraints.side_effect = None; i.get_unique_constraints.return_value = constraints
            with self.subTest(constraints=constraints), self.assertRaises(RuntimeError):
                gate.validate_schema(i, [gate.REVISION], NAMES)

    def test_partial_qr(self):
        for method in ('get_columns', 'get_foreign_keys', 'get_indexes', 'get_check_constraints'):
            i = inspector(); getattr(i, method).side_effect = None; getattr(i, method).return_value = []
            with self.subTest(method=method), self.assertRaises(RuntimeError):
                gate.validate_schema(i, [gate.REVISION], NAMES)

    def test_safe_configuration(self):
        gate.validate_configuration(config(), url())

    def test_wrong_database_account_host_port(self):
        for name, value in [('MYSQL_DATABASE','lankapex_test_db'), ('MYSQL_USER','root'), ('MYSQL_HOST','127.0.0.1'), ('MYSQL_PORT',3307), ('APP_ENV','testing')]:
            c=config(); setattr(c,name,value)
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                gate.validate_configuration(c,url())
        for name in ('database','username','host','port'):
            u=url(); setattr(u,name,'wrong')
            with self.subTest(url=name), self.assertRaises(RuntimeError):
                gate.validate_configuration(config(),u)

    def test_unsafe_effective_configuration(self):
        for name,value in [('AI_ENABLED',True),('APP_DEBUG',True),('LOG_LEVEL','DEBUG'),('RATE_LIMIT_MODE','external'),('CORS_ALLOWED_ORIGINS',['*']),('ALLOWED_HOSTS',['*'])]:
            c=config(); setattr(c,name,value)
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                gate.validate_configuration(c,url())

    def test_actual_identity(self):
        gate.validate_runtime_identity(gate.TARGET, 'lankapex_demo_app@localhost')
        for database, account in [('lankapex_db', 'lankapex_demo_app@localhost'), (gate.TARGET, 'root@localhost'), (gate.TARGET, 'lankapex_demo_app@%')]:
            with self.subTest(database=database, account=account), self.assertRaises(RuntimeError):
                gate.validate_runtime_identity(database, account)

    def test_mysql_reflection_variants(self):
        i=inspector()
        original=i.get_foreign_keys.side_effect
        def default_restrict(table):
            rows=original(table)
            for row in rows:
                row['options']={}
            return rows
        i.get_foreign_keys.side_effect=default_restrict
        i.get_check_constraints.return_value=[{'name':'ck_customer_join_status', 'sqltext': "(`status` in (_utf8mb4'pending',_utf8mb4'approved',_utf8mb4'rejected',_utf8mb4'cancelled'))"}]
        gate.validate_schema(i,[gate.REVISION],NAMES)
        i.get_foreign_keys.return_value=[]
        def cascading(table):
            rows=original(table)
            for row in rows:
                row['options']={'ondelete':'CASCADE'}
            return rows
        i.get_foreign_keys.side_effect=cascading
        with self.assertRaises(RuntimeError):
            gate.validate_schema(i,[gate.REVISION],NAMES)

    def test_reporting(self):
        self.assertEqual(len(NAMES),28)
        self.assertIn('28 application tables (29 total including alembic_version)',gate.PASS_MESSAGE)

    def test_launcher_restoration_and_no_migration(self):
        s=(ROOT/'backend/scripts/start_demo_backend.ps1').read_text()
        for name in ('AI_ENABLED','GROQ_API_KEY','CORS_ALLOWED_ORIGINS','ALLOWED_HOSTS'):
            self.assertIn("'"+name+"'",s)
        self.assertIn("$env:AI_ENABLED = 'false'",s)
        self.assertIn("SetEnvironmentVariable('GROQ_API_KEY', $null, 'Process')",s)
        self.assertIn("SetEnvironmentVariable($name, $previous[$name], 'Process')",s)
        self.assertIn('--host 127.0.0.1 --port 8001',s)
        self.assertNotIn('alembic',s.lower())
        self.assertIn('Unsupported inherited dotenv isolation flag',s)

    def test_linear_chain(self):
        links={}
        for path in (ROOT/'backend/alembic/versions').glob('*.py'):
            s=path.read_text()
            rev=re.search(r'^revision(?:\s*:[^=]+)?\s*=\s*[\'\"]([^\'\"]+)',s,re.M)
            prev=re.search(r'^down_revision(?:\s*:[^=]+)?\s*=\s*(?:[\'\"]([^\'\"]+)[\'\"]|None)',s,re.M)
            self.assertIsNotNone(rev); self.assertIsNotNone(prev)
            links[rev[1]]=prev[1]
        self.assertEqual(len(links),16)
        self.assertEqual(set(links)-set(links.values()),{gate.REVISION})
        self.assertEqual(links[gate.REVISION],'6e3f2c1a9b04')


if __name__ == '__main__':
    unittest.main()
