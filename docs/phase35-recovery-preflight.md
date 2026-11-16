# Phase 3.5: populated recovery preflight

2026-11-09, Asia/Colombo. **Read-only preflight PASS. Restore and migrations NOT RUN.** This report concerns only `lankapex_migration_verify_recovery20261109`. The completed clean-schema database, development database and test database were not changed.

## Prerequisites and observations

| Prerequisite | Actual result | Status |
|---|---|---|
| Source backup | Protected `.server-logs/private-backups/lankapex_db_20261109T001844+0530.sql`, 38,177 bytes; SHA-256 `9253fd3577d5c2bff37a4e5a08d08d5d6112190cd74775fe6d7aa8d6345477be`, equal to the private manifest and independently recomputed value | PASS |
| Source identity | Manifest says development `lankapex_db`, revision `c9d5e8f7a237`, MySQL 8.0.46; protected validation baseline has 17 application tables plus `alembic_version` and six ledger rows | PASS |
| Recovery connection | `SELECT DATABASE()` exactly `lankapex_migration_verify_recovery20261109`; `CURRENT_USER()` exactly `lankapex_app@localhost`; MySQL 8.0.46, strict mode and FK checks enabled | PASS |
| Empty destination | Zero tables/views, zero routines, zero events observed via read-only information_schema queries | PASS |
| Database grant | Escaped-underscore exact target grant has SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, INDEX and REFERENCES; no active role is required | PASS |
| SQL dump scope | Pinned bytes reviewed for database-switching, cross-database, DEFINER, user/grant/global, destructive/reset, stored-object and qualified-write forms; 18 CREATE TABLE, six ledger INSERTs, one Alembic INSERT. MySQL executable versioned comments contain session SET and per-table key ALTER directives; no CREATE DATABASE, USE or DEFINER | PASS for this exact checksum |
| Migration chain | One 14-revision graph ending `14c0d3e2f782`; exact five-revision tail from `c9d5e8f7a237`: `d0e6f9a8b348`, `e1f7a0b9c459`, `f2a8b1c0d560`, `03b9c2d1e671`, `14c0d3e2f782` | PASS |
| Model and final migration static checks | `validate_enhancement_schema.py`: 25 models/mappers; model/migration parity, FK/index/CHECK validation and offline MySQL rendering; Python compile passed | PASS |
| Guard negative checks | CLI rejected `lankapex_db` and `lankapex_test_db`; `restore` without `--execute` and exact confirmation was rejected before connection | PASS |
| Actual backup restore and populated migration | No execution was authorized in Phase 3.5 | NOT RUN; approval required |

The actual grant is sufficient for reviewed DDL and data import. It does **not** isolate the account by privilege alone because that account retains its separately granted development/test access. Confinement therefore also depends on exact target guards, the pinned and reviewed SQL bytes, and the native MySQL command's explicit `--database`. An arbitrary replacement dump must fail the hash check. A DBA should still prevent concurrent DDL or writes to the recovery target during the rehearsal; the advisory lock coordinates this runner only.

## Prepared recovery runner

[`backend/scripts/rehearse_populated_recovery.py`](../backend/scripts/rehearse_populated_recovery.py) defaults to read-only preflight. It validates the manifest and exact hash, parses relevant SQL statement forms without printing private rows, verifies the graph, rejects every target name except `lankapex_migration_verify_recovery20261109` at argument parsing and again before DBAPI connection, checks `SELECT DATABASE()` and account identity, and checks the exact grant and emptiness. Its SQLAlchemy gate refuses other engines and cross-database/database-management statements. The restore client receives only the pinned file's raw bytes through binary stdin, with a protected temporary MySQL option file; it never uses shell concatenation, `--force` or a text PowerShell pipeline. The temporary option file is removed in a `finally` block. Normal app test engine settings are set only within the runner process and are never connected; the supplied Alembic connection is restricted by the existing migration-purpose hook to the approved isolated namespace.

The runner has separate `restore` and `upgrade` stages. Both require `--execute` and matching `--confirm-target`. Before `restore`, it requires an empty target again. After restore it expects 17 original application tables plus version, version `c9d5e8f7a237`, every original row count and PK-ordered logical fingerprint from the protected backup baseline, and six ledger rows of the original two types. Before `upgrade`, it requires that same restored state. It applies only the five expected revisions, checks the recorded revision after each stage, expects 25 application tables plus version at head and no model difference, confirms all original rows/fingerprints and six ledger entries are preserved, and requires every newly created table to remain empty. Full original financial-row preservation is stronger than comparing only balances; no financial values are logged.

