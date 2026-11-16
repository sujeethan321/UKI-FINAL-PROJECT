"""Database-free tests for the dedicated live-test gate and launcher."""
from pathlib import Path
import runpy

import pytest

MODULE = runpy.run_path(str(Path(__file__).parents[1] / "scripts/check_ai_snapshot_test_runtime.py"))


def valid():
    tables = set(MODULE["EXPECTED_TABLES"])
    return dict(environment="ai_snapshot_testing", configured_db=MODULE["TARGET"],
                configured_user=MODULE["USER"], engine_db=MODULE["TARGET"],
                engine_user=MODULE["USER"], actual_db=MODULE["TARGET"],
                actual_user=MODULE["USER"] + "@localhost", revision=MODULE["REVISION"],
                tables=tables,
                grants=[f"GRANT USAGE ON *.* TO `{MODULE['USER']}`@`localhost`",
                        "GRANT SELECT, INSERT, UPDATE, DELETE ON " + MODULE["SCOPE"] +
                        f" TO `{MODULE['USER']}`@`localhost`"],
                row_counts={name: 0 for name in tables if name != "alembic_version"})


def test_exact_empty_target_and_dml_only_grant_pass():
    MODULE["validate_runtime"](**valid())


@pytest.mark.parametrize("change", [
    {"actual_db": "lankapex_test_db"}, {"configured_db": "lankapex_db"},
    {"revision": "wrong"}, {"actual_user": "other@localhost"},
])
def test_wrong_identity_or_schema_fails_closed(change):
    evidence = valid() | change
    with pytest.raises(ValueError):
        MODULE["validate_runtime"](**evidence)


def test_unexpected_or_missing_table_fails_even_when_count_remains_29():
    evidence = valid()
    evidence["tables"].remove("ledger_entries")
    evidence["tables"].add("unexpected_table")
    evidence["row_counts"].pop("ledger_entries")
    evidence["row_counts"]["unexpected_table"] = 0
    with pytest.raises(ValueError):
        MODULE["validate_runtime"](**evidence)


def test_nonempty_schema_and_excess_or_cross_database_grants_fail_closed():
    evidence = valid(); evidence["row_counts"]["users"] = 1
    with pytest.raises(ValueError): MODULE["validate_runtime"](**evidence)
    evidence = valid(); evidence["grants"].append("GRANT SELECT ON `lankapex_db`.* TO `x`@`localhost`")
    with pytest.raises(ValueError): MODULE["validate_runtime"](**evidence)
    evidence = valid(); evidence["grants"][1] = evidence["grants"][1].replace("DELETE", "DELETE, CREATE")
    with pytest.raises(ValueError): MODULE["validate_runtime"](**evidence)


def test_launcher_is_inert_by_default_and_clears_ai_configuration():
    script = (Path(__file__).parents[1] / "scripts/run_ai_snapshot_integration_tests.ps1").read_text()
    assert "[switch]$Execute" in script
    assert "READ-ONLY PREFLIGHT COMPLETE" in script
    assert "$env:AI_ENABLED = 'false'" in script and "$env:GROQ_API_KEY = ''" in script
    assert "lankapex_ai_snapshot_test_db" in script
    assert "lankapex_test_db" not in script
    assert "check_ai_snapshot_test_runtime.py" in script
    assert "$postflightExit" in script
    assert "post-test empty-schema verification failed" in script


def test_endpoint_integration_suite_is_included_without_network_transport():
    integration = (Path(__file__).parents[1] / "ai_snapshot_integration" /
                   "test_shop_owner_ai_summary_api_mysql.py").read_text()
    assert "TestClient" in integration
    assert "TamilCreditSummaryService(ProviderFailure())" in integration
    assert "GroqAIClient" not in integration
    assert "httpx" not in integration
    assert "fixture_fingerprint" in integration
    assert "db.commit" not in integration and "db.rollback" not in integration
