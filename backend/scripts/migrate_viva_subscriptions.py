"""PREPARED ONLY: one separately authorized, pinned viva subscription migration.

Never imported by startup. No seeding, provider calls, grants, retry or cleanup.
"""
import getpass
import importlib.util
import logging
import os
from pathlib import Path
import secrets
import ssl
import sys
import warnings

ROOT = Path(__file__).resolve().parents[2]
TARGET = "lankapex_viva_db"
MIGRATOR = "lankapex_viva_migrator"
OLD_HEAD, NEW_HEAD = "7b9e4d2c8a15", "8c0f5e3d9b26"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    require(sys.argv[1:] == ["--apply-authorized-viva-migration"], "Separate migration authorization required")
    require(sys.stdin.isatty(), "Private interactive terminal required")
    require(input("After separate authorization, type lankapex_viva_db: ") == TARGET, "Target confirmation differs")
    warnings.simplefilter("error", getpass.GetPassWarning)
    password = getpass.getpass("Existing viva migrator password: ")
    require(bool(password), "Password required")
    for key in list(os.environ):
        if key.startswith("MYSQL_") or key == "LANKAPEX_DISABLE_DOTENV":
            del os.environ[key]
    os.environ.update(APP_ENV="development", MYSQL_HOST="127.0.0.1", MYSQL_PORT="3306",
        MYSQL_DATABASE=TARGET, MYSQL_USER=MIGRATOR, MYSQL_PASSWORD=password,
        MYSQL_TLS_MODE="local_viva_required", AI_ENABLED="false", APP_DEBUG="false",
        LOG_LEVEL="WARNING", JWT_SECRET_KEY=secrets.token_urlsafe(48))
    logging.disable(logging.CRITICAL)
    sys.path.insert(0, str(ROOT / "backend"))
    os.chdir(ROOT / "backend")
    # Same isolated settings pattern as the already reviewed viva launcher.
    import app.core.config as config
    config.settings = config.load_settings(_env_file=None, MYSQL_SSL_CA=None)
    from app.core.database import engine
    from sqlalchemy import event
    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    require((engine.url.host, engine.url.port, engine.url.database, engine.url.username) ==
        ("127.0.0.1", 3306, TARGET, MIGRATOR), "Effective target differs")
    cfg = Config(str(ROOT / "backend/alembic.ini"))
    graph = ScriptDirectory.from_config(cfg)
    require(graph.get_heads() == [NEW_HEAD] and graph.get_revision(NEW_HEAD).down_revision == OLD_HEAD, "Migration graph differs")
    spec = importlib.util.spec_from_file_location("subscription_viva_guards", ROOT / "output/step322/guarded_viva_setup.py")
    guards = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guards)
    engine.pool._pre_ping = False
    connects = 0

    def socket_guard(dialect, record, args, kwargs):
        nonlocal connects
        connects += 1
        ctx = kwargs.get("ssl")
        require(connects == 1, "Reconnect/retry forbidden")
        require((kwargs.get("host"), kwargs.get("port"), kwargs.get("database"), kwargs.get("user")) ==
            ("127.0.0.1", 3306, TARGET, MIGRATOR), "DBAPI target differs")
        require(isinstance(ctx, ssl.SSLContext) and ctx.minimum_version >= ssl.TLSVersion.TLSv1_2
            and not ctx.check_hostname and ctx.verify_mode == ssl.CERT_NONE, "Required local TLS differs")

    def connection_guard(conn):
        raw = conn.connection.driver_connection
        guards.guard_migrator_connection(conn, guards.scalar(raw, "SELECT @@GLOBAL.partial_revokes"))

    event.listen(engine, "do_connect", socket_guard)
    event.listen(engine, "engine_connect", connection_guard)
    try:
        with engine.connect() as conn:
            require(conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalars().all() == [OLD_HEAD], "Starting revision differs; STOP, do not retry")
            require(conn.exec_driver_sql("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = %s AND table_type = 'BASE TABLE'", (TARGET,)).scalar_one() == 29, "Starting table count differs")
        # Normal env.py uses the same guarded engine and single pooled socket.
        command.upgrade(cfg, NEW_HEAD)
        with engine.connect() as conn:
            require(conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalars().all() == [NEW_HEAD], "Final revision differs")
            require(conn.exec_driver_sql("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = %s AND table_type = 'BASE TABLE'", (TARGET,)).scalar_one() == 32, "Final table count differs")
            require(conn.exec_driver_sql("SELECT COUNT(*) FROM subscription_trial_grants WHERE grant_status = 'GRANTED'").scalar_one() == 0, "Unexpected retroactive trial")
        print("SUBSCRIPTION_MIGRATION=PASS; TARGET=lankapex_viva_db; HEAD=" + NEW_HEAD)
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except BaseException as error:
        print("SUBSCRIPTION_MIGRATION=STOP; ERROR_CLASS=" + type(error).__name__, file=sys.stderr)
        sys.exit(1)
