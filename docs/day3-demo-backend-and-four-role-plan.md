# Day 3: demo backend and four-role preparation

Scope of this checkpoint: read-only/source review and local launch-gate
preparation. No API server was started and no demo record was inserted.
Phase 3.8 remains blocked; `lankapex_db`, `lankapex_test_db`, rehearsal
databases and backups were not changed.

## Day 2 baseline and runtime gates

The [Day 2 evidence](day2-demo-database-preparation.md) records one successful
empty-schema migration of `lankapex_demo_db`: head `14c0d3e2f782`, 25 empty
application tables plus `alembic_version`, no model/schema difference and no
seed records. A separate read-only check showed the normal development
configuration still at `lankapex_db` revision `c9d5e8f7a237`. Do not rerun
the empty-schema migration preflight: the demo schema is intentionally nonempty
after migration.

The operator previously reported the runtime account has only standard global
`USAGE` and `SELECT, INSERT, UPDATE, DELETE` on the exact escaped demo scope.
Independent verification **has not run**: neither a
`LANKAPEX_DEMO_DB_PASSWORD` process value nor
`.server-logs/private-demo/demo-app.dpapi` exists in this execution context.
The runtime grant and actual account are therefore **BLOCKED** pending a
private credential handoff. Never substitute the migrator credential.

The [read-only runtime checker](../backend/scripts/check_demo_backend.py)
requires effective `APP_ENV=development`, `MYSQL_DATABASE=lankapex_demo_db`,
`MYSQL_USER=lankapex_demo_app`, actual `SELECT DATABASE()` and
`CURRENT_USER()`, revision `14c0d3e2f782`, exactly 25 model tables plus
`alembic_version`, no active role and **exactly** the four expected DML
privileges on the escaped demo scope. Extra global/schema/DDL rights fail.
Its exception output omits SQL, URLs and secrets. The
[runtime preflight wrapper](../backend/scripts/preflight_demo_runtime.ps1)
sets process-local demo variables from a Windows DPAPI CurrentUser blob,
executes only that checker and restores prior environment. Python and
PowerShell syntax checks passed. No live checker result exists yet.

The operator can create the private blob under their own Windows `admin`
identity with the following commands from the repository root. The prompt
does not echo the password. The resulting file stays in ignored
`.server-logs/private-demo`; verify ACLs permit only the operator and SYSTEM.
Do not paste either the password or blob into chat:

```powershell
$privateDemoDir = Join-Path (Get-Location) '.server-logs/private-demo'
New-Item -ItemType Directory -Path $privateDemoDir -Force | Out-Null
$privateDemoSecret = Read-Host 'Demo runtime database password' -AsSecureString
$privateDemoSecret | ConvertFrom-SecureString |
  Set-Content -LiteralPath (Join-Path $privateDemoDir 'demo-app.dpapi') -NoNewline
$privateDemoSecret.Dispose()
```

Then the operator (or an approved process under that same Windows identity)
may run **only** the read-only gate:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File .\backend\scripts\preflight_demo_runtime.ps1
```

Record its sanitized PASS/STOP output. Stop if any account, grant, revision or
table check fails. No demo server starts from this command.

## Separate launch and API contract

The [demo launcher](../backend/scripts/start_demo_backend.ps1) now reads the
same private runtime credential, pins the demo schema/account and process
`APP_ENV=development`, requires a distinct demo JWT signing secret in
`LANKAPEX_DEMO_JWT_SECRET_KEY`, runs the identity/grant checker again, and only
then launches FastAPI on `127.0.0.1:8001`. It never edits `backend/.env`.
Do **not** run it at this checkpoint. A demo JWT secret must be provisioned
privately and kept separate from the normal development secret before launch.

FastAPI's generated OpenAPI paths were inspected in memory without a DB
connection: 83 paths, including all checked Day 3 routes. The common prefix is
`/api/v1`. The key paths are `POST /auth/register/shop-owner`,
`POST /auth/register/customer`, `POST /auth/register/driver`,
`POST /auth/login`, `GET /auth/me`, `POST /shop-owner/businesses`,
`POST /driver/profile`, `PATCH /admin/businesses/{business_id}/decision`,
`PATCH /admin/drivers/{user_id}/decision`, and `GET /admin/overview`.
JWT authentication and role/ownership policies remain active.

Current `frontend/.env.local` sets
`VITE_API_URL=http://127.0.0.1:8000/api/v1`; the demo API launcher uses
port 8001. A future separate frontend process must override
`VITE_API_URL=http://127.0.0.1:8001/api/v1` without changing the normal
frontend file. The frontend service layer uses `/api/v1` as its base and
routes requests to the listed paths. No frontend was launched here.

