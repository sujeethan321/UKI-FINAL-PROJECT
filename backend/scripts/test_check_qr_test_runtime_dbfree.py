"""Pure checks for the QR integration launcher; no MySQL imports or connections."""
import unittest

from check_qr_test_runtime import (PRIVILEGES, REVISION, SCOPE, TARGET, USER,
                                   validate_grants, validate_identity)


class QRTestRuntimeGateTests(unittest.TestCase):
    def setUp(self):
        self.grants = [
            f"GRANT USAGE ON *.* TO `{USER}`@`localhost`",
            "GRANT " + ", ".join(sorted(PRIVILEGES)) + f" ON {SCOPE} TO `{USER}`@`localhost`",
        ]
        self.tables = {"alembic_version", "business_join_links", "customer_join_requests"}
        self.tables.update(f"other_{i}" for i in range(26))

    def check(self, **changes):
        values = dict(configured_env="testing", configured_db=TARGET,
                      engine_db=TARGET, engine_user=USER, actual_db=TARGET,
                      actual_user=USER + "@localhost", revision=REVISION,
                      tables=self.tables, grants=self.grants)
        values.update(changes)
        validate_identity(**values)

    def test_exact_identity_revision_tables_and_grants(self):
        self.check()

    def test_other_database_account_revision_or_inventory_stops(self):
        for change in (dict(configured_env="development"), dict(configured_db="lankapex_db"),
                       dict(engine_db="lankapex_demo_db"), dict(actual_db="lankapex_test_db_copy"),
                       dict(actual_user="lankapex_qr_test_migrator@localhost"),
                       dict(revision="6e3f2c1a9b04"),
                       dict(tables=self.tables - {"business_join_links"})):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.check(**change)

    def test_unescaped_broad_extra_or_ddl_grants_stop(self):
        for bad in (
            self.grants[1].replace(SCOPE, "`lankapex_test_db`.*"),
            self.grants[1].replace(SCOPE, "`lankapex_demo_db`.*"),
            self.grants[1].replace(SCOPE, "*.*"),
            self.grants[1].replace("DELETE", "DELETE, CREATE"),
            self.grants[1].replace("DELETE", "DROP"),
            self.grants[1] + " WITH GRANT OPTION",
        ):
            with self.subTest(grant=bad), self.assertRaises(ValueError):
                validate_grants([self.grants[0], bad])


if __name__ == "__main__":
    unittest.main()
