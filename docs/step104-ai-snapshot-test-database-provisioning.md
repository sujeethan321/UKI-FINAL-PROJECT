# Step 104 — Guarded AI snapshot integration-test database provisioning

Status: **source preparation complete; live provisioning is BLOCKED pending separate DBA and operator authorizations.** No MySQL connection, schema/account creation, grant, credential creation, migration, integration test, or external AI request is performed by this preparation.

## Fixed identities and separation

- Database: `lankapex_ai_snapshot_test_db`
- Runtime: `lankapex_ai_snap_runtime@localhost`, global `USAGE` plus exact-schema DML only
- Temporary migrator: `lankapex_ai_snap_migrator@localhost`, global `USAGE` plus the exact reviewed schema privileges
- Migration environment: `APP_ENV=ai_snapshot_migration`
- Runtime environment: `APP_ENV=ai_snapshot_testing`
- Revision: `7b9e4d2c8a15`; 28 application tables plus `alembic_version`

The migration and runtime accounts use different DPAPI CurrentUser files. Neither wrapper reads `backend/.env` for its database identity. AI is forced off and `GROQ_API_KEY` is cleared in both test processes.

The usernames are respectively 24 and 25 characters and comply with MySQL's 32-character account-name limit. Backend settings reject every `MYSQL_USER` longer than 32 characters before a connection attempt.

## DBA read-only inventory

Run in an authorized MySQL administrator session. Do not place passwords in the transcript.

The complete fail-closed inventory, including similarly named objects and grant metadata, is now maintained in [Step 105](step105-ai-snapshot-dba-inventory.md) and `backend/scripts/inventory_ai_snapshot_dba.sql`. The shorter queries below remain a reference only.

```sql
SELECT UTC_TIMESTAMP(6) AS checked_utc, CURRENT_USER() AS checking_account;
SELECT SCHEMA_NAME FROM information_schema.SCHEMATA
 WHERE SCHEMA_NAME = 'lankapex_ai_snapshot_test_db';
SELECT 'tables_or_views' AS object_kind, COUNT(*) AS object_count
  FROM information_schema.TABLES WHERE TABLE_SCHEMA = 'lankapex_ai_snapshot_test_db'
UNION ALL SELECT 'routines', COUNT(*) FROM information_schema.ROUTINES
 WHERE ROUTINE_SCHEMA = 'lankapex_ai_snapshot_test_db'
UNION ALL SELECT 'events', COUNT(*) FROM information_schema.EVENTS
 WHERE EVENT_SCHEMA = 'lankapex_ai_snapshot_test_db'
UNION ALL SELECT 'triggers', COUNT(*) FROM information_schema.TRIGGERS
 WHERE TRIGGER_SCHEMA = 'lankapex_ai_snapshot_test_db';
SELECT User, Host FROM mysql.user
 WHERE User IN ('lankapex_ai_snap_runtime', 'lankapex_ai_snap_migrator',
                'lankapex_ai_snapshot_test_runtime',
                'lankapex_ai_snapshot_test_migrator')
   AND Host = 'localhost';
SHOW VARIABLES LIKE 'partial_revokes';
```

If the schema or either account exists, STOP. Inventory it and review ownership rather than running the creation template. The target must be absent before provisioning and completely empty before migration.

The failed Step 107 provisioning created the database before MySQL rejected the former 33/34-character usernames. For that preserved partial state, do **not** rerun `CREATE DATABASE`. A DBA must freshly confirm: the exact schema exists, it has zero tables/views/routines/events/triggers, both new accounts are absent, both former overlength accounts are absent, and there are no grant rows for any of the four names. Only then may a separately authorized continuation start at the two `CREATE USER` statements below. The original database-creation statement remains documented for a clean, never-started provisioning operation.

## Separately authorized DBA creation template

Use fresh strong passwords entered privately by the DBA. Do not use `IF NOT EXISTS`, because that would hide an unexpected pre-existing target.

