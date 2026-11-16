"""Exact populated-demo migration guards. No settings, DB or network at import."""
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version as package_version
import json
from pathlib import Path
import re
import subprocess

import demo_qr_preservation as preservation
import inventory_demo_database as inventory

ROOT = Path(__file__).resolve().parents[2]
TARGET = preservation.TARGET
USER = "lankapex_demo_migrator"
ACCOUNT = USER + "@localhost"
# Reviewed existing-account exception, not a new minimum privilege requirement.
# DELETE is unnecessary for this migration and remains forbidden by SQLGate.
# No other account, scope or extra privilege is accepted by this profile.
REQUIRED_MIGRATOR_RIGHTS = preservation.MINIMUM_MIGRATOR_RIGHTS | {"DELETE"}
START, END = preservation.START, preservation.END
REHEARSAL = "lankapex_demo_qr_rehearsal_20261115"
PRIVATE = ROOT / ".server-logs/private-demo-qr-migration"
MIGRATION = ROOT / "backend/alembic/versions/7b9e4d2c8a15_customer_qr_join.py"
MIGRATION_SHA = "79004cc0bf1be8650e3ecf6e9802eb53e7a39e096c8a13dd0f4465cf33e274d2"
AUDIT = ("SELECT 1 FROM customer_profiles WHERE user_id IS NOT NULL "
         "GROUP BY business_id, user_id HAVING COUNT(*) > 1 LIMIT 1")
LOCK_NAME = "lankapex_demo_db_qr_7b9e4d2c8a15"
META = dict(inventory.META)
META["tables"] = META["tables"].replace("TABLE_TYPE FROM", "TABLE_TYPE, TABLE_COLLATION FROM")
META["columns"] = META["columns"].replace(
    "ORDINAL_POSITION FROM", "ORDINAL_POSITION, COLUMN_DEFAULT, EXTRA FROM")
READS = set(META.values()) | inventory.IDENTITY | {
    AUDIT, inventory.DUPLICATES, inventory.BALANCES, inventory.LEDGER_TOTALS,
    "SELECT VERSION(), @@SESSION.sql_mode, @@SESSION.foreign_key_checks",
    "SELECT alembic_version.version_num FROM alembic_version",
    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ",
    "START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY",
    "SET SESSION lock_wait_timeout = 15",
}
INITIAL_READS = {"SELECT DATABASE()", "SELECT @@sql_mode", "SELECT @@lower_case_table_names"}
for name in ("alembic_version",):
    READS.add("DESCRIBE " + chr(96) + TARGET + chr(96) + "." + chr(96) + name + chr(96))
    READS.add("DESCRIBE " + TARGET + "." + name)


class Stop(RuntimeError):
    """Fixed categories only. Never include SQL, exception contents or values."""


def require(value, category):
    if not value:
        raise Stop(category)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(statement):
    require(not any(c in statement for c in (";", "--", "/*", "\x00")), "sql_refused")
    parts = re.split(r"('(?:''|\\.|[^'])*')", statement)
    return "".join(part if n % 2 else re.sub(r"\s+", " ", part).upper()
                   for n, part in enumerate(parts)).strip()


def validate_environment(env):
    values = {"APP_ENV": "development", "MYSQL_HOST": "localhost", "MYSQL_PORT": "3306",
              "MYSQL_DATABASE": TARGET, "MYSQL_USER": USER}
    require(all(env.get(k) == v for k, v in values.items())
            and bool(env.get("MYSQL_PASSWORD")), "configured_identity")


def validate_url(url):
    require((url.host, url.port, url.database, url.username) ==
            ("localhost", 3306, TARGET, USER), "connection_identity")


def validate_grants(rows):
    rights = set()
    for row in rows:
        if re.fullmatch(r"GRANT USAGE ON \*\.\* TO \S+", row):
            continue
        match = re.fullmatch(r"GRANT ([A-Z, ]+) ON " + chr(96) +
                            r"([^" + chr(96) + r"]+)" + chr(96) + r"\.\* TO \S+", row)
        require(match is not None, "migrator_grants")
        require(match[2] == r"lankapex\_demo\_db", "migrator_grants")
        rights.update(match[1].split(", "))
    require(rights == REQUIRED_MIGRATOR_RIGHTS, "migrator_grants")


