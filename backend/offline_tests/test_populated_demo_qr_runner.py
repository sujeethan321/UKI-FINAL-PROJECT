"""Fully mocked runner tests; never run Alembic upgrades or connect to MySQL."""
import copy
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/scripts"))
import demo_qr_migration_guard as g
import upgrade_populated_demo_qr as runner
from test_demo_qr_preservation import reports


def fixtures():
    old, new = reports()
    hashes = {"synthetic/source": "f" * 64}
    digest = "a" * 64
    baseline = {"format": 1, "schema_reviewed_for_start": True, "inventory": old,
                "full_schema_sha256": "1" * 64}
    backup = {"format": 1, "database": g.TARGET, "revision": g.START,
              "total_tables": 27, "complete_schema_and_rows": True,
              "stored_objects_reviewed": True, "baseline_sha256": digest,
              "size_bytes": 1, "dump_sha256": "b" * 64}
    rehearsal = {"format": 1, "database": g.REHEARSAL, "source_database": g.TARGET,
                 "start_revision": g.START, "end_revision": g.END,
                 "restore_verified": True, "migration_verified": True,
                 "full_row_preservation_verified": True, "post_schema_verified": True,
                 "backup_sha256": backup["dump_sha256"], "baseline_sha256": digest,
                 "source_hashes": hashes}
    pause = {"format": 1, "database": g.TARGET, "writers_paused": True,
             "ddl_paused": True, "active_transactions_reviewed": True,
             "maintained_until_signoff": True, "baseline_sha256": digest,
             "verified_utc": datetime.now(timezone.utc).isoformat()}
    bundle = dict(baseline=baseline, backup=backup, rehearsal=rehearsal,
                  pause=pause, baseline_sha256=digest)
    live = {}
    for key, report in (("before", old), ("after", new)):
        live[key] = {field: copy.deepcopy(report[field]) for field in
                     ("database", "revision", "row_counts", "preservation_fingerprints",
                      "foreign_key_orphan_counts", "signed_account_balance_fingerprint",
                      "ledger_type_totals_fingerprint")}
        live[key].update(account=g.ACCOUNT, full_schema_sha256=("1" if key == "before" else "2") * 64,
                         original_schema_sha256="1" * 64)
    return bundle, hashes, live


def adapter_for(live, hashes):
    adapter = Mock()
    adapter.snapshot.side_effect = lambda *, after: copy.deepcopy(live["after" if after else "before"])
    adapter.source_hashes.return_value = hashes
    return adapter


def options(execute=True):
    args = runner.parser().parse_args([])
    args.execute = execute
    args.preflight_only = not execute
    args.confirm_target = g.TARGET
    args.confirm_existing_migrator_policy = True
    args.confirm_revision = g.END if execute else None
    args.confirm_writer_ddl_pause = execute
    for name in ("baseline", "backup", "rehearsal", "pause"):
        setattr(args, name, "synthetic")
        setattr(args, name + "_sha256", "a" * 64)
    return args


