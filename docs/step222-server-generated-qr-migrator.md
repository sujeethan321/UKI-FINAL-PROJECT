# Step 222: server-generated QR migrator password (source preparation)

No live operation is authorized by this document. The original Step 205 engine
and Step 219 strict logging gate are unchanged. Use this separate alternative
only after reviewing its metadata and obtaining new execution authorization.

## Reviewed mechanism and strength

The supported build is exactly Oracle MySQL **8.0.46**, matching the installed
INFO_SRC metadata reviewed during preparation. This is not evidence of the
running server version: the authenticated live preflight must confirm it.
Other releases, MariaDB, forks and version suffixes fail closed pending review.

References: [MySQL generated passwords](https://dev.mysql.com/doc/refman/8.0/en/password-management.html),
[length variable](https://dev.mysql.com/doc/refman/8.0/en/server-system-variables.html#sysvar_generated_random_password_length),
[8.0.46 implementation](https://github.com/mysql/mysql-server/blob/mysql-8.0.46/sql/auth/sql_user.cc),
[password logging](https://dev.mysql.com/doc/refman/8.0/en/password-logging.html).

The reviewed source uses RAND_bytes and a rounded mapping from each byte into
an 83-character alphabet. It is not a uniform alphabet sampler. At most four
of 256 byte values map to any one output character: a conservative min-entropy
bound is 6 bits per character, conditional on independent cryptographically
secure random bytes. 64 characters therefore provide at least 384 bits under
that assumption. The default 20 characters cannot provide 256 bits even under
an optimistic uniform-alphabet estimate. A valid-looking string alone does
not prove entropy. The source ignores RAND_bytes' return value; these scripts
cannot independently prove the server RNG's health. A modified/untrusted build
or suspect RNG is a blocker, not a reason to lower the strength requirement.

The execution confirmation explicitly authorizes **SET SESSION
generated_random_password_length=64** in this one provisioning connection.
No GLOBAL variable or logging setting is changed. The exact session value is
read back before CREATE USER. A read-only preflight never sets this variable;
it reports a weak existing default as STOP. If this is the only STOP, the
reviewed session-only correction can be separately authorized with execution.
Unavailable length metadata is never bypassed.

Only these account writes are issued, once each, without password parameters:

```sql
CREATE USER 'lankapex_demo_qr_migrator'@'localhost'
IDENTIFIED WITH caching_sha2_password BY RANDOM PASSWORD;
GRANT SELECT, INSERT, UPDATE, CREATE, ALTER, INDEX, REFERENCES
ON `lankapex\_demo\_db`.* TO 'lankapex_demo_qr_migrator'@'localhost';
```

Global USAGE is implicit. No roles, proxy, GRANT OPTION, other schema rights,
DROP/DELETE or runtime-account changes. Existing Step 202 exact grant validation
is reused. All hosts for the proposed username and stale privilege metadata
are checked before creation; the exact account must not already exist.

## Transport, authentication and capture

The DBA connection is numeric IPv4 loopback 127.0.0.1:3306, with no default
schema. An independently trusted public CA PEM is required. Python verifies
the certificate chain and **127.0.0.1 IP identity**; the certificate must have
that IP SAN. TLS >=1.2, peer certificate, actual socket address, cipher and
server-side TLS version are checked. No plaintext, unverified TLS, DNS or RSA-only
fallback. A locally installed self-signed certificate is not automatically
trusted. Do not pass a private key as TlsCa. Establishing TLS prerequisites
requires separate review if not already available.

The confirmed DBA identity must be its exact localhost account, use the builtin
caching_sha2_password plugin and have no active/mandatory roles. The newly
created account explicitly uses that same plugin. The new account is not given
a new REQUIRE SSL attribute: this preserves the prepared migration runner's
existing account contract; TLS is mandatory for this sensitive result transfer.
This step does not authorize executing or changing that migration runner.

The read-only metadata transaction checks schema existence, account absence,
port, roles and partial_revokes=OFF. No financial or log contents are read.
Independent noncritical logging reads continue if another surface is unavailable.
The sanitized report covers general/slow logging and destination, binary format
and row-query settings, plugins/components, Performance Schema statement
consumers/instruments, session length and operator attestations.

Enabled general/slow/binlogging alone does not prove plaintext exposure: the
issued CREATE statement contains no new plaintext password. The documented
rewriting of supported account SQL is not a guarantee for arbitrary capture
paths. Binary logs may contain credential-derived authentication material and
must remain confidential. Raw-mode configuration is not reliably proven by the
selected SHOW VARIABLES query; it requires DBA review of actual server startup
configuration, without log-content inspection. External audit plugins, installed
components, unknown metadata and enabled statement capture remain STOP. This
version does not certify arbitrary audit/component policies or safely relax
them automatically. Missing metadata visibility is STOP, not absence.

Before attesting, review direct local server identity, no proxy/connector/debug
SQL tracing, no query/result capture, no transcript/IDE debugger/crash-dump capture
of process memory, secure operator session, raw logging disabled, confidential
binary-account-DDL handling, and configuration freeze. An attestation records
operator responsibility; it is not an automated proof. Do not supply flags
merely to satisfy the parser. No need to disable slow logging for this method.

## Storage and failure boundaries

Use the approved Windows operator that will later run the migrator. The wrapper
holds the Step 208 validated ancestor handles throughout execution. The engine
also checks storage metadata before connecting. The private destination is
resolved from the verified registered profile, never LOCALAPPDATA:

`AppData\Local\LankaPex\PrivateDemoQr\demo-qr-migrator.dpapi`.

It must be absent. Existing directories must pass the unchanged owner,
operator/SYSTEM protected DACL, ancestor replacement, reparse and exact-path
checks. Nothing modifies existing directory/file ACLs to make a check pass.

The sensitive one-row result is validated for exact username/host/auth_factor,
column names, 64-character length and source alphabet. It is never printed.
It passes only through an anonymous stdin pipe into the internal PowerShell
storage helper, not argv, environment, clipboard, transcript or plaintext file.
Child output/error streams are captured and never relayed. The helper verifies
DPAPI encrypt/decrypt compatibility in memory, then creates the destination
exclusively using a protected operator/SYSTEM-only DACL supplied at creation.
It writes UTF-8 Windows CurrentUser ConvertFrom-SecureString ciphertext, flushes
and validates ownership/DACL through the shared guard. Existing consumers use
ConvertTo-SecureString with no Key. No SACL or Set-Acl is used.

Both processes necessarily hold plaintext in memory briefly; .NET/Python
immutable strings and driver buffers cannot promise complete zeroization.
BSTR/byte buffers are cleared, driver references released, and both processes
exit. No process inspection/debug capture is permitted during this operation.

Account DDL can commit before result capture returns. A timeout/disconnect at
CREATE is **uncertain**, even with no credential file. Once CREATE succeeds,
result/storage/grant/verification failures are explicitly post-commit stages.
DPAPI storage occurs before GRANT; a storage failure may leave a USAGE-only
account and no usable credential. Never rerun, reset, delete, recreate, retry
DDL or remove partial files. Preserve state, maintain the administration pause,
and separately authorize read-only account/storage reconciliation. Later repair
or account removal requires its own reviewed authorization. Rollback on
connection teardown does not undo account DDL.

## Pause and exact future commands

Coordinate an operator-observed pause of all concurrent account/role/grant
administration and logging/configuration changes. Other DBA sessions/tools and
scheduled administration must acknowledge the pause. The script cannot enforce
that pause globally. Do not take table locks or change application records.
Keep the pause through postchecks or STOP reconciliation; no automatic restart.

From the project root, the following is **offline only**, with no file checks,
credential prompt or connection:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\provision_demo_qr_random_password.ps1
```

After separately authorizing read-only metadata access, and only after verifying
every attestation, set the public certificate path and authorized DBA identifier
(these are not secrets), then run:

```powershell
$dbaUser = 'REPLACE_WITH_AUTHORIZED_DBA_USER'
$caPem = 'C:\REPLACE_WITH_VERIFIED_PUBLIC_CA\ca.pem'
$reviewed = @{
  ConfirmTarget='lankapex_demo_db'
  ConfirmAccount='lankapex_demo_qr_migrator@localhost'
  DbaUser=$dbaUser
  ConfirmDbaAccount=($dbaUser+'@localhost')
  TlsCa=$caPem
  AttestRawLoggingDisabled=$true
  AttestNoSqlTracing=$true
  AttestNoResultCapture=$true
  AttestSecureOperatorSession=$true
  AttestConfigurationFreeze=$true
  AttestAccountDdlPause=$true
  AttestBinaryAccountDdlReviewed=$true
}
& .\backend\scripts\provision_demo_qr_random_password.ps1 -PreflightOnly @reviewed
```

The splatted invocation is for an existing **Windows PowerShell 5.1** session
with a policy permitting the reviewed script. To use process-only Bypass,
start `powershell.exe -NoProfile -ExecutionPolicy Bypass` from the project root
and enter the block there. No persistent execution-policy change is necessary.
The DBA password is requested with getpass; no-echo unavailability is STOP.
Expect fixed INFO check/status lines, then PASS or a fixed STOP category/stage.
Weak length is expected if the session default is still 20. No other STOP can
be overridden by the session-length confirmation.

Only after reviewing all findings and separately authorizing account creation,
exact grants, session-only length=64 and private DPAPI file creation:

```powershell
& .\backend\scripts\provision_demo_qr_random_password.ps1 -Execute @reviewed -ConfirmCredentialCreation -ConfirmSessionLength64
```

No migration, backup, cleanup, server change or application data write is
authorized by either command. Provisioning readiness remains unverified until
the actual server/TLS/capture/storage prerequisites are demonstrated. A Windows
CurrentUser DPAPI roundtrip with a synthetic, nonpersistent value remains a
separately authorized platform compatibility check if required; offline mocks
do not prove the local DPAPI service works.
