"""Guarded, one-revision QR join migration for the isolated test database.

Default mode is read-only. Execution needs separate operator approval, a
maintained writer/DDL pause, and a reviewed current backup or an explicitly
approved disposable-test-data policy. No reset, retry, stamp, or downgrade.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import sys

TARGET = "lankapex_test_db"
ACCOUNT = "lankapex_qr_test_migrator@localhost"
USER = "lankapex_qr_test_migrator"
START = "6e3f2c1a9b04"
END = "7b9e4d2c8a15"
ROOT = Path(__file__).resolve().parents[2]
PRIVATE_BACKUPS = ROOT / ".server-logs" / "private-backups"
NEW_TABLES = frozenset(("business_join_links", "customer_join_requests"))
REQUIRED_PRIVILEGES = frozenset(("SELECT", "INSERT", "UPDATE", "CREATE", "ALTER", "INDEX", "REFERENCES"))
EXACT_SCOPE = r"`lankapex\_test\_db`.*"


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
    parser.add_argument("--pause-verified", action="store_true")
    parser.add_argument("--backup")
    parser.add_argument("--sha256")
    parser.add_argument("--disposable-test-data-approved", action="store_true")
    args = parser.parse_args(argv)
    require(bool(args.backup) == bool(args.sha256),
            "Backup path and checksum must be supplied together")
    if args.execute:
        require(args.confirm_target == TARGET and args.pause_verified,
                "Execution requires exact target confirmation and maintained writer/DDL pause")
        require(bool(args.backup) != args.disposable_test_data_approved,
                "Execution requires one reviewed recovery policy: current backup or explicit disposable approval")
    else:
        require(not (args.confirm_target or args.pause_verified or args.disposable_test_data_approved),
                "Execution-only flags require --execute")
    return args


def validate_environment(environ, configured_database=None, configured_user=None, engine_database=None):
    require(environ.get("APP_ENV") == "testing" and environ.get("MYSQL_DATABASE") == TARGET
            and environ.get("MYSQL_USER") == USER,
            "Exact testing environment, database, and migrator account required")
    require(environ.get("MYSQL_HOST") == "localhost" and environ.get("MYSQL_PORT") == "3306",
            "Exact local MySQL host and port required")
    if configured_database is not None:
        require(configured_database == engine_database == TARGET and configured_user == USER,
                "Effective connection target or account differs")


def validate_grants(grants):
    """Accept global USAGE and precisely the escaped test-schema grant only."""
    privileges = set()
    saw_usage = False
    for grant in grants:
        match = re.fullmatch(r"GRANT (.*?) ON (.*?) TO .*", grant, re.IGNORECASE)
        require(match is not None and "GRANT OPTION" not in grant.upper(),
                "Unreviewed grant form or grant option")
        found = set(match.group(1).upper().split(", "))
        scope = match.group(2)
        if scope == "*.*":
            require(found == {"USAGE"}, "Global privilege exceeds USAGE")
            saw_usage = True
        else:
            require(scope == EXACT_SCOPE, "Grant targets an unreviewed schema or uses wildcard underscores")
            privileges.update(found)
    require(saw_usage and privileges == REQUIRED_PRIVILEGES,
            "Migrator grant must equal the exact required test-schema privileges")


def validate_graph(graph, metadata):
    chain = list(reversed(list(graph.walk_revisions())))
    require(graph.get_bases() == ["79d8d51548c6"] and graph.get_heads() == [END]
            and len(chain) == 16 and len({item.revision for item in chain}) == 16
            and chain[-2].revision == START and chain[-1].revision == END
            and chain[-1].down_revision == START and len(metadata.tables) == 28,
            "Reviewed 16-revision graph or model inventory differs")


def validate_start(revisions, table_names, modeled_names, duplicate_count, row_counts):
    expected = (set(modeled_names) - NEW_TABLES) | {"alembic_version"}
    require(revisions == [START], "Starting Alembic revision differs")
    require(set(table_names) == expected and len(table_names) == 27,
            "Starting 26-application-table inventory differs")
    require(duplicate_count == 0, "Duplicate linked customer profiles block migration")
    require(set(row_counts) == expected - {"alembic_version"} and all(value == 0 for value in row_counts.values()),
            "Application rows exist; backup and data policy require separate review")


def validate_backup(path, sha256):
    require(isinstance(sha256, str) and re.fullmatch(r"[0-9a-fA-F]{64}", sha256) is not None,
            "Pinned backup checksum is invalid")
    backup = Path(path).resolve()
    require(backup.parent == PRIVATE_BACKUPS.resolve() and backup.suffix.lower() == ".sql"
            and backup.is_file() and backup.stat().st_size > 0,
            "Current backup must be a private SQL file outside Git")
    digest = hashlib.sha256()
    with backup.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    require(digest.hexdigest() == sha256.lower(), "Pinned backup checksum differs")
    # This is an integrity/identity gate, not a claim that restoration was tested.
    content = backup.read_bytes()
    require(START.encode() in content and content.count(b"CREATE TABLE ") == 27
            and b"customer_join_requests" not in content and b"business_join_links" not in content
            and b"CREATE DATABASE" not in content.upper() and b"\nUSE " not in content.upper(),
            "Backup content is not the current 27-table test schema")


def safe_sql(statement, execute=False):
    """Allow only exact-target reads, approved DDL, and Alembic version update."""
    # Generated migration SQL has no comments. Reject them rather than trying
    # to interpret MySQL executable comments or split hidden identifiers.
    if re.search(r"--|/\*|\*/|#", statement):
        return False
    # Permit ordinary quoted identifiers, but not quoted names whose content
    # could evade the identifier/qualifier checks below.
    for quote in ('`', '"'):
        if statement.count(quote) % 2:
            return False
        quoted = re.findall(re.escape(quote) + r"([^" + re.escape(quote) + r"]*)" + re.escape(quote), statement)
        if any(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is None for name in quoted):
            return False
        statement = statement.replace(quote, "")
    sql = re.sub(r"\s+", " ", statement.strip()).upper()
    if (not sql or ";" in sql or re.search(r"\b(?:USE|GRANT|REVOKE|TRUNCATE|DROP|SET GLOBAL)\b", sql)
            or sql.startswith(("DELETE ", "INSERT ", "REPLACE "))):
        return False
    if re.search(r"\b(?:INTO OUTFILE|INTO DUMPFILE|LOAD_FILE|FOR UPDATE|LOCK IN SHARE MODE)\b", sql):
        return False
    if not execute and re.search(r"\b(?:GET_LOCK|RELEASE_LOCK)\s*\(", sql):
        return False
    if re.search(r"\b(?:LANKAPEX_DB|LANKAPEX_DEMO_DB|LANKAPEX_MIGRATION_VERIFY_[A-Z0-9_]+)\b", sql):
        return False
    if sql.startswith("SHOW "):
        shown_schema = re.search(r"\b(?:FROM|IN)\s+([A-Z][A-Z0-9_]*)\b", sql)
        if shown_schema and shown_schema.group(1) != TARGET.upper():
            return False
    qualifier_sql = re.sub(r"@@(?:SESSION|LOCAL|GLOBAL)\.[A-Z][A-Z0-9_]*", "SYSTEM_VARIABLE", sql)
    # FROM/JOIN/UPDATE/INTO/REFERENCES identify relations: a dotted name there
    # is a schema.table reference, never a table.column reference.
    for match in re.finditer(r"\b(?:FROM|JOIN|UPDATE|INTO|REFERENCES|TABLE)\s+([A-Z_][A-Z0-9_]*)\s*\.\s*([A-Z_][A-Z0-9_]*)\b", qualifier_sql):
        if match.group(1) not in (TARGET.upper(), "INFORMATION_SCHEMA"):
            return False
    version_aliases = {"ALEMBIC_VERSION"}
    source = re.search(r"\b(?:FROM|UPDATE)\s+ALEMBIC_VERSION(?:\s+(?:AS\s+)?([A-Z_][A-Z0-9_]*))?\b", qualifier_sql)
    if source and source.group(1) not in (None, "SET", "WHERE", "ORDER", "LIMIT", "JOIN"):
        version_aliases.add(source.group(1))
    for match in re.finditer(r"\b([A-Z_][A-Z0-9_]*)\s*\.\s*([A-Z_][A-Z0-9_]*)\b", qualifier_sql):
        left, right = match.groups()
        if left in (TARGET.upper(), "INFORMATION_SCHEMA"):
            continue
        if left in version_aliases and right == "VERSION_NUM" and source is not None:
            continue
        return False
    if sql.startswith(("SELECT ", "SHOW ", "DESCRIBE ")):
        return True
    if not execute:
        return False
    return bool(
        re.match(r"^CREATE TABLE (?:BUSINESS_JOIN_LINKS|CUSTOMER_JOIN_REQUESTS)\b", sql)
        or re.match(r"^CREATE INDEX IX_CUSTOMER_JOIN_BUSINESS_STATUS_CREATED ON CUSTOMER_JOIN_REQUESTS\b", sql)
        or re.match(r"^ALTER TABLE CUSTOMER_PROFILES ADD CONSTRAINT UQ_CUSTOMER_PROFILE_BUSINESS_USER UNIQUE\b", sql)
        or re.match(r"^UPDATE ALEMBIC_VERSION SET VERSION_NUM\s*=", sql)
    )


def main(argv=None):
    args = arguments(argv)
    validate_environment(os.environ)
    if args.backup:
        validate_backup(args.backup, args.sha256)
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

    validate_environment(os.environ, settings.MYSQL_DATABASE, settings.MYSQL_USER, engine.url.database)
    require(settings.APP_ENV == "testing" and settings.MYSQL_HOST == "localhost"
            and settings.MYSQL_PORT == 3306 and engine.url.username == USER,
            "Effective test connection differs")
    cfg = Config(str(ROOT / "backend" / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "backend" / "alembic"))
    validate_graph(ScriptDirectory.from_config(cfg), Base.metadata)

    def connection_gate(dialect, record, args_, kwargs):
        require(kwargs.get("database", kwargs.get("db")) == TARGET
                and kwargs.get("user") == USER, "Non-test DBAPI connection refused")

    def engine_gate(conn):
        require(conn.engine is engine and conn.engine.url.database == TARGET,
                "Non-test SQLAlchemy engine refused")

    def statement_gate(conn, cursor, statement, parameters, context, executemany):
        require(conn.engine is engine and conn.engine.url.database == TARGET and safe_sql(statement, args.execute),
                "Unsafe or non-test SQL refused")

    event.listen(Engine, "do_connect", connection_gate)
    event.listen(Engine, "engine_connect", engine_gate)
    event.listen(Engine, "before_cursor_execute", statement_gate)
    try:
        with engine.connect() as conn:
            require(conn.scalar(text("SELECT DATABASE()")) == TARGET
                    and conn.scalar(text("SELECT CURRENT_USER()")) == ACCOUNT
                    and conn.scalar(text("SELECT CURRENT_ROLE()")) == "NONE",
                    "Actual database, account, or active role differs")
            version, mode, fk = conn.execute(text(
                "SELECT VERSION(), @@SESSION.sql_mode, @@SESSION.foreign_key_checks")).one()
            require(str(version).startswith("8.0.") and "STRICT_TRANS_TABLES" in mode and fk == 1,
                    "MySQL version, strict mode, or foreign-key checks differ")
            validate_grants(conn.execute(text("SHOW GRANTS FOR CURRENT_USER()")).scalars().all())
            inspector = inspect(conn)
            tables = inspector.get_table_names()
            require(not inspector.get_view_names(), "Unexpected test views")
            revisions = conn.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
            duplicate_count = conn.scalar(text(
                "SELECT COUNT(*) FROM (SELECT business_id, user_id FROM customer_profiles "
                "WHERE user_id IS NOT NULL GROUP BY business_id, user_id HAVING COUNT(*) > 1) AS duplicates"))
            row_counts = {name: conn.scalar(text("SELECT COUNT(*) FROM `" + name + "`"))
                          for name in tables if name != "alembic_version"}
            validate_start(revisions, tables, Base.metadata.tables, duplicate_count, row_counts)
            print("PASS: exact empty test target/account/grant, revision, duplicate audit and 16-revision graph")
            if not args.execute:
                print("READ-ONLY PREFLIGHT COMPLETE; no migration executed")
                return 0
            conn.commit()
            lock_name = "lankapex_test_db_qr_join_migration"
            require(conn.scalar(text("SELECT GET_LOCK(:name, 0)"), {"name": lock_name}) == 1,
                    "Another QR test-schema migration is active")
            try:
                # Recheck every gate under the operator-maintained pause and
                # single-run lock immediately before DDL. This cannot pause writers.
                require(conn.scalar(text("SELECT DATABASE()")) == TARGET
                        and conn.execute(text("SELECT version_num FROM alembic_version")).scalars().all() == [START],
                        "Target changed before execution")
                require(set(inspect(conn).get_table_names()) == set(tables),
                        "Table inventory changed before execution")
                require(conn.scalar(text("SELECT COUNT(*) FROM (SELECT business_id, user_id FROM customer_profiles "
                                         "WHERE user_id IS NOT NULL GROUP BY business_id, user_id HAVING COUNT(*) > 1) AS duplicates")) == 0,
                        "Duplicate profiles appeared before execution")
                for table in row_counts:
                    require(conn.scalar(text("SELECT COUNT(*) FROM `" + table + "`")) == 0,
                            "Application rows appeared before execution")
                conn.commit()
                command.upgrade(cfg, END)
                conn.commit()
                require(conn.execute(text("SELECT version_num FROM alembic_version")).scalars().all() == [END],
                        "Final revision differs; preserve partial state")
                require(set(inspect(conn).get_table_names()) == set(Base.metadata.tables) | {"alembic_version"},
                        "Final table inventory differs; preserve partial state")
                require(not compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata),
                        "Model/schema comparison differs; preserve partial state")
                for table in Base.metadata.tables:
                    require(conn.scalar(text("SELECT COUNT(*) FROM `" + table + "`")) == 0,
                            "Unexpected application rows; preserve partial state")
                print("PASS: one QR test revision applied; 28 empty application tables plus alembic_version")
            finally:
                conn.scalar(text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name})
                conn.commit()
    finally:
        event.remove(Engine, "before_cursor_execute", statement_gate)
        event.remove(Engine, "engine_connect", engine_gate)
        event.remove(Engine, "do_connect", connection_gate)
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
        print("STOP: " + type(exc).__name__ + "; preserve current test schema for review", file=sys.stderr)
        sys.exit(1)
