# Day 5 — Populated demo invitation migration readiness

Status: **BLOCKED for migration** (2026-11-09). The subsequent operator-context preflight and fresh private backup passed; details and recovery preparation appear below. No demo migration, database write, grant change, restore target creation, or service stop occurred. Preserve the working viva demonstration until every remaining gate passes.

## Static review and current evidence

| Gate | Finding |
| --- | --- |
| Revision content | **PASS, static**. `6e3f2c1a9b04` follows `14c0d3e2f782`. It creates only `customer_link_invitations` (InnoDB, utf8mb4), a `customer_id` primary key, four `RESTRICT` foreign keys to `customer_profiles`, `businesses`, and `users`, a unique binary-collated code digest, and a recipient/expiry index. It has no backfill or `ALTER`, `DROP`, or `UPDATE` of an existing table. Its downgrade intentionally refuses data loss. |
| Alembic graph | **PASS, static**. One base `79d8d51548c6`, 15 linear revisions, head `6e3f2c1a9b04`, direct predecessor `14c0d3e2f782`. Python syntax validation passed. |
| Existing application data | **PASS for read-only baseline; BLOCKED for maintained-pause baseline**. Exact demo identity/revision, all 26 table row counts and SHA-256 fingerprints, per-account ledger aggregates, customer/order financial links and foreign-key orphan counts were captured privately before and after the dump. All source fingerprints matched and all foreign-key orphan counts were zero. Writers were not paused, so a fresh baseline remains necessary immediately before any migration. |
| Backup | **PASS for local logical integrity; BLOCKED for proven restore**. The validated populated-demo dump has a private checksum manifest, 26 table definitions, matching per-table row counts and no redirection markers. An independent SHA-256/size check passed. No separate restore rehearsal has been authorized or run. |
| Writer/DDL pause | **BLOCKED**. No operator signoff or DBA-wide session/transaction evidence. Observed inactivity is not a maintained pause. |
| Migrator target/grants | **PASS for read-only preflight**. Under the DPAPI-owning operator context, exact settings, actual database/account, escaped database-scoped grant, revision, 26 starting tables, MySQL prerequisites and 15-revision chain passed. The checksum-pinned read-only preflight passed again after backup. No grant was changed. |
| Customer link impact | **PASS, static**. The revision does not modify `CustomerProfile.user_id`, existing credit profiles, accounts or ledger entries. The new table starts empty. Existing links remain as stored; invitation issuance/acceptance is a later application write, outside this upgrade. |

## Prepared guard

### Post-migration integrity verification (operator command; not yet executed)

After the separately authorized one-revision upgrade, while the writer/DDL pause remains in force, run this **read-only** verifier from the project root under the Windows admin account that owns `.server-logs/private-demo/demo-app.dpapi`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\verify_demo_post_migration.ps1
```

The wrapper supplies only `APP_ENV=development`, `lankapex_demo_db`, and `lankapex_demo_app` through process-local variables and restores their prior values afterward. The Python verifier checks the pinned dump checksum and both matching pre-backup manifests before connecting. It checks the actual database/account, exact DML-only scoped grant, active role, head revision `6e3f2c1a9b04`, 27-table inventory, and zero invitation rows. In a consistent read-only transaction, it reuses `capture_demo_baseline.digest_rows` to compare the 25 pre-existing application tables, all four financial/link fingerprints, and all 53 original zero-orphan FK checks. `alembic_version` is checked for the new revision, not compared to its old row hash. Only `SELECT`/`SHOW`/`DESCRIBE` and read-only transaction setup are allowed; cross-schema LankaPex SQL is refused. It emits only clear PASS or sanitized STOP messages, not records, hashes, amounts, credentials, or connection URLs. A STOP preserves the writer pause and calls for operator review; do not retry or change data automatically. Six synthetic database-free tests and Python/PowerShell syntax checks passed. The live verifier has not yet been run.

`backend/scripts/upgrade_populated_demo_invitation.py` is a **new** populated-schema runner; never use `prepare_demo_database.py` here, because that runner requires an empty schema. The new runner defaults to read-only, accepts only `--database lankapex_demo_db`, requires `APP_ENV=development` and the dedicated migrator, verifies actual database/account/revision/tables/MySQL mode/grants, and refuses cross-database or database-global SQL. Execution additionally requires an exact confirmation, a private backup whose SHA-256 matches, and an operator pause assertion. It applies only `6e3f2c1a9b04`, then checks the final revision, 26 application tables plus `alembic_version`, and an empty invitation table. It never downgrades, stamps, resets, seeds, or retries. `backend/scripts/preflight_populated_demo_upgrade.ps1` supplies the migrator credential from the existing private DPAPI file in process memory; no normal `.env` is edited.

**Read-only command for the DPAPI-owning Windows operator** (from project root):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\preflight_populated_demo_upgrade.ps1
```

