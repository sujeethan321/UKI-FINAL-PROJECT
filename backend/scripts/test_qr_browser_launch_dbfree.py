"""Source-only guards; never import the application or open MySQL."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_qr_browser_config import validate_config  # noqa: E402


def valid_inputs():
    env = dict(APP_ENV="testing", MYSQL_HOST="localhost", MYSQL_PORT="3306",
               MYSQL_DATABASE="lankapex_test_db", MYSQL_USER="lankapex_qr_test_runtime",
               MYSQL_PASSWORD="synthetic-only", JWT_SECRET_KEY="synthetic-only-" * 5,
               APP_DEBUG="false", LOG_LEVEL="WARNING",
               CORS_ALLOWED_ORIGINS="http://127.0.0.1:5174", RATE_LIMIT_MODE="local")
    settings = SimpleNamespace(APP_ENV="testing", MYSQL_HOST="localhost", MYSQL_PORT=3306,
                               MYSQL_DATABASE="lankapex_test_db", MYSQL_USER="lankapex_qr_test_runtime",
                               MYSQL_PASSWORD=env["MYSQL_PASSWORD"], JWT_SECRET_KEY=env["JWT_SECRET_KEY"],
                               APP_DEBUG=False, LOG_LEVEL="WARNING",
                               CORS_ALLOWED_ORIGINS=[env["CORS_ALLOWED_ORIGINS"]], RATE_LIMIT_MODE="local")
    url = SimpleNamespace(database="lankapex_test_db", username="lankapex_qr_test_runtime",
                          host="localhost", port=3306)
    return settings, url, env


class BrowserLaunchSafety(unittest.TestCase):
    def test_exact_test_only_configuration_passes(self):
        validate_config(*valid_inputs())

    def test_wrong_configured_or_effective_database_fails(self):
        for name in ("lankapex_db", "lankapex_demo_db", "lankapex_test_db_old"):
            settings, url, env = valid_inputs()
            env["MYSQL_DATABASE"] = name
            with self.assertRaises(ValueError): validate_config(settings, url, env)
            settings, url, env = valid_inputs()
            url.database = name
            with self.assertRaises(ValueError): validate_config(settings, url, env)

    def test_account_origin_and_credentials_fail_closed(self):
        for key, value in (("MYSQL_USER", "lankapex_app"),
                           ("CORS_ALLOWED_ORIGINS", "http://0.0.0.0:5174"),
                           ("APP_ENV", "development"), ("MYSQL_PASSWORD", ""),
                           ("JWT_SECRET_KEY", "")):
            settings, url, env = valid_inputs()
            env[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_config(settings, url, env)

    def test_dotenv_fallback_cannot_replace_process_credentials(self):
        settings, url, env = valid_inputs()
        settings.MYSQL_PASSWORD = "other-credential"
        with self.assertRaises(ValueError): validate_config(settings, url, env)
        settings, url, env = valid_inputs()
        settings.JWT_SECRET_KEY = "other-secret" * 5
        with self.assertRaises(ValueError): validate_config(settings, url, env)

    def test_backend_launcher_has_private_gate_and_loopback_only(self):
        source = (ROOT / "backend/scripts/start_qr_browser_backend.ps1").read_text()
        for required in ("qr-test-runtime.dpapi", "qr-browser-jwt.dpapi", "check_qr_browser_config.py",
                         "check_qr_test_runtime.py", "--host 127.0.0.1 --port 8013",
                         "--no-access-log", "[switch]$PreflightOnly", "} finally {",
                         "ZeroFreeBSTR", "APP_ENV = 'testing'", "MYSQL_DATABASE = 'lankapex_test_db'"):
            self.assertIn(required, source)
        self.assertLess(source.index("check_qr_test_runtime.py"), source.index("-m uvicorn"))
        for forbidden in ("lankapex_demo_db", "lankapex_db'", "--host 0.0.0.0",
                          "alembic upgrade", "create_all", "-m pytest"):
            self.assertNotIn(forbidden, source)

    def test_frontend_launcher_is_test_only_and_restores_environment(self):
        source = (ROOT / "frontend/scripts/start_qr_browser_frontend.ps1").read_text()
        for required in ("http://127.0.0.1:8013/api/v1", "--host 127.0.0.1 --port 5174",
                         "--strictPort", "[switch]$PreflightOnly", "Env:VITE_*", "} finally {"):
            self.assertIn(required, source)
        for forbidden in ("start_demo_frontend", "lankapex_demo_db", "MYSQL_PASSWORD", "JWT_SECRET_KEY"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
