# Day 5 — Isolated demo-backup restore preparation

Status: **FAIL for the one-time isolated restore rehearsal** (2026-11-10). The previously blocked live preflight passed, but the authorized restore stopped after creating one table. The partial target is preserved; no retry, reset, migration, grant change or source-database write was performed. The protected source backup and recovery evidence are recorded in [the populated-demo readiness report](day5-demo-schema-upgrade-readiness.md).

## Pinned source and guard review

- Source dump: `.server-logs/private-demo-backups/lankapex_demo_db_20261109T175450Z_a7ace782.sql`.
- Source manifest: `.server-logs/private-demo-backups/lankapex_demo_db_20261109T175450Z_a7ace782.backup.json`.
- Independently verified SHA-256: `ede32b514a47efb4b3b06a206596ff8d23a03f9779cafc39e32099b5a654e685`.
- Source revision: `14c0d3e2f782`; 26 original tables. Its row counts, fingerprints, financial links and 53 FK checks passed. The isolated restore stopped after one table; restorability is **not** proven.
- `backend/scripts/rehearse_demo_backup_restore.py` is read-only by default, accepts only `lankapex_demo_restore_verify_20261109`, verifies the private manifest/dump checksum and statement scope, exact connected account/database, empty target, roles and escaped grants. Its future execution path rechecks target emptiness immediately before starting the MySQL client and compares all 26 restored row fingerprints to the pinned source. It cannot create a database, stamp Alembic, migrate, reset or clean up a failed target.
- Database-free negative checks: arguments naming `lankapex_demo_db`, `lankapex_db`, and `lankapex_test_db` were each rejected with exit 2 before connection. Python compilation and PowerShell parsing passed. The live target/account preflight later passed before the failed one-time restore.

## First manual DBA action — read-only inventory

In MySQL Workbench or an administrator MySQL CLI session, run the following **read-only** queries. Do not include passwords in a transcript. Record the UTC timestamp, result counts and any unexpected object names privately; share only non-sensitive evidence.

```sql
SELECT UTC_TIMESTAMP(6) AS checked_utc, CURRENT_USER() AS checking_account;
SELECT SCHEMA_NAME
  FROM information_schema.SCHEMATA
 WHERE SCHEMA_NAME = 'lankapex_demo_restore_verify_20261109';
SELECT 'tables_or_views' AS object_kind, COUNT(*) AS object_count
  FROM information_schema.TABLES
 WHERE TABLE_SCHEMA = 'lankapex_demo_restore_verify_20261109'
UNION ALL
SELECT 'routines', COUNT(*) FROM information_schema.ROUTINES
 WHERE ROUTINE_SCHEMA = 'lankapex_demo_restore_verify_20261109'
UNION ALL
SELECT 'events', COUNT(*) FROM information_schema.EVENTS
 WHERE EVENT_SCHEMA = 'lankapex_demo_restore_verify_20261109'
UNION ALL
SELECT 'triggers', COUNT(*) FROM information_schema.TRIGGERS
 WHERE TRIGGER_SCHEMA = 'lankapex_demo_restore_verify_20261109';
SELECT User, Host FROM mysql.user
 WHERE User = 'lankapex_demo_restore' AND Host = 'localhost';
SHOW VARIABLES LIKE 'partial_revokes';
```

Expected now: **zero schema rows** if the target has not been provisioned; all four object counts zero. If the schema exists, do not create another; inspect that it is empty. If any object count is nonzero, **STOP** and preserve it for review. The `mysql.user` query requires an authorized DBA; if denied, the DBA can inspect users/grants through Workbench administration. If the account already exists, inspect `SHOW GRANTS FOR 'lankapex_demo_restore'@'localhost';` before considering any grant changes. A broad or unescaped grant blocks the exact-target preflight.

## DBA setup template — separate authorization required

Only after reviewing the inventory and receiving separate authorization, the DBA may create the absent database and dedicated account. Do not run `CREATE DATABASE IF NOT EXISTS`: an existing unexpected target must be investigated. Enter the account password privately in MySQL Workbench or another approved local administrator process, never in chat or a saved SQL transcript. No password is specified here.

```sql
-- Execute only if the preceding SCHEMATA query returned zero rows.
CREATE DATABASE `lankapex_demo_restore_verify_20261109`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- The DBA substitutes a password privately before execution; never run this
-- literal placeholder or save the substituted statement in a shared log.
CREATE USER 'lankapex_demo_restore'@'localhost'
  IDENTIFIED BY '<private password entered locally by DBA>';

-- Execute only after confirming the new account has no unwanted grants.
GRANT SELECT, INSERT, CREATE, INDEX, REFERENCES, ALTER
  ON `lankapex\_demo\_restore\_verify\_20261109`.*
  TO 'lankapex_demo_restore'@'localhost';

SHOW GRANTS FOR 'lankapex_demo_restore'@'localhost';
```

