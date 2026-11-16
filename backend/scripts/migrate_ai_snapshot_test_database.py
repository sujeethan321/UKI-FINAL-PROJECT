"""Exact-target, empty-schema migration gate for AI snapshot integration tests.

Default mode is read-only. Execution is a separate, explicit operation. A
failure preserves partial MySQL DDL state for operator review; this tool never
retries, stamps, downgrades, resets, truncates, drops, or cleans a schema.
"""
import argparse
import os
from pathlib import Path
import re
import sys

TARGET = "lankapex_ai_snapshot_test_db"
USER = "lankapex_ai_snap_migrator"
ACCOUNT = USER + "@localhost"
ENVIRONMENT = "ai_snapshot_migration"
HEAD = "7b9e4d2c8a15"
BASE = "79d8d51548c6"
SCOPE = r"`lankapex\_ai\_snapshot\_test\_db`.*"
PRIVILEGES = {"SELECT", "INSERT", "UPDATE", "CREATE", "ALTER", "INDEX", "REFERENCES"}
PROTECTED = {
    "lankapex_db", "lankapex_demo_db", "lankapex_test_db",
    "lankapex_demo_restore_verify_20261109", "lankapex_demo_restore_verify_20261110b",
}
ROOT = Path(__file__).resolve().parents[2]


class Stop(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise Stop(message)


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, choices=[TARGET])
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-target")
    parser.add_argument("--confirm-empty", action="store_true")
    parser.add_argument("--pause-verified", action="store_true")
    args = parser.parse_args(argv)
    if args.execute:
        require(args.confirm_target == TARGET and args.confirm_empty and args.pause_verified,
                "Execution requires exact target, empty-schema, and writer/DDL-pause confirmation")
    else:
        require(not (args.confirm_target or args.confirm_empty or args.pause_verified),
                "Execution-only confirmations require --execute")
    return args


def validate_environment(environ, configured_database=None, configured_user=None,
                         engine_database=None, engine_user=None):
    expected = (ENVIRONMENT, "localhost", "3306", TARGET, USER)
    actual = tuple(environ.get(name) for name in
                   ("APP_ENV", "MYSQL_HOST", "MYSQL_PORT", "MYSQL_DATABASE", "MYSQL_USER"))
    require(actual == expected, "Exact AI snapshot migration process configuration required")
    if configured_database is not None:
        require((configured_database, configured_user, engine_database, engine_user)
                == (TARGET, USER, TARGET, USER), "Effective migration connection differs")


def validate_grants(grants):
    found, usage = set(), False
    for grant in grants:
        match = re.fullmatch(r"GRANT (.*?) ON (.*?) TO .*", grant, re.IGNORECASE)
        require(match is not None and "GRANT OPTION" not in grant.upper(), "Unreviewed grant form")
        privileges = {item.strip().upper() for item in match.group(1).split(",")}
        if match.group(2) == "*.*":
            require(privileges == {"USAGE"}, "Global privilege exceeds USAGE")
            usage = True
        else:
            require(match.group(2) == SCOPE, "Grant is broad, wildcarded, or targets another schema")
            found.update(privileges)
    require(usage and found == PRIVILEGES, "Migrator privileges differ from the reviewed minimum")


def validate_graph(graph, modeled_tables):
    chain = list(reversed(list(graph.walk_revisions())))
    require(graph.get_bases() == [BASE] and graph.get_heads() == [HEAD]
            and len(chain) == 16 and len({revision.revision for revision in chain}) == 16
            and chain[0].revision == BASE and chain[-1].revision == HEAD
            and len(modeled_tables) == 28, "Reviewed 16-revision graph or model inventory differs")


def validate_empty_state(tables, views, routines=0, events=0, triggers=0):
    require(not tables and not views and routines == events == triggers == 0,
            "Target is not completely empty; repeated execution and overwrite are refused")


def _strip_identifiers(statement):
    for quote in ('`', '"'):
        if statement.count(quote) % 2:
            return None
        names = re.findall(re.escape(quote) + r"([^" + re.escape(quote) + r"]*)" + re.escape(quote), statement)
        if any(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is None for name in names):
            return None
        statement = statement.replace(quote, "")
    return statement


def safe_sql(statement, execute=False):
    """Classify SQL without confusing table-qualified columns for schemas."""
    if re.search(r"--|/\*|\*/|#", statement):
        return False
    statement = _strip_identifiers(statement)
    if statement is None:
        return False
    sql = re.sub(r"\s+", " ", statement.strip()).upper()
    if not sql or ";" in sql or re.search(
            r"\b(?:USE|GRANT|REVOKE|TRUNCATE|DROP\s+(?:DATABASE|SCHEMA|TABLE|INDEX)|RENAME\s+TABLE|SET\s+GLOBAL)\b", sql):
        return False
    if sql.startswith(("DELETE ", "REPLACE ")) or re.search(
            r"\b(?:INTO OUTFILE|INTO DUMPFILE|LOAD_FILE)\b", sql):
        return False
    if any(name.upper() in sql for name in PROTECTED):
        return False
    # A dotted relation after these keywords is a schema-qualified reference.
    relation = r"\b(?:FROM|JOIN|UPDATE|INTO|REFERENCES|TABLE)\s+([A-Z_][A-Z0-9_]*)\s*\."
    for match in re.finditer(relation, sql):
        if match.group(1) not in {TARGET.upper(), "INFORMATION_SCHEMA"}:
            return False
    if sql.startswith(("SELECT ", "SHOW ", "DESCRIBE ")):
        return True
    if not execute:
        return False
    if re.match(r"^CREATE (?:UNIQUE )?(?:TABLE|INDEX)\b", sql):
        return " DATABASE " not in " " + sql
    if re.match(r"^ALTER TABLE [A-Z_][A-Z0-9_]*\b", sql):
        return not re.search(r"\b(?:DROP\s+TABLE|RENAME\s+TO)\b", sql)
    if re.match(r"^INSERT INTO ALEMBIC_VERSION\b", sql):
        return True
    if re.match(r"^UPDATE ALEMBIC_VERSION SET VERSION_NUM\b", sql):
        return True
    return False