Record its PASS/STOP text. The runner does not replace the separate runtime-account preflight. If it reports a different schema, account, privilege or revision, stop and diagnose; do not change the guard.

## Fresh baseline and private backup gates

### Live-data comparison after the maintained pause

The operator-only `backend/scripts/verify_live_demo_baseline.ps1` loads the existing `demo-migrator.dpapi` credential under its owning Windows account, sets `APP_ENV=development` and exact `lankapex_demo_db`/`lankapex_demo_migrator` process variables, and calls `capture_demo_baseline.py`. The capture verifies the actual database/account and starting revision `14c0d3e2f782`, then reads all 26 tables and financial/FK relationships inside a repeatable-read consistent **read-only** transaction. It writes a fresh timestamp-and-GUID-named JSON manifest under `.server-logs/private-demo-backups`; an existing file is refused. The wrapper then runs `compare_demo_baseline.py`, which verifies the pinned backup SHA-256 and compares exact `row_counts`, `table_fingerprints`, `financial_relationship_fingerprints`, and `foreign_key_orphans`, including their required 26/4/53 inventories. It prints only PASS or sanitized STOP messages, never row contents or credentials. The new manifest stays private for review, including on mismatch.

**Run only after a named operator establishes and maintains the writer/DDL pause and a DBA provides fresh session/transaction evidence**, from the project root in the Windows admin account that owns the DPAPI secret:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\verify_live_demo_baseline.ps1
```

This command is read-only against MySQL but creates one new private verification JSON file; it does not back up or migrate the database. PASS requires every pinned field to match exactly. If the current records legitimately changed after the pinned backup, STOP is correct: do not migrate on the old evidence; investigate and prepare a fresh validated backup and recovery evidence. The operator must separately rerun the guarded read-only migration preflight with the selected backup and checksum under the same maintained pause. Database-free verification of the new tools: five synthetic regression tests passed (matching, four mismatch classes, missing fields/wrong identity, invalid formats, existing-file refusal), plus Python and PowerShell syntax checks. No live capture has yet been run.

1. The maintenance operator identifies every backend on 8001, other FastAPI workers, Vite/API clients, test runners, scheduler/task, batch/import process, external integration, Admin/Owner/Customer/Driver browser session, and any direct SQL/DDL tool. Obtain explicit permission before stopping a process. Pause writes, registration, approvals, orders, deliveries, credit operations and invitation issuance; prevent new connections from writers while the upgrade and validation run. Keep a named operator supervising the pause. Do not treat a one-time idle snapshot as proof.
2. An authorized DBA captures timestamped `SELECT NOW(6), DATABASE(), CURRENT_USER()` plus complete session/process and InnoDB active-transaction evidence after the pause begins, then checks repeatedly through backup, upgrade and validation. Any writer/DDL transaction or unknown session blocks execution. The application account alone does not have complete visibility; do not grant it administrative privileges.
3. Under the pause, use exact-target, read-only SQL to capture the revision, `information_schema.TABLES` inventory and per-table row counts. Capture privacy-preserving, deterministic SHA-256 fingerprints of every existing table's complete rows ordered by primary key, with column names/types normalized. Store the manifest privately; print only table names, counts and digests. Include `users`, `businesses`, `customer_profiles` (including `user_id`), `credit_accounts`, `ledger_entries`, repayments, orders/items, products/categories, delivery requests/assignments and `alembic_version`. Record ledger count/sum by entry type, account balance sums, and orphan counts for customer/profile/account/ledger/order/product/delivery ownership relationships. Do not print individual financial rows or identifiers. A consistent transaction snapshot or verified pause is needed so the fingerprints represent one state.
4. Create a timestamped dump in `.server-logs/private-demo-backups/` (outside Git, restricted ACL) from **only** `lankapex_demo_db`. The operator-only wrapper below uses the existing DPAPI migrator credential without putting a password in arguments or logs. A fresh backup under the eventual maintained pause should be considered if the current demo records change. The prior `.server-logs/private-backups/` is ACL-restricted to the sandbox account and was left unchanged.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\backup_populated_demo.ps1 -Execute
```

