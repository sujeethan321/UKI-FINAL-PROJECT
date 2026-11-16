# Day 2: isolated LankaPex demo database — prepared, not executed

Target: `lankapex_demo_db` on local MySQL 8.0. The existing `lankapex_db`,
`lankapex_test_db`, and all `lankapex_migration_verify_*` schemas are outside
this procedure. Phase 3.8 remains blocked. Nothing in this document authorizes
database creation, grants, or migration execution.

## DBA review and manual provisioning

Use an already authorized DBA session. First record the server identity and
whether the target and account names already exist. Review any existing object
or grant before issuing the creation statements. Do not paste credentials or
financial rows into tickets or chat.

```sql
SELECT UTC_TIMESTAMP(6) AS observed_at_utc, @@hostname AS server_name,
       @@port AS server_port, CURRENT_USER() AS observer, @@version AS mysql_version;
SELECT SCHEMA_NAME FROM information_schema.SCHEMATA
 WHERE SCHEMA_NAME = 'lankapex_demo_db';
SELECT USER, HOST FROM mysql.user
 WHERE USER IN ('lankapex_demo_migrator', 'lankapex_demo_app');
```

**Only if the schema is absent**, and after DBA review, run:

```sql
CREATE DATABASE IF NOT EXISTS `lankapex_demo_db`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
```

The `IF NOT EXISTS` protects against an accidental repeated create; it does
not certify that an existing schema is empty or compatible. Stop if it already
exists and inspect it instead. The DBA should privately create two new,
different strong passwords using the organization's credential procedure;
the following placeholders are **not passwords**. Use a client/procedure that
does not record the completed secret-bearing SQL in shared logs or history.
Only if the exact accounts are absent:

```sql
CREATE USER 'lankapex_demo_migrator'@'localhost'
  IDENTIFIED BY '<DBA_SUPPLIES_PRIVATE_MIGRATOR_SECRET>';
CREATE USER 'lankapex_demo_app'@'localhost'
  IDENTIFIED BY '<DBA_SUPPLIES_PRIVATE_APP_SECRET>';
```

Review and apply these database-scoped grants. The backslashes before every
underscore in the **grant scope** are intentional for MySQL 8.0 database-name
wildcard handling; verify the escaped scope in `SHOW GRANTS`. Do not give either
account global privileges or `GRANT OPTION`.

```sql
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES
  ON `lankapex\_demo\_db`.* TO 'lankapex_demo_migrator'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE
  ON `lankapex\_demo\_db`.* TO 'lankapex_demo_app'@'localhost';
SHOW GRANTS FOR 'lankapex_demo_migrator'@'localhost';
SHOW GRANTS FOR 'lankapex_demo_app'@'localhost';
```

If the server's `partial_revokes` setting or grant display changes how exact
database scopes are represented, stop for DBA review rather than broadening
either grant. The migrator has only the DML and DDL rights required by this
reviewed chain; the runtime account has no DDL rights. The migrator credentials
must never be used to launch the app.

## Independent read-only preflight

The DBA should record the exact database name, four zero object counts, both
account grants, and MySQL 8.0 version. Inspect the target with DBA visibility:

```sql
SELECT UTC_TIMESTAMP(6) AS observed_at_utc,
       (SELECT COUNT(*) FROM information_schema.TABLES
         WHERE TABLE_SCHEMA='lankapex_demo_db') AS tables_and_views,
       (SELECT COUNT(*) FROM information_schema.ROUTINES
         WHERE ROUTINE_SCHEMA='lankapex_demo_db') AS routines,
       (SELECT COUNT(*) FROM information_schema.EVENTS
         WHERE EVENT_SCHEMA='lankapex_demo_db') AS events,
       (SELECT COUNT(*) FROM information_schema.TRIGGERS
         WHERE TRIGGER_SCHEMA='lankapex_demo_db') AS triggers;
```

In a **separate process**, set `APP_ENV=development`, `MYSQL_HOST=localhost`,
`MYSQL_PORT=3306`, `MYSQL_DATABASE=lankapex_demo_db`,
`MYSQL_USER=lankapex_demo_migrator`, and `MYSQL_PASSWORD` to the migrator secret
through the operator's private credential mechanism. Do not edit `backend/.env`.
From the repository root, run the exact-target runner in default read-only mode:

