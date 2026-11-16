# Phase 3.3: existing development database upgrade preparation

Current preparation and fresh read-only audit: [Phase 3.6](phase36-development-upgrade-readiness.md). The Phase 3.5 populated restore-and-upgrade rehearsal passed on the Phase 3.4 backup. This document retains the historical Phase 3.3 audit and earlier, unexecuted command example; use Phase 3.6 for the revised backup-validation argument and current blockers.

Latest backup status: [Phase 3.4](phase34-development-backup-and-recovery.md) created
and validated a protected timestamped dump on 2026-11-09. Historical "backup not
performed" statements below are superseded only for that artifact. Populated
restore/upgrade verification and development execution remain unperformed and
require separate authorization; no development migration occurred.

2026-11-09 (Asia/Colombo). **Audit/preparation only. No development or test migration/data change, backup execution, database creation, restoration, downgrade, stamp, reset, deployment or push.** Phase 3.2 successfully executed a clean isolated chain; this document does not extend that authorization to development.

## Fresh live audit

Asserted APP_ENV=development, configured engine and SELECT DATABASE()=**lankapex_db**, local MySQL **8.0.46**. Guarded schema/count/precondition reads ran in a read-only consistent snapshot. No private row contents or monetary balances are published. Ignored local artifacts: `.server-logs/phase33-development-audit.json` (full schema, row counts and one-way preservation fingerprints), `phase33-schema-diff.json`, `phase33-development-audit-summary.log`. Snapshot is an observation, not a backup or evidence that writers were paused.

Current Alembic revision: **c9d5e8f7a237**. Actual **17 application tables, 18 total** including alembic_version. All inspected tables InnoDB; zero visible views/routines/events/triggers. Backend Settings resolution, engine timeouts/TLS/password hiding are unchanged. Current account has ALL PRIVILEGES scoped to development, sufficient for the reviewed forward operations; that privilege scope is not execution authorization.

| Existing table | Exact snapshot row count |
|---|---:|
| users | 5 |
| businesses | 1 |
| business_members | 1 |
| customer_profiles | 2 |
| credit_accounts | 1 |
| ledger_entries | 6 |
| business_approval_audits | 1 |
| payment_reminders | 1 |
| notifications | 0 |
| communication_consents | 0 |
| communication_attempts | 0 |
| driver_profiles | 1 |
| delivery_requests | 0 |
| delivery_assignments | 0 |
| delivery_status_events | 0 |
| product_categories | 0 |
| products | 0 |
| alembic_version (metadata, excluded from application count) | 1 |

Ledger type counts: **4 credit sales, 2 repayments, 0 reversals**. Account/customer business mismatches: **0**. Ledger rows carrying order_id: **0**. No order table exists yet. Per-table PK-ordered content hashes and authoritative effective-ledger/balance hashes were captured privately without exporting records; these detect changes but do not allow data restoration. All financial arithmetic used existing ledger_service Decimal/reversal semantics.

## Schema delta and pending revisions

Read-only compare_metadata reports only expected additions: eight missing tables and their indexes, plus uq_delivery_id_business on delivery_requests. No unexpected tables, missing/extra columns, effective type/precision/nullability drift or destructive model diff on existing shared tables was found. MySQL aliases/inherited collation are normalized for type review. Autogenerate does not comprehensively compare CHECK semantics; the notification checks were inspected independently.

Missing target tables: **orders, order_items, admin_audits, customer_addresses, user_preferences, business_settings, vehicles, vehicle_documents**. Target: **25 application tables / 26 total** at **14c0d3e2f782**. No optional cart, earning/payout, inventory, subscription/group/dispute or AI tables are included.

| Pending revision, dependency order | Existing-data effects |
|---|---|
| d0e6f9a8b348 | Creates orders/order_items and indexes/FKs; replaces two notification checks. Does not import orders from ledger history or create debt. Target after stage: 19 application tables. |
| e1f7a0b9c459 | Adds delivery composite unique, nullable unique orders.delivery_request_id and same-business composite FK. No historical linkage inferred. Table count stays 19. |
| f2a8b1c0d560 | Replaces notification type/entity checks for requested/cancelled and order-linked deliveries; count stays 19. |
| 03b9c2d1e671 | Creates admin_audits and indexes; updates driver-approval notification checks. No historical audit records invented. Count 20. |
| 14c0d3e2f782 | Creates five approved foundations with ownership FKs/indexes/checks/defaults. No backfill or driver approval. Count 25. |

