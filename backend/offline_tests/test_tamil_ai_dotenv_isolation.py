"""Offline process tests for the exact browser dotenv-isolation context."""
import base64
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def browser_env(**updates):
    env = os.environ.copy()
    env.update({
        "PYTHONPATH": str(ROOT / "backend"),
        "LANKAPEX_DISABLE_DOTENV": "true",
        "APP_ENV": "ai_snapshot_testing", "MYSQL_HOST": "localhost", "MYSQL_PORT": "3306",
        "MYSQL_DATABASE": "lankapex_ai_snapshot_test_db", "MYSQL_USER": "lankapex_ai_snap_runtime",
        "MYSQL_PASSWORD": "synthetic-database-password", "JWT_SECRET_KEY": "j" * 64,
        "APP_DEBUG": "false", "LOG_LEVEL": "WARNING",
        "CORS_ALLOWED_ORIGINS": "http://127.0.0.1:5175", "RATE_LIMIT_MODE": "local",
        "AI_ENABLED": "false",
    })
    env.pop("GROQ_API_KEY", None)
    env.update(updates)
    return env


def child(code, env):
    return subprocess.run([sys.executable, "-c", code], cwd=ROOT / "backend", env=env,
                          capture_output=True, text=True, check=False)


def test_exact_isolated_context_loads_without_dotenv_or_groq_key():
    result = child("from app.core.config import settings; assert settings.GROQ_API_KEY is None; assert not settings.AI_ENABLED; print('PASS')", browser_env())
    assert result.returncode == 0 and result.stdout.strip() == "PASS"


def test_dotenv_key_is_ignored_for_direct_settings_construction(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("GROQ_API_KEY=synthetic-dotenv-provider-key-never-used\n", encoding="utf-8")
    code = f"from app.core.config import Settings; s=Settings(_env_file=r'{dotenv}'); assert s.GROQ_API_KEY is None; print('PASS')"
    result = child(code, browser_env())
    assert result.returncode == 0 and result.stdout.strip() == "PASS"


def test_isolation_flag_rejected_outside_exact_environment():
    for updates in ({"APP_ENV": "development"}, {"APP_ENV": "production"},
                    {"APP_ENV": "ai_snapshot_migration"},
                    {"APP_ENV": "testing", "MYSQL_DATABASE": "lankapex_test_db"},
                    {"MYSQL_USER": "another_user"}, {"AI_ENABLED": "true"},
                    {"CORS_ALLOWED_ORIGINS": "http://127.0.0.1:5173"}):
        result = child("import app.core.config", browser_env(**updates))
        assert result.returncode != 0


def test_present_groq_variable_is_rejected_even_when_empty():
    result = child("import app.core.config", browser_env(GROQ_API_KEY=""))
    assert result.returncode != 0


def test_direct_settings_cannot_change_environment_while_isolated():
    result = child("from app.core.config import Settings; Settings(APP_ENV='development')",
                   browser_env())
    assert result.returncode != 0


def test_normal_explicit_dotenv_behavior_remains_available(tmp_path):
    # Import safely under isolation first, then remove the flag and construct
    # a separate Settings instance against a synthetic temporary dotenv file.
    dotenv = tmp_path / ".env"
    synthetic = "synthetic-provider-key-with-sufficient-entropy-123"
    dotenv.write_text(f"GROQ_API_KEY={synthetic}\n", encoding="utf-8")
    code = ("import os; from app.core.config import Settings; "
            "os.environ.pop('LANKAPEX_DISABLE_DOTENV'); "
            f"s=Settings(_env_file=r'{dotenv}'); assert s.GROQ_API_KEY.get_secret_value()==r'{synthetic}'; print('PASS')")
    result = child(code, browser_env())
    assert result.returncode == 0 and result.stdout.strip() == "PASS"


def test_windows_powershell_empty_assignment_removes_variable():
    script = ("$env:LANKAPEX_EMPTY_ENV_PROBE=''; "
              "if([Environment]::GetEnvironmentVariable('LANKAPEX_EMPTY_ENV_PROBE','Process') -eq $null){exit 0}else{exit 9}")
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-EncodedCommand", encoded],
                            capture_output=True, check=False)
    assert result.returncode == 0
