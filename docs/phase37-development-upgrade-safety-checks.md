# Phase 3.7: writer inactivity, fresh backup and rehearsal preparation

For the later development-upgrade gates and operator checklist, see [Phase 3.8 readiness](phase38-development-upgrade-readiness.md). The isolated rehearsal below passed; it did not authorize a development migration.

2026-11-09, Asia/Colombo. **Fresh backup created and validated. No process was stopped. No restore, migration, grant change, schema change, downgrade, stamp, deployment or push occurred.** This phase is limited to the currently observed local development database and exact private backup below. Review [Phase 3.6](phase36-development-upgrade-readiness.md) for the later development upgrade sequence; this document does not authorize it.

## Writer inventory and pause checklist

Potential writers identified from this repository and local setup: the FastAPI backend (`uvicorn app.main:app`, including reload workers), any background or maintenance Python script that imports the normal development engine, any manual MySQL client connected to `lankapex_db`, and any externally configured job/service that calls these paths. The React/Vite frontend has no direct database connection, but an active frontend user could cause backend writes while the API runs. MySQL itself must remain running for the backup. The app's MySQL event scheduler is ON; this development schema currently has zero events. No LankaPex Windows scheduled task or dedicated Windows service was found.

The read-only Windows process inventory, repeated with elevated *read-only* access after ordinary CIM access was denied, found no Python, uvicorn, celery or LankaPex Node process. Only MySQL and unrelated Codex runtime Node processes appeared among the inspected candidates. No listener was observed on ports 8000, 8001, 5173 or 5174; MySQL listened on 3306. Two MySQL `information_schema.PROCESSLIST` samples showed zero **other** sessions whose selected database was `lankapex_db`. `information_schema.INNODB_TRX` visibility was unavailable to the application account, so active-transaction absence was not independently proved there. This supports **observed application-writer inactivity** at backup time, not a durable access freeze: an external/manual writer could connect later. No process was stopped or terminated.

Before any actual development upgrade, the maintenance operator must: identify the backend launch terminal/service and all job/import/manual SQL writers; prevent new requests and manual writes; stop known writers only with explicit authorization; drain in-flight work; use an authorized privileged, read-only transaction/process inventory if available; recheck API listeners, process list, scheduler/events and revision; record operator, time and components paused; hold the pause through fresh baseline, backup, populated rehearsal, upgrade and verification. Do not treat two idle samples or an advisory lock as a writer pause for a future maintenance window. Do not stop MySQL or kill an unidentified process.

## Fresh audit and protected backup

Immediately before backup, `.server-logs/phase33-development-audit.py` rechecked `SELECT DATABASE() = lankapex_db`, MySQL 8.0.46, revision `c9d5e8f7a237`, 17 application tables plus `alembic_version`, all InnoDB, no unexpected tables/column drift, and five pending revisions `d0e6f9a8b348` → `e1f7a0b9c459` → `f2a8b1c0d560` → `03b9c2d1e671` → `14c0d3e2f782`. All six intermediate notification predicates had zero incompatible rows. There were six ledger rows (four credit sales and two repayments), zero account/business mismatches and no linked ledger orders. The private `.server-logs/phase33-development-audit.json` holds row, ledger and effective-balance fingerprints, without publishing financial values.

The authorized `.server-logs/phase34-create-backup.py` then ran one consistent InnoDB `mysqldump --single-transaction` of **only** `lankapex_db`, with structure, data, triggers, routines and events included. Source snapshots before and after were equal. Actual protected artifacts under ignored `.server-logs/private-backups/`:

| Artifact | Name |
|---|---|
| SQL | `lankapex_db_20261109T105502+0530.sql` |
| Manifest | `lankapex_db_20261109T105502+0530.manifest.json` |
| Private validation/baseline | `lankapex_db_20261109T105502+0530.validation.json` |

**SQL size:** 38,177 bytes. **Independent SHA-256:** `1588a78f4e5b5e95d9556233d79241991ea063224fd6e73da363ae545e78245e`.