All six intermediate notification-check predicates (two each at d0/f2/03) were evaluated against current rows using `(predicate) IS FALSE`: **0 incompatible rows for each**. This is consistent with notifications currently empty; rerun after writers are paused because new notifications before migration can invalidate this precondition. The parent composite unique includes an existing PK, so it introduces no extra duplicate-id risk under the observed schema; metadata drift or conflicting constraint names still require a fresh check.

### Existing records and financial rules

- The two customer profiles and one credit account retain contact/linkage, limits, terms and statuses; no defaults table update propagates to them.
- Six ledger rows and repayment receipt/idempotency/reversal references must remain byte-equivalent at the logical row level. No outstanding/available balance cache is added; preserve effective-ledger and balance fingerprints. Repayment amounts and due_at are untouched. Existing balance totals are intentionally not published here.
- Existing products/categories have zero rows and remain intact; order creation is schema-only. No manual credit sale is converted to an order. New cash orders remain unpaid/no credit link; pending/rejected credit orders create no debt; authorized approval still posts exactly once through the existing service.
- Existing driver profile remains as-is; no copying legacy vehicle strings or automatically approving documents. New vehicle/document tables start empty. Self-supersession/cycles still require future service validation because MySQL cannot CHECK auto-increment document_id.
- Existing deliveries/assignments/events have zero rows. Their structures and server lifecycle remain; no reassignment, status event fabrication or new financial posting occurs.
- Notification checks are altered but existing recipient/read/event data must be preserved. Business approval audits, reminder and communication evidence remain unchanged. New Admin audits start empty.

## Backup procedure — prepared, NOT EXECUTED

Client-only version checks confirmed mysql.exe and mysqldump.exe **8.0.46** at `C:\Program Files\MySQL\MySQL Server 8.0\bin`. These checks do not authenticate a backup identity or prove dump privileges. Existing backup_manifest helpers were reviewed: they only build commands/validate files; no backup scheduler, backup execution or restore was invoked.

Prerequisites: independently approve a backup operation and private storage, a least-privilege backup identity/option file, NTFS ACLs and encrypted volume; pause all application writers, background jobs and concurrent DDL during baseline/dump/restore comparisons and later upgrade. Record the pause externally: an advisory lock only coordinates cooperating migration scripts. Retain safe baseline time/revision and reviewed source hashes. Do not use root credentials in chat or put secrets in command arguments/repository.

Illustrative exact command layout for an approved operator, **NOT RUN**; substitute reviewed private paths outside repo/public directories:

```powershell
& 'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe' `
  '--defaults-file=C:\LankaPexPrivate\mysql-backup.cnf' `
  --single-transaction --quick --skip-lock-tables --skip-add-locks `
  --skip-add-drop-table --no-tablespaces --set-gtid-purged=OFF `
  --column-statistics=0 --hex-blob --routines --events --triggers `
  --default-character-set=utf8mb4 `
  '--result-file=C:\LankaPexPrivate\backups\lankapex-preupgrade-20261109.sql' `
  lankapex_db
