"""Separate, fail-closed server-random provisioning path; default has no I/O.

Only the reviewed MySQL 8.0.46 implementation is supported. No password-bearing
SQL, SQL logging changes, application-table reads or automatic recovery.
"""
import argparse
import getpass
from pathlib import Path
import re
import ssl
import subprocess
import sys
import warnings

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_demo_qr_logging_security as logging_gate
import provision_demo_qr_migrator as legacy
import verify_demo_qr_migrator as verification

TARGET, USER, ACCOUNT = legacy.TARGET, legacy.USER, legacy.ACCOUNT
CREATE = ("CREATE USER 'lankapex_demo_qr_migrator'@'localhost' "
          "IDENTIFIED WITH caching_sha2_password BY RANDOM PASSWORD")
LENGTH = "SELECT @@SESSION.generated_random_password_length"
SET_LENGTH = "SET SESSION generated_random_password_length=64"
PLUGIN = ("SELECT plugin FROM mysql.user WHERE BINARY User=%s AND BINARY Host='localhost'")
TLS = "SHOW SESSION STATUS WHERE Variable_name IN ('Ssl_cipher','Ssl_version')"
ALPHABET = frozenset("1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ,.-;:_+*!%&/(){}[]<>@")
CONTROLS = ("raw_logging_disabled", "no_sql_tracing", "no_result_capture",
            "secure_operator_session", "configuration_freeze", "account_ddl_pause",
            "binary_account_ddl_reviewed")
require = verification.require


def collect(read):
    """Attempt every noncritical metadata surface, never return raw exceptions."""
    queries = dict(globals=logging_gate.GLOBALS, plugins=logging_gate.PLUGINS,
                   components=logging_gate.COMPONENTS, consumers=logging_gate.CONSUMERS,
                   instruments=logging_gate.INSTRUMENTS, password_length=LENGTH)
    result = {}
    for key, sql in queries.items():
        try:
            result[key] = read(sql)
        except Exception:
            result[key] = None
    return result


def assess(snapshot, controls):
    """All labels are constants. Enabled slow logging alone is not a failure.

    SQL contains no new plaintext credential; unknown/custom capture paths still
    block. Raw-mode and external capture are attested, not inferred from SQL.
    """
    findings = {}
    try:
        values = logging_gate.settings_map(snapshot['globals'], logging_gate.REQUIRED_GLOBALS)
    except Exception:
        values = {}
    for name in ('general_log', 'slow_query_log', 'log_bin', 'performance_schema'):
        value = values.get(name)
        findings[name] = ('enabled_no_plaintext_in_issued_sql' if value in ('ON', '1') else
                          'disabled' if value in ('OFF', '0') else 'STOP_metadata_unavailable')
    findings['log_output'] = ('known_destination' if values.get('log_output') in
                             ('FILE', 'TABLE', 'FILE,TABLE', 'TABLE,FILE', 'NONE') else
                             'STOP_metadata_unavailable')
    findings['binary_handling'] = ('reviewed_version_and_operator_attestation_required' if
                                  values.get('binlog_format') in ('ROW', 'STATEMENT', 'MIXED') and
                                  values.get('binlog_rows_query_log_events') in ('ON', 'OFF', '0', '1')
                                  else 'STOP_metadata_unavailable')
    plugins = snapshot.get('plugins')
    findings['audit_plugins'] = 'STOP_audit_or_plugin_state_unverified'
    findings['authentication_plugin'] = 'STOP_unexpected_plugin'
    if isinstance(plugins, (tuple, list)) and plugins:
        if all(isinstance(row, (list, tuple)) and len(row) == 4 and row[1] == 'ACTIVE' and row[2] in logging_gate.BUILTIN_TYPES
               and row[3] is None for row in plugins):
            findings['audit_plugins'] = 'builtin_only_no_audit_plugin'
        if ('caching_sha2_password', 'ACTIVE', 'AUTHENTICATION', None) in plugins:
            findings['authentication_plugin'] = 'explicit_builtin_caching_sha2_password'
    findings['components'] = ('none' if snapshot.get('components') in ([(0,)], ((0,),)) else
                              'STOP_component_state_unverified')
    findings['statement_capture'] = 'STOP_statement_capture_unverified'
    if values.get('performance_schema') in ('OFF', '0'):
        findings['statement_capture'] = 'performance_schema_disabled'
    else:
        try:
            consumers = logging_gate.settings_map(snapshot['consumers'], logging_gate.REQUIRED_CONSUMERS)
            instruments = logging_gate.settings_map(snapshot['instruments'], frozenset())
            if (set(consumers) == logging_gate.REQUIRED_CONSUMERS and instruments and
                    all(v == 'NO' for v in consumers.values()) and
                    all(k.startswith('statement/') and v == 'NO' for k, v in instruments.items())):
                findings['statement_capture'] = 'statement_capture_disabled'
        except Exception:
            pass
    length = snapshot.get('password_length')
    valid_length = (isinstance(length, (tuple, list)) and len(length) == 1 and
                    isinstance(length[0], (list, tuple)) and len(length[0]) == 1 and
                    type(length[0][0]) is int and 5 <= length[0][0] <= 255)
    findings['password_strength'] = ('at_least_384_bit_conservative_bound' if
                                    valid_length and length[0][0] >= 64 else 'STOP_length_below_64_or_unavailable')
    findings['observed_session_length'] = ('characters_' + str(length[0][0]) if valid_length else
                                          'STOP_length_metadata_unavailable')
    for control in CONTROLS:
        findings[control] = 'operator_attested_not_automatically_proven' if controls.get(control) else 'STOP_attestation_missing'
    return findings


