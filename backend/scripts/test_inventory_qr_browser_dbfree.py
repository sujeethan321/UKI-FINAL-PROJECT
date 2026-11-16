"""Static, database-free checks for the operator inventory path."""
import ast
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent


class InventorySafety(unittest.TestCase):
    def test_python_inventory_is_read_only_and_fail_closed(self):
        source = (HERE / "inventory_qr_browser_test_db.py").read_text()
        ast.parse(source)
        for required in ("validate_identity(", "modeled != tables - {\"alembic_version\"}",
                         "START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY",
                         "connection.rollback()", "engine.url.database != TARGET",
                         "engine.url.username != USER", "active_admin_ids_sample",
                         "application_row_counts", "ownership\": \"unverified"):
            self.assertIn(required, source)
        self.assertLess(source.index("validate_identity("), source.index("START TRANSACTION"))
        for forbidden in ("password_hash", "jwt.encode", "db.commit(", "connection.commit(",
                          "DELETE FROM", "TRUNCATE", "DROP TABLE", "CREATE TABLE", "UPDATE users"):
            self.assertNotIn(forbidden, source)

    def test_wrapper_reuses_private_runtime_gate_and_cleans_environment(self):
        source = (HERE / "inventory_qr_browser_test_db.ps1").read_text()
        for required in ("qr-test-runtime.dpapi", "qr-browser-jwt.dpapi",
                         "check_qr_test_runtime.py", "inventory_qr_browser_test_db.py",
                         "MYSQL_DATABASE = 'lankapex_test_db'",
                         "MYSQL_USER = 'lankapex_qr_test_runtime'", "APP_ENV = 'testing'",
                         "ZeroFreeBSTR", "} finally {"):
            self.assertIn(required, source)
        self.assertLess(source.index("check_qr_test_runtime.py"),
                        source.index("inventory_qr_browser_test_db.py"))
        for forbidden in ("lankapex_demo_db", "lankapex_db'", "uvicorn", "pytest", "alembic"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
