"""No credentials, filesystem mutations, database or network operations."""
import contextlib
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SPEC = importlib.util.spec_from_file_location("provision_qr", SCRIPTS / "provision_demo_qr_migrator.py")
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)
SECRET = "A" * 43 + "="  # Synthetic format only, never a real credential.
GOOD = "GRANT ALTER, CREATE, INDEX, INSERT, REFERENCES, SELECT, UPDATE ON `lankapex\\_demo\\_db`.* TO `lankapex_demo_qr_migrator`@`localhost`"


class ProvisionTests(unittest.TestCase):
    def args(self):
        return ["--execute", "--confirm-target", p.TARGET, "--confirm-account", p.ACCOUNT,
                "--confirm-account-ddl-pause", "--confirm-secure-logging", "--dba-user", "authorized_dba"]

    def run_main(self, args, connector=None, environ=None, prompt=None):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = p.main(args, connector=connector, prompt=prompt or Mock(return_value="synthetic-dba"),
                          environ={} if environ is None else environ)
        self.assertNotIn(SECRET, out.getvalue())
        return code, out.getvalue()

    def reader(self, existing=False, scope=True, extra=False):
        def read(sql, params=()):
            if sql.startswith("SELECT @@port"):
                return [(3306, "NONE", 0, "", "8.0.40")]
            if "information_schema.SCHEMATA" in sql:
                return [(int(scope),)]
            if sql.startswith("SELECT Host"):
                return [("localhost",)] if existing else []
            return [(int(extra),)]
        return read

    def connection(self):
        conn = Mock()
        cursor = Mock()
        conn.cursor.return_value.__enter__ = Mock(return_value=cursor)
        conn.cursor.return_value.__exit__ = Mock(return_value=False)
        return conn, cursor

    def test_default_no_credentials_or_connection(self):
        connector, prompt = Mock(), Mock()
        self.assertEqual(self.run_main([], connector, prompt=prompt)[0], 0)
        connector.assert_not_called()
        prompt.assert_not_called()

    def test_wrong_target_or_account(self):
        for flag in ("--confirm-target", "--confirm-account"):
            args = self.args()
            args[args.index(flag) + 1] = "wrong"
            connector, prompt = Mock(), Mock()
            self.assertEqual(self.run_main(args, connector, prompt=prompt)[0], 1)
            connector.assert_not_called()
            prompt.assert_not_called()

    def test_required_confirmations(self):
        for flag in ("--confirm-account-ddl-pause", "--confirm-secure-logging"):
            args = self.args()
            args.remove(flag)
            connector = Mock()
            self.assertEqual(self.run_main(args, connector)[0], 1)
            connector.assert_not_called()

    def test_credential_handling_failure(self):
        for env in ({}, {p.SECRET_ENV: "short"}):
            connector, prompt = Mock(), Mock()
            self.assertEqual(self.run_main(self.args(), connector, env, prompt)[0], 1)
            connector.assert_not_called()
            prompt.assert_not_called()

    def test_empty_dba_credential(self):
        connector = Mock()
        self.assertEqual(self.run_main(self.args(), connector, {p.SECRET_ENV: SECRET}, Mock(return_value=""))[0], 1)
        connector.assert_not_called()

    def test_expected_metadata(self):
        p.prepare(self.reader())

    def test_existing_account_or_wrong_schema_or_orphan_grants(self):
        for reader in (self.reader(existing=True), self.reader(scope=False), self.reader(extra=True)):
            with self.assertRaises(p.verification.Stop):
                p.prepare(reader)

    def test_metadata_unavailable_before_ddl(self):
        conn, cursor = self.connection()
        cursor.execute.side_effect = RuntimeError("synthetic-secret-error")
        with self.assertRaises(RuntimeError):
            p.provision(conn, SECRET, {"stage": "start"})
        self.assertFalse(any(call.args[0].startswith(("CREATE", "GRANT")) for call in cursor.execute.call_args_list))

    def test_exact_ddl_and_parameterized_secret(self):
        conn, cursor = self.connection()
        with patch.object(p, "prepare"), patch.object(p.verification, "verify") as verify:
            p.provision(conn, SECRET, {"stage": "start"})
        self.assertEqual(cursor.execute.call_args_list[0].args, (p.CREATE, (SECRET,)))
        self.assertEqual(cursor.execute.call_args_list[1].args, (p.GRANT,))
        self.assertNotIn(SECRET, p.CREATE)
        self.assertNotIn("IF NOT EXISTS", p.CREATE)
        self.assertIn(r"`lankapex\_demo\_db`.*", p.GRANT)
        for forbidden in ("DELETE", "DROP", "GRANT OPTION", "lankapex_demo_app", "*.*"):
            self.assertNotIn(forbidden, p.CREATE + p.GRANT)
        self.assertEqual(verify.call_args.args[1], "dba-metadata")

    def test_excessive_post_grants_rejected(self):
        with self.assertRaisesRegex(p.verification.Stop, "excessive"):
            p.verification.grants([GOOD.replace("ALTER, ", "DELETE, ALTER, ")])

    def test_partial_failure_no_retry_or_cleanup(self):
        conn, cursor = self.connection()
        cursor.execute.side_effect = [None, RuntimeError("synthetic-secret-error")]
        state = {"stage": "start"}
        with patch.object(p, "prepare"), self.assertRaises(RuntimeError):
            p.provision(conn, SECRET, state)
        self.assertEqual(cursor.execute.call_count, 2)
        self.assertEqual(state["stage"], "grant_attempted_partial_account_possible")
        self.assertFalse(any("DROP" in call.args[0] for call in cursor.execute.call_args_list))

    def test_success_both_connections_and_no_application_writes(self):
        dba, _ = self.connection()
        credential, cursor = self.connection()
        connector = Mock(side_effect=[dba, credential])
        with patch.object(p, "provision") as provision, patch.object(p.verification, "verify"):
            code, out = self.run_main(self.args(), connector, {p.SECRET_ENV: SECRET})
        self.assertEqual(code, 0)
        self.assertIn("PASS:", out)
        self.assertEqual(connector.call_count, 2)
        self.assertEqual(connector.call_args.kwargs["user"], p.USER)
        self.assertEqual(connector.call_args.kwargs["database"], p.TARGET)
        self.assertFalse(connector.call_args.kwargs["local_infile"])
        provision.assert_called_once()
        cursor.execute.assert_called_once_with("START TRANSACTION READ ONLY")
        for conn in (dba, credential):
            conn.close.assert_called_once()
            conn.commit.assert_not_called()

    def test_connection_failure_sanitized_no_retry(self):
        connector = Mock(side_effect=RuntimeError("synthetic-secret-error"))
        code, out = self.run_main(self.args(), connector, {p.SECRET_ENV: SECRET})
        self.assertEqual(code, 1)
        self.assertNotIn("synthetic-secret-error", out)
        connector.assert_called_once()

    def test_wrapper_exclusive_creation_acl_and_disposal_contract(self):
        source = (SCRIPTS / "provision_demo_qr_migrator.ps1").read_text(encoding="utf-8")
        self.assertIn("[IO.FileMode]::CreateNew", source)
        self.assertIn("$fileSecurity.SetAccessRuleProtection($true,$false)", source)
        self.assertIn("4096,[IO.FileOptions]::None,$fileSecurity)", source)
        self.assertIn("ConvertFrom-SecureString -SecureString $secure", source)
        self.assertIn("RandomNumberGenerator]::Create()", source)
        self.assertLess(source.index("Assert-DemoQrCredentialStorage -Mode Create"), source.index("$rng.GetBytes"))
        self.assertLess(source.index("Assert-DemoQrCredentialStorage -Path $credential -Mode Read"), source.index("& $python -I @arguments"))
        self.assertIn("finally {", source)
        self.assertIn("ZeroFreeBSTR", source)
        self.assertIn("$previous,'Process'", source)
        for forbidden in ("Set-Acl", "Remove-Item", "Set-Clipboard", "--password"):
            self.assertNotIn(forbidden, source)
        self.assertNotIn("-Key", next(line for line in source.splitlines()
                                      if line.strip().startswith("$cipher=ConvertFrom-SecureString")))


if __name__ == "__main__":
    unittest.main()
