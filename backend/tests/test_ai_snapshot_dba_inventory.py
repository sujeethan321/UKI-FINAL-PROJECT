"""Static safety checks for the Step 105 DBA metadata inventory."""
from pathlib import Path
import re


SQL_PATH = Path(__file__).parents[1] / "scripts/inventory_ai_snapshot_dba.sql"
SQL = SQL_PATH.read_text(encoding="utf-8")
UPPER = re.sub(r"--[^\n]*", "", SQL).upper()


def test_inventory_uses_only_metadata_sources_and_exact_target_literals():
    assert "INFORMATION_SCHEMA." in UPPER and "MYSQL.USER" in UPPER
    assert "lankapex_ai_snapshot_test_db" in SQL
    assert "lankapex_ai_snap_runtime" in SQL
    assert "lankapex_ai_snap_migrator" in SQL
    # Failed overlength identities remain explicit STOP evidence.
    assert "lankapex_ai_snapshot_test_runtime" in SQL
    assert "lankapex_ai_snapshot_test_migrator" in SQL
    assert "TABLE_SCHEMA = 'lankapex_ai_snapshot_test_db'" in SQL
    assert "SCHEMA_NAME = 'lankapex_ai_snapshot_test_db'" in SQL


def test_inventory_contains_no_mutation_or_secret_columns():
    forbidden = ("INSERT ", "UPDATE ", "DELETE ", "CREATE ", "ALTER ", "DROP ",
                 "TRUNCATE ", "GRANT ", "REVOKE ", "SET PASSWORD", "IDENTIFIED BY")
    assert not any(re.search(r"\b" + re.escape(word.strip()) + r"\b", UPPER) for word in forbidden)
    secret_columns = ("AUTHENTICATION_STRING", "PASSWORD_LAST_CHANGED", "PASSWORD_LIFETIME")
    assert not any(column in UPPER for column in secret_columns)


def test_inventory_fails_closed_for_visibility_and_existing_objects():
    assert "STOP_METADATA_VISIBILITY_UNPROVEN" in SQL
    assert "STOP_EXISTING_OR_SIMILAR_OBJECT_REQUIRES_REVIEW" in SQL
    assert "PASS_EXACT_TARGET_AND_ACCOUNTS_ABSENT" in SQL
    assert "SHOW GRANTS FOR CURRENT_USER()" in SQL
    assert "mysql.global_grants" in SQL and "mysql.role_edges" in SQL
    assert "User LIKE 'lankapex\\_ai\\_snap%'" in SQL


def test_inventory_never_reads_application_tables_or_protected_schemas():
    application_tables = ("ledger_entries", "credit_accounts", "customer_profiles", "users")
    protected = ("lankapex_db", "lankapex_demo_db", "lankapex_test_db")
    assert not any(name in SQL for name in application_tables)
    assert not any(name in SQL for name in protected)
