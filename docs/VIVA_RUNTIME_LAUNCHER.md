# Step 13.102 — VIVA runtime launcher

Status: `VIVA_RUNTIME_PREPARED_NOT_STARTED`. Implementation and offline tests only.
The maintenance freeze remains active. No credentials have been provisioned and
no live preflight or server startup has been performed by Codex.

## Security and configuration

The launcher uses backend `.venv`, the actual application Settings/SQLAlchemy
engine, and the unchanged `viva_tls.py` TLS 1.2+ / CERT_REQUIRED / SAN-only /
strict X.509 / pinned server certificate policy. The runtime gate additionally
checks the protected CA checksum before connecting. It pins loopback port 3306,
`lankapex_viva_db`, `lankapex_viva_runtime@127.0.0.1`, server UUID, MySQL 8.0.46,
revision `d15a8c902e64`, 45 InnoDB base tables, and 44 application model tables.
Model columns, primary keys and FK relationships are checked without requiring
the three FK names omitted by model declarations. This is a runtime inventory
gate, not a repeat of the full migration/recovery audit.

Only SELECT/INSERT/UPDATE/DELETE are accepted, on the exact schema. Grant scope
accounts for MySQL `partial_revokes` semantics; global rights, role grants,
active roles, table/column grants, grant options and extra privileges stop the
gate. Binary logging must be 1 and trust_function_creators must be 0. The
preflight uses only read-only queries in a read-only transaction and disposes
the connection pool on success or failure. It never tests write privileges by
performing a write.

`LANKAPEX_VIVA_RUNTIME=true` opts into a narrowly bound dotenv-free settings
source. All required settings must match the reviewed policy. Other modes keep
their existing source precedence. Conflicting inherited settings, inherited DB
password/JWT and external provider credentials are rejected rather than silently
replaced. Process settings are restored in `finally`, including partial credential
and preflight failures. No `.env` changes are needed.

Address book, address checkout, support and Driver Finance are proposed enabled;
AI and Stripe sandbox are disabled, rate limiting stays local. Address checkout
depends on address book AND Driver Finance. All three existing rollout services
require matching head DBA attestations and retain their request-time schema and
CHECK/uniqueness validation. `-ConfirmDbaHeadAttestation` means the operator has
reviewed the existing head migration evidence, including 18 protective triggers
and restricted runtime grants. It is an explicit operator assertion, not a fresh
independent trigger inspection or cryptographic attestation. The DML-only account
does not need TRIGGER privileges. Do not supply the switch without that evidence.

The new launcher does not configure/enable Driver private document storage.
Dotenv-only storage configuration is deliberately not imported. If document
submission is needed later, separately verify its existing protected path/ACLs
and provide the approved `DRIVER_DOCUMENT_PRIVATE_ROOT` process setting. Missing
storage remains fail-closed; this task does not enable uploads.

Source inspection and an offline import under blocked network/DB connections,
process launches, schema creation and background-thread starts found no automatic
startup migrations, seeding, database writes or external service calls. Services
are not run in the tests. Normal authenticated requests can write after startup;
therefore startup requires formal freeze release AND separate authorization.

## Credentials — operator only, Windows PowerShell 5.1

Run as the intended non-SYSTEM Windows operator. The existing reviewed registry-
derived profile, held-ancestor, owner/DACL and reparse policies are reused from
`demo_qr_credential_storage.ps1` and `demo_credential_dacl.ps1`; demo credentials
are never read. New protected objects use exclusive native creation and an
operator/SYSTEM-only DACL. Existing unsafe directories/files are rejected; their
ACLs are never repaired. Valid existing secrets are preserved.

Files are outside Git at the registered profile's
`AppData\Local\LankaPex\VivaRuntimeSecrets\runtime.dpapi` and `jwt.dpapi`.
The existing DB password is prompted securely, never reset. A new JWT uses 64
CSPRNG bytes encoded as 128 hex characters and is persisted with DPAPI CurrentUser.
No secret is accepted in argv or printed. SecureStrings, BSTRs and RNG byte arrays
are disposed/cleared where practical. The application's existing configuration
interface necessarily receives plaintext password/JWT in its private process
environment and Python memory; they are not promised to be absent from memory or
protected against a debugger running as the same operator/SYSTEM.

On any failure, preserve partial files; do not automatically retry, overwrite,
delete or reset credentials. Have the operator review the fixed stage diagnostic.
Actual operator-session ACL/DPAPI behavior and persistence must still be verified.

Provision credentials (local filesystem changes only, operator executes):

```powershell
powershell.exe -NoProfile -File "C:\Users\admin\Desktop\LankaPex\backend\scripts\provision_viva_runtime_credentials.ps1" -ConfirmCredentialProvisioning
```