## Exact commands for a separately approved rehearsal

Run from the project root. The first command is safe and **was run**:

```powershell
.\backend\.venv\Scripts\python.exe .\backend\scripts\rehearse_populated_recovery.py --database lankapex_migration_verify_recovery20261109
```

These commands are **prepared only and were not run**. Execute the restore once after separate approval and immediately inspect its result before any upgrade:

```powershell
.\backend\.venv\Scripts\python.exe .\backend\scripts\rehearse_populated_recovery.py --database lankapex_migration_verify_recovery20261109 --stage restore --execute --confirm-target lankapex_migration_verify_recovery20261109
```

Expected restore: 18 total tables, one `alembic_version` at `c9d5e8f7a237`, all protected baseline row counts and fingerprints, including six ledger entries. Only after that stage passes, and under the same separate execution approval, run:

```powershell
.\backend\.venv\Scripts\python.exe .\backend\scripts\rehearse_populated_recovery.py --database lankapex_migration_verify_recovery20261109 --stage upgrade --execute --confirm-target lankapex_migration_verify_recovery20261109
```

Expected upgrade: 25 application tables plus `alembic_version` = 26 total, version `14c0d3e2f782`, no model difference, all original row fingerprints/counts and six ledger records preserved, and eight newly added tables empty. The first four pending revisions create orders, order items, Admin audits and notification/order-delivery constraints; the last adds the five approved enhancement tables. MySQL DDL may commit independently, so failure cannot be treated as an atomic rollback.

On a nonzero exit or any failed verification, **stop**. Preserve the partially restored or migrated database, source dump and sanitized error evidence. Do not rerun the stage, drop/reset the database, downgrade, stamp or repair financial rows automatically. Diagnose the exact partial Alembic revision and object inventory read-only, then seek a reviewed forward correction or a new disposable target. Do not move a failed copy into production or development. The existing Phase 3.3 development-upgrade template still has a `restore_verify` evidence-name guard that does not match this approved `migration_verify` target; it must be reviewed and aligned before a future development upgrade, not bypassed here.

The SQL backup is ACL-protected but not verified as encrypted or offsite. Actual restore compatibility, populated migration behavior, recovery duration and future development writer-pause/backup freshness remain unverified until execution. No development upgrade, deployment, push or AI integration is included.

## Authorized Phase 3.5 execution result — 2026-11-09

The user separately authorized both stages against **only** `lankapex_migration_verify_recovery20261109`, with Stage 2 conditional on Stage 1 passing. The two exact commands above were run once each, in order. Neither stage required a retry, cleanup, downgrade or stamp. This section supersedes the earlier "NOT RUN" status for the isolated rehearsal only; it does not authorize or report a development upgrade.

| Verification | Actual result | Status |
|---|---|---|
| Restore process | Exit code 0 | PASS |
| Restored original tables | 17 application tables plus `alembic_version` = 18 total | PASS |
| Restored Alembic revision | `c9d5e8f7a237`, one version row | PASS |
| Restored data | Every original table count and PK-ordered row fingerprint matched the protected backup baseline; six ledger entries, four credit sales and two repayments | PASS |
| Upgrade stages | `d0e6f9a8b348`, `e1f7a0b9c459`, `f2a8b1c0d560`, `03b9c2d1e671`, `14c0d3e2f782`, each recorded after execution; process exit code 0 | PASS |
| Final schema and revision | Independent read-only connection found 25 application tables plus `alembic_version` = 26 total, one version row at `14c0d3e2f782` | PASS |
| Model/schema comparison | Alembic `compare_metadata` returned no differences against 25 modeled tables | PASS |
| Existing data and financial records | All original application row counts and fingerprints unchanged; six ledger rows retained with original type counts; all eight new tables empty | PASS |
| Relationship checks | Independent read-only query found zero credit-account customer/business orphans and zero ledger/account orphans; 53 foreign-key constraints present across application tables | PASS |
| Source or unrelated database changes | Runner connected only to the exact recovery target and rejected other DBAPI destinations; no command targeted development, test or the prior clean-chain database | PASS for operation scope |

No passwords, raw financial values or customer records were printed in the report. The rehearsal demonstrates restore and populated upgrade compatibility for this **specific backup and current 8.0.46 server**. The development database remains at its previously observed revision unless independently checked later; no development migration was performed here. The development-upgrade template's restore evidence namespace still needs reviewed alignment, and any later development upgrade requires a fresh writer pause/baseline, backup-currentness decision and separate explicit authorization. Backup encryption/offsite retention and a timed recovery objective remain unresolved operational items. Stop after this isolated rehearsal.