```powershell
.\backend\.venv\Scripts\python.exe .\backend\scripts\prepare_demo_database.py --database lankapex_demo_db
```

It requires the explicit process environment and verifies the effective
settings, DBAPI target, `SELECT DATABASE()`, `CURRENT_USER()`, MySQL strict/FK
settings, active roles, exact escaped grant, empty tables/views/routines/events/
triggers, 14-revision graph and 25 models. A failed condition means **STOP**.
No application rows or schemas are changed by this preflight.

## Migration command — proposed, NOT authorized or run

Only after both independent and runner preflights pass, the target is confirmed
empty, and the user explicitly approves this demo-only execution, use the same
private migrator environment to run **once**:

```powershell
.\backend\.venv\Scripts\python.exe .\backend\scripts\prepare_demo_database.py --database lankapex_demo_db --execute --confirm-target lankapex_demo_db
```

The runner rejects any other `--database` value, missing confirmation,
production mode, implicit normal dotenv target, non-demo account, broad or
wildcard grants, nonempty target, and non-demo DBAPI connections. Its SQL gate
refuses database-switching/global/reset statements and references to the
development, test and previous rehearsal schemas. Alembic uses the normal
engine only within the explicitly overridden demo process. It upgrades the
empty schema in reviewed stages to `14c0d3e2f782`, then requires exactly 25
empty application tables plus `alembic_version` and no model/schema diff.
It never seeds application data.

MySQL DDL is not atomic across the chain. If any stage or validation fails,
stop; preserve the partial demo schema and sanitized error. Do not rerun,
downgrade, stamp, drop or reset it automatically. A DBA-reviewed forward fix or
newly named disposable schema needs separate approval. Keep the Phase 3.7
backup and all prior rehearsal evidence unchanged.

## Separate backend launch, after the migration passes

The source-only [demo launch script](../backend/scripts/start_demo_backend.ps1)
uses `lankapex_demo_app`, pins `lankapex_demo_db`, and starts the backend on
`127.0.0.1:8001`. The operator provides the runtime account secret privately
as `LANKAPEX_DEMO_DB_PASSWORD` and a distinct demo JWT signing secret as
`LANKAPEX_DEMO_JWT_SECRET_KEY` in that PowerShell process and invokes:

```powershell
.\backend\scripts\start_demo_backend.ps1
```

The script overrides the process environment; it does not alter the normal
`backend/.env`. Its read-only gate requires the exact demo database, runtime
account and final Alembic revision before opening the API port. Run the frontend
in a separate shell with
`VITE_API_URL=http://127.0.0.1:8001/api/v1`; do not change the existing
frontend `.env.local` for this demonstration. Verify the demo backend's
database identity before any synthetic data is inserted. Authentication and
seed creation are later, separately reviewed steps.

## Read-only preflight attempt: private credential pending

The operator reported that the DBA manually created the demo schema and two
accounts, with migrator `SELECT, INSERT, UPDATE, DELETE, CREATE, REFERENCES,
INDEX, ALTER` and runtime `SELECT, INSERT, UPDATE, DELETE` on the escaped exact
demo scope, plus only global `USAGE`. This is **operator-reported**, not yet
independently verified by the migrator preflight.

Read-only inspection of the assistant's process found no
`LANKAPEX_DEMO_MIGRATOR_PASSWORD`, `MYSQL_PASSWORD`, or demo-target process
override. `cmdkey /list` succeeded but listed no demo-related credential
target. No password was read or printed. Consequently the demo runner's live
preflight **was not launched**; actual identity, emptiness, effective grants,
MySQL settings and live database access remain **BLOCKED**. The migration
command was not run.

For a private local handoff, the operator may use Windows DPAPI CurrentUser in
their own PowerShell session. The credential blob is under ignored
`.server-logs/private-demo/` and must not be committed, uploaded or pasted.
Do not include the secret in any command argument or chat message:

```powershell
$privateDemoDir = Join-Path (Get-Location) '.server-logs/private-demo'
New-Item -ItemType Directory -Path $privateDemoDir -Force | Out-Null
$privateDemoSecret = Read-Host 'Demo migrator password' -AsSecureString
$privateDemoSecret | ConvertFrom-SecureString |
  Set-Content -LiteralPath (Join-Path $privateDemoDir 'demo-migrator.dpapi') -NoNewline
$privateDemoSecret.Dispose()
```

