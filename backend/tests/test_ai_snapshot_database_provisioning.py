"""Database-free tests for the AI snapshot schema migration gate."""
from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).parents[2]
GATE = runpy.run_path(str(ROOT / "backend/scripts/migrate_ai_snapshot_test_database.py"))
Stop = GATE["Stop"]


def environment(**changes):
    values = dict(APP_ENV=GATE["ENVIRONMENT"], MYSQL_HOST="localhost", MYSQL_PORT="3306",
                  MYSQL_DATABASE=GATE["TARGET"], MYSQL_USER=GATE["USER"])
    values.update(changes)
    return values


def grants():
    privileges = ", ".join(sorted(GATE["PRIVILEGES"]))
    return [f"GRANT USAGE ON *.* TO `{GATE['USER']}`@`localhost`",
            f"GRANT {privileges} ON {GATE['SCOPE']} TO `{GATE['USER']}`@`localhost`"]


def test_exact_environment_and_protected_targets_fail_closed():
    assert len(GATE["USER"]) <= 32
    GATE["validate_environment"](environment(), GATE["TARGET"], GATE["USER"],
                                 GATE["TARGET"], GATE["USER"])
    for change in ({"MYSQL_DATABASE": "lankapex_db"}, {"MYSQL_DATABASE": "lankapex_demo_db"},
                   {"MYSQL_DATABASE": "lankapex_test_db"}, {"APP_ENV": "testing"},
                   {"MYSQL_USER": "lankapex_ai_snap_runtime"}):
        with pytest.raises(Stop):
            GATE["validate_environment"](environment(**change))


def test_migrator_grant_is_exact_escaped_and_without_drop():
    GATE["validate_grants"](grants())
    assert "DROP" not in GATE["PRIVILEGES"]
    for change in (lambda value: value.replace(GATE["SCOPE"], "`lankapex_ai_snapshot_test_db`.*"),
                   lambda value: value.replace("REFERENCES", "REFERENCES, DROP"),
                   lambda value: value.replace(GATE["SCOPE"], "`lankapex_db`.*")):
        bad = grants(); bad[1] = change(bad[1])
        with pytest.raises(Stop):
            GATE["validate_grants"](bad)


def test_empty_schema_and_repeated_execution_are_refused():
    GATE["validate_empty_state"]([], [])
    for values in ((["alembic_version"], []), ([], ["view"]), ([], [], 1, 0, 0)):
        with pytest.raises(Stop):
            GATE["validate_empty_state"](*values)


def test_graph_is_pinned_to_exact_sixteen_revision_head():
    chain = [SimpleNamespace(revision=GATE["BASE"])]
    chain.extend(SimpleNamespace(revision=f"r{index}") for index in range(1, 15))
    chain.append(SimpleNamespace(revision=GATE["HEAD"]))
    graph = SimpleNamespace(get_bases=lambda: [GATE["BASE"]], get_heads=lambda: [GATE["HEAD"]],
                            walk_revisions=lambda: iter(reversed(chain)))
    GATE["validate_graph"](graph, {str(index): None for index in range(28)})
    bad = SimpleNamespace(get_bases=graph.get_bases, get_heads=lambda: ["wrong"],
                          walk_revisions=graph.walk_revisions)
    with pytest.raises(Stop):
        GATE["validate_graph"](bad, {str(index): None for index in range(28)})


def test_execution_needs_all_confirmations_and_cannot_repeat_silently():
    GATE["arguments"](["--database", GATE["TARGET"]])
    for args in (["--execute"], ["--execute", "--confirm-target", GATE["TARGET"]],
                 ["--confirm-target", GATE["TARGET"]],
                 ["--execute", "--confirm-target", "lankapex_db", "--confirm-empty", "--pause-verified"]):
        with pytest.raises((Stop, SystemExit)):
            GATE["arguments"](["--database", GATE["TARGET"], *args])
    GATE["arguments"](["--database", GATE["TARGET"], "--execute", "--confirm-target",
                       GATE["TARGET"], "--confirm-empty", "--pause-verified"])


def test_sql_gate_allows_migration_shapes_and_rejects_cleanup_and_cross_schema():
    allowed = ("SELECT DATABASE()", "SHOW GRANTS FOR CURRENT_USER()",
               "CREATE TABLE users (user_id BIGINT)", "CREATE INDEX ix_users_email ON users (email)",
               "ALTER TABLE notifications DROP CHECK ck_notification_type, ADD CONSTRAINT ck CHECK (1=1)",
               "INSERT INTO alembic_version (version_num) VALUES (%s)",
               "UPDATE alembic_version SET version_num=%s WHERE alembic_version.version_num=%s")
    assert all(GATE["safe_sql"](sql, execute=True) for sql in allowed)
    refused = ("DROP DATABASE lankapex_ai_snapshot_test_db", "DROP TABLE users", "TRUNCATE TABLE users",
               "DELETE FROM users", "CREATE DATABASE x", "USE lankapex_db",
               "SELECT * FROM lankapex_db.users", "UPDATE ledger_entries SET amount=0",
               "ALTER TABLE users RENAME TO stolen", "CREATE TABLE unrelated.users (id INT)")
    assert not any(GATE["safe_sql"](sql, execute=True) for sql in refused)
    assert not GATE["safe_sql"]("CREATE TABLE users (id INT)", execute=False)


def test_wrapper_is_inert_by_default_and_uses_distinct_dpapi_files():
    wrapper = (ROOT / "backend/scripts/migrate_ai_snapshot_test_database.ps1").read_text()
    runtime = (ROOT / "backend/scripts/run_ai_snapshot_integration_tests.ps1").read_text()
    assert "[switch]$Execute" in wrapper and "--execute" in wrapper
    assert "ai-snapshot-test-migrator.dpapi" in wrapper
    assert "ai-snapshot-test-runtime.dpapi" in runtime
    assert "AI_ENABLED = 'false'" in wrapper and "GROQ_API_KEY = ''" in wrapper
    assert "DROP DATABASE" not in wrapper.upper() and "alembic downgrade" not in wrapper.lower()
    assert "lankapex_ai_snap_migrator" in wrapper
    assert "lankapex_ai_snap_runtime" in runtime
    assert "lankapex_ai_snapshot_test_migrator" not in wrapper
    assert "lankapex_ai_snapshot_test_runtime" not in runtime
