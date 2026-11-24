"""Synthetic report comparisons and migration AST checks; no database or secrets."""
import ast
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "preservation", ROOT / "backend/scripts/demo_qr_preservation.py"
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def reports():
    before = {
        "database": m.TARGET, "account": m.ACCOUNT, "host": "localhost", "port": 3306,
        "revision": m.START, "application_tables": 26, "total_tables": 27,
        "tables": sorted(m.ORIGINAL | {"alembic_version"}),
        "privileges": ["DELETE", "INSERT", "SELECT", "UPDATE"],
        "global_usage_only": True, "active_roles": "NONE",
        "duplicate_profile_pair_count": 0, "database_changed": False,
        "evidence_file_created": False, "fingerprint_unavailable": [],
        "row_counts": {t: 1 for t in m.ORIGINAL},
        "preservation_fingerprints": {
            t: {"rows": 1, "sha256": "a" * 64} for t in m.PROJECTIONS
        },
        "signed_account_balance_fingerprint": {"rows": 1, "sha256": "b" * 64},
        "ledger_type_totals_fingerprint": {"rows": 1, "sha256": "c" * 64},
        "foreign_key_orphan_counts": {"customer_profiles:original": 0},
        "qr_schema_state": "absent",
        "missing_current_tables": sorted(m.QR),
        "qr_metadata": {"customer_profiles": {"required_unique_constraint_present": False}},
    }
    after = copy.deepcopy(before)
    after.update(
        revision=m.END, application_tables=28, total_tables=29,
        tables=sorted(m.ORIGINAL | m.QR | {"alembic_version"}),
        current_schema_compatible=True, qr_structure_complete=True,
        qr_schema_state="complete", missing_current_tables=[],
    )
    after["row_counts"].update({t: 0 for t in m.QR})
    after["foreign_key_orphan_counts"].update({k: 0 for k in m.NEW_FK_KEYS})
    return before, after


