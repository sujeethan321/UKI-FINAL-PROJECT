"""Pure diagnostic tests: compile the actual helper without app/DB initialization."""
import ast
from pathlib import Path
import unittest
from sqlalchemy.exc import DBAPIError, OperationalError

source = Path(__file__).resolve().parents[1] / 'app/core/http_security.py'
tree = ast.parse(source.read_text(encoding='utf-8'))
helper = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'database_failure_diagnostic')
namespace = {'DBAPIError': DBAPIError}
exec(compile(ast.Module(body=[helper], type_ignores=[]), str(source), 'exec'), namespace)
diagnostic = namespace['database_failure_diagnostic']


class DiagnosticTests(unittest.TestCase):
    def error(self, code):
        return OperationalError('SELECT private-columns', {'password': 'private-parameter'},
                                Exception(code, 'private-error-message'))

    def test_database_error_categories(self):
        for code, category in ((1040, 'CONNECTION_LIMIT'), (1044, 'DATABASE_ACCESS_DENIED'),
                               (1045, 'AUTHENTICATION_FAILED'), (1054, 'SCHEMA_COLUMN_MISMATCH'),
                               (1142, 'STATEMENT_PERMISSION_DENIED'), (1146, 'SCHEMA_TABLE_MISSING'),
                               (1205, 'LOCK_WAIT_TIMEOUT'), (1213, 'DEADLOCK'),
                               (2003, 'CONNECTION_FAILED'), (2006, 'CONNECTION_LOST'),
                               (2013, 'CONNECTION_LOST'), (2026, 'TLS_CONNECTION_FAILED')):
            with self.subTest(code=code):
                self.assertEqual(diagnostic(self.error(code)), (code, category))

    def test_invalid_codes_are_not_rendered(self):
        for value in ('private-code', '1045', True, None, -1, 999999):
            with self.subTest(kind=type(value).__name__):
                self.assertEqual(diagnostic(self.error(value)),
                                 ('UNAVAILABLE', 'DATABASE_ERROR_UNCLASSIFIED'))

    def test_unknown_numeric_code(self):
        self.assertEqual(diagnostic(self.error(1999)), (1999, 'DATABASE_ERROR_UNCLASSIFIED'))

    def test_no_exception_stringification(self):
        class PrivateError(Exception):
            def __str__(self):
                raise AssertionError('Must not render raw errors')
        exc = OperationalError('private-SQL', {'secret': 'private-value'}, PrivateError(1045))
        self.assertEqual(diagnostic(exc), (1045, 'AUTHENTICATION_FAILED'))
        self.assertEqual(diagnostic(PrivateError('private-value')),
                         ('UNAVAILABLE', 'NOT_DBAPI_ERROR'))

    def test_values_never_appear_in_diagnostic(self):
        output = repr(diagnostic(self.error(2013)))
        self.assertNotIn('private', output)
        self.assertNotIn('SELECT', output)


if __name__ == '__main__':
    unittest.main()
