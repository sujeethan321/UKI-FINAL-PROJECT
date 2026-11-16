"""Read-only logging gate. Default: no credential prompt, database or file access."""
import argparse
import getpass
import re
import sys
import warnings

TARGET = "lankapex_demo_db"
IDENTITY = "SELECT CURRENT_USER(), USER(), DATABASE(), @@port, VERSION(), CURRENT_ROLE(), @@GLOBAL.mandatory_roles"
SCHEMA = "SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE BINARY SCHEMA_NAME='lankapex_demo_db'"
GLOBALS = ("SHOW GLOBAL VARIABLES WHERE Variable_name IN "
           "('general_log','log_output','slow_query_log','log_bin','binlog_format',"
           "'binlog_rows_query_log_events','performance_schema')")
PLUGINS = "SELECT PLUGIN_NAME, PLUGIN_STATUS, PLUGIN_TYPE, PLUGIN_LIBRARY FROM information_schema.PLUGINS"
COMPONENTS = "SELECT COUNT(*) FROM mysql.component"
CONSUMERS = ("SELECT NAME, ENABLED FROM performance_schema.setup_consumers "
             "WHERE NAME LIKE 'events_statements%' OR NAME='statements_digest'")
INSTRUMENTS = "SELECT NAME, ENABLED FROM performance_schema.setup_instruments WHERE NAME LIKE 'statement/%'"
READS = frozenset((IDENTITY, SCHEMA, GLOBALS, PLUGINS, COMPONENTS, CONSUMERS, INSTRUMENTS))
REQUIRED_GLOBALS = frozenset(("general_log", "log_output", "slow_query_log", "log_bin",
                              "binlog_format", "binlog_rows_query_log_events", "performance_schema"))
REQUIRED_CONSUMERS = frozenset(("events_statements_current", "events_statements_history",
                               "events_statements_history_long", "statements_digest"))
BUILTIN_TYPES = frozenset(("STORAGE ENGINE", "AUTHENTICATION", "INFORMATION SCHEMA", "DAEMON"))
ATTESTATIONS = ("attest_direct_local_server", "attest_no_sql_tracing",
                "attest_secure_operator_session", "attest_no_out_of_band_capture",
                "attest_configuration_freeze")


class Stop(RuntimeError):
    """Only fixed internal category labels, never driver exception text."""


def require(condition, category):
    if not condition:
        raise Stop(category)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Stop("invalid_arguments")


def settings_map(rows, required):
    require(isinstance(rows, (list, tuple)), "metadata_incomplete")
    result = {}
    for row in rows:
        require(isinstance(row, (list, tuple)) and len(row) == 2 and
                isinstance(row[0], str) and isinstance(row[1], str), "metadata_incomplete")
        name = row[0].lower()
        require(name not in result, "metadata_incomplete")
        result[name] = row[1].upper()
    require(required <= result.keys(), "metadata_incomplete")
    return result


def enabled(value):
    require(value in ("ON", "OFF", "1", "0"), "metadata_incomplete")
    return value in ("ON", "1")


def verify_identity(rows, expected_account, dba_user):
    require(len(rows) == 1 and len(rows[0]) == 7, "identity_metadata_unavailable")
    current, login, database, port, version, role, mandatory = rows[0]
    require(current == expected_account and isinstance(login, str) and
            login.split("@", 1)[0] == dba_user, "unexpected_dba_identity")
    require(database is None and port == 3306 and isinstance(version, str) and
            version.startswith("8.0."), "unexpected_server_identity")
    require(role == "NONE" and mandatory in ("", "NONE"), "unexpected_dba_roles")


def assess(snapshot):
    """Strict disabled-capture baseline, not a general MySQL redaction proof."""
    values = settings_map(snapshot["globals"], REQUIRED_GLOBALS)
    require(values["log_output"] in ("FILE", "TABLE", "FILE,TABLE", "TABLE,FILE", "NONE"),
            "log_destination_unverified")
    require(not enabled(values["general_log"]), "general_logging_enabled")
    require(not enabled(values["slow_query_log"]), "slow_logging_enabled")
    require(values["binlog_format"] in ("ROW", "STATEMENT", "MIXED"), "binary_log_metadata_unverified")
    enabled(values["binlog_rows_query_log_events"])
    # Enabled binlogs are not automatically a plaintext leak. Their account-DDL
    # handling is outside this narrow automated proof, so no PASS is issued.
    require(not enabled(values["log_bin"]), "binary_log_handling_unverified")
    plugins = snapshot["plugins"]
    require(isinstance(plugins, (list, tuple)) and bool(plugins), "plugin_metadata_unavailable")
    names = set()
    for row in plugins:
        require(len(row) == 4 and isinstance(row[0], str) and row[0] not in names,
                "plugin_metadata_unavailable")
        name, status, kind, library = row
        names.add(name)
        require(kind != "AUDIT", "audit_logging_unverified")
        require(status == "ACTIVE" and kind in BUILTIN_TYPES and library is None,
                "plugin_state_unverified")
    require(snapshot["components"] == [(0,)] or snapshot["components"] == ((0,),),
            "component_state_unverified")
    if enabled(values["performance_schema"]):
        consumers = settings_map(snapshot.get("consumers"), REQUIRED_CONSUMERS)
        require(all(name in REQUIRED_CONSUMERS and value in ("YES", "NO")
                    for name, value in consumers.items()), "statement_collection_unverified")
        require(all(value == "NO" for value in consumers.values()), "statement_collection_enabled")
        instruments = settings_map(snapshot.get("instruments"), frozenset())
        require(bool(instruments) and all(name.startswith("statement/") and value in ("YES", "NO")
                                        for name, value in instruments.items()), "statement_collection_unverified")
        require(all(value == "NO" for value in instruments.values()), "statement_instrumentation_enabled")