```sql
CREATE DATABASE `lankapex_ai_snapshot_test_db`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'lankapex_ai_snap_runtime'@'localhost' IDENTIFIED BY '<private runtime password>';
CREATE USER 'lankapex_ai_snap_migrator'@'localhost' IDENTIFIED BY '<private migrator password>';
GRANT SELECT, INSERT, UPDATE, DELETE
  ON `lankapex\_ai\_snapshot\_test\_db`.*
  TO 'lankapex_ai_snap_runtime'@'localhost';
GRANT SELECT, INSERT, UPDATE, CREATE, ALTER, INDEX, REFERENCES
  ON `lankapex\_ai\_snapshot\_test\_db`.*
  TO 'lankapex_ai_snap_migrator'@'localhost';
SHOW GRANTS FOR 'lankapex_ai_snap_runtime'@'localhost';
SHOW GRANTS FOR 'lankapex_ai_snap_migrator'@'localhost';
```

Every underscore is escaped so the grant is a literal schema name, not a MySQL wildcard pattern. The migrator does not receive `DELETE` or `DROP`; its only DML permissions are the `SELECT`, `INSERT`, and `UPDATE` operations Alembic needs for `alembic_version`. Global DDL, `GRANT OPTION`, and access to development, demo, QR test, restore, or rehearsal schemas are not required.

## Private Windows credentials (separate authorization)

From the repository root in Windows PowerShell 5.1, create each file once under the same Windows administrator account that will run its wrapper. These commands refuse overwrite and never print the secret.

```powershell
$dir = '.server-logs\private-ai-tests'
New-Item -ItemType Directory -Path $dir -Force | Out-Null
$path = Join-Path $dir 'ai-snapshot-test-migrator.dpapi'
if (Test-Path -LiteralPath $path) { throw 'Migrator credential already exists; STOP and review.' }
$secret = Read-Host 'AI snapshot test migrator password' -AsSecureString
try { $secret | ConvertFrom-SecureString | Set-Content -LiteralPath $path -Encoding ASCII -NoNewline }
finally { $secret.Dispose() }
```

After migration succeeds and before integration tests are separately authorized, repeat with path `ai-snapshot-test-runtime.dpapi` and the runtime password. Do not copy DPAPI blobs to another Windows user.

## Guarded migration commands

Read-only preflight after DBA setup and migrator credential creation:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\migrate_ai_snapshot_test_database.ps1
```

Expected:

```text
PASS: exact empty AI snapshot target/migrator/grant and 16-revision graph
READ-ONLY PREFLIGHT COMPLETE; no migration executed
```

One-time execution requires a fresh passing preflight, a maintained writer/DDL pause, and separate explicit authorization:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\migrate_ai_snapshot_test_database.ps1 -Execute -ConfirmTarget lankapex_ai_snapshot_test_db -ConfirmEmpty -PauseVerified
```

The runner rechecks identity, account, grants, MySQL prerequisites, revision graph, and emptiness immediately before Alembic. It applies only the fixed 16-revision graph ending at `7b9e4d2c8a15`, then requires exactly 29 tables, no model/schema differences, and zero application rows. SQL classification rejects cross-schema access, database/table drops, truncation, cleanup DML, schema creation, and renames. The migrator has no `DROP` privilege. Reviewed migrations replace some check constraints through `ALTER TABLE ... DROP CHECK`, which is covered by the exact-schema `ALTER` privilege.

On failure, STOP. MySQL DDL is non-transactional, so preserve the partial target and sanitized console evidence. Do not retry, stamp, downgrade, reset, drop, or recreate it automatically. DBA/operator review and a separately authorized recovery decision are required. A successful or partial execution makes the target nonempty, so later preflights fail closed.

After successful validation, the temporary migrator account should be retired by the DBA only under a separate authorization. The application and integration-test launcher use the DML-only runtime account; neither tool automatically revokes grants or drops the migrator account.

## Runtime and test boundary

After migration, create the runtime DPAPI file and run the existing runtime preflight through `run_ai_snapshot_integration_tests.ps1` without `-Execute`. Integration execution remains separately authorized. The runtime account is DML-only and exact-schema scoped. The application configuration has distinct exact allowlists for migration and runtime environments, and neither mode accepts `lankapex_db`, `lankapex_demo_db`, `lankapex_test_db`, or a rehearsal database.