The backup script first verifies there are zero views/routines/events/triggers; if any appear, it stops for DBA review rather than silently omitting them. It uses a consistent InnoDB transaction dump, one INSERT per row for count validation, and a temporary option file in the operator-private directory that is removed immediately afterward. Validate nonzero size, 26 table definitions, source revision `14c0d3e2f782`, per-table dump row counts and no `CREATE DATABASE`, `USE`, or cross-schema `DEFINER`/qualified statement. Never print row content. A separate isolated restore rehearsal would establish practical restorability; it has **not** been done and needs separate provisioning/authorization.
5. Re-run the read-only preflight with `-Backup <private absolute dump path> -Sha256 <recorded digest>` while the pause holds. Independently compare the backup manifest to source fingerprints. Recheck current source revision and rows immediately before any execution.

## Proposed execution, after separate authorization only

The exact guarded command is shown for review, **not executed or authorized by this request**:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\preflight_populated_demo_upgrade.ps1 -Execute -Backup '<absolute path under .server-logs\private-demo-backups>' -Sha256 '<verified 64-character SHA-256>' -PauseVerified
```

Before invoking it, independently verify the operator is maintaining the pause and the DBA has fresh zero-conflict transaction evidence. The `-PauseVerified` switch records operator signoff; software cannot prove that an external writer remains stopped. Do not invoke the old empty-schema demo runner. Do not put a password on the command line.

After any separately authorized execution, require `SELECT DATABASE()=lankapex_demo_db`, revision `6e3f2c1a9b04`, 26 application tables plus `alembic_version` (27 total), an empty invitation table, SQLAlchemy model comparison with no unexpected differences, and matching pre/post row counts and fingerprints for **all 25 pre-existing application tables**. The `alembic_version` row must change only from `14c0d3e2f782` to `6e3f2c1a9b04`. Compare financial aggregates and every pre-existing CustomerProfile link, account balance, credit sale, repayment, product/category, order/item, delivery assignment/status and ownership-orphan count. Check `/api/v1/health/database`, runtime preflight and four-role read-only screens only after database verification. Resume writers only after operator and DBA signoff.

MySQL DDL is non-transactional. On any failure, stop, keep the writer pause, preserve the partial schema and logs, and do not downgrade, stamp, retry or clean up. Compare the failure state with the pinned backup; have an operator restore into a **new isolated** database first, verify fingerprints and application compatibility, then approve any recovery of the original demo schema separately. Keep the source dump untouched. A partial migration may leave `customer_link_invitations` created while `alembic_version` remains old; an automatic rerun could fail or worsen the state.

## Authorizations still required

- Operator approval and signoff to stop/pause all identified application writers and DDL sources, plus maintained supervision.
- DBA-wide read-only transaction/session evidence; no new admin grant to the application account.
- Private backup creation and checksum/content validation, with a separate isolated restore rehearsal if practical recovery must be proven.
- Separate explicit authorization for the **populated demo** one-revision migration after the above evidence passes. This request does not grant it.

**Readiness decision: BLOCKED for migration.** Preserve the existing demo environment. The next action is separate DBA provisioning of the empty restore-verification database and its restricted account, followed by read-only restore preflight. No upgrade should begin until restore evidence, a maintained writer/DDL pause and separate migration authorization are available.

## Completed backup and recovery preparation

The operator-context read-only preflight passed exactly: `lankapex_demo_db`, `lankapex_demo_migrator@localhost`, `14c0d3e2f782`, 26 total tables, scoped grant and 15-revision graph. A new `.server-logs/private-demo-backups/` directory was created with inheritance disabled and access only for the Windows `admin` operator and `SYSTEM`; the existing backup ACL was not changed.

`capture_demo_baseline.py` recorded, in private JSON only, each table's count and deterministic row SHA-256, financial aggregate/link fingerprints and FK orphan counts. `backup_populated_demo.py` compared the baseline before and after a successful `mysqldump` and counted each dump INSERT against the source table count. The source matched on all 26 tables, financial/link fingerprints and FK orphan counts. The MySQL connection was read-only for snapshots. No service was stopped, so this is evidence of observed stability across the dump, **not** a maintained writer/DDL pause.

| Evidence | Result |
| --- | --- |
| Validated SQL dump | `.server-logs/private-demo-backups/lankapex_demo_db_20261109T175450Z_a7ace782.sql` |
| Private checksum/size manifest | `.server-logs/private-demo-backups/lankapex_demo_db_20261109T175450Z_a7ace782.backup.json` |
| SHA-256 | `ede32b514a47efb4b3b06a206596ff8d23a03f9779cafc39e32099b5a654e685` — independently rechecked |
| Size | 54,909 bytes — independently matched manifest |
| SQL scope/content | 26 CREATE TABLE definitions, source revision marker, exact source database marker, each table's one-row INSERT count matched baseline; no CREATE/ALTER/DROP DATABASE, USE, DEFINER, or development/test qualified reference |
| Temporary credential file | None remained after the dump |
| Source before/after | Exact revision, row counts, row fingerprints and financial/ownership hashes matched; all FK orphan counts zero |
| Checksum-pinned migration preflight | PASS, read-only; no migration executed |

The private baseline records these aggregate counts: 4 users, 1 business, 1 customer profile, 1 credit account, 2 ledger entries, 3 product categories, 2 products, 1 order with 1 item, and 1 delivery request with 1 assignment. It checked 53 foreign-key relationships (zero orphans) and stored four financial/link aggregate fingerprints. These counts contain no individual financial amounts. The current demo data may change while writers remain active, so recheck it under the eventual maintained pause.

Six earlier dump attempts stopped on optional dump flags or overly strict validation. They have **no validated manifest and must not be used for recovery**; their files remain private for diagnosis. Only the timestamped dump above is pinned. The backup is local and access-controlled; encryption, offsite storage and a successful restore are still unverified.

### Separate restore-verification target — preparation only

Proposed exact target: `lankapex_demo_restore_verify_20261109`. **It has not been created or granted.** A DBA must first confirm that it does not exist, then separately approve/create an empty MySQL 8.0 schema with utf8mb4 and a dedicated `lankapex_demo_restore@localhost` account. Provision its password privately in MySQL Workbench or the DBA's secure local process; do not enter it in chat or a command argument. The account needs only SELECT, INSERT, CREATE, INDEX, REFERENCES and ALTER on the exact database, with escaped underscores in the grant pattern; no global privileges, no access to `lankapex_demo_db`, `lankapex_db` or `lankapex_test_db`.

DBA-reviewed SQL template (execute **only after separate authorization**, and only if the target is absent):

```sql
CREATE DATABASE `lankapex_demo_restore_verify_20261109`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- Create 'lankapex_demo_restore'@'localhost' with a privately held password.
GRANT SELECT, INSERT, CREATE, INDEX, REFERENCES, ALTER
  ON `lankapex\_demo\_restore\_verify\_20261109`.*
  TO 'lankapex_demo_restore'@'localhost';