| Backup check | Actual result | Status |
|---|---|---|
| Dump exit/stderr | 0 / empty | PASS |
| File size and SHA | 38,177 bytes; independent hash equals private manifest | PASS |
| Schema/revision | 18 CREATE TABLE definitions, one `c9d5e8f7a237` version row | PASS |
| Rows and finance | Per-table INSERT counts equal source; six ledger INSERTs with four credit sales/two repayments; all source row/fingerprint baselines match the fresh audit | PASS |
| Source stability | Backup script's pre/post schema/count/fingerprint snapshots identical | PASS |
| Scope/SQL review | New exact-hash profile accepted dump's database-scope review; no database switch, target redirect or unexpected privileged statement | PASS for these pinned bytes |
| File privacy | SQL, manifest and validation ignored by Git; file ACL has only local restricted identity and SYSTEM; temporary client credential file absent | PASS |
| Formal administrative writer freeze | No such freeze was imposed or proved for this backup | NOT ESTABLISHED |
| Backup restoreability | This fresh checksum has not yet been restored | NOT RUN |

The backup has local ACL protection, but file encryption, offsite retention and a measured recovery time are not verified. Preserve the SQL and its two companions together; never print or attach the SQL contents. No existing backup was overwritten.

## New exact-target isolated rehearsal preparation

Prepared target: **`lankapex_migration_verify_recovery20261109b`**. It is distinct from `lankapex_db`, `lankapex_test_db`, the clean-schema verification database and the already populated Phase 3.5 recovery database. It was **not created or modified** here; it is not visible to the current app account. A DBA must provision an empty utf8mb4 target with an escaped-underscore, database-scoped grant and confirm `SELECT DATABASE()`, `CURRENT_USER()`, privileges, zero tables/views/routines/events and supported MySQL settings. Do not reuse or reset a previous verification target.

[`backend/scripts/rehearse_populated_recovery.py`](../backend/scripts/rehearse_populated_recovery.py) now has a second **fixed profile** pairing this exact target with this exact SQL filename and SHA-256. The original Phase 3.5 profile remains pinned to its own target/backup. The runner rejects `lankapex_db`, `lankapex_test_db` and all other names at parsing; before any DBAPI connection it checks the selected target, and restore/upgrade additionally require exact `--execute --confirm-target`. Its database-free inspection of this new pinned dump and manifest passed, and syntax/negative-target checks passed. No new-target connection, restore or migration was attempted.

Once the DBA provisions the new target, the **read-only preflight** command is:

```powershell
.\backend\.venv\Scripts\python.exe .\backend\scripts\rehearse_populated_recovery.py --database lankapex_migration_verify_recovery20261109b
```

The following two commands are **prepared only; do not run without separate explicit restore-and-upgrade authorization**. Stage 2 is conditional on every Stage 1 check passing:

```powershell
.\backend\.venv\Scripts\python.exe .\backend\scripts\rehearse_populated_recovery.py --database lankapex_migration_verify_recovery20261109b --stage restore --execute --confirm-target lankapex_migration_verify_recovery20261109b
```

Expected after restore: 18 original tables, revision `c9d5e8f7a237`, all protected row fingerprints and six ledger records preserved.

```powershell
.\backend\.venv\Scripts\python.exe .\backend\scripts\rehearse_populated_recovery.py --database lankapex_migration_verify_recovery20261109b --stage upgrade --execute --confirm-target lankapex_migration_verify_recovery20261109b
```

Expected after upgrade: 25 application tables plus version, revision `14c0d3e2f782`, no model differences, original row/ledger fingerprints preserved and eight newly created tables empty. On any failure, stop and preserve partial state; no reset, retry, downgrade, stamp or automatic cleanup. This rehearsal still needs private evidence tied to the new SHA for the later guarded development command. The current runner prints success but does not yet create the reviewed restore-evidence JSON required by the development template; prepare and independently review that attestation only after an actual successful rehearsal.

## Remaining blockers