```

Use defaults-file first and `--result-file` instead of PowerShell redirection (which can alter encoding). Private defaults must identify the reviewed source, connection account/host/port and appropriate TLS verification, without schema switching or automatic commands. Explicit final source argument is the one database; never use --all-databases/--databases or pipe directly into a running restore. All tables are InnoDB, allowing consistent single-transaction rows, but concurrent DDL can invalidate a dump. --no-tablespaces avoids PROCESS; --set-gtid-purged=OFF avoids importing global GTID state. Review exact privileges for stored object export even though none were observed. [MySQL mysqldump documentation](https://dev.mysql.com/doc/refman/8.0/en/mysqldump.html).

Stop on nonzero exit/any dump error. Validate nonempty file, MySQL header, source identity, byte size and SHA-256; generate a private manifest using existing exact keys: format_version=1, format=mysql-logical-sql, created_at UTC ISO timestamp, source_environment=development, source_database=lankapex_db, mysql_version=8.0.46, schema_revision=c9d5e8f7a237, sha256, size_bytes. No passwords in manifest. Encrypt and protect dump at rest and offsite under approved policy, retain keys separately, and verify decryption/hash. A checksum is not proof of provenance, encryption or successful restore.

No backup path/option-file permissions, successful dump, manifest or encryption were verified in this task. **These remain execution blockers.**

## Restoration verification — planned, NOT EXECUTED

The Phase 3.2 clean schema success **does not prove this populated backup restores**. Do not restore over lankapex_db/lankapex_test_db or reuse the now-nonempty migration target. A separately designated empty target such as **lankapex_restore_verify_20261109** needs explicit approval and authorized DBA provisioning/access. Current account sees no schema under that exact name; absence is not authoritative under filtered metadata. No schema creation was attempted.

1. Approve creation/access and restore independently, then assert configured target and SELECT DATABASE() plus all-object emptiness. Use target-only restore credentials with no access to existing databases, same supported MySQL version, strict mode/charset/timezone and sufficient disk. Do not restore as a broad DBA identity.
2. Authenticate trusted backup provenance and manifest, decrypt privately, verify bytes. Review SQL for USE/CREATE DATABASE, fully qualified references to existing DBs, DEFINER/global statements, grants/accounts, stored objects, unexpected executable content and DROP/TRUNCATE. --database alone cannot confine arbitrary dump SQL. No automatic text rewriting of an unreviewed dump.
3. Stream bytes through a native subprocess to mysql stdin (PowerShell text Get-Content pipelines can change encoding), with argument list: `mysql.exe`, `--defaults-file=<private target-only option file>`, `--binary-mode`, `--default-character-set=utf8mb4`, `--database=lankapex_restore_verify_20261109`. Do not use --force. Inspect exit/error status; stop/preserve partial restore on failure. This describes a procedure, not an executed command.
4. At restored c9d5e8f7a237, compare 17 application tables/18 total, all original row counts and full per-table PK-ordered hashes to the **same paused source baseline**; compare ledger/effective-balance hashes, business linkage, receipts, idempotency and reversal invariants. Do not compare unrelated moving snapshots or log private rows.
5. Rehearse the five-revision populated upgrade on that restored isolated copy under a separately reviewed execution path. Existing supplied-connection Alembic hook accepts only migration_verify names, **not restore_verify names**; it must not be bypassed with a fake URL or passed unmodified. A reviewed restore-copy rehearsal harness/configuration adaptation requires separate code authorization, or DBA provision a fresh migration_verify target and restore into it under separately reviewed guard purpose. Do not use the completed/nonempty Phase 3.2 target or disable testing guards. This tooling/prerequisite is currently unresolved.
6. Verify target 25 tables plus version at head; preserve all original row hashes and financial balances; exercise only separately authorized synthetic API/constraint tests. Keep real restored data private and integrations disabled; no automatic cleanup.
7. Retain a private operator-reviewed evidence JSON tied to the exact backup SHA, source revision and head, approved isolated restore database name and original table_fingerprints. Require status PASS only after actual restore AND populated upgrade pass. Approval must inspect provenance; an editable JSON is an attestation, not cryptographic proof or a way to bypass rehearsal.

Restoration feasibility was reviewed against installed clients, helper code, naming/configuration guards and SQL format; **restoration is NOT VERIFIED**. A real successful restore/populated upgrade remains a blocking prerequisite, not something to mark passed from the clean schema run.

## Prepared guarded development command — NOT RUN

Reviewable source template: [phase33-upgrade-development.py.example](operations/phase33-upgrade-development.py.example). This is explicitly an unexecuted operator template, not an approved production tool or default app path. Syntax and safeguards are statically checked; no execution against a database was performed. It requires backup bytes+manifest, matching populated-restore evidence, the same paused-source baseline hashes, exact database/source/head, no inventory drift and explicit execution/pause confirmations. It rejects other DB connections before DBAPI connect and refuses test/isolated database references in SQL. It makes no backups/restores/grant changes/resets or financial repairs. No automatic retry/downgrade/stamp.

```powershell
.\backend\.venv\Scripts\python.exe .\docs\operations\phase33-upgrade-development.py.example `
  --database lankapex_db `
  --baseline .\.server-logs\phase33-development-audit.json `
  --backup 'C:\LankaPexPrivate\backups\lankapex-preupgrade-20261109.sql' `
  --backup-manifest 'C:\LankaPexPrivate\backups\lankapex-preupgrade-20261109.json' `
  --restore-evidence 'C:\LankaPexPrivate\backups\populated-restore-upgrade-evidence.json' `
  --execute --confirm-writes-paused --confirm-target lankapex_db