def source_hashes():
    files = [
        MIGRATION,
        ROOT / "backend/scripts/demo_qr_migration_guard.py",
        ROOT / "backend/scripts/upgrade_populated_demo_qr.py",
        ROOT / "backend/scripts/upgrade_populated_demo_qr.ps1",
        ROOT / "backend/scripts/demo_qr_preservation.py",
        ROOT / "backend/scripts/inventory_demo_database.py",
        ROOT / "backend/scripts/check_demo_backend.py",
        ROOT / "backend/scripts/check_demo_qr_private_path.ps1",
        ROOT / "backend/scripts/demo_qr_credential_storage.ps1",
        ROOT / "backend/scripts/tamil_ai_private_acl.ps1",
        ROOT / "backend/alembic_demo_qr/env.py",
    ]
    files += sorted((ROOT / "backend/alembic/versions").glob("*.py"))
    require(sha(MIGRATION.read_bytes()) == MIGRATION_SHA, "migration_source")
    inventory.revision_chain()
    hashes = {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p.read_bytes()) for p in files}
    hashes.update({"package/" + name: sha(package_version(name).encode())
                   for name in ("SQLAlchemy", "alembic", "PyMySQL")})
    return hashes


def no_reparse(path):
    require(path.is_absolute(), "artifact_path")
    for part in (path, *path.parents):
        stat = part.lstat()
        require(not part.is_symlink() and not getattr(stat, "st_file_attributes", 0) & 0x400,
                "artifact_path")


def private_acl(path):
    result = subprocess.run([
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
        str(ROOT / "backend/scripts/check_demo_qr_private_path.ps1"), "-Path", str(path)],
        capture_output=True, text=True, timeout=30, check=False)
    require(result.returncode == 0 and result.stdout.strip() == "PASS", "artifact_acl")


def read_pinned(path, digest, prefix):
    path = Path(path)
    require(path.parent == PRIVATE and
            re.fullmatch(prefix + r"-[0-9a-f]{32}\.json", path.name) is not None,
            "artifact_path")
    no_reparse(path)
    private_acl(PRIVATE)
    private_acl(path)
    require(re.fullmatch("[0-9a-f]{64}", digest or "") is not None, "artifact_checksum")
    require(path.stat().st_size <= 16 * 1024 * 1024, "artifact_format")
    raw = path.read_bytes()
    require(len(raw) <= 16 * 1024 * 1024 and sha(raw) == digest, "artifact_checksum")
    value = json.loads(raw.decode("utf-8-sig"))
    require(isinstance(value, dict), "artifact_format")
    return value


def validate_evidence(bundle, hashes, now=None):
    baseline, backup, rehearsal, pause = (bundle[k] for k in
                                        ("baseline", "backup", "rehearsal", "pause"))
    require(baseline.get("format") == 1 and baseline.get("schema_reviewed_for_start") is True,
            "baseline_proof")
    preservation.validate(baseline["inventory"])
    require(re.fullmatch("[0-9a-f]{64}", baseline.get("full_schema_sha256", "")) is not None,
            "baseline_proof")
    require(backup.get("format") == 1 and backup.get("database") == TARGET
            and backup.get("revision") == START and backup.get("total_tables") == 27
            and backup.get("complete_schema_and_rows") is True
            and backup.get("stored_objects_reviewed") is True
            and backup.get("baseline_sha256") == bundle["baseline_sha256"]
            and type(backup.get("size_bytes")) is int and backup["size_bytes"] > 0
            and re.fullmatch("[0-9a-f]{64}", backup.get("dump_sha256", "")) is not None,
            "backup_proof")
    require(rehearsal.get("format") == 1 and rehearsal.get("database") == REHEARSAL
            and rehearsal.get("source_database") == TARGET
            and rehearsal.get("start_revision") == START and rehearsal.get("end_revision") == END
            and rehearsal.get("restore_verified") is True
            and rehearsal.get("migration_verified") is True
            and rehearsal.get("full_row_preservation_verified") is True
            and rehearsal.get("post_schema_verified") is True
            and rehearsal.get("backup_sha256") == backup["dump_sha256"]
            and rehearsal.get("baseline_sha256") == bundle["baseline_sha256"]
            and rehearsal.get("source_hashes") == hashes, "rehearsal_proof")
    require(pause.get("format") == 1 and pause.get("database") == TARGET
            and pause.get("writers_paused") is True and pause.get("ddl_paused") is True
            and pause.get("active_transactions_reviewed") is True
            and pause.get("maintained_until_signoff") is True
            and pause.get("baseline_sha256") == bundle["baseline_sha256"], "writer_pause")
    issued = datetime.fromisoformat(pause.get("verified_utc", ""))
    now = now or datetime.now(timezone.utc)
    require(issued.tzinfo is not None and 0 <= (now - issued).total_seconds() <= 600,
            "writer_pause")