## Synthetic four-role data and demonstration plan — not executed

1. After runtime gate and explicit demo-data authorization, provision one
   synthetic Administrator using the reviewed local
   `backend/scripts/provision_admin.py` entry point, privately prompted for
   its password and with exact `--confirm-database lankapex_demo_db`. This
   cannot be done through public registration and must never target another
   schema. Record only synthetic identifiers, not credentials.
2. Register one synthetic Shop Owner, Customer and Driver through their real
   `/auth/register/*` routes. Login and verify `/auth/me` role/account state
   for each. Use unique example-only identities and keep their passwords
   outside source control and reports.
3. Have the Owner submit a pending synthetic business. Have the Admin approve
   it using the actual Admin business decision route. Verify owner context
   and the approval audit; no direct SQL status update or self-approval.
4. Have the Driver submit their own vehicle/profile through `/driver/profile`.
   Confirm pending review and ineligible job access, then have the Admin
   approve through the Driver decision route. Recheck eligibility using the
   existing Driver session.
5. Link the synthetic Customer to the approved business through the existing
   Owner customer/credit-account workflow. Verify Customer isolation and the
   empty starting ledger. Do not create financial entries during this
   account-preparation checkpoint.
6. The later end-to-end demo can show category/product publication, Customer
   browse/cart and cash or credit order, Owner decision, delivery request,
   approved Driver acceptance/status updates, Customer tracking, notification
   inboxes, and Admin overview. Use real API records, not mock data. For the
   financial segment, prestate expected sale, partial repayment and closing
   balance, then compare both Owner and Customer views with the ledger.

Verify every stage's HTTP status and persisted result, reload each role's
page, and test one wrong-role or cross-owner request. Keep synthetic data
strictly within `lankapex_demo_db`. Do not claim the browser journey passed
until it is observed.

## Readiness decision

| Gate | Result |
|---|---|
| Day 2 demo schema and migration evidence | PASS (historical Day 2 execution) |
| Runtime checker and launcher syntax | PASS (static only) |
| Required FastAPI routes in generated OpenAPI | PASS (source/import only) |
| Frontend URL points to separate demo API | FAIL at current default; process-only override planned |
| Private runtime credential | NOT PROVISIONED in this context |
| Actual runtime account/permissions/database/revision | BLOCKED pending credential and read-only gate |
| Distinct demo JWT secret | NOT PROVISIONED |
| Four-role records and browser workflow | NOT RUN |

**Next exact step:** operator creates `demo-app.dpapi` privately, then run the
read-only `preflight_demo_runtime.ps1` under the same Windows identity. Do not
start the backend or insert data until that output is reviewed.

The table and next step above record the **earlier checkpoint**. The later
operator-reported runtime PASS and JWT preparation are recorded below; the
current next step is a separately instructed backend launch using the command
in the final section, followed by the frontend launch and read-only health
checks. Four-role data creation remains unstarted.

## Runtime checker import-path correction

Direct script execution made `backend/scripts` Python's first search path;
`app` is a sibling directory under `backend`. The wrapper correctly selected
`backend/.venv/Scripts/python.exe` and changed its working directory to
`backend`, but direct script execution does not guarantee that the working
directory is on `sys.path`. A database-free reproduction found SQLAlchemy
importable and `app` missing with the script-directory-only import path.

The checker now inserts its own parent `backend` directory into `sys.path`
before importing `app`. It reports `ModuleNotFoundError.name` without printing
connection configuration or secrets. Its database identity, account, final
revision, 26-table inventory and exact DML-only grant checks were not changed.
Database-free syntax/import checks passed from both the repository root and
the frontend directory; an intentionally disabled site-packages run printed
the missing module name `sqlalchemy` and opened no database connection.
The live runtime preflight is still **NOT RUN** after this correction.

## Launch preparation after operator-reported runtime PASS

The operator subsequently reported the live read-only runtime result:
`PASS: demo API exact target/account, 26-table schema, revision and DML-only
grant`. This is a supplied preflight result; the backend was not started by
this preparation task.

