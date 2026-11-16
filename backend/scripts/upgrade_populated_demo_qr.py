"""One exact populated-demo QR upgrade; default mode performs no live operation."""
import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import demo_qr_migration_guard as guard


def validate_options(args):
    require = guard.require
    require(not (args.execute and args.preflight_only), "flags")
    if not (args.execute or args.preflight_only):
        require(not any(getattr(args, n) for n in (
            "confirm_target", "confirm_revision", "confirm_writer_ddl_pause",
            "baseline", "backup", "rehearsal", "pause", "baseline_sha256",
            "backup_sha256", "rehearsal_sha256", "pause_sha256",
            "confirm_existing_migrator_policy")), "flags")
        return False
    require(args.confirm_target == guard.TARGET, "confirmation")
    require(args.confirm_existing_migrator_policy, "existing_migrator_policy")
    if args.execute:
        require(args.confirm_revision == guard.END and args.confirm_writer_ddl_pause,
                "confirmation")
    for kind in ("baseline", "backup", "rehearsal", "pause"):
        require(getattr(args, kind) and getattr(args, kind + "_sha256"), "required_evidence")
    return True


def planned_transition(args, bundle, adapter, hashes):
    """Orchestrator also tested with a fully synthetic adapter, never Alembic."""
    guard.validate_evidence(bundle, hashes)
    locked = False
    try:
        if args.execute:
            adapter.acquire_lock()
            locked = True
        before = adapter.snapshot(after=False)
        guard.compare_baseline(bundle, before)
        if not args.execute:
            return "PASS: populated-demo QR read-only preflight; no DDL executed"
        guard.require(adapter.source_hashes() == hashes, "source_changed")
        guard.validate_evidence(bundle, hashes)  # Fresh pause proof before DDL.
        adapter.duplicate_audit()
        adapter.migrate()
        after = adapter.snapshot(after=True)
        guard.compare_after(before, after)
        return ("PASS: one populated-demo QR revision applied and guarded preservation checks passed; "
                "keep writers paused pending independent runtime verification")
    finally:
        if locked:
            adapter.release_lock()


class LiveAdapter:
    def __init__(self, conn, gate):
        self.conn, self.gate = conn, gate
        self.reader = guard.Reader(conn, gate)

    def snapshot(self, *, after):
        return guard.snapshot(self.reader, after=after)

    def source_hashes(self):
        return guard.source_hashes()

    def acquire_lock(self):
        guard.identity(self.reader)
        self.gate.executing = True
        guard.require(self.conn.exec_driver_sql("SELECT GET_LOCK(%s,0)",
                      (guard.LOCK_NAME,)).scalar_one() == 1, "migration_lock")
        self.conn.rollback()

    def release_lock(self):
        guard.require(self.conn.exec_driver_sql("SELECT RELEASE_LOCK(%s)",
                      (guard.LOCK_NAME,)).scalar_one() == 1, "migration_lock_release")
        self.conn.rollback()

    def duplicate_audit(self):
        guard.identity(self.reader)
        guard.require(self.reader.execute(guard.AUDIT).first() is None, "duplicate_profiles")
        self.conn.rollback()

    def migrate(self):
        from alembic import command
        from alembic.config import Config
        cfg = Config()
        cfg.set_main_option("script_location", str(guard.ROOT / "backend/alembic_demo_qr"))
        cfg.set_main_option("version_locations", str(guard.ROOT / "backend/alembic/versions"))
        cfg.set_main_option("demo_qr_target", guard.END)
        self.reader.execute("SET SESSION lock_wait_timeout = 15")
        self.conn.rollback()
        self.gate.writes_enabled = True
        try:
            cfg.attributes["connection"] = self.conn
            cfg.attributes["demo_qr_permit"] = guard.MigrationPermit(
                self.conn, self.gate, guard._SEAL)
            command.upgrade(cfg, guard.END)
            guard.require(self.gate.position == len(self.gate.writes), "migration_sequence")
            self.conn.commit()  # Only after guarded exact DDL/version UPDATE.
        finally:
            self.gate.writes_enabled = False


