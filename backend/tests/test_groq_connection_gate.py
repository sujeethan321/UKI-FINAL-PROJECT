"""Mocked and database-free tests for the one-request GroqCloud gate."""
import asyncio
from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

MODULE = runpy.run_path(str(Path(__file__).parents[1] / "scripts/test_groq_connection.py"))
Stop = MODULE["Stop"]
SECRET = "gsk_synthetic_offline_4pQ9mT2xR8vN6cK1"


def config(**changes):
    values = dict(AI_ENABLED=True, GROQ_API_KEY=SecretStr(SECRET),
                  GROQ_BASE_URL=MODULE["BASE_URL"], GROQ_MODEL=MODULE["MODEL"],
                  GROQ_TIMEOUT_SECONDS=MODULE["TIMEOUT_SECONDS"],
                  GROQ_MAX_OUTPUT_TOKENS=MODULE["MAX_OUTPUT_TOKENS"])
    return SimpleNamespace(**(values | changes))


def request_factory():
    return SimpleNamespace(system_prompt=MODULE["SYSTEM_PROMPT"], user_prompt=MODULE["USER_PROMPT"])


@pytest.mark.parametrize("changes,diagnostic", [
    ({"AI_ENABLED": False}, "AI_DISABLED"),
    ({"GROQ_API_KEY": None}, "KEY_MISSING"),
    ({"GROQ_MODEL": "other"}, "MODEL_MISMATCH"),
    ({"GROQ_MAX_OUTPUT_TOKENS": 400}, "TOKEN_BUDGET_MISMATCH"),
])
def test_configuration_diagnostics_are_specific_and_private(changes, diagnostic):
    with pytest.raises(Stop) as error:
        MODULE["validate_config"](config(**changes))
    assert error.value.diagnostic == diagnostic
    assert SECRET not in str(error.value)


def test_standalone_loader_resolves_backend_and_sanitizes_settings(monkeypatch):
    import sys
    fake = SimpleNamespace(load_settings=lambda: config())
    monkeypatch.setitem(sys.modules, "app.core.config", fake)
    assert MODULE["load_validated_settings"]().GROQ_MODEL == MODULE["MODEL"]
    def broken():
        raise RuntimeError(SECRET)
    fake.load_settings = broken
    with pytest.raises(Stop) as error:
        MODULE["load_validated_settings"]()
    assert error.value.diagnostic == "SETTINGS_VALIDATION"
    assert SECRET not in str(error.value)


def test_default_preflight_makes_no_request():
    calls = 0
    async def executor(*_):
        nonlocal calls
        calls += 1
    message = MODULE["run"]([], lambda: config(), executor, request_factory)
    assert message.endswith("NO NETWORK REQUEST") and calls == 0


def test_wrong_or_missing_model_confirmation_stops_before_config_or_request():
    for arguments in (["--execute"], ["--execute", "--confirm-model", "wrong"],
                      ["--confirm-model", MODULE["MODEL"]]):
        calls = 0
        def loader():
            nonlocal calls
            calls += 1
            return config()
        with pytest.raises(Stop):
            MODULE["run"](arguments, loader, None, request_factory)
        assert calls == 0


def test_missing_key_and_disabled_ai_stop_without_request():
    for bad in (config(GROQ_API_KEY=None), config(AI_ENABLED=False)):
        with pytest.raises(Stop) as error:
            MODULE["run"]([], lambda bad=bad: bad, None, request_factory)
        assert error.value.category == "configuration"


def test_connection_budget_is_bounded_but_allows_reasoning_before_visible_text():
    assert MODULE["MAX_OUTPUT_TOKENS"] == 256
    assert MODULE["MAX_OUTPUT_TOKENS"] < 400


def test_execute_issues_exactly_one_request_and_discards_text():
    calls = []
    async def executor(supplied_config, request):
        calls.append((supplied_config, request))
        return SimpleNamespace(model=MODULE["MODEL"], text="சரி", finish_reason="stop")
    message = MODULE["run"](["--execute", "--confirm-model", MODULE["MODEL"]],
                            lambda: config(), executor, request_factory)
    assert message == "PASS: one sanitized GroqCloud connection request completed"
    assert len(calls) == 1
    assert calls[0][1].user_prompt == MODULE["USER_PROMPT"]
    assert "சரி" not in message and SECRET not in message


@pytest.mark.parametrize("category", sorted(MODULE["SAFE_CATEGORIES"]))
def test_failures_are_sanitized(category):
    class Failure(Exception):
        def __init__(self):
            self.category = SimpleNamespace(value=category)
            super().__init__(f"provider detail {SECRET}")
    async def executor(*_):
        raise Failure()
    with pytest.raises(Stop) as error:
        MODULE["run"](["--execute", "--confirm-model", MODULE["MODEL"]],
                      lambda: config(), executor, request_factory)
    assert error.value.category == category
    assert SECRET not in str(error.value)


def test_unexpected_failure_and_invalid_response_are_sanitized():
    async def unexpected(*_):
        raise RuntimeError(f"private {SECRET}")
    with pytest.raises(Stop) as error:
        MODULE["run"](["--execute", "--confirm-model", MODULE["MODEL"]],
                      lambda: config(), unexpected, request_factory)
    assert error.value.category == "provider_error" and SECRET not in str(error.value)

    async def invalid(*_):
        return SimpleNamespace(model="wrong", text="", finish_reason=None)
    with pytest.raises(Stop) as error:
        MODULE["run"](["--execute", "--confirm-model", MODULE["MODEL"]],
                      lambda: config(), invalid, request_factory)
    assert error.value.category == "invalid_response"


def test_source_has_no_database_or_model_imports_and_wrapper_is_inert():
    root = Path(__file__).parents[2]
    source = (root / "backend/scripts/test_groq_connection.py").read_text(encoding="utf-8")
    wrapper = (root / "backend/scripts/test_groq_connection.ps1").read_text(encoding="utf-8")
    forbidden = ("app.core.database", "sqlalchemy", "app.models", "SessionLocal", "create_engine")
    assert not any(value in source for value in forbidden)
    assert "[switch]$Execute" in wrapper and "--execute" in wrapper
    assert "GROQ_API_KEY" in wrapper and "$env:GROQ_API_KEY" not in wrapper
    assert "MYSQL_" not in wrapper
    assert "GROQ_MAX_OUTPUT_TOKENS = '256'" in wrapper
    assert MODULE["USER_PROMPT"] in source