A fresh demo JWT signing secret was generated from 48 cryptographically random
bytes and stored as a Windows DPAPI CurrentUser blob at ignored
`.server-logs/private-demo/demo-jwt.dpapi`. The value was never printed or
placed in source, command arguments or logs. Read-only verification under
`DESKTOP-00P7UEF\admin` confirmed that the blob decrypts to the expected
64-character Base64 representation, its ACL contains only that account and
SYSTEM, and Git ignores the path. The creation script refuses to overwrite
an existing secret. The runtime database credential remains a separate DPAPI
blob; neither is copied into Git.

The backend launcher now decrypts both blobs in memory, sets process-only
`APP_ENV=development`, `MYSQL_HOST=localhost`, `MYSQL_PORT=3306`,
`MYSQL_DATABASE=lankapex_demo_db`, `MYSQL_USER=lankapex_demo_app` and the
demo-only JWT key, then runs `check_demo_backend.py` before opening
`127.0.0.1:8001`. It restores its caller's prior environment and clears
unmanaged BSTR buffers when the server exits. The runtime check still
requires actual target/account, revision, table inventory and DML-only grant.
No normal backend or frontend environment file was edited.

The separate frontend launcher sets process-only
`VITE_API_URL=http://127.0.0.1:8001/api/v1` and starts Vite on
`127.0.0.1:5173` with strict port matching the development CORS allowlist.
Vite `loadEnv` returned that override despite the existing `.env.local`
port 8000. Both launch scripts' PowerShell syntax passed. A database-free
synthetic configuration import confirmed FastAPI can load with the exact demo
environment and 83 OpenAPI paths while `Engine.connect` was blocked. It used
synthetic, non-credential strings, not the real secrets. No backend or frontend
server was started.

When separately instructed to start the demonstration, use two Windows
PowerShell terminals. Launch the backend under the `admin` identity that owns
both DPAPI files; it will fail closed if the live runtime gate fails:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File "C:\Users\admin\Desktop\LankaPex\backend\scripts\start_demo_backend.ps1"
```

After the backend confirms its identity and port, launch the frontend in a
second terminal. Its process-only URL override leaves `.env.local` alone:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File "C:\Users\admin\Desktop\LankaPex\frontend\scripts\start_demo_frontend.ps1"
```

Expected endpoints are backend `http://127.0.0.1:8001/api/v1/health` and
frontend `http://127.0.0.1:5173`. Verify no other service already owns either
port. Startup alone does not authorize synthetic account provisioning, data
seeding or a change to `lankapex_db`. Phase 3.8 remains blocked.

## Four-role setup review after demo launch

The operator reports the API and frontend on ports 8001 and 5173. A fresh
`GET /api/v1/health/database` returned `status=ok`. This public response does
not expose the schema name or user count. The launch script pins
`APP_ENV=development`, `MYSQL_DATABASE=lankapex_demo_db` and
`MYSQL_USER=lankapex_demo_app`, then runs the read-only exact-target gate before
starting Uvicorn. A fresh gate from this execution identity failed to decrypt
the operator's DPAPI CurrentUser credential (`ConvertTo-SecureString`
cryptographic error); process inventory was access-denied. The running
instance's exact database identity and current `users` count are therefore
**not independently reconfirmed**. The Day 2 zero-user result is historical.

Before any write, the operator should run `preflight_demo_runtime.ps1` under
the Windows identity owning the DPAPI blobs, then use the privately prompted
demo runtime account for these read-only queries:

```sql
SELECT DATABASE() AS database_name, CURRENT_USER() AS account_name;
SELECT COUNT(*) AS users_count FROM lankapex_demo_db.users;
```

Expected: `lankapex_demo_db`, `lankapex_demo_app@localhost`, and
`users_count=0`. Stop if any result differs. Do not paste passwords, tokens
or DPAPI material into chat, command arguments, Git or reports.

The public registration routes are `POST /api/v1/auth/register/shop-owner`,
`/customer` and `/driver`. Their input includes `full_name`, `email`, a
password of at least 12 characters, optional `phone`, and
`preferred_language`. The service uses the recommended `pwdlib` password
hasher, assigns the requested public role server-side, and creates an active
account. Login is `POST /api/v1/auth/login` with OAuth2 form `username`
(email) and `password`; `GET /api/v1/auth/me` confirms the JWT identity.
There is no public Admin registration. The reviewed operator-only
`backend/scripts/provision_admin.py` privately prompts for the password and
requires `--confirm-database lankapex_demo_db`; run it only with a freshly
verified demo process environment. Do not insert a hash or promote a user
directly in SQL.