def ready(findings, allow_length_change=False):
    return not any(value.startswith('STOP_') for key, value in findings.items()
                   if not (allow_length_change and key == 'password_strength' and
                           value == 'STOP_length_below_64_or_unavailable'))


def result_password(cursor):
    require(tuple(field[0] for field in (cursor.description or ())) ==
            ('user', 'host', 'generated password', 'auth_factor'), 'sensitive_result_shape')
    rows = cursor.fetchall()
    require(len(rows) == 1 and len(rows[0]) == 4, 'sensitive_result_shape')
    user, host, password, factor = rows[0]
    require(user == USER and host == 'localhost' and factor == 1, 'sensitive_result_identity')
    require(isinstance(password, str) and len(password) == 64 and set(password) <= ALPHABET,
            'sensitive_result_strength')
    # Release driver references; Python/driver immutable strings cannot promise zeroization.
    cursor._rows = None
    cursor._result = None
    return password


def store_password(password, runner=subprocess.run):
    """Anonymous stdin pipe only: no credential in argv, environment or output.

    PowerShell uses the existing ConvertFrom-SecureString CurrentUser format.
    Both child outputs are captured privately and never relayed, even on failure.
    """
    script = Path(__file__).with_name('store_demo_qr_random_password.ps1')
    result = runner(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                     str(script), '-StoreFromPrivatePipe', '-ConfirmAccount', ACCOUNT],
                    input=password, text=True, encoding='utf-8', capture_output=True,
                    timeout=30, check=False)
    require(result.returncode == 0 and result.stdout.strip() ==
            'PASS: server-generated credential stored and verified' and not result.stderr.strip(),
            'credential_storage_failed_preserve_account_and_files')


def storage_metadata(runner=subprocess.run):
    result = runner(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                     str(Path(__file__).with_name('store_demo_qr_random_password.ps1')),
                     '-MetadataOnly', '-ConfirmAccount', ACCOUNT], capture_output=True,
                    text=True, timeout=30, check=False)
    require(result.returncode == 0 and result.stdout.strip() ==
            'PASS: absent credential and protected storage verified' and not result.stderr.strip(),
            'storage_metadata_unverified')


def provision(connection, read, store, state):
    """Caller has verified transport, all metadata and explicit confirmations."""
    legacy.prepare(read)  # Immediate existence/grant-scope recheck before DDL.
    with connection.cursor() as cursor:
        state['stage'] = 'session_length'
        cursor.execute(SET_LENGTH)  # Not GLOBAL and never changes logging.
        require(read(LENGTH) in (((64,),), [(64,)]), 'session_length_unverified')
        state['stage'] = 'create_attempted_commit_uncertain'
        cursor.execute(CREATE)  # No parameters, no new password in issued SQL.
        state['stage'] = 'account_committed_result_capture'
        password = None
        try:
            password = result_password(cursor)
            connection._result = None
            state['stage'] = 'account_committed_credential_storage'
            store(password)  # Save first; grant failure leaves usable evidence.
        finally:
            password = None
            cursor._rows = None
            cursor._result = None
            connection._result = None
        state['stage'] = 'account_committed_grant_attempted'
        cursor.execute(legacy.GRANT)
        state['stage'] = 'account_committed_privilege_verification'
        verification.verify(read, 'dba-metadata')
        require(read(PLUGIN, (USER,)) in
                ((('caching_sha2_password',),), [('caching_sha2_password',)]), 'created_plugin_unverified')


def parser():
    p = logging_gate.Parser(description=__doc__)
    modes = p.add_mutually_exclusive_group()
    modes.add_argument('--preflight-only', action='store_true')
    modes.add_argument('--execute', action='store_true')
    for name in ('confirm-target', 'confirm-account', 'dba-user', 'confirm-dba-account', 'tls-ca'):
        p.add_argument('--' + name)
    p.add_argument('--host', default='localhost')
    p.add_argument('--port', default='3306')
    p.add_argument('--confirm-credential-creation', action='store_true')
    p.add_argument('--confirm-session-length-64', action='store_true')
    for name in CONTROLS:
        p.add_argument('--attest-' + name.replace('_', '-'), action='store_true')
    return p


