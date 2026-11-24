"""Synthetic metadata only. No database, secrets, or application imports."""
import contextlib
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import Mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/verify_demo_qr_migrator.py"
SPEC = importlib.util.spec_from_file_location("account_verifier", SCRIPT)
v = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v)
RECIPIENT = "`lankapex_demo_qr_migrator`@`localhost`"
GOOD = "GRANT ALTER, CREATE, INDEX, INSERT, REFERENCES, SELECT, UPDATE ON `lankapex\\_demo\\_db`.* TO " + RECIPIENT


class VerificationTests(unittest.TestCase):
    def rejected(self, rows, category):
        with self.assertRaisesRegex(v.Stop, category):
            v.grants(rows)

    def test_exact_grants(self):
        v.grants(["GRANT USAGE ON *.* TO " + RECIPIENT, GOOD])

    def test_insufficient(self):
        self.rejected([GOOD.replace("ALTER, ", "")], "insufficient")

    def test_excessive(self):
        self.rejected([GOOD.replace("ALTER, ", "DELETE, ALTER, ")], "excessive")

    def test_wrong_scope_and_unescaped_scope(self):
        for scope in ("lankapex_demo_db", "other"):
            self.rejected([GOOD.replace(r"lankapex\_demo\_db", scope)], "wrong_database_scope")

    def test_grant_option(self):
        self.rejected([GOOD + " WITH GRANT OPTION"], "excessive")

    def test_roles_global_table_and_wrong_recipient(self):
        for row in ("GRANT `role`@`%` TO " + RECIPIENT,
                    "GRANT SELECT ON *.* TO " + RECIPIENT,
                    "GRANT SELECT ON `lankapex_demo_db`.`users` TO " + RECIPIENT,
                    GOOD.replace("qr_migrator", "app")):
            self.rejected([row], "unexpected_effective_privileges")

    def reader(self, accounts=None, identity=None, roles="NONE", extra=0):
        def read(sql, params=()):
            if sql.startswith("SELECT @@port"):
                return [(3306, roles, 0, "", "8.0.40")]
            if sql.startswith("SELECT Host"):
                return [("localhost", "N")] if accounts is None else accounts
            if sql.startswith("SELECT DATABASE"):
                return [identity or (v.TARGET, v.ACCOUNT, v.ACCOUNT)]
            if "information_schema.SCHEMATA" in sql:
                return [(1,)]
            if sql.startswith("SELECT COUNT"):
                return [(extra,)]
            if sql.startswith("SHOW GRANTS"):
                return [(GOOD,)]
            self.fail("unexpected statement")
        return read

    def test_dba_metadata(self):
        v.verify(self.reader(), "dba-metadata")

    def test_missing_account(self):
        with self.assertRaisesRegex(v.Stop, "account_missing"):
            v.verify(self.reader(accounts=[]), "dba-metadata")

    def test_conflicting_hosts(self):
        with self.assertRaisesRegex(v.Stop, "conflicting_account"):
            v.verify(self.reader(accounts=[("%", "N")]), "dba-metadata")

    def test_roles_and_effective_privileges(self):
        for reader in (self.reader(roles="role"), self.reader(extra=1)):
            with self.assertRaises(v.Stop):
                v.verify(reader, "dba-metadata")

    def test_credential_identity(self):
        v.verify(self.reader(), "credential")
        for identity in (("wrong", v.ACCOUNT, v.ACCOUNT), (v.TARGET, "wrong", v.ACCOUNT)):
            with self.assertRaises(v.Stop):
                v.verify(self.reader(identity=identity), "credential")

    def run_gate(self, argv, connector, prompt):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = v.main(argv, connector=connector, prompt=prompt)
        return code, output.getvalue()

    def test_default_no_credentials_or_connection(self):
        connector, prompt = Mock(), Mock()
        self.assertEqual(self.run_gate([], connector, prompt)[0], 0)
        connector.assert_not_called()
        prompt.assert_not_called()

    def test_wrong_target_no_credentials(self):
        connector, prompt = Mock(), Mock()
        self.assertEqual(self.run_gate(["--execute", "--confirm-target", "other"], connector, prompt)[0], 1)
        prompt.assert_not_called()
        connector.assert_not_called()

    def test_missing_credential(self):
        connector = Mock()
        code, output = self.run_gate(["--execute", "--confirm-target", v.TARGET, "--mode", "credential"], connector, lambda _: "")
        self.assertEqual(code, 1)
        self.assertIn("credential_unavailable", output)
        connector.assert_not_called()

    def test_sanitized_metadata_and_auth_errors_no_retry(self):
        for error, category in ((RuntimeError("secret-synthetic"), "metadata_or_connection_unavailable"),
                                (RuntimeError(1045, "secret-synthetic"), "authentication_rejected_existence_unknown")):
            connector = Mock(side_effect=error)
            code, output = self.run_gate(["--execute", "--confirm-target", v.TARGET, "--mode", "credential"], connector, lambda _: "secret-synthetic")
            self.assertEqual(code, 1)
            self.assertIn(category, output)
            self.assertNotIn("secret-synthetic", output)
            connector.assert_called_once()

    def test_read_only_connection_and_rollback_no_commit(self):
        connection, cursor = Mock(), Mock()
        connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
        connection.cursor.return_value.__exit__ = Mock(return_value=False)
        reader = self.reader()
        latest = [None]

        def execute(sql, params=()):
            latest[0] = [] if sql == "START TRANSACTION READ ONLY" else reader(sql, params)

        cursor.execute.side_effect = execute
        cursor.fetchall.side_effect = lambda: latest[0]
        connector = Mock(return_value=connection)
        code, output = self.run_gate(["--execute", "--confirm-target", v.TARGET, "--mode", "credential"], connector, lambda _: "synthetic-only")
        self.assertEqual(code, 0)
        self.assertIn("PASS:", output)
        self.assertEqual(cursor.execute.call_args_list[0].args, ("START TRANSACTION READ ONLY",))
        self.assertEqual(connector.call_args.kwargs["database"], v.TARGET)
        self.assertEqual(connector.call_args.kwargs["host"], "localhost")
        self.assertFalse(connector.call_args.kwargs["local_infile"])
        connection.commit.assert_not_called()
        connection.rollback.assert_called_once()
        connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