def run(args, env):
    guard.validate_environment(env)
    bundle = guard.load_evidence(args)
    hashes = guard.source_hashes()
    from sqlalchemy import create_engine, event
    from sqlalchemy.engine import URL
    gate = guard.SQLGate()
    engine = create_engine(URL.create(
        "mysql+pymysql", host="localhost", port=3306, database=guard.TARGET,
        username=guard.USER, password=env["MYSQL_PASSWORD"]),
        echo=False, hide_parameters=True, pool_pre_ping=False,
        connect_args={"connect_timeout": 5, "read_timeout": 120, "write_timeout": 30})

    def connecting(dialect, record, args_, kwargs):
        guard.require(kwargs.get("host") == "localhost" and kwargs.get("port") == 3306
                      and kwargs.get("database", kwargs.get("db")) == guard.TARGET
                      and kwargs.get("user") == guard.USER, "dbapi_identity")

    event.listen(engine, "do_connect", connecting)
    event.listen(engine, "before_cursor_execute", gate.before_cursor)
    try:
        with engine.connect() as conn:
            guard.validate_url(engine.url)
            gate.connection = conn
            try:
                return planned_transition(args, bundle, LiveAdapter(conn, gate), hashes)
            except guard.Stop as exc:
                exc.ddl_attempted = gate.ddl_started
                raise
            except Exception:
                # SQLAlchemy cleanup may roll back an uncommitted version UPDATE;
                # this cannot undo MySQL DDL. Never infer the schema from this.
                error = guard.Stop("ddl_state_uncertain_keep_pause" if gate.ddl_started
                                   else "live_gate_failed")
                error.ddl_attempted = gate.ddl_started
                raise error from None
    finally:
        event.remove(engine, "before_cursor_execute", gate.before_cursor)
        event.remove(engine, "do_connect", connecting)
        engine.dispose()


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--execute", action="store_true")
    p.add_argument("--preflight-only", action="store_true")
    p.add_argument("--confirm-target")
    p.add_argument("--confirm-revision")
    p.add_argument("--confirm-writer-ddl-pause", action="store_true")
    p.add_argument("--confirm-existing-migrator-policy", action="store_true",
                   help="Acknowledge the exact existing demo migrator grants, including unused DELETE")
    for kind in ("baseline", "backup", "rehearsal", "pause"):
        p.add_argument("--" + kind)
        p.add_argument("--" + kind + "-sha256")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if not validate_options(args):
            print("PASS: offline populated-demo QR preparation only; no evidence, credentials or database accessed")
            return 0
        print(run(args, os.environ))
        return 0
    except Exception as exc:
        categories = {
            "flags", "confirmation", "required_evidence", "configured_identity", "existing_migrator_policy",
            "baseline_proof", "backup_proof", "rehearsal_proof", "writer_pause",
            "artifact_path", "artifact_checksum", "artifact_format", "artifact_acl", "backup_path",
            "backup_checksum", "migration_source", "ddl_state_uncertain_keep_pause",
            "live_gate_failed",
            "actual_identity", "connection_identity", "dbapi_identity", "migrator_grants",
            "mysql_settings", "revision", "partial_schema", "duplicate_profiles",
            "baseline_drift", "predecessor_schema", "migration_lock", "migration_lock_release",
            "source_changed", "unexpected_ddl", "unexpected_connection", "unexpected_binds",
            "executemany_refused", "initialization_sql", "migration_sequence", "alembic_permit",
            "fingerprint_changed", "row_counts_changed", "foreign_keys", "foreign_key_orphans",
            "metadata_changed", "unexpected_schema_change", "qr_columns", "qr_defaults",
            "qr_collation", "required_columns", "required_primary_key", "foreign_key_scope",
        }
        label = str(exc) if isinstance(exc, guard.Stop) and str(exc) in categories else "preparation_or_evidence_failed"
        print("STOP: populated-demo QR category=" + label +
              " ddl_attempted=" + str(bool(getattr(exc, "ddl_attempted", False))).lower() +
              "; preserve evidence; no automatic retry; maintain writer/DDL pause")
        return 1


if __name__ == "__main__":
    sys.exit(main())
