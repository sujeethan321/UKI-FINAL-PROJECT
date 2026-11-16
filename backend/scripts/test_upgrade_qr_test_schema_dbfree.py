"""Synthetic safety tests; importing the runner never connects to MySQL."""
import tempfile
import unittest
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import upgrade_qr_test_schema as runner


class TestGuardedQRMigration(unittest.TestCase):
    def test_exact_target_and_environment(self):
        good = dict(APP_ENV="testing", MYSQL_DATABASE=runner.TARGET,
                    MYSQL_USER=runner.USER, MYSQL_HOST="localhost", MYSQL_PORT="3306")
        runner.validate_environment(good, runner.TARGET, runner.USER, runner.TARGET)
        for change in (dict(MYSQL_DATABASE="lankapex_db"), dict(MYSQL_DATABASE="lankapex_demo_db"),
                       dict(MYSQL_DATABASE="lankapex_migration_verify_20261107"),
                       dict(APP_ENV="production"), dict(MYSQL_USER="lankapex_app")):
            with self.subTest(change=change), self.assertRaises(runner.Stop):
                runner.validate_environment(good | change)
        with self.assertRaises(runner.Stop):
            runner.validate_environment(good, runner.TARGET, runner.USER, "lankapex_db")

    def test_grants_are_exact_and_escaped(self):
        usage = "GRANT USAGE ON *.* TO `lankapex_qr_test_migrator`@`localhost`"
        good = "GRANT SELECT, INSERT, UPDATE, CREATE, ALTER, INDEX, REFERENCES ON " + runner.EXACT_SCOPE + " TO `lankapex_qr_test_migrator`@`localhost`"
        runner.validate_grants([usage, good])
        for bad in (
            good.replace(runner.EXACT_SCOPE, "`lankapex_test_db`.*"),
            good.replace("SELECT, ", ""),
            good.replace("REFERENCES", "REFERENCES, DROP"),
            good.replace(runner.EXACT_SCOPE, "`lankapex_db`.*"),
            good + " WITH GRANT OPTION",
        ):
            with self.subTest(bad=bad), self.assertRaises(runner.Stop):
                runner.validate_grants([usage, bad])
        with self.assertRaises(runner.Stop):
            runner.validate_grants(["GRANT SELECT ON *.* TO `x`@`localhost`", good])

    def test_start_revision_inventory_duplicates_and_rows(self):
        names = {"alembic_version"} | {f"table_{index}" for index in range(26)}
        modeled = (names - {"alembic_version"}) | runner.NEW_TABLES
        counts = {name: 0 for name in names - {"alembic_version"}}
        runner.validate_start([runner.START], names, modeled, 0, counts)
        for revisions, duplicates, rows in ((["03b9c2d1e671"], 0, counts),
                                            ([runner.START], 1, counts),
                                            ([runner.START], 0, counts | {"table_0": 1})):
            with self.assertRaises(runner.Stop):
                runner.validate_start(revisions, names, modeled, duplicates, rows)

    def test_graph_requires_one_new_head(self):
        chain = [SimpleNamespace(revision=f"r{i}", down_revision=None) for i in range(14)]
        chain += [SimpleNamespace(revision=runner.START, down_revision="r13"),
                  SimpleNamespace(revision=runner.END, down_revision=runner.START)]
        graph = SimpleNamespace(get_bases=lambda: ["79d8d51548c6"],
                                get_heads=lambda: [runner.END],
                                walk_revisions=lambda: iter(reversed(chain)))
        metadata = SimpleNamespace(tables={str(i): None for i in range(28)})
        runner.validate_graph(graph, metadata)
        with self.assertRaises(runner.Stop):
            runner.validate_graph(SimpleNamespace(get_bases=graph.get_bases,
                get_heads=lambda: [runner.START], walk_revisions=graph.walk_revisions), metadata)

    def test_execution_flags_and_recovery_policy(self):
        runner.arguments(["--database", runner.TARGET])
        for flags in (["--execute"], ["--execute", "--confirm-target", runner.TARGET],
                      ["--execute", "--confirm-target", runner.TARGET, "--pause-verified"],
                      ["--confirm-target", runner.TARGET],
                      ["--execute", "--confirm-target", "lankapex_db", "--pause-verified",
                       "--disposable-test-data-approved"],
                      ["--execute", "--confirm-target", runner.TARGET, "--pause-verified",
                       "--disposable-test-data-approved", "--backup", "partial.sql"]):
            with self.subTest(flags=flags), self.assertRaises(runner.Stop):
                runner.arguments(["--database", runner.TARGET, *flags])
        runner.arguments(["--database", runner.TARGET, "--execute", "--confirm-target", runner.TARGET,
                          "--pause-verified", "--disposable-test-data-approved"])

    def test_sql_allowlist(self):
        for sql in ("SELECT DATABASE()", "SELECT VERSION(), @@SESSION.sql_mode, @@SESSION.foreign_key_checks",
                    "SHOW FULL TABLES FROM `lankapex_test_db`",
                    "CREATE TABLE business_join_links (business_id BIGINT)",
                    "CREATE TABLE customer_join_requests (request_id BIGINT)",
                    "ALTER TABLE customer_profiles ADD CONSTRAINT uq_customer_profile_business_user UNIQUE (business_id, user_id)",
                    "UPDATE alembic_version SET version_num = %s WHERE version_num = %s"):
            self.assertTrue(runner.safe_sql(sql, execute=True), sql)
        for sql in ("DROP TABLE customer_profiles", "TRUNCATE TABLE users", "USE lankapex_db",
                    "CREATE DATABASE lankapex_test_db", "CREATE TABLE users (id BIGINT)",
                    "UPDATE ledger_entries SET amount=0", "DELETE FROM alembic_version",
                    "SELECT * FROM lankapex_db.users", "SELECT * FROM unrelated_schema.users",
                    "SHOW TABLES FROM lankapex_db", "SHOW TABLES; DROP DATABASE lankapex_db",
                    "SELECT * INTO OUTFILE 'x' FROM users", "SELECT GET_LOCK('x',0) FOR UPDATE"):
            self.assertFalse(runner.safe_sql(sql, execute=True), sql)
        self.assertFalse(runner.safe_sql("CREATE TABLE business_join_links (id BIGINT)", execute=False))
        self.assertFalse(runner.safe_sql("SELECT GET_LOCK('x',0)", execute=False))

    def test_alembic_version_column_qualifiers(self):
        from sqlalchemy import Column, MetaData, String, Table, select, update
        from sqlalchemy.dialects.mysql import dialect

        version = Table("alembic_version", MetaData(), Column("version_num", String(32)))
        statements = (
            str(select(version.c.version_num).compile(dialect=dialect())),
            str(update(version).where(version.c.version_num == runner.START)
                .values(version_num=runner.END).compile(dialect=dialect())),
            "SELECT `alembic_version`.`version_num` FROM `alembic_version`",
            "UPDATE `alembic_version` SET `version_num` = %s "
            "WHERE `alembic_version`.`version_num` = %s",
            "SELECT av.version_num FROM alembic_version AS av",
            "SELECT av.version_num FROM alembic_version av",
        )
        for sql in statements:
            with self.subTest(sql=sql):
                self.assertTrue(runner.safe_sql(sql, execute=True))
        self.assertTrue(runner.safe_sql(statements[0], execute=False))
        self.assertFalse(runner.safe_sql(statements[1], execute=False))

    def test_cross_schema_qualifiers_and_obfuscation_are_refused(self):
        statements = (
            "SELECT * FROM unrelated_schema.users",
            "SELECT * FROM `unrelated_schema`.`users`",
            'SELECT * FROM "unrelated_schema"."users"',
            "SELECT * FROM unrelated_schema . users AS av",
            "SELECT av.version_num FROM unrelated_schema.alembic_version AS av",
            "SELECT av.version_num FROM alembic_version av JOIN unrelated_schema.users u",
            "UPDATE unrelated_schema.alembic_version SET version_num = %s",
            "UPDATE `unrelated_schema`.`alembic_version` SET version_num = %s",
            "UPDATE alembic_version SET version_num = %s "
            "WHERE unrelated_schema.alembic_version.version_num = %s",
            "CREATE TABLE unrelated_schema.business_join_links (id BIGINT)",
            "ALTER TABLE unrelated_schema.customer_profiles ADD CONSTRAINT x UNIQUE (id)",
            "SELECT * FROM unrelated_schema/**/.users",
            "SELECT * FROM unrelated_schema-- hidden\n.users",
            "SELECT * FROM unrelated_schema# hidden\n.users",
            "SELECT * FROM `unrelated_schema.users`",
            "SELECT * FROM `unrelated_schema``.users`",
        )
        for sql in statements:
            with self.subTest(sql=sql):
                self.assertFalse(runner.safe_sql(sql, execute=True))

    def test_compiled_model_ddl_is_allowed(self):
        from sqlalchemy.dialects.mysql import dialect
        from sqlalchemy.schema import AddConstraint, CreateIndex, CreateTable
        from app.models import BusinessJoinLink, CustomerJoinRequest, CustomerProfile

        statements = (
            CreateTable(BusinessJoinLink.__table__),
            CreateTable(CustomerJoinRequest.__table__),
            CreateIndex(next(index for index in CustomerJoinRequest.__table__.indexes
                             if index.name == "ix_customer_join_business_status_created")),
            AddConstraint(next(constraint for constraint in CustomerProfile.__table__.constraints
                               if constraint.name == "uq_customer_profile_business_user")),
        )
        for statement in statements:
            self.assertTrue(runner.safe_sql(str(statement.compile(dialect=dialect())), execute=True))

    def test_backup_requires_current_revision_and_checksum(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            dump = root / "synthetic.sql"
            content = b"-- test backup\n" + b"CREATE TABLE " * 27 + runner.START.encode()
            dump.write_bytes(content)
            import hashlib
            digest = hashlib.sha256(content).hexdigest()
            with patch.object(runner, "PRIVATE_BACKUPS", root):
                runner.validate_backup(dump, digest)
                with self.assertRaises(runner.Stop):
                    runner.validate_backup(dump, "0" * 64)
                dump.write_bytes(content.replace(runner.START.encode(), b"03b9c2d1e671"))
                with self.assertRaises(runner.Stop):
                    runner.validate_backup(dump, hashlib.sha256(dump.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
