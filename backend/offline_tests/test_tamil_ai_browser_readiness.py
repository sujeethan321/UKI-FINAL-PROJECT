"""Database-free safety checks for Step 127 operator tooling."""
import runpy
from pathlib import Path
from types import SimpleNamespace
ROOT = Path(__file__).resolve().parents[2]
CONFIG = runpy.run_path(str(ROOT / "backend/scripts/check_tamil_ai_browser_config.py"))
FIXTURE = runpy.run_path(str(ROOT / "backend/scripts/tamil_ai_browser_fixture.py"))


def valid_environment():
    return {
        "APP_ENV": "ai_snapshot_testing", "MYSQL_HOST": "localhost", "MYSQL_PORT": "3306",
        "MYSQL_DATABASE": "lankapex_ai_snapshot_test_db", "MYSQL_USER": "lankapex_ai_snap_runtime",
        "MYSQL_PASSWORD": "synthetic-password", "JWT_SECRET_KEY": "j" * 48,
        "APP_DEBUG": "false", "LOG_LEVEL": "WARNING", "CORS_ALLOWED_ORIGINS": "http://127.0.0.1:5175",
        "RATE_LIMIT_MODE": "local", "AI_ENABLED": "false", "LANKAPEX_DISABLE_DOTENV": "true",
    }


def valid_settings(env):
    return SimpleNamespace(APP_ENV="ai_snapshot_testing", MYSQL_DATABASE="lankapex_ai_snapshot_test_db",
        MYSQL_USER="lankapex_ai_snap_runtime", MYSQL_HOST="localhost", MYSQL_PORT=3306,
        MYSQL_PASSWORD=env["MYSQL_PASSWORD"], JWT_SECRET_KEY=env["JWT_SECRET_KEY"], APP_DEBUG=False,
        LOG_LEVEL="WARNING", CORS_ALLOWED_ORIGINS=["http://127.0.0.1:5175"], RATE_LIMIT_MODE="local",
        AI_ENABLED=False, GROQ_API_KEY=None)


def test_exact_loopback_process_config_is_accepted():
    env = valid_environment()
    engine = SimpleNamespace(database="lankapex_ai_snapshot_test_db", username="lankapex_ai_snap_runtime", host="localhost", port=3306)
    CONFIG["validate_config"](valid_settings(env), engine, env)


def test_config_rejects_ai_key_wrong_target_and_nonloopback():
    engine = SimpleNamespace(database="lankapex_ai_snapshot_test_db", username="lankapex_ai_snap_runtime", host="localhost", port=3306)
    for key, value in (("AI_ENABLED", "true"), ("GROQ_API_KEY", "secret"), ("LANKAPEX_DISABLE_DOTENV", "false"), ("MYSQL_DATABASE", "lankapex_demo_db"),
                       ("CORS_ALLOWED_ORIGINS", "http://0.0.0.0:5175")):
        env = valid_environment(); env[key] = value
        try:
            CONFIG["validate_config"](valid_settings(valid_environment()), engine, env)
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe {key} accepted")


def test_config_rejects_effective_groq_key_when_process_key_is_absent():
    env = valid_environment()
    settings = valid_settings(env)
    settings.GROQ_API_KEY = object()
    engine = SimpleNamespace(database="lankapex_ai_snapshot_test_db",
                             username="lankapex_ai_snap_runtime", host="localhost", port=3306)
    try:
        CONFIG["validate_config"](settings, engine, env)
    except ValueError:
        pass
    else:
        raise AssertionError("effective Groq credential accepted")


def test_reservation_is_deterministic_and_contains_no_secrets():
    run_id = "a" * 32
    document = FIXTURE["reservation_document"](run_id)
    assert document == FIXTURE["reservation_document"](run_id)
    assert document["database"] == "lankapex_ai_snapshot_test_db"
    assert document["expected_amounts"] == {"sale": "100.20", "repayment": "30.10", "outstanding": "70.10"}
    assert not ({"password", "token", "jwt", "api_key"} & set(document))


def test_invalid_run_ids_and_modified_reservations_stop():
    for value in ("", "A" * 32, "a" * 31, "../unsafe", "g" * 32):
        try: FIXTURE["require_run_id"](value)
        except ValueError: pass
        else: raise AssertionError("invalid run ID accepted")
    changed = FIXTURE["reservation_document"]("b" * 32); changed["business_name"] = "changed"
    try: FIXTURE["validate_reservation"](changed)
    except ValueError: pass
    else: raise AssertionError("modified reservation accepted")


def test_fingerprint_is_exact_id_and_amount_bound():
    ids = dict(zip(("owner_user_id","customer_user_id","business_id","membership_id","customer_id","credit_account_id","sale_entry_id","repayment_entry_id"), range(1, 9)))
    first = FIXTURE["fixture_fingerprint"](ids, "c" * 32)
    ids["sale_entry_id"] = 99
    assert first != FIXTURE["fixture_fingerprint"](ids, "c" * 32)
    assert FIXTURE["inventory_fingerprint"]({"users": 0, "ledger_entries": 0}) != FIXTURE["inventory_fingerprint"]({"users": 1, "ledger_entries": 0})