SHOW GRANTS FOR 'lankapex_demo_restore'@'localhost';
```

The operator may store the restore account password as DPAPI CurrentUser in `.server-logs/private-demo/demo-restore.dpapi` using `Read-Host -AsSecureString` and `ConvertFrom-SecureString`; do not print it. `preflight_demo_restore.ps1` loads it only into a child process and clears the process environment. `rehearse_demo_backup_restore.py` accepts only the proposed target, checks the pinned checksum and safe dump statement forms, requires the actual target to be empty and the account scoped to that target, and defaults to **read-only**. Its `--execute` path requires a separate exact-target confirmation, uses the dedicated account, and verifies all 26 restored table fingerprints against the private baseline. It neither creates nor resets the target.

Operator command for the future **read-only** restore preflight, after DBA setup and private credential storage:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\preflight_demo_restore.ps1 -Manifest 'C:\Users\admin\Desktop\LankaPex\.server-logs\private-demo-backups\lankapex_demo_db_20261109T175450Z_a7ace782.backup.json'
```

Proposed restore command for **later separate authorization only**: add `-Execute` to that exact command after the preflight passes. On a failure, preserve the partial restore target; do not delete, retry, downgrade, stamp or use the original demo schema as a restore target. Compare the restored counts/fingerprints and revision to the pinned baseline before planning any upgrade rehearsal.

### Remaining post-upgrade gate

After any future authorized demo migration, capture a fresh read-only snapshot and compare the 25 original application-table hashes, row counts, financial aggregates and customer/order links to this baseline (or a newer pause-time baseline if data changed). Check zero FK orphans, one new empty invitation table, 27 total tables, revision `6e3f2c1a9b04`, model/schema consistency, runtime preflight and four-role read-only smoke tests. MySQL DDL is non-transactional: if anything fails, keep writers paused and preserve the partial schema and pinned backup for operator-reviewed recovery. Do not attempt an automatic downgrade or restore over the demo database.
