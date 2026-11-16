"""Exact-account provisioning engine. Default mode does not read credentials."""
import argparse
import getpass
import os
from pathlib import Path
import re
import sys
import warnings

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_demo_qr_migrator as verification

TARGET, USER, ACCOUNT = verification.TARGET, verification.USER, verification.ACCOUNT
CREATE = "CREATE USER 'lankapex_demo_qr_migrator'@'localhost' IDENTIFIED BY %s"
GRANT = ("GRANT SELECT, INSERT, UPDATE, CREATE, ALTER, INDEX, REFERENCES ON "
         "`lankapex\\_demo\\_db`.* TO 'lankapex_demo_qr_migrator'@'localhost'")
SECRET_ENV = "LANKAPEX_QR_PROVISION_PASSWORD"


def require(value, category):
    if not value:
        raise verification.Stop(category)


def prepare(read):
    """Only metadata reads; any failed query must block account creation."""
    port, roles, partial, mandatory, version = read(
        "SELECT @@port, CURRENT_ROLE(), @@GLOBAL.partial_revokes, "
        "@@GLOBAL.mandatory_roles, VERSION()"
    )[0]
    require(port == 3306 and str(version).startswith("8.0."), "server_identity")
    require(roles == "NONE" and mandatory in ("", "NONE") and partial == 0,
            "unsafe_grant_semantics_or_roles")
    require(read("SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE BINARY SCHEMA_NAME=%s",
                 (TARGET,))[0][0] == 1, "target_missing_or_not_visible")
    # All hosts are checked, not just localhost. No authentication columns read.
    require(not read("SELECT Host FROM mysql.user WHERE BINARY User=%s", (USER,)),
            "account_already_exists")
    # Reject stale/orphan permission metadata rather than adopting it.
    for table, column in (("db", "User"), ("tables_priv", "User"), ("columns_priv", "User"),
                          ("procs_priv", "User"), ("global_grants", "USER"),
                          ("default_roles", "USER")):
        require(read("SELECT COUNT(*) FROM mysql." + table + " WHERE BINARY " + column + "=%s",
                     (USER,))[0][0] == 0, "conflicting_privilege_metadata")
    for sql in (
        "SELECT COUNT(*) FROM mysql.role_edges WHERE BINARY TO_USER=%s OR BINARY FROM_USER=%s",
        "SELECT COUNT(*) FROM mysql.proxies_priv WHERE BINARY User=%s OR BINARY Proxied_user=%s",
    ):
        require(read(sql, (USER, USER))[0][0] == 0, "conflicting_privilege_metadata")


def provision(connection, password, state):
    with connection.cursor() as cursor:
        def read(sql, params=()):
            require(sql.startswith(("SELECT ", "SHOW GRANTS")), "read_statement_refused")
            cursor.execute(sql, params)
            return cursor.fetchall()

        state["stage"] = "metadata_preflight"
        prepare(read)
        # Account DDL autocommits. Never retry or issue compensating DDL.
        state["stage"] = "create_attempted_commit_uncertain"
        cursor.execute(CREATE, (password,))
        state["stage"] = "grant_attempted_partial_account_possible"
        cursor.execute(GRANT)
        state["stage"] = "post_grant_metadata"
        verification.verify(read, "dba-metadata")


def main(argv=None, connector=None, prompt=getpass.getpass, environ=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-target")
    parser.add_argument("--confirm-account")
    parser.add_argument("--confirm-account-ddl-pause", action="store_true")
    parser.add_argument("--confirm-secure-logging", action="store_true")
    parser.add_argument("--dba-user")
    args = parser.parse_args(argv)
    connection = credential_connection = None
    password = dba_password = None
    state = {"stage": "confirmation"}
    try:
        if not args.execute:
            print("PASS: offline QR migrator provisioning preparation; no credentials or database accessed")
            return 0
        require(args.confirm_target == TARGET and args.confirm_account == ACCOUNT
                and args.confirm_account_ddl_pause and args.confirm_secure_logging, "confirmation")
        require(args.dba_user and re.fullmatch(r"[A-Za-z0-9_]{1,32}", args.dba_user)
                and args.dba_user not in (USER, "lankapex_demo_app"), "dba_identity")
        state["stage"] = "credential_preparation"
        password = (os.environ if environ is None else environ).get(SECRET_ENV)
        require(isinstance(password, str) and re.fullmatch(r"[A-Za-z0-9+/]{43}=", password),
                "credential_preparation")
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            dba_password = prompt("Existing authorized DBA password (hidden): ")
        require(bool(dba_password) and dba_password != password, "dba_credential_unavailable")
        if connector is None:
            import pymysql
            connector = pymysql.connect
        options = dict(host="localhost", port=3306, connect_timeout=5, read_timeout=10,
                       write_timeout=10, autocommit=True, local_infile=False)
        state["stage"] = "dba_connection"
        connection = connector(user=args.dba_user, password=dba_password, database=None, **options)
        dba_password = None
        provision(connection, password, state)
        state["stage"] = "credential_identity_verification"
        credential_connection = connector(user=USER, password=password, database=TARGET, **options)
        with credential_connection.cursor() as cursor:
            cursor.execute("START TRANSACTION READ ONLY")

            def read(sql, params=()):
                require(sql.startswith(("SELECT ", "SHOW GRANTS")), "read_statement_refused")
                cursor.execute(sql, params)
                return cursor.fetchall()

            verification.verify(read, "credential")
        print("PASS: exact QR migrator created; metadata, privileges and credential identity verified")
        return 0
    except Exception:
        # Stage names are constants, not provider/driver exception strings.
        print("STOP: QR migrator provisioning category=" + state["stage"] + "; preserve credential; no retry or automatic repair")
        return 1
    finally:
        password = dba_password = None
        for conn in (credential_connection, connection):
            if conn is not None:
                try:
                    conn.rollback()
                    conn.close()
                except Exception:
                    pass


if __name__ == "__main__":
    raise SystemExit(main())