def test_expected_inventory_rejects_missing_tables_and_marks_only_fixture_rows():
    tables = {"alembic_version", *FIXTURE["FIXTURE_COUNTS"], "orders", "notifications"}
    counts = FIXTURE["expected_counts"](tables)
    assert counts["orders"] == counts["notifications"] == 0
    assert counts["ledger_entries"] == 2 and counts["users"] == 2
    try: FIXTURE["expected_counts"]({"alembic_version", "users"})
    except ValueError: pass
    else: raise AssertionError("incomplete schema accepted")


def test_launchers_are_loopback_fail_closed_and_ai_disabled():
    backend = (ROOT / "backend/scripts/start_tamil_ai_browser_backend.ps1").read_text()
    frontend = (ROOT / "frontend/scripts/start_tamil_ai_browser_frontend.ps1").read_text()
    manager = (ROOT / "backend/scripts/manage_tamil_ai_browser_fixture.ps1").read_text()
    assert "127.0.0.1 --port 8014" in backend and "verify --run-id $RunId" in backend
    assert "tamil-ai-browser-jwt.dpapi" in backend and "$env:AI_ENABLED='false'" in backend
    assert "$env:LANKAPEX_DISABLE_DOTENV='true'" in backend and "Remove-Item Env:GROQ_API_KEY" in backend
    assert "$env:GROQ_API_KEY=''" not in backend and "--no-access-log" in backend
    assert "http://127.0.0.1:8014/api/v1" in frontend and "--host 127.0.0.1" in frontend
    assert "[switch]$Execute" in manager and "ConfirmWriterPause" in manager and "ConfirmEmpty" in manager
    assert "Assert-TamilAiPrivateFileAcl" in manager and "Set-Acl" not in manager
    for text in (backend, frontend, manager):
        assert "lankapex_demo_db" not in text and "lankapex_db'" not in text


def test_backend_fixture_verification_passes_complete_exact_argument_vector():
    backend = (ROOT / "backend/scripts/start_tamil_ai_browser_backend.ps1").read_text()
    invocation = next(line.strip() for line in backend.splitlines()
                      if "tamil_ai_browser_fixture.py') verify" in line)
    expected = ("verify --run-id $RunId --reservation $reservation "
                "--evidence $evidence")
    assert invocation.endswith(expected)

    run_id = "d" * 32
    parsed = FIXTURE["parser"]().parse_args([
        "verify", "--run-id", run_id,
        "--reservation", "synthetic-reservation.json",
        "--evidence", "synthetic-evidence.json",
    ])
    assert parsed.command == "verify"
    assert parsed.run_id == run_id
    assert parsed.reservation == "synthetic-reservation.json"
    assert parsed.evidence == "synthetic-evidence.json"


def test_fixture_source_has_no_broad_or_destructive_database_operations():
    source = (ROOT / "backend/scripts/tamil_ai_browser_fixture.py").read_text().upper()
    assert "TRUNCATE " not in source and "DROP DATABASE" not in source and "DELETE FROM" not in source
    assert "DELETE(MODEL).WHERE(KEY.IN_(PRIMARY_KEYS))" in source
    assert source.index("LEDGERENTRY, [IDS[") < source.index("CREDITACCOUNT, [IDS[") < source.index("CUSTOMERPROFILE, [IDS[")


def test_powershell_defaults_are_preflight_only():
    manager = (ROOT / "backend/scripts/manage_tamil_ai_browser_fixture.ps1").read_text()
    assert "[string]$Mode='Preflight'" in manager
    assert "READ-ONLY TAMIL AI FIXTURE PREFLIGHT COMPLETE" in manager
    assert "never retry automatically" in manager


def test_acl_helper_is_dacl_only_and_fail_closed():
    helper = (ROOT / "backend/scripts/tamil_ai_private_acl.ps1").read_text()
    repair = (ROOT / "backend/scripts/repair_tamil_ai_browser_evidence_acl.ps1").read_text()
    manager = (ROOT / "backend/scripts/manage_tamil_ai_browser_fixture.ps1").read_text()
    assert "icacls.exe" in helper and "'/inheritance:r'" in helper and "'/grant:r'" in helper
    assert "*S-1-5-18:(F)" in helper and "Set-Acl" not in helper and "FileSecurity" not in helper
    assert "Assert-TamilAiIcaclsExitCode $LASTEXITCODE" in helper and "unexpected explicit principal" in helper
    assert "if(-not $Execute)" in repair and "Set-TamilAiPrivateFileDaclOnly" in repair
    assert manager.index("} finally {") < manager.index("SetEnvironmentVariable", manager.index("} finally {"))
    assert "Set-TamilAiPrivateFileDaclOnly" not in manager[manager.index("if($Mode -in @('Verify','CleanupReview'))"):manager.index("if(-not $Execute", manager.index("if($Mode -in @('Verify','CleanupReview'))"))]
    assert "while(" not in helper.lower() and "retry" not in helper.lower()


def test_acl_tools_do_not_reference_database_or_external_ai():
    combined = "\n".join((ROOT / path).read_text() for path in (
        "backend/scripts/tamil_ai_private_acl.ps1",
        "backend/scripts/repair_tamil_ai_browser_evidence_acl.ps1",
    )).lower()
    assert "mysql" not in combined and "groq" not in combined and "http://" not in combined and "https://" not in combined