def collect(read, state):
    state["stage"] = "global_logging_metadata"
    variables = read(GLOBALS)
    values = settings_map(variables, REQUIRED_GLOBALS)
    state["stage"] = "plugin_metadata"
    plugins = read(PLUGINS)
    state["stage"] = "component_metadata"
    components = read(COMPONENTS)
    snapshot = dict(globals=variables, plugins=plugins, components=components)
    if enabled(values["performance_schema"]):
        state["stage"] = "statement_consumer_metadata"
        snapshot["consumers"] = read(CONSUMERS)
        state["stage"] = "statement_instrument_metadata"
        snapshot["instruments"] = read(INSTRUMENTS)
    return snapshot


def parser():
    result = Parser(description=__doc__)
    result.add_argument("--execute", action="store_true")
    result.add_argument("--confirm-target")
    result.add_argument("--host", default="localhost")
    result.add_argument("--port", default="3306")
    result.add_argument("--dba-user")
    result.add_argument("--confirm-dba-account")
    for name in ATTESTATIONS:
        result.add_argument("--" + name.replace("_", "-"), action="store_true")
    return result


def main(argv=None, connector=None, prompt=getpass.getpass):
    connection = None
    password = None
    state = {"stage": "arguments"}
    category = None
    offline = False
    try:
        args = parser().parse_args(argv)
        if not args.execute:
            offline = True
        else:
            state["stage"] = "confirmation"
            require(args.confirm_target == TARGET and args.host == "localhost" and args.port == "3306",
                    "wrong_target_or_endpoint")
            require(args.dba_user and re.fullmatch(r"[A-Za-z0-9_]{1,32}", args.dba_user) and
                    args.confirm_dba_account == args.dba_user + "@localhost" and
                    args.dba_user not in ("lankapex_demo_app", "lankapex_demo_qr_migrator"),
                    "unexpected_dba_identity")
            require(all(getattr(args, name) for name in ATTESTATIONS), "operator_controls_unverified")
            state["stage"] = "client_controls"
            require(sys.gettrace() is None and sys.getprofile() is None, "sql_tracing_unverified")
            if connector is None:
                import pymysql
                require(pymysql.connections.DEBUG is False, "sql_tracing_enabled")
                connector = pymysql.connect
            state["stage"] = "hidden_dba_prompt"
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                password = prompt("Existing authorized DBA password (hidden): ")
            require(bool(password), "credential_unavailable")
            state["stage"] = "connection"
            # Numeric IPv4 loopback avoids hosts/DNS redirection. Logical endpoint
            # remains localhost:3306; no default database and no option-file read.
            connection = connector(host="127.0.0.1", port=3306, user=args.dba_user, password=password,
                                   database=None, autocommit=True, local_infile=False,
                                   connect_timeout=5, read_timeout=10, write_timeout=10)
            password = None
            with connection.cursor() as cursor:
                state["stage"] = "read_only_boundary"
                cursor.execute("START TRANSACTION READ ONLY")

                def read(sql):
                    require(sql in READS, "read_statement_refused")
                    cursor.execute(sql)
                    return cursor.fetchall()

                state["stage"] = "identity_metadata"
                verify_identity(read(IDENTITY), args.confirm_dba_account, args.dba_user)
                state["stage"] = "target_schema_metadata"
                require(read(SCHEMA) in ([(1,)], ((1,),)), "target_schema_missing_or_not_visible")
                snapshot = collect(read, state)
                state["stage"] = "logging_assessment"
                assess(snapshot)
    except Stop as exc:
        category = str(exc)
    except (EOFError, KeyboardInterrupt, getpass.GetPassWarning):
        category = "credential_or_operator_input_unavailable"
    except Exception:
        category = "metadata_or_connection_unavailable"
    finally:
        password = None
        if connection is not None:
            try:
                try:
                    connection.rollback()
                finally:
                    connection.close()
            except Exception:
                category = "connection_teardown_unverified"
    if category:
        print("STOP: QR logging preflight category=" + category + " stage=" + state["stage"])
        return 1
    if offline:
        print("PASS: offline QR logging preparation; no credentials, files or database accessed")
    else:
        print("PASS: strict MySQL logging metadata baseline and explicit operator attestations satisfied; read-only only")
        print("PASS: scope excludes provisioning authorization and proof of universal credential secrecy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
