# Phase 3.4: development backup and recovery preparation

2026-11-09, Asia/Colombo. **Authorized backup CREATED and file validation PASSED. Restore and populated upgrade NOT RUN.** No schema/record/privilege change, Alembic command, rehearsal-database creation, deployment or push was performed. No access to lankapex_test_db or modification of the completed isolated verification database was needed.

## Backup artifact and protection

Backup start identifier: **20261109T001844+0530**, local time 2026-11-09 00:18:44 UTC+05:30. Timestamp came from an explicitly selected Asia/Colombo offset, not the host's timezone.

Protected directory, outside version control:

```text
C:\Users\admin\Desktop\LankaPex\.server-logs\private-backups\
```

Files:

| Artifact | Filename |
|---|---|
| SQL dump | lankapex_db_20261109T001844+0530.sql |
| Manifest | lankapex_db_20261109T001844+0530.manifest.json |
| Private validation and baseline | lankapex_db_20261109T001844+0530.validation.json |

**Size: 38,177 bytes. SHA-256:**

```text
9253fd3577d5c2bff37a4e5a08d08d5d6112190cd74775fe6d7aa8d6345477be
```

The directory is inside the workspace but **not version-controlled**: .server-logs/ and *.sql are ignored, independently confirmed by git check-ignore. It is not in frontend/public or any served artifact folder. NTFS directory inheritance is disabled; only the current Windows user and SYSTEM have allowed access. All generated files were rechecked for unexpected allowed principals; none were found. No backup file was staged, committed, uploaded or attached to a report. The report contains no credentials, raw records or monetary balances.

This is an ACL-protected local SQL file, **not a claim of file encryption, verified disk encryption or offsite protection**. Encryption/offsite retention and key custody remain to be approved and verified before relying on it against machine loss. Plaintext staging is restricted to the authorized Windows user/SYSTEM. Do not copy the SQL into the repository, public folders, issue comments or chat.

## What actually ran

Reviewed [Phase 3.3 plan](phase33-development-upgrade-plan.md), backend Settings/URL construction and backup_manifest helpers. Confirmed local mysqldump 8.0.46. Source guards required APP_ENV=development, local host, engine database and SELECT DATABASE()=lankapex_db; revision c9d5e8f7a237, 18 tables, 6 ledger entries and all InnoDB. Zero views/triggers/routines/events were observed before and after. If those preconditions had changed, the backup script would have stopped.

One mysqldump process ran, with a private temporary option file loaded from existing backend credentials in memory; no password was put in command arguments or logs. The option file inherited the protected directory ACL and was removed afterward. Its absence was independently checked. The local existing connection has no configured CA; local client SSL mode was PREFERRED, not falsely described as certificate-verified remote TLS.

Executed command structure (temporary option filename redacted; no password shown):

```text
"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe"
  --defaults-file=<temporary protected option file>
  --single-transaction --quick --skip-lock-tables --skip-add-locks
  --skip-add-drop-table --no-tablespaces --set-gtid-purged=OFF
  --column-statistics=0 --hex-blob --routines --events --triggers
  --complete-insert --skip-extended-insert --order-by-primary
  --default-character-set=utf8mb4
  --result-file=<protected timestamped SQL path>
  lankapex_db
```

Options include structures/data and stored-object export where present; no existing objects were omitted by a schema-only/data-only filter. Complete, single-row INSERT statements permit private per-table row counts without executing SQL. Output went directly to --result-file, avoiding PowerShell encoding conversion. No --all-databases, --databases, flush privileges, destructive source SQL or global GTID export. --skip-add-locks avoids generating restore LOCK TABLES statements; --skip-lock-tables avoids source table locks.

