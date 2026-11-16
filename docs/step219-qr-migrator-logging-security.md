# Step 219: Credential-safe logging preflight preparation

SOURCE AND OFFLINE TESTS ONLY. No MySQL connection, live verifier, credential
prompt/generation, query-log read, provisioning or filesystem-security operation
was executed. Step 218 directory success is operator-reported, not rechecked.

## Confirmed exposure paths

Reviewed provision_demo_qr_migrator.py/.ps1, Step 205, existing direct PyMySQL
verification conventions, and installed PyMySQL cursor/connection source. No
existing complete logging-security verifier was found.

Installed Cursor.execute calls _mogrify before _query and retains rendered SQL
in _executed after success. The provisioner binds its password parameter, but
this is client-side escaping: CREATE USER still reaches MySQL containing the
password. Binding is not proof of redaction or server-side prepared execution.
Failed DDL can also reach capture mechanisms. GRANT itself has no password.

PyMySQL connection objects retain authentication material in memory. The
PowerShell wrapper stores a newly generated password as DPAPI ciphertext and
transfers plaintext to the child in a process-local environment variable. It
restores that variable and disposes buffers, but managed strings, connector
objects and process/crash snapshots cannot promise physical erasure.

The provisioner emits fixed failure stages rather than exception text, and
installed PyMySQL DEBUG defaults False. Neither guarantees safety against
instrumentation, server auditing, proxies, operator tracing or memory capture.
This new verifier generates no password and sends no credential-bearing DDL.

## Metadata inspected and strict PASS baseline

| Metadata | Required evidence |
|---|---|
| CURRENT_USER(), USER(), DATABASE(), @@port, VERSION(), CURRENT_ROLE(), @@GLOBAL.mandatory_roles | Exact confirmed DBA identity/login; no default schema; port 3306; MySQL 8.0; no active/mandatory roles |
| Exact information_schema.SCHEMATA count for lankapex_demo_db | Target visible; absence or invisibility is STOP |
| general_log, log_output | Logging OFF; recognized FILE/TABLE/NONE destination type |
| slow_query_log | OFF for this strict automated baseline |
| log_bin, binlog_format, binlog_rows_query_log_events | Complete metadata; enabled binlogs require separate account-DDL handling review and STOP |
| performance_schema | If OFF, no statement-control queries; if ON, controls below must be fully visible |
| setup_consumers for statement current/history/history_long and digest | All four known controls present and NO; unknown/incomplete/enabled controls STOP |
| setup_instruments for statement/% | Nonempty collection, all disabled |
| information_schema.PLUGINS name/status/type/library | AUDIT plugins, external libraries, unknown types and non-ACTIVE states STOP; only built-in ACTIVE storage/authentication/information-schema/daemon types fit the baseline |
| mysql.component COUNT(*) | Zero; registered components need separate review |

The script uses a fixed SELECT/SHOW allowlist inside START TRANSACTION READ ONLY.
It reads no application/financial rows, log contents, binary-log events,
SQL_TEXT, statement-history contents, password hashes or authentication strings.
log_output is a destination TYPE, not a pathname. File ACLs, collectors, rotation
and exports require separate operator review without exposing log contents.

General/slow logging enabled proves a capture facility is enabled, not that it
necessarily logs plaintext. Binary logging likewise is not automatically a
plaintext leak: account-DDL rewriting, derived authentication data and replication
handling must be reviewed for the actual version/implementation. ROW format is
not proof of credential safety. No redaction guarantee or probe-password test
is implemented. Enabled binary logging therefore yields an unverified STOP.

Do NOT disable binary, audit or operational logging to manufacture a PASS.
Review an alternative redaction-aware policy separately. This strict baseline
may reject ordinary configurations, including default statement consumers,
mysqlx libraries or benign password components. Rejection is unresolved evidence,
not proof those facilities leak credentials. No flag bypasses a metadata STOP.
Missing metadata privileges, malformed results and teardown failures also STOP.