def load_evidence(args):
    bundle = {}
    for kind, prefix in (("baseline", "baseline"), ("backup", "backup-proof"),
                         ("rehearsal", "rehearsal-proof"), ("pause", "pause-proof")):
        bundle[kind] = read_pinned(getattr(args, kind), getattr(args, kind + "_sha256"), prefix)
    bundle["baseline_sha256"] = args.baseline_sha256
    validate_evidence(bundle, source_hashes())
    dump = Path(bundle["backup"].get("dump_path", ""))
    require(dump.parent == PRIVATE and re.fullmatch(r"source-[0-9a-f]{32}\.sql", dump.name),
            "backup_path")
    no_reparse(dump)
    private_acl(dump)
    require(dump.stat().st_size == bundle["backup"]["size_bytes"], "backup_checksum")
    with dump.open("rb") as handle:
        require(hashlib.file_digest(handle, "sha256").hexdigest() ==
                bundle["backup"]["dump_sha256"], "backup_checksum")
    return bundle


def expected_writes():
    """Compile SQLAlchemy DDL only; never invoke a migration or connect."""
    import sqlalchemy as sa
    from sqlalchemy.dialects.mysql import pymysql
    md = sa.MetaData()
    sa.Table("businesses", md, sa.Column("business_id", sa.BigInteger(), primary_key=True))
    sa.Table("users", md, sa.Column("user_id", sa.BigInteger(), primary_key=True))
    links = sa.Table(
        "business_join_links", md,
        sa.Column("business_id", sa.BigInteger(), sa.ForeignKey(
            "businesses.business_id", name="fk_business_join_business", ondelete="RESTRICT"),
                  primary_key=True),
        sa.Column("public_code", sa.String(32, collation="utf8mb4_bin"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("public_code", name="uq_business_join_public_code"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci")
    requests = sa.Table(
        "customer_join_requests", md,
        sa.Column("request_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("business_id", sa.BigInteger(), sa.ForeignKey(
            "businesses.business_id", name="fk_customer_join_business", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("customer_user_id", sa.BigInteger(), sa.ForeignKey(
            "users.user_id", name="fk_customer_join_user", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("decided_by", sa.BigInteger(), sa.ForeignKey(
            "users.user_id", name="fk_customer_join_decider", ondelete="RESTRICT"), nullable=True),
        sa.UniqueConstraint("business_id", "customer_user_id", name="uq_customer_join_business_user"),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'cancelled')",
                           name="ck_customer_join_status"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci")
    index = sa.Index("ix_customer_join_business_status_created", requests.c.business_id,
                     requests.c.status, requests.c.created_at)
    profiles = sa.Table("customer_profiles", md, sa.Column("business_id", sa.BigInteger()),
                        sa.Column("user_id", sa.BigInteger()))
    unique = sa.UniqueConstraint(profiles.c.business_id, profiles.c.user_id,
                                 name="uq_customer_profile_business_user")
    dialect = pymysql.dialect()
    statements = [sa.schema.CreateTable(links), sa.schema.CreateTable(requests),
                  sa.schema.CreateIndex(index), sa.schema.AddConstraint(unique)]
    return [canonical(str(s.compile(dialect=dialect))) for s in statements] + [
        canonical("UPDATE alembic_version SET version_num='7b9e4d2c8a15' "
                  "WHERE alembic_version.version_num = '6e3f2c1a9b04'")]


class SQLGate:
    def __init__(self):
        self.allowed = {canonical(s) for s in READS}
        self.executing = False
        self.writes_enabled = False
        self.writes = expected_writes()
        self.position = 0
        self.ddl_started = False
        self.connection = None

    def before_cursor(self, conn, cursor, statement, params, context, many):
        require(not many, "executemany_refused")
        sql = canonical(statement)
        if self.connection is None:
            # SQLAlchemy's first-connect dialect probe uses a temporary Connection.
            # It must never be allowed application reads or DDL.
            validate_url(conn.engine.url)
            require(sql in {canonical(s) for s in INITIAL_READS} and not params,
                    "initialization_sql")
            return
        require(conn is self.connection, "unexpected_connection")
        if sql in self.allowed:
            require(not params, "unexpected_binds")
            return
        if sql in {canonical("SELECT GET_LOCK(%s,0)"), canonical("SELECT RELEASE_LOCK(%s)")}:
            require(self.executing and tuple(params) == (LOCK_NAME,), "migration_lock")
            return
        require(self.executing and self.writes_enabled and self.position < len(self.writes)
                and sql == self.writes[self.position] and not params, "unexpected_ddl")
        self.ddl_started = True  # Attempted; errors still leave DDL state uncertain.
        self.position += 1


class Reader(inventory.Reader):
    def __init__(self, conn, gate):
        super().__init__(conn)
        self.allowed = set(READS)
        self.gate = gate

    def execute(self, sql):
        require(sql in self.allowed, "sql_refused")
        self.gate.allowed.add(canonical(sql))
        return self.conn.exec_driver_sql(sql)

    def generated(self, sql):
        # Reuse the existing constrained SELECT grammar before registering SQL.
        return super().generated(sql)


def identity(reader):
    validate_url(reader.conn.engine.url)
    require(reader.scalar("SELECT DATABASE()") == TARGET
            and reader.scalar("SELECT CURRENT_USER()") == ACCOUNT
            and reader.scalar("SELECT @@port") == 3306
            and reader.scalar("SELECT CURRENT_ROLE()") == "NONE"
            and reader.scalar("SELECT @@GLOBAL.partial_revokes") == 0, "actual_identity")
    validate_grants([r[0] for r in reader.execute("SHOW GRANTS FOR CURRENT_USER()")])
    version, mode, fk = reader.execute(
        "SELECT VERSION(), @@SESSION.sql_mode, @@SESSION.foreign_key_checks").one()
    require(str(version).startswith("8.0.") and "STRICT_TRANS_TABLES" in mode and fk == 1
            and "ANSI_QUOTES" not in mode and "NO_BACKSLASH_ESCAPES" not in mode,
            "mysql_settings")


def schema_digest(data, original_only=False):
    rows = []
    for key in sorted(data):
        for row in data[key]:
            if original_only:
                if key == "checks":
                    if row[0] == "ck_customer_join_status":
                        continue
                elif row[0] in preservation.QR:
                    continue
                if key in {"keys", "constraints", "indexes"} and row[:2] == (
                        "customer_profiles", "uq_customer_profile_business_user"):
                    continue
            rows.append([key, *row])
    return inventory.fingerprint(rows)["sha256"]


def snapshot(reader, *, after=False):
    identity(reader)
    reader.conn.rollback()
    reader.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
    reader.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
    try:
        data = {key: [tuple(r) for r in reader.execute(sql)] for key, sql in META.items()}
        metadata = inventory.Metadata(data)
        names = set(metadata.get_table_names())
        require(names == preservation.ORIGINAL | {"alembic_version"} |
                (preservation.QR if after else set()), "partial_schema")
        require(all(r[1] == "InnoDB" and r[2] == "BASE TABLE" for r in data["tables"]),
                "table_engine")
        revisions = [r[0] for r in reader.execute("SELECT version_num FROM alembic_version")]
        require(revisions == [END if after else START], "revision")
        require(reader.scalar(inventory.DUPLICATES) == 0, "duplicate_profiles")
        if not after:
            require(not any(len(c["column_names"]) == 2 and
                            set(c["column_names"]) == {"business_id", "user_id"}
                            for c in metadata.get_unique_constraints("customer_profiles")),
                    "partial_schema")
            for category in ("keys", "constraints", "indexes"):
                require(not any(r[0] == "customer_profiles" and
                                r[1] == "uq_customer_profile_business_user" for r in data[category]),
                        "partial_schema")
        else:
            from check_demo_backend import validate_schema
            validate_schema(metadata, revisions, preservation.ORIGINAL | preservation.QR)
            validate_qr_columns(data)
        counts, hashes, orphans = {}, {}, {}
        for table in sorted(names - {"alembic_version"}):
            counts[table] = reader.generated(
                "SELECT COUNT(*) FROM " + inventory.ident(table)).scalar_one()
        for table, projection in inventory.PROJECTIONS.items():
            columns = projection.split()
            require(set(columns) <= {c["name"] for c in metadata.get_columns(table)},
                    "required_columns")
            keys = metadata.get_pk_constraint(table)["constrained_columns"]
            require(keys and set(keys) <= set(columns), "required_primary_key")
            hashes[table] = inventory.fingerprint(reader.generated(
                "SELECT " + ",".join(map(inventory.ident, columns)) + " FROM " +
                inventory.ident(table) + " ORDER BY " + ",".join(map(inventory.ident, keys))))
        for table in sorted(names):
            for fk in metadata.get_foreign_keys(table):
                parent, a, b = (fk["referred_table"], fk["constrained_columns"], fk["referred_columns"])
                require(fk["referred_schema"] in (None, TARGET) and parent in names
                        and a and len(a) == len(b), "foreign_key_scope")
                join = " AND ".join("c." + inventory.ident(x) + "=p." + inventory.ident(y)
                                    for x, y in zip(a, b))
                present = " AND ".join("c." + inventory.ident(x) + " IS NOT NULL" for x in a)
                sql = ("SELECT COUNT(*) FROM " + inventory.ident(table) + " c LEFT JOIN " +
                       inventory.ident(parent) + " p ON " + join + " WHERE " + present +
                       " AND p." + inventory.ident(b[0]) + " IS NULL")
                orphans[table + ":" + sha(fk["name"].encode())] = reader.generated(sql).scalar_one()
        require(all(c == 0 for c in orphans.values()), "foreign_key_orphans")
        result = {
            "database": TARGET, "account": ACCOUNT, "revision": revisions[0],
            "row_counts": counts, "preservation_fingerprints": hashes,
            "foreign_key_orphan_counts": orphans,
            "signed_account_balance_fingerprint": inventory.fingerprint(reader.execute(inventory.BALANCES)),
            "ledger_type_totals_fingerprint": inventory.fingerprint(reader.execute(inventory.LEDGER_TOTALS)),
            "full_schema_sha256": schema_digest(data),
            "original_schema_sha256": schema_digest(data, original_only=True),
        }
        require(all([tuple(r) for r in reader.execute(sql)] == data[key]
                    for key, sql in META.items()), "metadata_changed")
        return result
    finally:
        reader.conn.rollback()


def validate_qr_columns(data):
    for row in data["columns"]:
        table, name, kind, nullable, collation, ordinal, default, extra = row
        if table not in preservation.QR:
            continue
        expected_type = ("varchar(32)" if name == "public_code" else "varchar(20)"
                         if name == "status" else "datetime" if name.endswith("_at") else "bigint")
        require(kind == expected_type and nullable ==
                ("YES" if name in {"decided_at", "decided_by"} else "NO"), "qr_columns")
        if name == "public_code":
            require(collation == "utf8mb4_bin", "qr_collation")
        if name == "status":
            require(default == "pending", "qr_defaults")
        if name == "created_at":
            require(str(default).lower().replace("()", "") == "current_timestamp", "qr_defaults")
        require(("auto_increment" in extra) == (name == "request_id"), "qr_defaults")
    require(all(r[3] == "utf8mb4_unicode_ci" for r in data["tables"]
                if r[0] in preservation.QR), "qr_collation")


def compare_baseline(bundle, live):
    require(live["account"] == ACCOUNT and live["database"] == TARGET, "live_identity")
    before = bundle["baseline"]["inventory"]
    for field in ("row_counts", "preservation_fingerprints", "foreign_key_orphan_counts",
                  "signed_account_balance_fingerprint", "ledger_type_totals_fingerprint"):
        require(before[field] == live[field], "baseline_drift")
    require(live["full_schema_sha256"] == bundle["baseline"]["full_schema_sha256"],
            "predecessor_schema")


def compare_after(before, after):
    require(before["account"] == after["account"] == ACCOUNT and
            before["database"] == after["database"] == TARGET, "live_identity")
    require(before["revision"] == START and after["revision"] == END, "revision")
    require(set(after["row_counts"]) == set(before["row_counts"]) | preservation.QR
            and all(after["row_counts"][t] == 0 for t in preservation.QR)
            and all(after["row_counts"][t] == n for t, n in before["row_counts"].items()),
            "row_counts_changed")
    for field in ("preservation_fingerprints", "signed_account_balance_fingerprint",
                  "ledger_type_totals_fingerprint"):
        require(before[field] == after[field], "fingerprint_changed")
    require(set(after["foreign_key_orphan_counts"]) ==
            set(before["foreign_key_orphan_counts"]) | preservation.NEW_FK_KEYS
            and all(v == 0 for v in after["foreign_key_orphan_counts"].values()), "foreign_keys")
    require(before["full_schema_sha256"] == after["original_schema_sha256"],
            "unexpected_schema_change")


_SEAL = object()


class MigrationPermit:
    """Dedicated Alembic environment accepts only this verified connection."""
    def __init__(self, connection, gate, seal):
        require(seal is _SEAL and gate.executing and gate.writes_enabled
                and gate.connection is connection,
                "alembic_permit")
        self.connection, self.gate = connection, gate
        self.used = False

    def enter(self, config):
        require(not self.used and config.attributes.get("connection") is self.connection
                and config.get_main_option("demo_qr_target") == END, "alembic_permit")
        validate_url(self.connection.engine.url)
        reader = Reader(self.connection, self.gate)
        identity(reader)
        require([r[0] for r in reader.execute("SELECT version_num FROM alembic_version")] == [START],
                "revision")
        self.used = True
        return self.connection