Run this while the current directory is the LankaPex repository root, using
the same Windows account that will execute the preflight. The encrypted blob
is machine/user-bound and is only a local handoff, not a portable backup.
Verify the directory/file ACL is limited to the operator and system identities.
The [read-only wrapper](../backend/scripts/preflight_demo_database.ps1) sets
the exact demo process variables, decrypts the blob in memory, runs only the
non-`--execute` command above, and restores its caller's previous environment.
It does not run migrations. Do not run it until the private handoff exists.

### Attempt after operator credential handoff

The operator created the DPAPI file. The first wrapper invocation was refused
by this shell's Windows execution policy before script execution. A second
invocation used a new `powershell.exe -NoProfile -ExecutionPolicy RemoteSigned`
process, changing no system policy. It stopped at `ConvertTo-SecureString`
with `CryptographicException` / `ImportSecureString_InvalidArgument_CryptographicError`
before setting demo database environment variables or launching Python.

Read-only metadata confirmed the encrypted file exists (620 bytes), is owned by
`DESKTOP-00P7UEF\admin`, and the tool process runs as
`DESKTOP-00P7UEF\codexsandboxoffline`. DPAPI CurrentUser material is therefore
not decryptable in this process identity. No secret bytes were printed, no
MySQL connection was opened by the wrapper, and no migration, schema, account,
grant or application data changed. **Live preflight: BLOCKED / NOT RUN.**

Resolve by executing the read-only wrapper in an operator-controlled process
under the same Windows identity that created the DPAPI file, or arrange an
approved credential handoff bound to the actual execution identity. Do not
copy the encrypted blob or password into chat, commit it, weaken MySQL grants,
or bypass the demo runner. The sanitized runner output is still required for
database identity, actual account, emptiness, effective grants, MySQL settings,
and graph PASS. Stop before `--execute`.

## Authorized one-time demo migration execution

The user subsequently authorized **only** the one-time migration of
`lankapex_demo_db`, conditional on a fresh passing read-only preflight. An
elevated process ran as `DESKTOP-00P7UEF\admin`, the DPAPI owner. The
read-only wrapper then returned exit 0 with: exact demo database/account,
empty schema, scoped grants, MySQL 8.0 strict/FK settings, 14 revisions,
25 modeled tables and head `14c0d3e2f782` all **PASS**. It executed no
migration during that preflight.

The wrapper was reviewed and given an explicit `-Execute` switch that runs
the same read-only preflight immediately before invoking the already reviewed
runner with `--database lankapex_demo_db --execute --confirm-target
lankapex_demo_db`. PowerShell syntax passed. Its default mode remains
read-only. The one authorized `-Execute` invocation ran once and exited 0.

| Check | Actual result | Status |
|---|---|---|
| Immediate fresh read-only gate | Exact target/account, empty tables/views/routines/events/triggers, scoped grants, MySQL 8.0 strict/FK prerequisites, 14 revisions and 25 models | PASS |
| Migration stages | Initial chain through `c9d5e8f7a237`, then `d0e6f9a8b348`, `e1f7a0b9c459`, `f2a8b1c0d560`, `03b9c2d1e671`, `14c0d3e2f782`; stage revisions checked | PASS |
| Final revision | `14c0d3e2f782` | PASS |
| Final inventory | 25 application tables plus `alembic_version` | PASS |
| SQLAlchemy model/schema comparison | No differences reported by runner | PASS |
| Application seed records | Every modeled application table count was zero | PASS |
| Normal development target | Subsequent read-only check: `SELECT DATABASE() = lankapex_db`, revision still `c9d5e8f7a237` | PASS for identity/revision; no data fingerprint check repeated |

No migration failure or retry occurred. The guarded runner's DBAPI and SQL
target gates were active for execution; it did not seed accounts or start a
backend. Test and earlier rehearsal databases, backups and unrelated data
were outside the permitted target and were not intentionally accessed or
modified. Phase 3.8 remains blocked. Day 3 synthetic demo account creation
and API launch require their own instructions and review.