```

Those private files do not exist as verified artifacts in this task. Refresh the baseline after pausing writers and coordinate dump/evidence against it; today's audit is not a future maintenance-window backup. Restore evidence fields consumed by template: restore_database, status, backup_sha256, source_revision, target_revision, table_fingerprints. Fingerprints must match the same source baseline. A meaningful change since the backup requires re-baselining, backup/restore review and renewed approval, not editing evidence to match.

The isolated connection hook in env.py intentionally forbids development, so this template uses the **normal development Alembic path** after guarding its engine; it does not expand or bypass that hook. It leaves environment files unchanged and rejects non-development Settings. The script holds an advisory lock in a dedicated connection while Alembic opens its own guarded normal-engine connections. App writers must already be stopped. Expected effects: new eight empty tables, existing delivery uniqueness/order link, updated notification checks/indexes, and version-row advancement through the five pending revisions. No existing financial data or application defaults are backfilled. The target is never empty/reset.

### Post-upgrade acceptance checklist

- Reassert exact database/account and one version row at 14c0d3e2f782; 25 application tables/26 total, correct names and no unexpected objects.
- compare_metadata empty; independently verify actual CHECK definitions/enforcement/defaults/PK/FK/unique/indexes and no missing type precision. Do not equate CHECK names with behavioral testing.
- Existing table counts and complete logical row fingerprints unchanged; version metadata intentionally changes. Existing account/ledger/balance/receipt/idempotency/reversal fingerprints unchanged. New eight tables empty unless separately authorized subsequent application writes occur.
- Notification predicates still accept all rows; recipient/read/event state preserved. Account/business ownership/reversal/domain checks clean; no inferred historical order debt/linkages.
- With writers still paused, run approved read-only application smoke checks for customer credit/history, owner dashboard, Admin queries and driver status. Avoid manual acceptance/posting actions against real finance; isolated synthetic integration tests require separate scope.
- Verify no data/config change in test DB through appropriate independent baseline/monitoring, not by writing tests there. Agent will not migrate that DB.
- Record safe evidence, versions, times, backup ID and errors. Resume writers only after acceptance/operator approval. New role features stay unsupported until their services/authorization exist.

### Failure/recovery

MySQL DDL can commit and lock; the five-revision chain cannot be rolled back as one transaction. Any failure stops the template; no reset/retry or downgrade. Preserve partial development state and logs, keep writers paused, collect read-only schema/version/row fingerprints. If safe, propose a narrowly reviewed forward correction with new authorization. Otherwise restore the verified backup into a separate empty schema, reconcile and obtain explicit cutover/configuration approval; do not overwrite the failed DB or automatically restore on top. The backup/recovery procedure must account for any writes after backup (hence writer pause). No successful recovery drill or measured RTO is claimed.

## Readiness and blockers

| Item | Status |
|---|---|
| Live identity/schema/row count audit | PASS |
| Schema delta and five-revision plan | PASS for preparation |
| Current intermediate notification compatibility | PASS: zero violating rows |
| Empty isolated migration chain | PASS from authorized Phase 3.2 |
| Backup tooling availability | PASS: mysql/mysqldump 8.0.46 |
| Verified backup, encryption/ACL and manifest | BLOCKED / not performed |
| Dedicated populated restore and upgrade tooling/access/evidence | BLOCKED / not authorized or performed |
| Writer pause, maintenance/lock budget and recovery/cutover approval | REQUIRED / not established |
| Guarded command template | PREPARED; syntax/static validation only |
| Development execution authorization | NOT GIVEN; migrations NOT RUN |

Do not execute the template yet. Next safe step is approval for backup and an isolated populated restore/upgrade rehearsal with the necessary reviewed tooling. Once those prerequisites pass, request separate **explicit authorization to upgrade only lankapex_db from c9d5e8f7a237 to 14c0d3e2f782** using refreshed reviewed evidence. Authorization to plan or migrate an isolated schema never implies permission to migrate development. Stop after this audit/preparation. AI remains deferred.
