"""Mocked logging metadata/transport only; no MySQL, logs, files or secrets."""
import contextlib
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / "scripts/check_demo_qr_logging_security.py"
SPEC = importlib.util.spec_from_file_location("logging_gate", SOURCE)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def snapshot(performance=True):
    values = {"general_log": "OFF", "log_output": "FILE", "slow_query_log": "OFF",
              "log_bin": "OFF", "binlog_format": "ROW", "binlog_rows_query_log_events": "OFF",
              "performance_schema": "ON" if performance else "OFF"}
    return dict(globals=list(values.items()), plugins=[("InnoDB", "ACTIVE", "STORAGE ENGINE", None)],
                components=[(0,)], consumers=[(name, "NO") for name in sorted(gate.REQUIRED_CONSUMERS)],
                instruments=[("statement/sql/create_user", "NO"), ("statement/sql/select", "NO")])


class LoggingSecurityTests(unittest.TestCase):
    def args(self):
        return ["--execute", "--confirm-target", gate.TARGET, "--dba-user", "authorized_dba",
                "--confirm-dba-account", "authorized_dba@localhost"] + [
                    "--" + name.replace("_", "-") for name in gate.ATTESTATIONS]

    def run_gate(self, args, connector, prompt=None):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = gate.main(args, connector=connector, prompt=prompt or Mock(return_value="synthetic-password-marker"))
        self.assertNotIn("synthetic-password-marker", output.getvalue())
        self.assertNotIn("synthetic-private-exception", output.getvalue())
        return code, output.getvalue()

    def connection(self, data=None):
        data = snapshot() if data is None else data
        connection, cursor = Mock(), Mock()
        connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
        connection.cursor.return_value.__exit__ = Mock(return_value=False)
        result = [None]
        rows = {gate.IDENTITY: [("authorized_dba@localhost", "authorized_dba@localhost", None,
                                 3306, "8.0.36", "NONE", "")],
                gate.SCHEMA: [(1,)], gate.GLOBALS: data["globals"], gate.PLUGINS: data["plugins"],
                gate.COMPONENTS: data["components"], gate.CONSUMERS: data.get("consumers"),
                gate.INSTRUMENTS: data.get("instruments")}

        def execute(sql):
            if sql == "START TRANSACTION READ ONLY":
                return
            self.assertIn(sql, gate.READS)
            result[0] = rows[sql]

        cursor.execute.side_effect = execute
        cursor.fetchall.side_effect = lambda: result[0]
        return connection, cursor, rows

    def test_default_no_connection_or_prompt(self):
        connector, prompt = Mock(), Mock()
        self.assertEqual(self.run_gate([], connector, prompt)[0], 0)
        connector.assert_not_called()
        prompt.assert_not_called()

    def test_wrong_host_port_or_target_no_prompt(self):
        for flag, value in (("--host", "remote.invalid"), ("--port", "3307"),
                            ("--confirm-target", "lankapex_test_db")):
            args = self.args()
            if flag in args:
                args[args.index(flag) + 1] = value
            else:
                args += [flag, value]
            connector, prompt = Mock(), Mock()
            code, output = self.run_gate(args, connector, prompt)
            self.assertEqual(code, 1)
            self.assertIn("wrong_target_or_endpoint", output)
            connector.assert_not_called()
            prompt.assert_not_called()

    def test_unexpected_dba_identity_before_prompt(self):
        args = self.args()
        args[args.index("--confirm-dba-account") + 1] = "other@localhost"
        connector = Mock()
        self.assertEqual(self.run_gate(args, connector)[0], 1)
        connector.assert_not_called()

    def test_actual_dba_identity_rejected(self):
        connection, _, rows = self.connection()
        rows[gate.IDENTITY] = [("other@localhost", "authorized_dba@localhost", None, 3306, "8.0.36", "NONE", "")]
        code, output = self.run_gate(self.args(), Mock(return_value=connection))
        self.assertEqual(code, 1)
        self.assertIn("unexpected_dba_identity", output)
        connection.close.assert_called_once()

    def test_actual_server_port_rejected(self):
        connection, _, rows = self.connection()
        rows[gate.IDENTITY] = [("authorized_dba@localhost", "authorized_dba@localhost", None, 3307, "8.0.36", "NONE", "")]
        code, output = self.run_gate(self.args(), Mock(return_value=connection))
        self.assertEqual(code, 1)
        self.assertIn("unexpected_server_identity", output)

    def test_all_operator_controls_required(self):
        for name in gate.ATTESTATIONS:
            args = self.args()
            args.remove("--" + name.replace("_", "-"))
            connector, prompt = Mock(), Mock()
            code, output = self.run_gate(args, connector, prompt)
            self.assertEqual(code, 1)
            self.assertIn("operator_controls_unverified", output)
            connector.assert_not_called()
            prompt.assert_not_called()

    def test_general_logging_enabled(self):
        data = snapshot()
        data["globals"] = [(name, "ON" if name == "general_log" else value) for name, value in data["globals"]]
        with self.assertRaisesRegex(gate.Stop, "general_logging_enabled"):
            gate.assess(data)

    def test_slow_logging_enabled(self):
        data = snapshot()
        data["globals"] = [(name, "ON" if name == "slow_query_log" else value) for name, value in data["globals"]]
        with self.assertRaisesRegex(gate.Stop, "slow_logging_enabled"):
            gate.assess(data)

    def test_log_destination_unknown(self):
        data = snapshot()
        data["globals"] = [(name, "unexpected" if name == "log_output" else value) for name, value in data["globals"]]
        with self.assertRaisesRegex(gate.Stop, "log_destination_unverified"):
            gate.assess(data)

    def test_enabled_binary_log_requires_more_evidence(self):
        data = snapshot()
        data["globals"] = [(name, "ON" if name == "log_bin" else value) for name, value in data["globals"]]
        with self.assertRaisesRegex(gate.Stop, "binary_log_handling_unverified"):
            gate.assess(data)

    def test_missing_binary_log_metadata(self):
        data = snapshot()
        data["globals"] = [row for row in data["globals"] if row[0] != "binlog_format"]
        with self.assertRaisesRegex(gate.Stop, "metadata_incomplete"):
            gate.assess(data)

    def test_unverified_audit_plugin(self):
        data = snapshot()
        data["plugins"] += [("synthetic_audit", "ACTIVE", "AUDIT", "synthetic.dll")]
        with self.assertRaisesRegex(gate.Stop, "audit_logging_unverified"):
            gate.assess(data)

    def test_unexpected_plugin_or_component(self):
        for mutate in (lambda d: d.update(plugins=[("synthetic", "ACTIVE", "DAEMON", "synthetic.dll")]),
                       lambda d: d.update(plugins=[("synthetic", "DISABLED", "STORAGE ENGINE", None)]),
                       lambda d: d.update(components=[(1,)])):
            data = snapshot()
            mutate(data)
            with self.assertRaises(gate.Stop):
                gate.assess(data)

    def test_statement_history_uncertainty(self):
        for key, value in (("consumers", []), ("consumers", None), ("instruments", [])):
            data = snapshot()
            data[key] = value
            with self.assertRaises(gate.Stop):
                gate.assess(data)

    def test_statement_collection_enabled(self):
        for key in ("consumers", "instruments"):
            data = snapshot()
            name, _ = data[key][0]
            data[key][0] = (name, "YES")
            with self.assertRaises(gate.Stop):
                gate.assess(data)

    def test_missing_metadata_privileges_sanitized(self):
        connection, cursor, _ = self.connection()
        cursor.execute.side_effect = RuntimeError(1142, "synthetic-private-exception")
        code, output = self.run_gate(self.args(), Mock(return_value=connection))
        self.assertEqual(code, 1)
        self.assertIn("metadata_or_connection_unavailable", output)

    def test_sql_tracing_rejected_before_prompt(self):
        connector, prompt = Mock(), Mock()
        with patch.object(gate.sys, "gettrace", return_value=object()):
            code, output = self.run_gate(self.args(), connector, prompt)
        self.assertEqual(code, 1)
        self.assertIn("sql_tracing_unverified", output)
        connector.assert_not_called()
        prompt.assert_not_called()

    def test_connector_debug_rejected_before_prompt(self):
        connector, prompt = Mock(), Mock()
        fake = SimpleNamespace(connections=SimpleNamespace(DEBUG=True), connect=connector)
        with patch.dict(gate.sys.modules, {"pymysql": fake}):
            code, output = self.run_gate(self.args(), None, prompt)
        self.assertEqual(code, 1)
        self.assertIn("sql_tracing_enabled", output)
        connector.assert_not_called()
        prompt.assert_not_called()

    def test_connection_error_no_retry_no_password_output(self):
        connector = Mock(side_effect=RuntimeError("synthetic-private-exception"))
        self.assertEqual(self.run_gate(self.args(), connector)[0], 1)
        connector.assert_called_once()

    def test_empty_credential_and_echoing_prompt_fail_closed(self):
        for prompt in (Mock(return_value=""), Mock(side_effect=getpass_warning)):
            connector = Mock()
            self.assertEqual(self.run_gate(self.args(), connector, prompt)[0], 1)
            connector.assert_not_called()

    def test_safe_baseline_and_fixed_read_allowlist(self):
        connection, cursor, _ = self.connection()
        connector = Mock(return_value=connection)
        code, output = self.run_gate(self.args(), connector)
        self.assertEqual(code, 0)
        self.assertIn("strict MySQL logging metadata baseline", output)
        self.assertEqual(connector.call_args.kwargs["host"], "127.0.0.1")
        self.assertEqual(connector.call_args.kwargs["port"], 3306)
        self.assertIsNone(connector.call_args.kwargs["database"])
        self.assertFalse(connector.call_args.kwargs["local_infile"])
        for call in cursor.execute.call_args_list:
            self.assertIn(call.args[0], gate.READS | {"START TRANSACTION READ ONLY"})
        connection.commit.assert_not_called()
        connection.rollback.assert_called_once()
        connection.close.assert_called_once()
        for prohibited in ("SQL_TEXT", "mysql.general_log", "mysql.slow_log", "events_statements_history "):
            self.assertFalse(any(prohibited in statement for statement in gate.READS))

    def test_disabled_performance_schema_does_not_query_history_controls(self):
        connection, cursor, _ = self.connection(snapshot(performance=False))
        self.assertEqual(self.run_gate(self.args(), Mock(return_value=connection))[0], 0)
        statements = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertNotIn(gate.CONSUMERS, statements)
        self.assertNotIn(gate.INSTRUMENTS, statements)

    def test_teardown_failure_not_pass(self):
        connection, _, _ = self.connection()
        connection.rollback.side_effect = RuntimeError("synthetic-private-exception")
        code, output = self.run_gate(self.args(), Mock(return_value=connection))
        self.assertEqual(code, 1)
        self.assertNotIn("PASS:", output)
        self.assertIn("connection_teardown_unverified", output)
        connection.close.assert_called_once()

    def test_arbitrary_argument_error_redacted(self):
        connector = Mock()
        code, output = self.run_gate(["--synthetic-private-exception"], connector)
        self.assertEqual(code, 1)
        self.assertIn("invalid_arguments", output)
        connector.assert_not_called()


def getpass_warning(*args):
    raise gate.getpass.GetPassWarning("synthetic-private-exception")


if __name__ == "__main__":
    unittest.main()