Proposed sequence after separate authorization for synthetic demo writes:

1. Verify the exact schema/account, revision and empty `users` table. Choose
   four unique fictional identities and strong passwords, kept in a private
   credential manager outside Git and logs.
2. Provision the Admin with the reviewed local operator script, then log in
   and confirm `/auth/me` reports `platform_role=admin`.
3. Register the Shop Owner, Customer and Driver through their existing public
   routes or UI. Log in to each separately; verify `/auth/me` and dashboard.
4. As Owner, create one fictional grocery business using
   `POST /api/v1/shop-owner/businesses`. Confirm its pending state. As Admin,
   approve it through `PATCH /api/v1/admin/businesses/{business_id}/decision`
   with `{"decision":"approve"}`; verify the owner business context.
5. As Driver, submit fictional vehicle details through
   `POST /api/v1/driver/profile`. Confirm pending approval and no job access.
   As Admin, approve through `PATCH /api/v1/admin/drivers/{user_id}/decision`
   with `{"decision":"approve"}`. Recheck profile eligibility.
6. As Owner, create a few fictional categories and published, available
   products through `/api/v1/shop-owner/categories` and `/products` using the
   approved business ID and decimal-string LKR prices. As Customer, verify
   the shop and products appear in `/api/v1/customer/catalogue/shops`. The
   supported cash-order workflow can then be exercised without ledger data.

**Credit demo dependency:** `POST /shop-owner/customers` creates
`CustomerProfile.user_id=None`. Public Customer registration does not link
that profile; customer dashboard and credit checkout require a persisted
`CustomerProfile.user_id` match. Therefore a shop-created customer or credit
account cannot be assumed visible to the registered demo Customer. Do not
link by phone or direct SQL. Implement and test an authorized account-link
workflow before demonstrating credit, or defer credit and use cash orders.
This corrects the earlier plan's implied Customer link.

No accounts, profiles, businesses, catalogue records, orders or ledger
entries were created during this review. Registration, Admin provisioning,
approvals and catalogue creation require separate synthetic-demo-data
authorization. The read-only identity/count gate does not. No other database,
backup or Phase 3.8 state is part of this setup.

## Authorized setup attempt: operator identity gate

The operator reported a passing live runtime preflight and zero users, and
authorized synthetic writes to the exact demo database. Immediately before
the first write, this execution context reran the read-only gate. It ran as
`DESKTOP-00P7UEF\codexsandboxoffline`; the DPAPI CurrentUser credential was
created under the operator's Windows identity and could not be decrypted here.
`ConvertTo-SecureString` raised `CryptographicException`. The unauthenticated
`/api/v1/health/database` endpoint returned `status=ok`, but it does not prove
the connection's schema or account. The exact-target prewrite condition did
not pass in this context, so the attempt stopped before Admin provisioning.

| Stage | Result | Evidence |
|---|---|---|
| Fresh exact-target runtime gate in this execution context | FAIL | DPAPI CurrentUser decryption error |
| Demo API database health | PASS, limited | HTTP health response `status=ok`; no schema identity |
| Fresh `users` count in this execution context | BLOCKED | No private demo account credential available |
| Admin provisioning | NOT RUN | Prewrite gate did not pass |
| Three public registrations and `/auth/me` checks | NOT RUN | Prewrite gate did not pass |
| Business submission/approval | NOT RUN | No Admin or Owner account created |
| Driver profile/approval | NOT RUN | No Admin or Driver account created |
| Fictional catalogue | NOT RUN | No approved business or Owner account |

Resume only from an operator terminal under the Windows identity that owns
the DPAPI blobs. Rerun the strict read-only preflight and zero-user query
immediately before the first write, verify the exact demo target, and use the
reviewed operator bootstrap followed by the supported role APIs. Keep all
four passwords privately prompted; do not copy the DPAPI blob, credentials or
bearer tokens to this execution identity. If any stage differs from the
expected role, state or HTTP result, stop before the next write. No account,
business, driver profile, product, credit record or other data was changed in
this attempt.

## One-time demo Admin bootstrap preparation