InnoDB --single-transaction produces a consistent committed-row snapshot. No writer pause or global lock was imposed during this authorized backup. Independent source row/schema snapshots before and after matched exactly for every existing table, including ledger and version row. This supports the observed stability but is **not proof that all writers or concurrent DDL were administratively paused**. A future maintenance baseline must still freeze writers/DDL; concurrent DDL can invalidate a transactional dump. [MySQL backup consistency rules](https://dev.mysql.com/doc/refman/8.0/en/mysqldump.html).

## Actual read-only validation results

| Check | Actual result | Status |
|---|---|---|
| mysqldump exit | 0 | PASS |
| Client stderr | Empty, no warnings/errors | PASS |
| File presence/size/header/footer | 38,177 bytes, MySQL header and dump-completed footer | PASS |
| Hash | SHA-256 above, independently reread and verified against manifest | PASS |
| Structures | Exactly 18 expected CREATE TABLE statements | PASS |
| Data | INSERT row counts match each of the 18 source tables | PASS |
| Ledger | Exactly 6 row INSERTs: 4 credit_sale, 2 repayment | PASS |
| Alembic | One version row containing c9d5e8f7a237 | PASS |
| Source stability | All pre/post row counts, PK-ordered logical-row hashes, schema, version and object counts equal | PASS |
| SQL scope precheck | No plain USE/CREATE DATABASE/DROP DATABASE/DROP TABLE/TRUNCATE/GRANT/REVOKE or global GTID assignment detected | PASS for file precheck |
| Manifest | Existing validate_manifest/read_manifest accepted exact metadata, file size/header/hash | PASS |
| ACL/version-control protection | Restricted user/SYSTEM; ignored by Git | PASS |
| Temporary credentials | Option file absent after completion | PASS |
| Restoration and recovery | Not executed; no restore database created | NOT RUN |

Row counts embedded in the private dump:

| Table | Rows |
|---|---:|
| users | 5 |
| businesses | 1 |
| business_members | 1 |
| customer_profiles | 2 |
| credit_accounts | 1 |
| ledger_entries | 6 |
| business_approval_audits | 1 |
| payment_reminders | 1 |
| driver_profiles | 1 |
| notifications, communication_consents, communication_attempts | 0 each |
| delivery_requests, delivery_assignments, delivery_status_events | 0 each |
| product_categories, products | 0 each |
| alembic_version | 1 |

Table definitions and INSERT counts were parsed privately; financial values, contacts, password hashes, receipt identifiers and idempotency values were never logged. The private validation JSON contains schema, aggregate counts and non-reversible table hashes, not raw row contents. SQL content prechecks and checksums do not establish that every statement is safe for any destination or that restoration succeeds; the next stage must review executable comments/session directives and verify destination confinement.

## Separate disposable restore-and-upgrade rehearsal — proposed only

New proposed target: **lankapex_migration_verify_recovery20261109**. This name is distinct from both existing application databases and the completed lankapex_migration_verify_20261107. It intentionally fits the existing **migration** verification namespace so env.py can accept a guarded supplied connection for the populated-upgrade stage. It has not been created, connected to or modified here.

The existing restore_command helper accepts only restore_verify names, so **do not pass this new name to that helper, fake an engine URL, rename an existing schema or bypass identity checks**. A separately reviewed standalone recovery harness must explicitly support the exact dual-purpose disposable target, verify it using the migration-purpose guard, and confine both restore and subsequent migration to it. This is a future tooling task; no restore executor is run or claimed ready in this step.

Proposed approval and execution order:

1. Obtain separate authorization for the exact new disposable target, restore operation and five-revision populated upgrade. Authorized DBA independently confirms absence, creates it with utf8mb4/utf8mb4_unicode_ci, and provides a suitably confined connection identity. No account/password/global privilege change is implied. Escape underscores in database-level grants under current partial_revokes=OFF. Do not use a broad root session to import SQL. Do not reuse/reset completed isolated databases.
2. Review/prepare the standalone recovery harness and its default read-only preflight. Require exact target name, actual SELECT DATABASE(), engine URL, identity, MySQL version, strict mode, source fingerprint manifest, and no tables/views/routines/events. Before any DBAPI connection, reject lankapex_db, lankapex_test_db, the completed verification target and every unapproved destination.
3. Revalidate this exact SHA-256 and metadata from the protected SQL/manifest. Review all SQL including versioned executable comments, stored definers and references; allow expected session-only dump directives only after review. Never treat --database as a sandbox for arbitrary SQL. Keep external integrations disabled and restored real financial/customer data private.
4. Construct a binary stdin restore subprocess with an argument list, no shell expansion or text pipeline:

   `mysql.exe --defaults-file=<private target-only options> --binary-mode --default-character-set=utf8mb4 --database=lankapex_migration_verify_recovery20261109`

   Feed the validated file's bytes to stdin, not a Get-Content text pipeline. Stop on first error; no --force or automatic cleanup. Only the approved dedicated target may receive the dump's CREATE TABLE/INSERT/session statements. Do not run this command now.
5. After restore, reenable/check normal FK validation as required by the reviewed dump session settings. Confirm 18 total tables, 17 application tables and exactly one c9d5e8f7a237 version row. Compare all table row counts/logical hashes against the **backup validation JSON**, not the possibly changed current development database. Validate account-business/reversal integrity and effective ledger balances using existing Decimal semantics in memory; record only aggregate/fingerprint evidence. A full current-model integrity checker will report missing future tables at this legacy stage, so use schema-aware checks rather than fabricate PASS.
6. On that same restored disposable database, pass its verified connection via the existing migration-purpose Alembic hook with testing Settings and normal test engine unused. Apply d0e6f9a8b348 -> e1f7a0b9c459 -> f2a8b1c0d560 -> 03b9c2d1e671 -> 14c0d3e2f782. Never use a plain CLI upgrade that resolves development settings. Snapshot notification preconditions at every intermediate stage; preserve all restored rows.
7. Verify 25 application tables/26 total, exact final revision, model/schema/constraint definitions, no unexpected objects, every original table count/hash preserved (excluding intentionally advanced version metadata), six ledger rows and unchanged financial fingerprints. New eight tables should be empty. Separate synthetic constraint/API tests need explicit scope; do not modify restored records merely to manufacture security evidence.
8. Record private restore/upgrade evidence tied to this backup SHA and baseline, operator, actual identities, timestamps, stage/results and errors. Only actual successful restoration and populated upgrade permits a PASS attestation. If adapting Phase 3.3's command template, its restore-evidence guard currently expects restore_verify: align that reviewed guard/evidence contract with this explicitly approved dual-purpose name under separate code authorization; never edit evidence fields to defeat the guard.

Any restore or migration failure: stop, preserve the partial disposable database and sanitized error evidence, and request a reviewed forward correction or new target. No retry/reset/downgrade/drop/stamp, source restore, financial repair or automatic cutover. The backup remains the preserved source. Creating the disposable target and changing privileges remain DBA actions, not implied permission in this backup task.

## Maintenance writer-pause checklist for eventual development upgrade

- Name the owner, maintenance window, exact lankapex_db source/head and approved command. Inform local users through an explicitly authorized channel; no messages were sent here.
- Stop accepting writes at the application boundary; pause API workers, scheduled tasks, reminders, imports, webhooks and manual SQL writers/DDL. Do not merely close the frontend browser or hold an advisory lock. Record components paused and operator/time.
- Drain/confirm in-flight transactions and stop background retry queues; review metadata/process/transaction activity without logging private statements. Do not kill DB sessions or toggle global read_only without separate approval.
- Capture a fresh consistent read-only schema/count/row-hash/financial baseline under the pause; rerun all intermediate notification preconditions and schema-drift checks. If source changed since this backup, take a newly authorized matching backup and repeat necessary restore validation or approve a documented compatible evidence strategy; do not forge a new baseline into old evidence.
- Verify backup checksum, storage/ACL/encryption policy, actual successful populated restore/upgrade evidence, available disk, lock budget and rollback-forward/cutover decision. Obtain separate explicit development-upgrade approval. Session UTC, exact target guards and no normal test-engine connection are mandatory.
- Keep writers paused while applying approved revisions and checking final table/schema/revision, preserved original rows/financial fingerprints and approved read-only application smoke checks. No automated balance repair or seeded real orders.
- On any failure, preserve state and keep writers paused; assess read-only, request recovery approval. MySQL DDL cannot be rolled back as a unit. Never automatically restore over source, stamp forward or run destructive downgrades.
- Resume write components only after operator acceptance; verify activity/errors and retain private evidence. No development maintenance pause was imposed or upgraded DB claimed during this backup task.

## Remaining blockers and authorization boundary

**Resolved:** timestamped backup exists, mysqldump/file/manifest/content validation passed, protected ACL and version-control exclusion verified, no source changes observed across backup.

**Still required:** new target provisioning/access; reviewed exact-target recovery harness and aligned evidence guard; separately authorized restore/populated upgrade; actual restore verification; encryption/offsite retention decision; maintenance writer pause and a sufficiently current matching baseline/backup before development changes. The existing isolated clean-chain PASS is not a populated recovery PASS. Recovery RTO/RPO was not measured.

Stop after this backup and file validation. Request separate authorization before performing the restore-and-upgrade rehearsal solely in **lankapex_migration_verify_recovery20261109**, after DBA provisioning and review of its guarded tooling. No development upgrade, restoration, database creation or privilege modification is authorized by the completed backup operation. AI remains deferred.