def main(argv=None, connector=None, prompt=getpass.getpass, store=store_password, tls_check=None,
         check_storage=storage_metadata):
    connection = None
    password = None
    state = {'stage': 'confirmation'}
    category = None
    offline = False
    try:
        args = parser().parse_args(argv)
        if not (args.execute or args.preflight_only):
            offline = True
        else:
            require(args.confirm_target == TARGET and args.confirm_account == ACCOUNT and
                    args.host == 'localhost' and args.port == '3306', 'wrong_target_or_endpoint')
            require(args.dba_user and re.fullmatch(r'[A-Za-z0-9_]{1,32}', args.dba_user) and
                    args.dba_user not in (USER, 'lankapex_demo_app') and
                    args.confirm_dba_account == args.dba_user + '@localhost', 'wrong_dba_identity')
            controls = {name: getattr(args, 'attest_' + name) for name in CONTROLS}
            require(all(controls.values()), 'operator_controls_unverified')
            require(not args.execute or (args.confirm_credential_creation and args.confirm_session_length_64),
                    'execution_confirmation_missing')
            require(sys.gettrace() is None and sys.getprofile() is None, 'client_tracing')
            state['stage'] = 'storage_metadata'
            check_storage()
            state['stage'] = 'verified_tls_prerequisite'
            require(args.tls_ca is not None, 'trusted_tls_ca_required')
            context = ssl.create_default_context(cafile=args.tls_ca)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            if connector is None:
                import pymysql
                require(pymysql.connections.DEBUG is False, 'client_tracing')
                connector = pymysql.connect
            with warnings.catch_warnings():
                warnings.simplefilter('error', getpass.GetPassWarning)
                password = prompt('Existing authorized DBA password (hidden): ')
            require(bool(password), 'dba_credential_unavailable')
            state['stage'] = 'authenticated_loopback_tls'
            connection = connector(host='127.0.0.1', port=3306, user=args.dba_user,
                                   password=password, database=None, ssl=context,
                                   autocommit=True, local_infile=False, connect_timeout=5,
                                   read_timeout=10, write_timeout=10)
            password = None
            if tls_check is not None:
                require(tls_check(connection), 'verified_tls_required')
            else:
                sock = connection._sock
                require(isinstance(sock, ssl.SSLSocket) and sock.context.check_hostname and
                        sock.context.verify_mode == ssl.CERT_REQUIRED and bool(sock.getpeercert()) and
                        sock.getpeername()[0] == '127.0.0.1', 'verified_tls_required')
            with connection.cursor() as cursor:
                def read(sql, params=()):
                    require(sql.startswith(('SELECT ', 'SHOW ')), 'read_statement_refused')
                    cursor.execute(sql, params)
                    return cursor.fetchall()

                cursor.execute('START TRANSACTION READ ONLY')
                state['stage'] = 'identity_and_account_metadata'
                identity = read(logging_gate.IDENTITY)
                logging_gate.verify_identity(identity, args.confirm_dba_account, args.dba_user)
                print('INFO: QR random preflight running_version=' + identity[0][4]
                      if re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', identity[0][4]) else
                      'INFO: QR random preflight running_version=unreviewed_build')
                require(identity[0][4] == '8.0.46', 'unreviewed_server_version')
                require(read(PLUGIN, (args.dba_user,)) in
                        ([("caching_sha2_password",)], (("caching_sha2_password",),)), 'unexpected_dba_plugin')
                tls_values = dict(read(TLS))
                require(tls_values.get('Ssl_version') in ('TLSv1.2', 'TLSv1.3') and
                        bool(tls_values.get('Ssl_cipher')), 'verified_tls_required')
                legacy.prepare(read)
                state['stage'] = 'consolidated_metadata'
                findings = assess(collect(read), controls)
                for key, value in sorted(findings.items()):
                    print('INFO: QR random preflight check=' + key + ' status=' + value)
                require(ready(findings, allow_length_change=args.execute), 'security_assessment_blocked')
                connection.rollback()  # Ends read-only assessment before optional account DDL.
                if args.execute:
                    provision(connection, read, store, state)
    except (verification.Stop, logging_gate.Stop) as exc:
        category = str(exc)
    except (Exception, KeyboardInterrupt):
        category = 'metadata_transport_or_storage_unavailable'
    finally:
        password = None
        if connection is not None:
            try:
                try:
                    connection.rollback()
                finally:
                    connection.close()
            except Exception:
                category = 'connection_teardown_unverified'
    if category:
        print('STOP: QR random provisioning category=' + category + ' stage=' + state['stage'] +
              '; preserve partial account/files; no retry or automatic repair')
        return 1
    if offline:
        print('PASS: offline random provisioning preparation; no I/O')
    elif args.preflight_only:
        print('PASS: read-only random provisioning assessment complete; no account or credential created')
    else:
        print('PASS: exact random provisioning checks complete; no migration performed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