## Mandatory operator attestations

Before even entering the existing DBA password, establish all five controls:

1. Direct local server: localhost:3306 is the intended MySQL instance, without
   proxy/forwarder or alternate instance. The verifier connects to 127.0.0.1 to
   avoid DNS/hosts redirection. The existing provisioner uses localhost: confirm
   it reaches the SAME reviewed instance, including IPv4/IPv6 routing.
2. No SQL tracing: no SQL/debug hooks, dumps, APM/proxy/analytics export or packet
   capture. The tool checks Python trace/profile hooks and PyMySQL DEBUG where
   detectable, but cannot discover all instrumentation.
3. Secure operator session: trusted account, console and source files; no debugger,
   variable-capturing trace, unsafe transcript or process/crash-dump export.
   Keep Windows/security auditing intact; do not disable it automatically.
4. No out-of-band capture: review server startup/raw logging, audit/proxy agents,
   monitoring and collection outside the queried metadata. Unknown means STOP.
5. Configuration freeze: maintain reviewed controls through separately approved
   provisioning. A metadata transaction does not freeze global variables,
   plugins, external agents or concurrent account administration.

These are attestations, not automated facts. Missing confirmation is STOP before
prompting. Disabled general logging alone never proves secrecy. PASS is limited
to this strict metadata baseline plus reviewed, continuing operator controls;
universal credential secrecy cannot be proven by this tool.

## Future commands (not executed here)

Project-root no-connection/default preparation:

```powershell
& .\backend\.venv\Scripts\python.exe -I .\backend\scripts\check_demo_qr_logging_security.py
```

Expected:

```text
PASS: offline QR logging preparation; no credentials, files or database accessed
```

For a separately authorized READ-ONLY inspection, replace the DBA placeholder
in both places with an existing authorized login. CURRENT_USER() must match
that exact login at localhost. Confirm each attestation before using its flag:

```powershell
& .\backend\.venv\Scripts\python.exe -I .\backend\scripts\check_demo_qr_logging_security.py --execute --confirm-target lankapex_demo_db --host localhost --port 3306 --dba-user AUTHORIZED_DBA_USERNAME --confirm-dba-account 'AUTHORIZED_DBA_USERNAME@localhost' --attest-direct-local-server --attest-no-sql-tracing --attest-secure-operator-session --attest-no-out-of-band-capture --attest-configuration-freeze
```

Enter the EXISTING DBA password at the hidden prompt. Echoing fallback is
rejected. No credential file, clipboard, environment-credential transfer,
option-file/dotenv loading, application engine, model or Settings import is
used. One numeric loopback connection has bounded timeouts and no retry. The
connector negotiates its normal session/character-set state; the script never
changes logging variables or persistent/server configuration. It rolls back
the read-only transaction and closes before PASS.

Successful output:

```text
PASS: strict MySQL logging metadata baseline and explicit operator attestations satisfied; read-only only
PASS: scope excludes provisioning authorization and proof of universal credential secrecy
```

Example failures (not actual local findings):

```text
STOP: QR logging preflight category=general_logging_enabled stage=logging_assessment
STOP: QR logging preflight category=binary_log_handling_unverified stage=logging_assessment
STOP: QR logging preflight category=audit_logging_unverified stage=logging_assessment
STOP: QR logging preflight category=statement_collection_enabled stage=logging_assessment
STOP: QR logging preflight category=metadata_or_connection_unavailable stage=component_metadata
```

Only fixed categories/stages are printed: no raw SQL, grants, plugin rows,
environment values, identities, passwords or connector exceptions. On STOP,
preserve configuration; never retry, repair logging or provision automatically.
Further metadata diagnosis or an alternative reviewed acceptance policy needs
separate authorization. The existing -ConfirmSecureLogging flag remains a manual
provisioning gate, not automatic integration or durable evidence from this tool.
Credential generation, account creation/grants, account-administration pause,
backup/rehearsal and migration still require separate authorization.