The operator reported a fresh read-only PASS for the demo runtime account,
`SELECT DATABASE()=lankapex_demo_db`,
`CURRENT_USER()=lankapex_demo_app@localhost` and `users_count=0`. This is
operator-provided evidence; the sandbox cannot decrypt the operator's DPAPI
CurrentUser blobs, so it has not independently executed a live database
count. Authorization is limited to one synthetic Admin record.

The new [operator wrapper](../backend/scripts/provision_demo_admin.ps1)
decrypts the existing demo runtime and JWT blobs only under their owning
Windows account, sets process-only exact demo configuration, runs the
read-only `check_demo_backend.py` gate, then calls the existing
`scripts.provision_admin` module with `--demo-only` and the literal
`--confirm-database lankapex_demo_db`. It restores prior process environment
and frees unmanaged secret buffers when finished. Password entry uses the
existing two hidden `getpass` prompts; no password or token appears in
arguments or success output. The [CLI](../backend/scripts/provision_admin.py)
now checks the literal demo database, development mode, runtime account,
engine target and actual `SELECT DATABASE()`/`CURRENT_USER()`. Immediately
after the private prompt and before the insert, it checks the actual target
again and requires exactly zero users. It verifies one active Admin user
before and after commit and prints only a sanitized PASS. A wrong target is
rejected before connecting or prompting. No direct hash insertion is used:
the existing service hashes with `pwdlib` and writes an audit event.

From a PowerShell terminal signed in as the Windows `admin` account that owns
the private DPAPI files, with no transcript or command logging of secrets,
run exactly once from any directory:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File "C:\Users\admin\Desktop\LankaPex\backend\scripts\provision_demo_admin.ps1"
```

Expected sanitized output: the read-only checker PASS, two private password
prompts, then `PASS: demo Admin active; users_count=1`. If the gate, prompt,
count or verification fails, stop and inspect the resulting state before any
retry. This command creates only the synthetic Admin and its Admin audit row;
it does not register the other roles or create business, driver, catalogue or
financial records. PowerShell syntax, Python compilation, and a database-free
wrong-target rejection passed. The live operator run is **NOT YET EXECUTED**
in this context, so provisioning status remains **BLOCKED pending the operator
command and its sanitized result**.

## Admin bootstrap input failure diagnosis and safe retry

The operator reported that the runtime gate passed but the Admin bootstrap
ended with `Invalid input or an existing non-Administrator account` after the
password prompt. A database-free Pydantic reproduction confirmed the wrapper's
original default `demo.admin@example.test` fails `EmailStr` validation even
with a valid synthetic password. `demo.admin@example.com` validates. The
default address was the confirmed source-code defect; no MySQL write is
needed to reproduce it. The same old generic message could also result from
a password under 12 characters, over 128 characters, or an invalid name. A
password mismatch has its own `Password confirmation failed` message. With
the demo-only zero-users guard active, an existing non-Admin account would
also produce an earlier nonempty-users error rather than this validation
message, barring a concurrent writer. Python `getpass` receives direct
console input from the child process; its hidden typing in CMD/PowerShell is
expected. No evidence shows subprocess input forwarding failed.

The wrapper default is now `demo.admin@example.com`. The CLI now reports
only invalid field names, never values, and tells the operator that hidden
typing requires pressing Enter. A new `-CheckOnly` wrapper mode runs the
strict runtime gate and a read-only exact-target/account/zero-users query,
without prompting or writing. The normal run repeats the zero-user check
before prompting and again immediately before insertion. Exact demo target,
account, revision and grant gates remain unchanged.

Run these in an interactive PowerShell terminal signed in as the Windows
`admin` account owning the DPAPI files, not in a redirected/automated shell.
No password should be included on the command line or in a transcript:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File "C:\Users\admin\Desktop\LankaPex\backend\scripts\provision_demo_admin.ps1" -CheckOnly
```

Proceed only if it prints both the runtime gate PASS and
`PASS: exact demo database/account; users_count=0; no writes`. Then run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File "C:\Users\admin\Desktop\LankaPex\backend\scripts\provision_demo_admin.ps1"
```

The second command rechecks the target and count. At each password prompt,
type a fresh 12–128 character Admin password even though no characters or
asterisks appear, then press Enter; repeat exactly at confirmation. The
expected final line is `PASS: demo Admin active; users_count=1`. Stop on any
other result and inspect state before retrying. No account was created in
this diagnostic task. Python compilation, PowerShell parsing, Pydantic
reproduction and database-free wrong-target rejection passed.