class PreservationTests(unittest.TestCase):
    def test_matching_reports_preserved_without_mutating_inputs(self):
        before, after = reports()
        copies = copy.deepcopy((before, after))
        result = m.compare(before, after)
        self.assertEqual((before, after), copies)
        self.assertEqual(result["existing_application_tables_preserved"], 26)
        self.assertFalse(result["full_row_preservation_proven"])

    def test_wrong_target_and_account(self):
        for field, value in (
            ("database", "lankapex_db"), ("database", "lankapex_test_db"),
            ("database", "lankapex_ai_snapshot_test_db"),
            ("database", "lankapex_demo_qr_rehearsal_20261115"),
            ("account", "root@localhost"), ("host", "127.0.0.1"), ("port", 3307),
        ):
            before, after = reports()
            before[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(m.PreservationStop):
                m.compare(before, after)

    def test_wrong_revision_partial_start_and_duplicate_profiles(self):
        for field, value in (
            ("revision", m.END), ("total_tables", 29),
            ("qr_schema_state", "partial_or_mismatched"),
            ("duplicate_profile_pair_count", 1),
            ("fingerprint_unavailable", ["ledger_entries"]),
        ):
            before, after = reports()
            before[field] = value
            with self.subTest(field=field), self.assertRaises(m.PreservationStop):
                m.compare(before, after)

    def test_all_existing_counts_must_match(self):
        for table in m.ORIGINAL:
            before, after = reports()
            # Tables without projected fingerprints still must retain row counts.
            after["row_counts"][table] += 1
            with self.subTest(table=table), self.assertRaises(m.PreservationStop):
                m.compare(before, after)

    def test_all_projected_fingerprints_must_match(self):
        for table in m.PROJECTIONS:
            before, after = reports()
            after["preservation_fingerprints"][table]["sha256"] = "d" * 64
            with self.subTest(table=table), self.assertRaisesRegex(
                m.PreservationStop, "^preservation_fingerprint_changed$"
            ):
                m.compare(before, after)

    def test_balances_and_ledger_totals_must_match(self):
        for field in ("signed_account_balance_fingerprint", "ledger_type_totals_fingerprint"):
            before, after = reports()
            after[field]["sha256"] = "e" * 64
            with self.subTest(field=field), self.assertRaises(m.PreservationStop):
                m.compare(before, after)

    def test_qr_tables_empty_and_schema_complete(self):
        for field in ("current_schema_compatible", "qr_structure_complete"):
            before, after = reports()
            after[field] = False
            with self.subTest(field=field), self.assertRaises(m.PreservationStop):
                m.compare(before, after)
        before, after = reports()
        after["row_counts"]["customer_join_requests"] = 1
        with self.assertRaisesRegex(m.PreservationStop, "^new_qr_rows$"):
            m.compare(before, after)

    def test_only_expected_foreign_keys_added_and_zero_orphans(self):
        for mode in ("missing", "extra", "orphan"):
            before, after = reports()
            if mode == "missing":
                after["foreign_key_orphan_counts"].pop(next(iter(m.NEW_FK_KEYS)))
            elif mode == "extra":
                after["foreign_key_orphan_counts"]["unreviewed"] = 0
            else:
                after["foreign_key_orphan_counts"][next(iter(m.NEW_FK_KEYS))] = 1
            with self.subTest(mode=mode), self.assertRaises(m.PreservationStop):
                m.compare(before, after)

    def test_malformed_hashes_and_privileges(self):
        before, after = reports()
        after["preservation_fingerprints"]["ledger_entries"]["sha256"] = "not-a-hash"
        with self.assertRaises(m.PreservationStop):
            m.compare(before, after)
        before, after = reports()
        after["privileges"].append("ALTER")
        with self.assertRaises(m.PreservationStop):
            m.compare(before, after)

    def test_migration_ast_only_one_reviewed_revision(self):
        path = ROOT / "backend/alembic/versions/7b9e4d2c8a15_customer_qr_join.py"
        tree = ast.parse(path.read_text())
        constants = {
            node.targets[0].id: ast.literal_eval(node.value)
            for node in tree.body if isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
        }
        self.assertEqual(constants["revision"], m.END)
        self.assertEqual(constants["down_revision"], m.START)
        upgrade = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "upgrade")
        calls = [
            n for n in ast.walk(upgrade) if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name) and n.func.value.id == "op"
        ]
        self.assertEqual(
            sorted(n.func.attr for n in calls),
            ["create_index", "create_table", "create_table", "create_unique_constraint", "get_bind"],
        )
        tables = {ast.literal_eval(n.args[0]) for n in calls if n.func.attr == "create_table"}
        self.assertEqual(tables, m.QR)
        unique = next(n for n in calls if n.func.attr == "create_unique_constraint")
        self.assertEqual([ast.literal_eval(n) for n in unique.args],
                         ["uq_customer_profile_business_user", "customer_profiles", ["business_id", "user_id"]])
        audit = next(n for n in ast.walk(upgrade) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Attribute) and n.func.attr == "text")
        sql = ast.literal_eval(audit.args[0])
        self.assertTrue(sql.startswith("SELECT 1 FROM customer_profiles"))
        self.assertIn("WHERE user_id IS NOT NULL", sql)
        self.assertIn("HAVING COUNT(*) > 1", sql)
        self.assertLess(audit.lineno, min(n.lineno for n in calls if n.func.attr.startswith("create_")))
        downgrade = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "downgrade")
        self.assertTrue(any(isinstance(n, ast.Raise) for n in downgrade.body))

    def test_minimum_rights_and_account_lengths(self):
        self.assertEqual(m.MINIMUM_MIGRATOR_RIGHTS,
                         {"SELECT", "INSERT", "UPDATE", "CREATE", "ALTER", "INDEX", "REFERENCES"})
        for username in ("lankapex_demo_migrator", "lankapex_demo_qr_migrator",
                         "lankapex_demo_qr_rehearse"):
            self.assertLessEqual(len(username), 32)
        self.assertNotIn("DELETE", m.MINIMUM_MIGRATOR_RIGHTS)
        self.assertNotIn("DROP", m.MINIMUM_MIGRATOR_RIGHTS)

    def test_no_connections_file_access_or_application_imports(self):
        tree = ast.parse((ROOT / "backend/scripts/demo_qr_preservation.py").read_text())
        imports = {
            n.names[0].name for n in ast.walk(tree) if isinstance(n, ast.Import)
        }
        self.assertEqual(imports, {"hashlib", "re"})
        self.assertFalse(any(isinstance(n, ast.ImportFrom) for n in ast.walk(tree)))
        self.assertFalse(any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "open"
            for n in ast.walk(tree)
        ))


if __name__ == "__main__":
    unittest.main()
