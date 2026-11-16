# Step 205: Dedicated QR migrator provisioning preparation

Step 222 adds a separate recommended server-generated-password alternative:
[reviewed mechanism, consolidated preflight and commands](step222-server-generated-qr-migrator.md).
The legacy path below remains unchanged and must not be used to bypass its
logging prerequisites. Step 222 does not authorize live execution.

Source and offline tests only. No account, grant, credential, evidence, database,
directory or ACL operation was executed. The operator reported Step 202
account_missing; absence must still be checked freshly during execution.

## Exact contract

Only `lankapex_demo_qr_migrator@localhost` (25-character username) may be created.
Only the existing `lankapex_demo_db` on localhost:3306 may receive privileges.
The schema is neither created nor modified by this procedure. It must exist.
No application records are queried or changed.

The only two write statements are structurally:

```sql
CREATE USER 'lankapex_demo_qr_migrator'@'localhost' IDENTIFIED BY <bound-private-password>;
GRANT SELECT, INSERT, UPDATE, CREATE, ALTER, INDEX, REFERENCES
ON `lankapex\_demo\_db`.* TO 'lankapex_demo_qr_migrator'@'localhost';
```

The placeholder above is explanatory, not executable SQL. The password is
bound by PyMySQL, never formatted into source, command-line arguments or logs.
Every database underscore is escaped. MySQL 8.0, partial_revokes=OFF and no
active/mandatory roles are required. There is no IF NOT EXISTS, ALTER USER,
DROP USER, password reset, global grant, DELETE, DROP, GRANT OPTION or role grant.
Global USAGE is implicit for an otherwise unprivileged new account, not an
extra global capability. The existing runtime account and all other users
remain outside the write statement allowlist.

SELECT supports preservation and duplicate checks; CREATE, ALTER, INDEX and
REFERENCES support the two QR tables, foreign keys, request index and profile
unique constraint. UPDATE supports the existing Alembic version row. INSERT is
retained as the reviewed Step 201 Alembic bookkeeping allowance. No migration
is executed here, and no runtime permissions are expanded.

## Operator prerequisites and authorization

Separately authorize this exact account creation, exact grant, private DPAPI
credential creation and its file-only DACL protection. This does NOT authorize
a migration. Use the Windows admin operator that will run Step 201 later.
Use an existing authorized DBA login with metadata visibility, CREATE USER and
ability to grant the seven exact-schema privileges; do not change DBA grants
as part of this operation. The tool reads mysql.user Host only, privilege
metadata, schema existence and server flags, never authentication strings.
Pause concurrent account/role/grant administration for the operation. This is
an operator-maintained prerequisite: the script cannot prevent a separate DBA
from racing it. CREATE USER still refuses an existing exact account.

Review server general/audit/proxy logging and tracing policies for redaction of
CREATE USER authentication material. Do not run under SQL tracing, debugger,
screen/terminal capture of secrets, or client instrumentation that logs bound
parameters. --confirm-secure-logging / -ConfirmSecureLogging is an explicit
operator attestation, not automated proof of external logging behavior. Stop
if safe logging cannot be established; never disable MySQL security checks.
Step 219 adds a separately authorized metadata-only logging verifier; see
step219-qr-migrator-logging-security.md. Its strict baseline and mandatory
operator attestations do not authorize provisioning or prove universal secrecy.
Disabled general logging alone is insufficient. Do not disable operational or
security logging to force a PASS. The existing -ConfirmSecureLogging gate is
not automatically satisfied by the presence of the new source tool.

Step 208 replaces only the new QR credential location with
<verified operator profile>/AppData/Local/LankaPex/PrivateDemoQr/demo-qr-migrator.dpapi.
The shared storage helper derives the profile from the actual operator SID's
HKLM ProfileList entry, never LOCALAPPDATA. The private directory must already
have protected operator/SYSTEM-only Full Control and operator ownership. Every
existing ancestor must pass the conservative path-integrity policy and remain
handle-pinned during the operation. The directory has NOT been created or
validated live. Missing storage reports preparation-required; this script does
not create directories or modify existing runtime/JWT storage. See the Step 207
storage runbook for a separately authorized directory-preparation procedure.
The exact credential must be absent. Storage lies outside Git; never copy or
force-add it to the repository. Logging and account-administration gates remain.

## Credential design