Then, after reviewing the DBA head evidence, run the read-only live gate; this does
not release the freeze or start FastAPI:

```powershell
powershell.exe -NoProfile -File "C:\Users\admin\Desktop\LankaPex\backend\scripts\start_viva_backend.ps1" -PreflightOnly -ConfirmDbaHeadAttestation
```

Expected: `VIVA_RUNTIME_PREFLIGHT=PASS_READ_ONLY` and
`VIVA_RUNTIME=PASS_PREFLIGHT_ONLY; SERVER_STARTED=no`.
Any STOP requires investigation, not fallback credentials, a different target or
relaxed TLS/grants. If local execution policy blocks scripts, obtain the operator's
normal script approval/signing; these operator commands do not bypass that policy.

## Startup — NOT AUTHORIZED TO EXECUTE YET

Only after formal DBA/operator freeze release and separate server-start approval:

```powershell
powershell.exe -NoProfile -File "C:\Users\admin\Desktop\LankaPex\backend\scripts\start_viva_backend.ps1" -ConfirmDbaHeadAttestation -ConfirmMaintenanceReleased
```

Uvicorn binds **127.0.0.1:8001**, with no reload and no access logging; application
logging remains INFO and SQL parameters are hidden. Both current
`frontend/.env.local` and `.env.example` select
`http://127.0.0.1:8001/api/v1`. Explicit frontend origins are
`http://127.0.0.1:5173` and `http://127.0.0.1:5176`.
No frontend startup, migrations or automatic database setup are performed.

## Offline verification

26 Python runtime tests, 29 PowerShell launcher assertions, and 26 existing TLS /
dotenv regression tests passed. Four Python files compile and four PowerShell
files parse. The test environment uses fictional credentials, mocked DB/socket
results, blocked network operations, and substituted child/credential interfaces.
The two real credential-reader negative cases use a nonexistent test path and a
non-credential test source file. No operator credential is read.

Native credential provisioning, actual MySQL identity/schema/grants/TLS and normal
application request behavior are still runtime checks. The reported migration
and 18-trigger state remain operator-provided evidence, not independently queried
in this task. No database connections, records, migrations, grants, global
settings, historical evidence or existing launchers were changed.

## Step 13.110 — CORS correction, restart required

The previous dedicated VIVA list was
`http://127.0.0.1:5173,http://localhost:5173`. The corrected list is
`http://127.0.0.1:5173,http://127.0.0.1:5176` in both the launcher and the exact
dotenv-isolation policy. No wildcard or production policy change was made.
The preflight automatically validates the new list through its existing policy
comparison; its database/TLS/credential checks are unchanged.

Read-only HTTP observations before this change: GET `/` and OPTIONS
`/api/v1/auth/login` from 5173 returned 200 with the matching allow-origin header;
GET from 5176 lacked that header. Thus the missing 5176 allowance is confirmed.
The reported earlier failure for origin 5173 was not reproduced and must not be
attributed to that omission. The exact earlier request/status/running-process
configuration would be needed if the issue recurs from 5173.

The existing HTTP security middleware already allows POST and OPTIONS, plus
Authorization and Content-Type headers, using bearer authentication rather than
cross-origin cookies. Offline tests exercise the actual application's preflight
and missing-credential POST validation responses for both approved origins and
reject other origins. TestClient runs in-process without HTTP or MySQL transport;
only Windows' internal event-loop socketpair handshake is exempted from the test
network guard.

The current frontend `.env.local` and example both point to port 8001, and
`authService.js` posts OAuth2 form data to `/auth/login` through that shared base
URL. They require no edits. Do not restart automatically: the operator must stop
the current backend with Ctrl+C and invoke the existing startup command above,
only with valid DBA attestation and maintenance-release confirmation. A fresh
operator terminal must not inherit the obsolete CORS value; conflicting inherited
settings still fail closed. No running process has been reconfigured by this edit.

After that operator-controlled restart, verify both preflights without logging in:

```powershell
$ErrorActionPreference='Stop'; foreach($port in @(5173,5176)){$origin='http://127.0.0.1:'+$port;$r=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8001/api/v1/auth/login' -Method OPTIONS -Headers @{Origin=$origin;'Access-Control-Request-Method'='POST';'Access-Control-Request-Headers'='content-type,authorization'} -TimeoutSec 10;if($r.StatusCode -ne 200 -or $r.Headers['Access-Control-Allow-Origin'] -ne $origin -or $r.Headers['Access-Control-Allow-Methods'] -notmatch '\bPOST\b'){throw ('CORS verification failed for '+$origin)};Write-Output ('CORS=PASS; ORIGIN='+$origin+'; STATUS=200; POST_PREFLIGHT=ALLOWED')}
```