1. The new isolated database, its exact grant and read-only preflight are pending DBA provisioning.
2. Separate explicit approval is required before either isolated restore or isolated migration stage. No rehearsal of the fresh checksum has run.
3. A formal, sustained writer/DDL pause and transaction check must be established for any actual development maintenance window. The observed inactivity at backup time is not a future pause guarantee.
4. The fresh backup still needs populated restore/upgrade evidence, with the exact checksum and application-only fingerprints, before the guarded development command can accept it. The current prior rehearsal evidence cannot be relabeled.
5. A separate explicit authorization is required for **any** upgrade of `lankapex_db`. No such upgrade occurred here.

Stop after this backup and preparation. AI Summary remains deferred.

## Authorized isolated rehearsal attempt — preflight stopped

The user subsequently authorized restore and upgrade **only if** the DBA-provisioned, empty `lankapex_migration_verify_recovery20261109b` passed read-only preflight. The exact preflight command shown above was run once. It exited **1** with sanitized `OperationalError`, **MySQL error 1044** (access denied to the target database). The failure occurred before any restore or Alembic command. No execution-stage command was attempted, and the fresh backup and all existing databases were left unchanged.

| Gate | Actual result | Status |
|---|---|---|
| New target access as configured application account | MySQL 1044 during preflight connection | FAIL / BLOCKED |
| Exact target identity, emptiness and grants | Could not be checked after connection denial | NOT VERIFIED |
| Restore of fresh backup | Not attempted because preflight failed | BLOCKED |
| Populated upgrade | Not attempted because restore did not occur | BLOCKED |
| Fresh backup file validation | Passed before the attempted preflight; source SQL checksum remains the pinned value | PASS |

MySQL 1044 alone does not distinguish a missing database from an absent/incorrect database-scoped grant. An authorized DBA must independently confirm that the **exact** new database exists, has zero tables and has a correctly escaped-underscore grant for `lankapex_app@localhost`, then verify login and `SELECT DATABASE()` as that account. Do not change broad grants or use the development/test database as a substitute. Once the DBA confirms access, rerun the read-only preflight; its original restore/upgrade authorization remains conditional on that preflight passing. No automatic retry, cleanup, reset or grant change is part of this stopped attempt.

## Read-only diagnosis of MySQL 1044

The subsequent user request authorized diagnosis only until existence and privileges are known. A read-only connection to the existing development configuration verified `CURRENT_USER() = lankapex_app@localhost` and `SELECT DATABASE() = lankapex_db`. `SHOW GRANTS FOR CURRENT_USER()` returned five grant lines, **none for the exact** `lankapex_migration_verify_recovery20261109b` target. `@@GLOBAL.partial_revokes = 0`, so unescaped underscores in a database grant would be wildcard characters. `information_schema.SCHEMATA` exposed zero rows for the target to this account, but that is **not authoritative evidence of absence** when the account lacks target privileges. No grant, schema or data was changed and no restore/preflight retry was attempted. The exact grant is missing; existence and emptiness require a DBA's privileged read-only check.

The DBA should run the following **read-only SQL as an authorized administrator**, without sharing passwords or raw financial rows:

```sql
SELECT SCHEMA_NAME
FROM information_schema.SCHEMATA
WHERE SCHEMA_NAME = 'lankapex_migration_verify_recovery20261109b';

SELECT COUNT(*) AS objects_in_target
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'lankapex_migration_verify_recovery20261109b';

SELECT COUNT(*) AS routines_in_target
FROM information_schema.ROUTINES
WHERE ROUTINE_SCHEMA = 'lankapex_migration_verify_recovery20261109b';

SELECT COUNT(*) AS events_in_target
FROM information_schema.EVENTS
WHERE EVENT_SCHEMA = 'lankapex_migration_verify_recovery20261109b';

SHOW GRANTS FOR 'lankapex_app'@'localhost';
```

**Stop if any target object/routine/event exists. Do not clear or reuse a nonempty target.** If the first query confirms the exact database is **absent**, the authorized DBA may review and execute this one-time creation separately:

```sql
CREATE DATABASE `lankapex_migration_verify_recovery20261109b`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Only after the exact target exists and is confirmed empty, the authorized DBA may review and execute this **database-scoped** grant. The backslash before **each** underscore is required under the observed `partial_revokes = 0` setting; backticks alone do not escape wildcard underscores in the GRANT database pattern:

```sql
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, INDEX, REFERENCES
ON `lankapex\_migration\_verify\_recovery20261109b`.*
TO 'lankapex_app'@'localhost';

SHOW GRANTS FOR 'lankapex_app'@'localhost';
```

Do not revoke/change existing development/test grants, grant on `*.*`, change user passwords or use root for the restore. The DBA should confirm the resulting `SHOW GRANTS` contains the exact escaped target and no unintended broader target pattern. Then, using the existing application account and **selecting only the new target**, confirm `SELECT DATABASE()`, `CURRENT_USER()` and zero tables. Once the user confirms those results, rerun the documented read-only preflight. The already granted conditional authorization permits the isolated restore/upgrade only after that preflight passes; it does not extend to `lankapex_db`.

## Authorized isolated rehearsal after DBA setup — PASS

After the user confirmed DBA setup, the previously authorized exact-target sequence was executed **once**, in order, against only `lankapex_migration_verify_recovery20261109b`. This successful result supersedes the earlier blocked preflight attempt above. The pinned SQL source remained `lankapex_db_20261109T105502+0530.sql`, SHA-256 `1588a78f4e5b5e95d9556233d79241991ea063224fd6e73da363ae545e78245e`. No reset, retry, downgrade, stamp or cleanup was needed.

| Gate | Actual result | Status |
|---|---|---|
| Read-only preflight | Exit 0; exact target/account identity, zero target objects, required exact grant, backup hash/SQL scope and five-revision graph passed | PASS |
| Restore command | Exit 0; 17 original application tables plus `alembic_version` (18 total), source revision `c9d5e8f7a237`, all original row counts/fingerprints and six ledger rows retained | PASS |
| Independent read-only restore check, before migration | Exact target, 18 original tables, source revision and every original fingerprint/six ledger entries passed | PASS |
| Five pending migration stages | `d0e6f9a8b348`, `e1f7a0b9c459`, `f2a8b1c0d560`, `03b9c2d1e671`, `14c0d3e2f782` applied in order; upgrade exit 0 | PASS |
| Final isolated structure | 25 application tables plus `alembic_version` (26 total), one version row at `14c0d3e2f782`, no Alembic model differences | PASS |
| Original data and financial integrity | All original table counts and PK-ordered row fingerprints matched pinned backup; six ledger entries/types retained; independent effective-balance fingerprint matched the fresh development audit | PASS |
| Relationships/new tables | Zero credit-account customer/business and ledger/account orphans; all eight new tables empty | PASS |
| Development schema | Separate read-only check still found `lankapex_db` at `c9d5e8f7a237` with 18 total tables | PASS: no development migration |

The private, ignored artifact `.server-logs/private-backups/lankapex_db_20261109T105502+0530.populated-rehearsal-evidence.json` was created after successful execution. It binds the exact backup SHA, isolated target, source/head revisions, original application-row fingerprints and balance fingerprint; its fields were independently checked against the fresh audit and manifest. It is an operator attestation backed by the actual run, not cryptographic proof of who ran it. Do not edit its values to satisfy the development upgrade guard. The earlier note that this runner does not *automatically* create such evidence remains true; this artifact was explicitly written after the successful checks.

**Remaining risks and gates:** the fresh backup is locally ACL-protected but not proven encrypted/offsite; writer inactivity observed at backup time is not a durable maintenance freeze; no timed recovery objective or actual development failover has been tested. A future development maintenance window still requires an authorized, sustained writer/DDL pause, a recheck that source rows and backup evidence match, operator review of the guarded development template and separate **explicit authorization to upgrade `lankapex_db`**. This isolated success does not grant that authorization. Stop after the isolated rehearsal.