def main(argv=None):
    args = arguments(argv)
    validate_environment(os.environ)
    sys.path.insert(0, str(ROOT / "backend"))
    from alembic import command
    from alembic.autogenerate import compare_metadata
    from alembic.config import Config
    from alembic.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from sqlalchemy import event, inspect, text
    from sqlalchemy.engine import Engine
    from app.core.config import settings
    from app.core.database import Base, engine
    import app.models  # noqa: F401

    validate_environment(os.environ, settings.MYSQL_DATABASE, settings.MYSQL_USER,
                         engine.url.database, engine.url.username)
    cfg = Config(str(ROOT / "backend" / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "backend" / "alembic"))
    validate_graph(ScriptDirectory.from_config(cfg), Base.metadata.tables)

    def connect_gate(dialect, record, args_, kwargs):
        require(kwargs.get("database", kwargs.get("db")) == TARGET and kwargs.get("user") == USER,
                "Non-target DBAPI connection refused")

    def statement_gate(conn, cursor, statement, parameters, context, executemany):
        require(conn.engine is engine and conn.engine.url.database == TARGET
                and safe_sql(statement, args.execute), "Unsafe or cross-schema SQL refused")

    event.listen(Engine, "do_connect", connect_gate)
    event.listen(Engine, "before_cursor_execute", statement_gate)
    try:
        with engine.connect() as connection:
            require(connection.scalar(text("SELECT DATABASE()")) == TARGET
                    and connection.scalar(text("SELECT CURRENT_USER()")) == ACCOUNT
                    and connection.scalar(text("SELECT CURRENT_ROLE()")) == "NONE",
                    "Actual database, account, or active role differs")
            version, sql_mode, foreign_keys = connection.execute(text(
                "SELECT VERSION(), @@SESSION.sql_mode, @@SESSION.foreign_key_checks")).one()
            require(str(version).startswith("8.0.") and "STRICT_TRANS_TABLES" in sql_mode and foreign_keys == 1,
                    "MySQL prerequisites differ")
            validate_grants(connection.execute(text("SHOW GRANTS FOR CURRENT_USER()"))
                            .scalars().all())
            inspector = inspect(connection)
            routine_count = connection.scalar(text("SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=DATABASE()"))
            event_count = connection.scalar(text("SELECT COUNT(*) FROM information_schema.EVENTS WHERE EVENT_SCHEMA=DATABASE()"))
            trigger_count = connection.scalar(text("SELECT COUNT(*) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=DATABASE()"))
            validate_empty_state(inspector.get_table_names(), inspector.get_view_names(),
                                 routine_count, event_count, trigger_count)
            print("PASS: exact empty AI snapshot target/migrator/grant and 16-revision graph")
            if not args.execute:
                print("READ-ONLY PREFLIGHT COMPLETE; no migration executed")
                return 0
            connection.commit()
            lock_name = "lankapex_ai_snapshot_test_db_migration"
            require(connection.scalar(text("SELECT GET_LOCK(:name, 0)"), {"name": lock_name}) == 1,
                    "Another migration gate is active")
            try:
                validate_empty_state(inspect(connection).get_table_names(), inspect(connection).get_view_names())
                connection.commit()
                cfg.attributes["connection"] = connection
                command.upgrade(cfg, HEAD)
                connection.commit()
                tables = set(inspect(connection).get_table_names())
                require(tables == set(Base.metadata.tables) | {"alembic_version"} and len(tables) == 29,
                        "Final table inventory differs; preserve partial state")
                require(connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD,
                        "Final revision differs; preserve partial state")
                require(not compare_metadata(MigrationContext.configure(connection, opts={"compare_type": True}), Base.metadata),
                        "Model/schema comparison differs; preserve partial state")
                for table in Base.metadata.tables:
                    require(connection.scalar(text(f"SELECT COUNT(*) FROM `{table}`")) == 0,
                            "Unexpected application records; preserve partial state")
                print("PASS: 16 revisions applied; 28 empty application tables plus alembic_version")
            finally:
                connection.scalar(text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name})
                connection.commit()
    finally:
        event.remove(Engine, "before_cursor_execute", statement_gate)
        event.remove(Engine, "do_connect", connect_gate)
        engine.dispose()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (Stop, SystemExit) as exc:
        if isinstance(exc, SystemExit):
            raise
        print("STOP: " + str(exc), file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print("STOP: " + type(exc).__name__ + "; preserve target state and evidence", file=sys.stderr)
        sys.exit(1)
