"""No database, real private files, or provider transport."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/scripts"))
spec = importlib.util.spec_from_file_location("owner_gate", ROOT / "backend/scripts/verify_tamil_ai_owner_credential.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def owner():
    return SimpleNamespace(user_id=123, email="synthetic@example.com", platform_role="shop_owner",
                           account_status="active", password_hash="synthetic-hash")


def test_match():
    verifier = Mock(return_value=True)
    gate.compare(owner(), 123, "synthetic@example.com", "synthetic-password", verifier)
    verifier.assert_called_once_with("synthetic-password", "synthetic-hash")


def test_mismatch_is_sanitized():
    with pytest.raises(gate.Stop, match="^credential_mismatch$"):
        gate.compare(owner(), 123, "synthetic@example.com", "private-value", Mock(return_value=False))


def test_wrong_owner_stops_before_password_check():
    verifier = Mock()
    with pytest.raises(gate.Stop, match="owner_identity"):
        gate.compare(owner(), 999, "synthetic@example.com", "secret", verifier)
    verifier.assert_not_called()


def test_default_never_reads_evidence_or_connects(monkeypatch, capsys):
    read = Mock(side_effect=AssertionError("must not read"))
    execute = Mock(side_effect=AssertionError("must not connect"))
    monkeypatch.setattr(gate, "documents", read)
    monkeypatch.setattr(gate, "execute", execute)
    gate.main(["--run-id", gate.RUN_ID])
    read.assert_not_called()
    execute.assert_not_called()
    assert "no credentials decrypted or database connected" in capsys.readouterr().out


def test_wrong_target_stops_before_evidence(monkeypatch):
    read = Mock()
    monkeypatch.setattr(gate, "documents", read)
    with pytest.raises(gate.Stop, match="confirmation"):
        gate.main(["--run-id", gate.RUN_ID, "--execute", "--confirm-target", "lankapex_test_db"])
    read.assert_not_called()


def test_missing_evidence_never_connects(monkeypatch):
    monkeypatch.setattr(gate.fixture, "load_json", Mock(side_effect=FileNotFoundError()))
    execute = Mock()
    monkeypatch.setattr(gate, "execute", execute)
    with pytest.raises(FileNotFoundError):
        gate.main(["--run-id", gate.RUN_ID, "--execute", "--confirm-target", gate.fixture.TARGET])
    execute.assert_not_called()


def test_source_guards():
    python = (ROOT / "backend/scripts/verify_tamil_ai_owner_credential.py").read_text()
    wrapper = (ROOT / "backend/scripts/verify_tamil_ai_owner_credential.ps1").read_text()
    assert "WITH CONSISTENT SNAPSHOT, READ ONLY" in python
    assert "session.rollback()" in python and "session.commit(" not in python
    assert "fixture._verify_fixture" in python and "validate_config(settings, engine.url, os.environ)" in python
    assert wrapper.index("if (-not $Execute)") < wrapper.index("ConvertTo-SecureString")
    assert "Assert-TamilAiPrivateFileAcl" in wrapper and "Set-Acl" not in wrapper
    assert "Remove-Item Env:GROQ_API_KEY" in wrapper
    assert "SetEnvironmentVariable" in wrapper and "ZeroFreeBSTR" in wrapper
    assert "uvicorn" not in wrapper and "SendKeys" not in wrapper