class RunnerTests(unittest.TestCase):
    def test_existing_account_policy_is_exact_and_acknowledgment_is_required(self):
        self.assertEqual(g.ACCOUNT, 'lankapex_demo_migrator@localhost')
        self.assertEqual(g.REQUIRED_MIGRATOR_RIGHTS, {
            'SELECT','INSERT','UPDATE','DELETE','CREATE','REFERENCES','INDEX','ALTER'})
        args = options()
        args.confirm_existing_migrator_policy = False
        with self.assertRaisesRegex(g.Stop, '^existing_migrator_policy$'):
            runner.validate_options(args)
        args = runner.parser().parse_args(['--confirm-existing-migrator-policy'])
        with self.assertRaises(g.Stop):
            runner.validate_options(args)

    def test_other_accounts_and_schema_grants_remain_rejected(self):
        env = dict(APP_ENV='development',MYSQL_HOST='localhost',MYSQL_PORT='3306',
                   MYSQL_DATABASE=g.TARGET,MYSQL_USER=g.USER,MYSQL_PASSWORD='synthetic')
        g.validate_environment(env)
        for user in ('lankapex_demo_qr_migrator','lankapex_demo_app','root'):
            with self.subTest(user=user), self.assertRaises(g.Stop):
                g.validate_environment(dict(env,MYSQL_USER=user))
        grant = 'GRANT ' + ', '.join(sorted(g.REQUIRED_MIGRATOR_RIGHTS)) + r' ON `lankapex\_demo\_db`.* TO `lankapex_demo_migrator`@`localhost`'
        for extra in (r'GRANT SELECT ON `lankapex\_db`.* TO x',
                      'GRANT SELECT ON *.* TO x', 'GRANT role TO x',
                      grant.replace('SELECT','EXECUTE, SELECT'),
                      grant.replace('SELECT','CREATE USER, SELECT')):
            with self.subTest(extra=extra), self.assertRaises(g.Stop):
                g.validate_grants([grant,extra])

    def test_account_policy_wrapper_requires_opt_in_before_credentials(self):
        source = (ROOT/'backend/scripts/upgrade_populated_demo_qr.ps1').read_text()
        self.assertIn("$env:MYSQL_USER='lankapex_demo_migrator'",source)
        self.assertIn("'--confirm-existing-migrator-policy'",source)
        self.assertLess(source.index('-not $ConfirmExistingMigratorPolicy'),
                        source.index('ConvertTo-SecureString'))

    def test_default_is_no_operation_options(self):
        self.assertFalse(runner.validate_options(runner.parser().parse_args([])))

    def test_flags_and_missing_evidence(self):
        self.assertTrue(runner.validate_options(options()))
        for field, value in (("confirm_target", "lankapex_db"), ("confirm_revision", g.START),
                             ("confirm_writer_ddl_pause", False), ("confirm_existing_migrator_policy", False), ("backup", None),
                             ("rehearsal_sha256", None)):
            args = options()
            setattr(args, field, value)
            with self.subTest(field=field), self.assertRaises(g.Stop):
                runner.validate_options(args)

    def test_wrong_database_account_host_port_environment(self):
        env = dict(APP_ENV="development", MYSQL_HOST="localhost", MYSQL_PORT="3306",
                   MYSQL_DATABASE=g.TARGET, MYSQL_USER=g.USER, MYSQL_PASSWORD="synthetic")
        g.validate_environment(env)
        for field, value in (("MYSQL_DATABASE", "lankapex_db"), ("MYSQL_DATABASE", "lankapex_test_db"),
                             ("MYSQL_DATABASE", "lankapex_ai_snapshot_test_db"),
                             ("MYSQL_USER", "lankapex_demo_app"), ("MYSQL_HOST", "127.0.0.1"),
                             ("MYSQL_PORT", "3307"), ("APP_ENV", "testing")):
            bad = dict(env, **{field: value})
            with self.subTest(field=field, value=value), self.assertRaises(g.Stop):
                g.validate_environment(bad)
        for field in ("host", "port", "database", "username"):
            url = SimpleNamespace(host="localhost", port=3306, database=g.TARGET, username=g.USER)
            setattr(url, field, "wrong")
            with self.subTest(field=field), self.assertRaises(g.Stop):
                g.validate_url(url)

    def test_exact_migrator_grants(self):
        q = chr(96)
        scope = q + r"lankapex\_demo\_db" + q
        grant = "GRANT " + ", ".join(sorted(g.REQUIRED_MIGRATOR_RIGHTS)) + " ON " + scope + ".* TO " + q + g.USER + q + "@" + q + "localhost" + q
        g.validate_grants([grant])
        for bad in (grant.replace("REFERENCES, ", ""), grant.replace("SELECT", "DROP, SELECT"),
                    grant.replace("DELETE, ", ""),
                    grant + " WITH GRANT OPTION", grant.replace(scope, "*"),
                    grant.replace(r"\_", "_")):
            with self.subTest(grant=bad), self.assertRaises(g.Stop):
                g.validate_grants([bad])

    def test_actual_account_and_server_identity(self):
        q = chr(96)
        grant = "GRANT " + ", ".join(sorted(g.REQUIRED_MIGRATOR_RIGHTS))
        grant += " ON " + q + r"lankapex\_demo\_db" + q + ".* TO " + q + g.USER + q + "@" + q + "localhost" + q
        values = {
            "SELECT DATABASE()": g.TARGET, "SELECT CURRENT_USER()": g.ACCOUNT,
            "SELECT @@port": 3306, "SELECT CURRENT_ROLE()": "NONE",
            "SELECT @@GLOBAL.partial_revokes": 0,
        }
        reader = Mock()
        reader.conn.engine.url = SimpleNamespace(host="localhost", port=3306,
                                                 database=g.TARGET, username=g.USER)
        def execute(sql):
            if sql.startswith("SHOW GRANTS"):
                return [(grant,)]
            return SimpleNamespace(one=lambda: ("8.0.40", "STRICT_TRANS_TABLES", 1))
        reader.execute.side_effect = execute
        reader.scalar.side_effect = lambda sql: values[sql]
        g.identity(reader)
        for query, value in (("SELECT CURRENT_USER()", "lankapex_demo_app@localhost"),
                             ("SELECT CURRENT_USER()", "lankapex_demo_qr_migrator@localhost"),
                             ("SELECT DATABASE()", "lankapex_db"), ("SELECT @@port", 3307),
                             ("SELECT CURRENT_ROLE()", "unexpected_role"),
                             ("SELECT @@GLOBAL.partial_revokes", 1)):
            changed = dict(values, **{query: value})
            reader.scalar.side_effect = lambda sql: changed[sql]
            with self.subTest(query=query), self.assertRaises(g.Stop):
                g.identity(reader)

    def test_dedicated_alembic_invocation_fully_mocked(self):
        from alembic import command
        conn = Mock()
        conn.engine.url = SimpleNamespace(host="localhost", port=3306,
                                         database=g.TARGET, username=g.USER)
        conn.exec_driver_sql.return_value = [(g.START,)]
        gate = g.SQLGate()
        gate.connection = conn
        gate.executing = True
        adapter = runner.LiveAdapter(conn, gate)
        def upgrade(config, revision):
            self.assertEqual(revision, g.END)
            self.assertEqual(config.get_main_option("script_location"),
                             str(ROOT / "backend/alembic_demo_qr"))
            self.assertIs(config.attributes["connection"], conn)
            permit = config.attributes["demo_qr_permit"]
            self.assertIs(permit.enter(config), conn)
            with self.assertRaises(g.Stop):
                permit.enter(config)
            gate.position = len(gate.writes)
        with patch.object(command, "upgrade", side_effect=upgrade) as mocked, \
                patch.object(g, "identity"):
            adapter.migrate()
        mocked.assert_called_once()
        conn.commit.assert_called_once()
        self.assertFalse(gate.writes_enabled)

    def test_missing_backup_rehearsal_pause_and_mismatched_hashes(self):
        for kind, field in (("backup", "complete_schema_and_rows"),
                            ("rehearsal", "restore_verified"),
                            ("rehearsal", "migration_verified"),
                            ("rehearsal", "full_row_preservation_verified"),
                            ("rehearsal", "source_hashes"),
                            ("pause", "writers_paused"), ("pause", "maintained_until_signoff")):
            bundle, hashes, live = fixtures()
            bundle[kind].pop(field)
            adapter = adapter_for(live, hashes)
            with self.subTest(kind=kind, field=field), self.assertRaises(g.Stop):
                runner.planned_transition(options(), bundle, adapter, hashes)
            adapter.migrate.assert_not_called()
            adapter.acquire_lock.assert_not_called()

    def test_stale_or_naive_writer_pause(self):
        for stamp in ((datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat(),
                      datetime.now().isoformat(),
                      (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()):
            bundle, hashes, _ = fixtures()
            bundle["pause"]["verified_utc"] = stamp
            with self.subTest(stamp=stamp), self.assertRaises(g.Stop):
                g.validate_evidence(bundle, hashes)

    def test_wrong_revision_and_duplicates_in_baseline(self):
        for field, value in (("revision", g.END), ("duplicate_profile_pair_count", 1)):
            bundle, hashes, live = fixtures()
            bundle["baseline"]["inventory"][field] = value
            adapter = adapter_for(live, hashes)
            with self.subTest(field=field), self.assertRaises(ValueError):
                runner.planned_transition(options(), bundle, adapter, hashes)
            adapter.migrate.assert_not_called()

    def test_baseline_and_predecessor_drift(self):
        for field in ("row_counts", "preservation_fingerprints", "full_schema_sha256"):
            bundle, hashes, live = fixtures()
            if field == "full_schema_sha256":
                live["before"][field] = "9" * 64
            else:
                live["before"][field] = {}
            adapter = adapter_for(live, hashes)
            with self.subTest(field=field), self.assertRaises(g.Stop):
                runner.planned_transition(options(), bundle, adapter, hashes)
            adapter.migrate.assert_not_called()
            adapter.release_lock.assert_called_once()

    def test_successful_fully_guarded_synthetic_transition(self):
        bundle, hashes, live = fixtures()
        adapter = adapter_for(live, hashes)
        self.assertIn("PASS:", runner.planned_transition(options(), bundle, adapter, hashes))
        self.assertEqual([call[0] for call in adapter.method_calls],
                         ["acquire_lock", "snapshot", "source_hashes", "duplicate_audit",
                          "migrate", "snapshot", "release_lock"])
        adapter.migrate.assert_called_once()

    def test_read_only_preflight_no_migration(self):
        bundle, hashes, live = fixtures()
        adapter = adapter_for(live, hashes)
        self.assertIn("no DDL", runner.planned_transition(options(False), bundle, adapter, hashes))
        adapter.acquire_lock.assert_not_called()
        adapter.migrate.assert_not_called()
        adapter.duplicate_audit.assert_not_called()

    def test_post_migration_fingerprint_mismatch_keeps_failure(self):
        bundle, hashes, live = fixtures()
        live["after"]["signed_account_balance_fingerprint"]["sha256"] = "9" * 64
        adapter = adapter_for(live, hashes)
        with self.assertRaisesRegex(g.Stop, "fingerprint_changed"):
            runner.planned_transition(options(), bundle, adapter, hashes)
        adapter.migrate.assert_called_once()
        adapter.release_lock.assert_called_once()
        self.assertFalse(hasattr(adapter, "reset") and adapter.reset.called)

    def test_immediate_duplicate_audit_failure_no_ddl(self):
        bundle, hashes, live = fixtures()
        adapter = adapter_for(live, hashes)
        adapter.duplicate_audit.side_effect = g.Stop("duplicate_profiles")
        with self.assertRaises(g.Stop):
            runner.planned_transition(options(), bundle, adapter, hashes)
        adapter.migrate.assert_not_called()

    def test_partial_schema_wrong_revision_duplicate_snapshot(self):
        reader = Mock()
        for mode in ("partial_schema", "revision", "duplicate_profiles"):
            data = {key: [] for key in g.META}
            data["tables"] = [(t, "InnoDB", "BASE TABLE", "utf8mb4_unicode_ci")
                              for t in g.preservation.ORIGINAL | {"alembic_version"}]
            if mode == "partial_schema":
                data["tables"].append(("business_join_links", "InnoDB", "BASE TABLE", "utf8mb4_unicode_ci"))
            reader.execute.side_effect = lambda sql: (
                [("wrong" if mode == "revision" else g.START,)] if sql ==
                "SELECT version_num FROM alembic_version" else
                data[next(k for k, v in g.META.items() if v == sql)] if sql in g.META.values() else [])
            reader.scalar.return_value = 1
            with self.subTest(mode=mode), patch.object(g, "identity"), self.assertRaisesRegex(g.Stop, mode):
                g.snapshot(reader)

    def test_sql_gate_exact_order_no_retry_or_cross_schema(self):
        gate = g.SQLGate()
        conn = object()
        gate.connection = conn
        for sql in ("DELETE FROM users", "DROP TABLE customer_profiles",
                    "SELECT * FROM lankapex_db.users", gate.writes[0]):
            with self.subTest(sql=sql), self.assertRaises(g.Stop):
                gate.before_cursor(conn, None, sql, (), None, False)
        gate.executing = gate.writes_enabled = True
        for statement in gate.writes:
            gate.before_cursor(conn, None, statement, (), None, False)
        self.assertEqual(gate.position, 5)
        with self.assertRaises(g.Stop):
            gate.before_cursor(conn, None, gate.writes[0], (), None, False)
        with self.assertRaises(g.Stop):
            gate.before_cursor(conn, None, "SELECT DATABASE()", (), None, True)

    def test_sql_literal_changes_rejected_and_qualified_columns_accepted(self):
        gate = g.SQLGate()
        gate.connection = object()
        gate.before_cursor(gate.connection, None,
                           "SELECT alembic_version.version_num FROM alembic_version", (), None, False)
        self.assertNotEqual(g.canonical("SELECT 'pending'"), g.canonical("SELECT 'PENDING'"))
        with self.assertRaises(g.Stop):
            gate.before_cursor(gate.connection, None,
                               "SELECT alembic_version.version_num FROM lankapex_db.alembic_version",
                               (), None, False)

    def test_dialect_initialization_only_safe_probes(self):
        gate = g.SQLGate()
        conn = SimpleNamespace(engine=SimpleNamespace(url=SimpleNamespace(
            host="localhost", port=3306, database=g.TARGET, username=g.USER)))
        gate.before_cursor(conn, None, "SELECT @@sql_mode", (), None, False)
        with self.assertRaises(g.Stop):
            gate.before_cursor(conn, None, "SELECT * FROM users", (), None, False)
        self.assertIsNone(gate.connection)

    def test_no_fallback_or_generic_guard_change(self):
        source = (ROOT / "backend/alembic_demo_qr/env.py").read_text()
        for forbidden in ("create_engine", "app.core", "app.models", "engine.connect", "stamp"):
            self.assertNotIn(forbidden, source)
        self.assertIn("MigrationPermit", source)
        self.assertIn("permit.enter(config)", source)
        with self.assertRaises(g.Stop):
            g.MigrationPermit(object(), g.SQLGate(), object())

    def test_source_pinning_and_compilation_no_connections(self):
        hashes = g.source_hashes()
        self.assertEqual(hashes["backend/alembic/versions/7b9e4d2c8a15_customer_qr_join.py"],
                         g.MIGRATION_SHA)
        self.assertIn("package/SQLAlchemy", hashes)
        self.assertEqual(len(g.expected_writes()), 5)

    def test_artifact_acl_fail_closed_no_actual_powershell(self):
        with patch.object(g.subprocess, "run", return_value=SimpleNamespace(
                returncode=1, stdout="STOP")) as command:
            with self.assertRaisesRegex(g.Stop, "artifact_acl"):
                g.private_acl(Path("C:/synthetic/no-private-files"))
        self.assertIn("-NoProfile", command.call_args.args[0])

    def test_wrapper_preserves_cleanup_and_default_no_secret_read(self):
        source = (ROOT / "backend/scripts/upgrade_populated_demo_qr.ps1").read_text()
        self.assertLess(source.index("if (-not $Execute"), source.index("ConvertTo-SecureString"))
        self.assertIn("Assert-DemoQrCredentialStorage -Mode Read", source)
        self.assertLess(source.index("Assert-DemoQrCredentialStorage -Mode Read"), source.index("Get-Content -LiteralPath $credential"))
        self.assertIn("Close-DemoQrStorageLease $storageLease", source)
        self.assertIn("ZeroFreeBSTR", source)
        self.assertIn("SetEnvironmentVariable($name,$previous[$name]", source)
        self.assertIn("& $python -I @arguments", source)
        self.assertNotIn("Set-Acl", source)
        self.assertNotIn("Start-Process", source)


if __name__ == "__main__":
    unittest.main()