The backslashes before **every underscore** make the database grant literal, rather than a wildcard pattern. Give the restore account standard global `USAGE` only. No development, test, demo-source or rehearsal-database privileges are required. The account need not have `DROP`, `GRANT OPTION` or global administrative privileges. If DBA policy requires a different account/grant, stop and review the guard; do not bypass it.

## Historical first-attempt operator procedure — do not reuse

The first restore attempt used `demo-restore.dpapi` for the original `lankapex_demo_restore` account and `lankapex_demo_restore_verify_20261109` target. That target now contains a preserved partial restore. **Do not overwrite or reuse the original credential file or target.** The current second-attempt procedure below uses the distinct `demo-restore-b.dpapi` file and `lankapex_demo_restore_b` account. The current wrapper reads only that new file.

## Authorized one-time rehearsal result

The operator had provisioned the exact empty target and restricted account. Immediately before execution, the fresh read-only preflight returned:

```text
PASS: exact empty restore target/account/grant and pinned backup checksum
READ-ONLY RESTORE PREFLIGHT COMPLETE; no restore executed
```

The reviewed `preflight_demo_restore.ps1 -Execute` command was then run **once** against `lankapex_demo_restore_verify_20261109`. It returned `STOP: Restore failed; preserve partial target` and exited nonzero. No automatic retry or cleanup occurred. A separate read-only diagnosis using the same exact-target account found **one table (`admin_audits`)**, **zero routines/events/triggers**, and **no `alembic_version` table**. The required 26 tables, revision, row fingerprints, financial fingerprints and foreign-key validation therefore **FAILED / were not reached**; none is reported as passed.

The pinned dump includes `LOCK TABLES` statements, while the reviewed least-privileged restore account lacks `LOCK TABLES`. This is the strongest supported cause of the client failure, but the runner discarded client stderr, so the exact MySQL error code was **not captured**. The guard has now been tightened to reject this dump/grant mismatch during preflight. It is a source-only safety fix; the failed target was not altered further. Any next attempt requires operator/DBA review of either a newly validated dump without lock statements or a separately approved exact-target `LOCK TABLES` grant, plus a **new empty isolated target** or separately authorized disposition of this partial one. Do not retry the same command against this target.

After the failure, the original `lankapex_demo_db` still passed its read-only identity, account, revision `14c0d3e2f782`, 26-table inventory and scoped-grant check. The pinned backup SHA-256 still matched `ede32b514a47efb4b3b06a206596ff8d23a03f9779cafc39e32099b5a654e685`. `lankapex_db`, `lankapex_test_db`, other schemas, backups and Phase 3.8 were not changed.

**Current decision: BLOCKED.** Preserve the partial restore target and its evidence. Do not run the demo migration or claim recovery is proven. The exact next operator action is read-only review of the MySQL client failure cause and the dump's `LOCK TABLES` requirement; a revised restore plan and separate authorization are needed before another execution.

## 2026-11-10 diagnosis and new-target retry preparation

**Retry status: BLOCKED; no second restore is authorized or executed.** The failed `lankapex_demo_restore_verify_20261109` remains untouched with its single `admin_audits` table. Do not reset or reuse it. Read-only inspection confirmed the pinned dump checksum above and counted 26 `CREATE TABLE`, 41 `INSERT`, 26 `LOCK TABLES`, 26 `UNLOCK TABLES`, and 26 pairs of MySQL versioned `ALTER TABLE ... DISABLE/ENABLE KEYS` statements. It has session `SET` directives, including `FOREIGN_KEY_CHECKS` and `UNIQUE_CHECKS`, but no `CREATE DATABASE`, `USE`, `DROP`, `DEFINER`, view, trigger, routine, event, `UPDATE`, `DELETE`, `REPLACE`, `LOAD DATA`, or `GRANT` statement. No row contents were displayed. The reviewed restore account lacked `LOCK TABLES`; the original runner discarded MySQL stderr. Thus the dump/grant incompatibility is confirmed, and it is the strongest explanation for the stop immediately after the first `CREATE TABLE`; the exact MySQL error code remains unknown. No other privilege gap was found in the reviewed statement classes, but live execution has not verified this conclusion.