The wrapper uses Windows cryptographic RNG for 32 bytes (256 bits), encoded as
44-character Base64. It does not ask the operator to invent or retype the new
password. It writes only CurrentUser DPAPI ciphertext, in the existing
ConvertFrom-SecureString-without-Key format used by Step 201. File creation is
exclusive CreateNew with an explicit protected operator/SYSTEM-only DACL
supplied to the .NET Framework FileStream constructor at creation. This avoids
a transient default DACL even if parent rules are non-inheritable. Only access
rules are supplied, never SACL/audit or ownership changes. The file is then
checked/protected using the existing DACL-only icacls helper.
Owner, protected inheritance, explicit operator/SYSTEM Full Control and absence
of unexpected access rules are verified before any DBA connection.

Decryptability and expected password format are checked privately. The password
is transferred to the short-lived Python child in a dedicated process-local
environment variable, not an argument or persistent setting. The prior variable
is restored in finally; SecureStrings, BSTR and byte arrays are disposed/cleared.
Managed strings/environment copies cannot guarantee physical memory erasure;
local privileged processes can inspect memory. Use a trusted operator session.
Nothing reads backend/.env or application Settings. The DBA password is entered
at a hidden interactive getpass prompt; an echoing fallback is rejected.

## Commands for later review, not execution now

No-connection/default preparation:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\provision_demo_qr_migrator.ps1
```

Expected: PASS: offline QR migrator provisioning preparation; no credentials, files or database accessed

One-time execution, ONLY after the above authorizations and prerequisites;
replace AUTHORIZED_DBA_USERNAME with the existing DBA login name:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\provision_demo_qr_migrator.ps1 -Execute -ConfirmTarget lankapex_demo_db -ConfirmAccount lankapex_demo_qr_migrator@localhost -ConfirmCredentialCreation -ConfirmAccountDdlPause -ConfirmSecureLogging -DbaUser AUTHORIZED_DBA_USERNAME
```

Expected successful output:

```text
PASS: exact QR migrator created; metadata, privileges and credential identity verified
PASS: QR migrator provisioning and protected credential checks complete; no migration performed
```

The fresh preflight rejects this username at ANY host, inaccessible metadata,
missing target schema, unexpected server/grant semantics and orphan/stale
privilege, role or proxy metadata. The new-account password must differ from
the DBA password. After CREATE and GRANT, reuse Step 202 DBA verification to
reject extra/missing grants, scope, roles, proxy or dynamic privileges. A new
connection using the generated credential checks DATABASE(), CURRENT_USER(),
login username and exact grants inside a read-only transaction. Wrapper PASS
occurs only after the final private-file metadata check.

Independent future read-only verification (separate authorization):

```powershell
& .\backend\.venv\Scripts\python.exe -I .\backend\scripts\verify_demo_qr_migrator.py --execute --confirm-target lankapex_demo_db --mode dba-metadata --dba-user AUTHORIZED_DBA_USERNAME
```

Expected: PASS: exact QR migrator account and schema-scoped privileges; read-only check complete

## STOP and separately reviewed recovery

Account DDL autocommits; rollback cannot undo CREATE USER or GRANT. No automatic
retry, drop, revoke, overwrite, password reset or file deletion is implemented.
A failure prints only a constant stage category, exits nonzero and preserves
any created file/account. Even a connection timeout can leave commit state
uncertain. Preserve the operator's stage output and keep the account/grant
administration pause until read-only review establishes the actual state.

Credential creation precedes fresh DBA absence checks. Thus an existing-account
STOP or wrong DBA password may leave a new private credential file WITHOUT a
created account. An ACL/DPAPI failure occurs before database access. A CREATE
failure may leave an account; a GRANT failure may leave an account with USAGE
only or uncertain grants. A post-check failure may leave a fully granted
account. Do not infer state solely from a missing final PASS.

Separately authorize read-only DBA metadata verification and credential-file
metadata inspection to establish state. Preserve the encrypted file even if
account creation failed. If the account exists, compare its exact grants and
credential usability through reviewed guarded checks; do not run this creation
wrapper again. Any grant correction, account removal, credential replacement,
or archival of a failed attempt requires its own reviewed procedure and
authorization, limited to the exact new migrator. Never modify the runtime
account or populated schema as recovery. No recovery mutations are automated.

Step 201 migration remains blocked until verified recoverable backup, isolated
rehearsal, writer/DDL pause and pinned preservation evidence are separately met.
