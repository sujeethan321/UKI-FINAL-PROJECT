"""Read-only account verification; default invocation has no I/O or connection."""
import argparse
import getpass
import re

TARGET = "lankapex_demo_db"
USER = "lankapex_demo_qr_migrator"
ACCOUNT = USER + "@localhost"
RIGHTS = {"SELECT", "INSERT", "UPDATE", "CREATE", "ALTER", "INDEX", "REFERENCES"}


class Stop(RuntimeError):
    pass


def require(condition, category):
    if not condition:
        raise Stop(category)


def grants(rows):
    """Accept only explicit USAGE and the exact escaped schema privilege set."""
    found = set()
    recipient = r"(?:`" + USER + r"`@`localhost`|'" + USER + r"'@'localhost')"
    for row in rows:
        require(isinstance(row, str), "metadata_unavailable")
        require("WITH GRANT OPTION" not in row, "excessive_privileges")
        if re.fullmatch(r"GRANT USAGE ON \*\.\* TO " + recipient, row):
            continue
        match = re.fullmatch(r"GRANT ([A-Z, ]+) ON `([^`]+)`\.\* TO " + recipient, row)
        require(match is not None, "unexpected_effective_privileges")
        require(match[2] == r"lankapex\_demo\_db", "wrong_database_scope")
        found.update(match[1].split(", "))
    require(not found - RIGHTS, "excessive_privileges")
    require(found == RIGHTS, "insufficient_privileges")


def verify(read, mode):
    port, roles, partial, mandatory, version = read(
        "SELECT @@port, CURRENT_ROLE(), @@GLOBAL.partial_revokes, "
        "@@GLOBAL.mandatory_roles, VERSION()"
    )[0]
    require(port == 3306, "wrong_server_port")
    require(str(version).startswith("8.0."), "unsupported_metadata_version")
    require(roles == "NONE" and mandatory in ("", "NONE"), "active_or_mandatory_roles")
    require(partial == 0, "unsupported_grant_semantics")
    if mode == "dba-metadata":
        # Successful mysql.user access is mandatory: absence must not be inferred
        # from information_schema visibility alone. No authentication fields read.
        accounts = read("SELECT Host, account_locked FROM mysql.user WHERE BINARY User = %s", (USER,))
        require(bool(accounts), "account_missing")
        require(len(accounts) == 1 and accounts[0][0] == "localhost", "conflicting_account_identity")
        require(accounts[0][1] == "N", "account_locked")
        checks = (
            ("SELECT COUNT(*) FROM mysql.role_edges WHERE (BINARY TO_USER=%s AND TO_HOST='localhost') OR (BINARY FROM_USER=%s AND FROM_HOST='localhost')", (USER, USER)),
            ("SELECT COUNT(*) FROM mysql.default_roles WHERE BINARY USER=%s AND HOST='localhost'", (USER,)),
            ("SELECT COUNT(*) FROM mysql.global_grants WHERE BINARY USER=%s AND HOST='localhost'", (USER,)),
            ("SELECT COUNT(*) FROM mysql.proxies_priv WHERE (BINARY User=%s AND Host='localhost') OR (BINARY Proxied_user=%s AND Proxied_host='localhost')", (USER, USER)),
        )
        for sql, params in checks:
            require(read(sql, params)[0][0] == 0, "unexpected_effective_privileges")
        statements = read("SHOW GRANTS FOR 'lankapex_demo_qr_migrator'@'localhost'")
    else:
        database, current, login = read("SELECT DATABASE(), CURRENT_USER(), USER()")[0]
        require(database == TARGET, "wrong_database_identity")
        require(current == ACCOUNT and login.split("@", 1)[0] == USER, "wrong_account_identity")
        statements = read("SHOW GRANTS")
    require(read("SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE BINARY SCHEMA_NAME=%s", (TARGET,))[0][0] == 1,
            "target_schema_missing_or_not_visible")
    grants([row[0] for row in statements])


def main(argv=None, connector=None, prompt=getpass.getpass):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-target")
    parser.add_argument("--mode", choices=("dba-metadata", "credential"), default="dba-metadata")
    parser.add_argument("--dba-user")
    args = parser.parse_args(argv)
    connection = None
    password = None
    try:
        if not args.execute:
            print("PASS: offline account verification preparation; no credentials or database accessed")
            return 0
        require(args.confirm_target == TARGET, "confirmation")
        user = USER if args.mode == "credential" else args.dba_user
        require(bool(user) and re.fullmatch(r"[A-Za-z0-9_]{1,32}", user), "account_parameter")
        password = prompt("Existing authorized account password (hidden): ")
        require(bool(password), "credential_unavailable")
        if connector is None:
            import pymysql
            connector = pymysql.connect
        connection = connector(host="localhost", port=3306, user=user, password=password,
                               database=TARGET if args.mode == "credential" else None,
                               connect_timeout=5, read_timeout=10, write_timeout=10,
                               autocommit=False, local_infile=False)
        password = None
        with connection.cursor() as cursor:
            cursor.execute("START TRANSACTION READ ONLY")

            def read(sql, params=()):
                require(sql.startswith(("SELECT ", "SHOW GRANTS")), "non_read_statement")
                cursor.execute(sql, params)
                return cursor.fetchall()

            verify(read, args.mode)
        print("PASS: exact QR migrator account and schema-scoped privileges; read-only check complete")
        return 0
    except Stop as exc:
        print("STOP: QR migrator verification category=" + str(exc))
        return 1
    except Exception as exc:
        code = exc.args[0] if exc.args else None
        category = "authentication_rejected_existence_unknown" if code == 1045 else "metadata_or_connection_unavailable"
        print("STOP: QR migrator verification category=" + category)
        return 1
    finally:
        password = None
        if connection is not None:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                # Never disclose DBAPI exception text during teardown.
                pass


if __name__ == "__main__":
    raise SystemExit(main())