The replacement guard accepts **only** `lankapex_demo_restore_verify_20261110b` with `lankapex_demo_restore_b@localhost`. It requires exactly `SELECT, INSERT, CREATE, INDEX, REFERENCES, ALTER, LOCK TABLES` on that database with every underscore escaped, plus global `USAGE` only and no active role. The `LOCK TABLES` privilege is scoped to the isolated target; it gives no rights on the demo source or other databases. The runner checks the pinned backup, statement inventory, actual connected identity, empty target, and exact grant before any restore. Its future MySQL failure output reports only exit code, MySQL error number, SQLSTATE, and a controlled category; raw stderr, SQL, rows, and credentials are discarded. This improves diagnosis but cannot recover the first attempt's missing error code.

Static validation passed: Python compilation, PowerShell parsing, rejection of the original demo, development, test, and failed restore targets before connection, and a synthetic 1142 error-sanitization check. A live preflight of the new target is **BLOCKED** until a DBA provisions the separate database/account/grant and the operator stores the new private credential. No second restore or database-changing command was run.

First, an authorized DBA performs this **read-only** inventory and records UTC time and counts. Any existing schema or account requires review before creation; any object in the proposed target is a STOP:

```sql
SELECT UTC_TIMESTAMP(6) AS checked_utc, CURRENT_USER() AS checking_account;
SELECT SCHEMA_NAME FROM information_schema.SCHEMATA
 WHERE SCHEMA_NAME = 'lankapex_demo_restore_verify_20261110b';
SELECT 'tables_or_views' AS kind, COUNT(*) AS objects FROM information_schema.TABLES
 WHERE TABLE_SCHEMA = 'lankapex_demo_restore_verify_20261110b'
UNION ALL SELECT 'routines', COUNT(*) FROM information_schema.ROUTINES
 WHERE ROUTINE_SCHEMA = 'lankapex_demo_restore_verify_20261110b'
UNION ALL SELECT 'events', COUNT(*) FROM information_schema.EVENTS
 WHERE EVENT_SCHEMA = 'lankapex_demo_restore_verify_20261110b'
UNION ALL SELECT 'triggers', COUNT(*) FROM information_schema.TRIGGERS
 WHERE TRIGGER_SCHEMA = 'lankapex_demo_restore_verify_20261110b';
SELECT User, Host FROM mysql.user
 WHERE User = 'lankapex_demo_restore_b' AND Host = 'localhost';
SHOW VARIABLES LIKE 'partial_revokes';
```

After **separate DBA authorization**, and only if the inventory proves both names absent, the administrator may run the following locally. Supply the password privately in the local MySQL client; do not save or share the substituted statement. Do not run `IF NOT EXISTS`, grant the old account access, or touch the failed target:

```sql
CREATE DATABASE `lankapex_demo_restore_verify_20261110b`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'lankapex_demo_restore_b'@'localhost'
  IDENTIFIED BY '<private password entered locally by DBA>';
GRANT SELECT, INSERT, CREATE, INDEX, REFERENCES, ALTER, LOCK TABLES
  ON `lankapex\_demo\_restore\_verify\_20261110b`.*
  TO 'lankapex_demo_restore_b'@'localhost';
SHOW GRANTS FOR 'lankapex_demo_restore_b'@'localhost';
```

Under the **same Windows administrator account** that will run the future rehearsal, store this new account's password in a separate DPAPI CurrentUser file outside Git, without displaying it:

```powershell
$secretPath = '.server-logs\private-demo\demo-restore-b.dpapi'
if (Test-Path -LiteralPath $secretPath) { throw 'New restore credential already exists; stop for review.' }
$secret = Read-Host 'New restore-only MySQL password' -AsSecureString
try { $secret | ConvertFrom-SecureString | Set-Content -LiteralPath $secretPath -Encoding ASCII -NoNewline }
finally { $secret.Dispose() }
```

Then run **only** the read-only preflight from the project root. Do not add `-Execute` in this preparation stage:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\preflight_demo_restore.ps1 -Manifest 'C:\Users\admin\Desktop\LankaPex\.server-logs\private-demo-backups\lankapex_demo_db_20261109T175450Z_a7ace782.backup.json'
```

Expected: `PASS: exact empty restore target/account/grant and pinned backup checksum` followed by `READ-ONLY RESTORE PREFLIGHT COMPLETE; no restore executed`. A STOP or different identity, privilege, object count, checksum, or source baseline blocks execution. A future one-time restore requires separate explicit authorization. After that restore, require 26 original tables, revision `14c0d3e2f782`, all pinned row counts/table hashes, financial-link hashes, and zero FK orphans before declaring recovery verified. If a future restore fails, preserve the new partial target and sanitized error evidence, do not retry or clean up automatically, and plan a new isolated target after operator/DBA review. The original demo database and backup remain the recovery source; no recovery write to the original demo is authorized here.
