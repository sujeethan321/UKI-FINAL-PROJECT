# Phase 3.6: final development upgrade preparation

Phase 3.7 has since recorded observed writer inactivity, created a fresh protected backup and prepared an exact-target isolated rehearsal profile. See [Phase 3.7 safety checks](phase37-development-upgrade-safety-checks.md). The Phase 3.6 statements below describe the state before that backup; development upgrade authorization remains absent.

2026-11-09 (Asia/Colombo). **Preparation only. `lankapex_db` was not upgraded or changed.** No backup, restore, schema change, database reset, stamp, downgrade, deployment or push ran in this phase. This plan supersedes historical readiness statements in [Phase 3.3](phase33-development-upgrade-plan.md), [Phase 3.4](phase34-development-backup-and-recovery.md) and [Phase 3.5](phase35-recovery-preflight.md) where later evidence resolved them.

## Fresh read-only development audit

Ran the existing guarded `.server-logs/phase33-development-audit.py` against the configured local development engine in a read-only consistent snapshot. The audit verified both the engine URL database and `SELECT DATABASE()` as exactly `lankapex_db`. Its private `.server-logs/phase33-development-audit.json` contains schema, counts and one-way financial fingerprints; do not publish it or raw financial rows.

| Check | Actual result | Status |
|---|---|---|
| MySQL and Alembic | MySQL 8.0.46; one version row at `c9d5e8f7a237` | PASS |
| Current inventory | 17 application tables, 18 total; all InnoDB; zero views, routines, events or triggers | PASS |
| Target delta | Eight expected tables missing, no unexpected tables or column drift | PASS |
| Pending chain | `d0e6f9a8b348` → `e1f7a0b9c459` → `f2a8b1c0d560` → `03b9c2d1e671` → `14c0d3e2f782` | PASS |
| Intermediate notification predicates | Zero incompatible rows for all six inspected checks | PASS at audit time |
| Financial/ownership baseline | Six ledger rows (four credit sales, two repayments); zero customer/business mismatches; no ledger order links | PASS |
| Comparison with Phase 3.4 backup | Table counts and **all 17 application-row fingerprints match**. The backup baseline also hashes `alembic_version`, which the audit excludes from application hashes; comparing whole dictionaries gives a misleading mismatch | PASS after matching comparable tables |
| Writer pause and fresh backup | Neither has been performed in Phase 3.6 | BLOCKER for execution |

The earlier Phase 3.5 populated rehearsal passed on the *specific* Phase 3.4 backup: 18 original tables restored, five revisions applied, 26 total tables at head, original rows/ledger preserved, and no model difference. It does not establish that a future freshly generated SQL file has been restored successfully.

## Prepared safeguards and commands

The reviewed development command template is [`operations/phase33-upgrade-development.py.example`](operations/phase33-upgrade-development.py.example). This phase aligned its restore evidence guard with the real `migration_verify` namespace used by the Phase 3.5 supplied-connection Alembic hook. It now requires `--backup-validation` and checks that the fresh dump validation's source row counts and application fingerprints equal the paused baseline, that its source identity/revision match, and that the separately reviewed populated rehearsal evidence names the **same backup SHA-256**. It still requires exact development settings, target, current revision, expected chain, unchanged pre-upgrade rows, explicit pause/execute flags, a connection gate before DBAPI opening and a SQL gate against test/isolated/database-management statements. Its local source is an unexecuted operator template, not evidence that a development upgrade has run. Do not bypass or fabricate evidence fields.

The new [`backend/scripts/verify_development_upgrade.py`](../backend/scripts/verify_development_upgrade.py) is an independently invoked read-only post-upgrade verifier. It requires `lankapex_db`, the original `c9d5e8f7a237` baseline and final `14c0d3e2f782`; checks 26 tables, model parity, all original row counts/fingerprints, eight empty new tables, six ledger entries/types, account/business and ledger/account relationships, and unchanged effective balance and ledger fingerprints computed with the existing Decimal ledger service. It prints no balances or customer rows. Syntax checks passed; a deliberate read-only invocation against the still-unmigrated development DB stopped as expected at the revision guard. The test target name was rejected at argument parsing.

### Exact recommended maintenance sequence (future, NOT executed)

1. Obtain separate **explicit authorization to upgrade `lankapex_db`** and designate a maintenance operator/window. Capture current service inventory without printing process command lines or connection SQL. Stop the actual FastAPI workers and every app/background worker, scheduler, import, webhook and manual writer by their known service managers or verified PIDs. Prevent new sessions/writes and drain in-flight transactions. The frontend alone is not a writer pause. Record operator, pause start, components and observed active transactions. A MySQL advisory lock coordinates only cooperating scripts; it cannot prove that all writers stopped. Do not kill unknown processes or toggle global `read_only` automatically.
2. With writers and DDL still paused, rerun a fresh guarded read-only audit:

   ```powershell
   .\backend\.venv\Scripts\python.exe .\.server-logs\phase33-development-audit.py
   ```

   Inspect the private output for exact target, `c9d5e8f7a237`, 18 original tables, known pending chain, zero drift, valid notification predicates and financial/ownership invariants. Keep `.server-logs/phase33-development-audit.json` as the paused baseline; save its checksum and a private, immutable copy for the operator before further work. If counts/data have changed, review the new baseline; the historical six-ledger-row assumptions in the current backup script require a reviewed adjustment before proceeding.
3. While the pause holds, run the previously validated timestamped backup script **only after separate backup authorization in the maintenance plan**:

   ```powershell
   .\backend\.venv\Scripts\python.exe .\.server-logs\phase34-create-backup.py
   ```

   This script writes a new unique `lankapex_db_YYYYMMDDTHHMMSS+0530.sql` under the protected ignored `.server-logs/private-backups/` directory, plus `.manifest.json` and `.validation.json`. It uses a temporary protected client option file (removed afterward), `mysqldump` 8.0.46, `--single-transaction`, structure/data/triggers/routines/events, no global GTID, and explicit `lankapex_db` source. Verify exit status 0, empty stderr, nonzero file size, SHA-256 equal to manifest, 18 expected CREATE TABLE statements, exact per-table row counts and protected baseline fingerprints, the current Alembic revision, six ledger entries/types (or revised approved expectations), source before/after equality and private ACL/Git exclusion. Keep the writer pause during these checks. The existing script labels its validation `writer_pause` as not imposed; the operator must record the external pause separately.
4. **Restore-test that exact fresh checksum** into a newly provisioned empty disposable database under the `lankapex_migration_verify_...` namespace, using a reviewed exact-target adaptation of the Phase 3.5 runner. Do not reuse or clear either completed verification database. Assert target identity/grants/emptiness, dump SQL scope and protected backup baseline; execute one restore, verify all original rows and balances, then execute the five revisions and verify 26 tables at head and unchanged original data. Produce private evidence with `restore_database`, `status=PASS`, `backup_sha256`, `source_revision`, `target_revision` and original **application-only** `table_fingerprints`. Independently inspect the evidence provenance; an editable JSON is only an attestation. This new target and runner adaptation are **not yet prepared or authorized**. Keep the development writer pause until the upgrade decision; if the maintenance window cannot cover this rehearsal, stop and replan rather than relying on a moving source baseline.
5. After the exact fresh backup and populated rehearsal pass, recheck writers paused, current revision, source fingerprints and backup checksum. The guarded development upgrade command is then:

   ```powershell
   .\backend\.venv\Scripts\python.exe .\docs\operations\phase33-upgrade-development.py.example `
     --database lankapex_db `
     --baseline .\.server-logs\phase33-development-audit.json `
     --backup '<protected-fresh-SQL-absolute-path>' `
     --backup-manifest '<matching-manifest-absolute-path>' `
     --backup-validation '<matching-validation-absolute-path>' `
     --restore-evidence '<reviewed-fresh-rehearsal-evidence-absolute-path>' `
     --execute --confirm-writes-paused --confirm-target lankapex_db
   ```

   This command is **not authorized by Phase 3.6**. Replace every bracketed path only with the reviewed private artifact from steps 3–4. The tool must refuse missing/mismatched evidence or changed rows. MySQL DDL is non-transactional; it checks the version after each revision and stops on any mismatch.
6. Keep writers paused and run the prepared read-only post-upgrade verifier against the same paused baseline:

   ```powershell
   .\backend\.venv\Scripts\python.exe .\backend\scripts\verify_development_upgrade.py --database lankapex_db --baseline .\.server-logs\phase33-development-audit.json
   ```

   Independently inspect final constraint definitions/CHECK enforcement and required application read-only smoke routes; no synthetic acceptance, repayments, seed data or repair scripts on development. Confirm test and earlier isolated databases remained outside the upgrade scope. Record revision, counts, private hashes, timings and sanitized errors. Resume writers only after operator acceptance.

### Failure and recovery

Stop immediately on a failed dump, restore, migration stage or post-check. Preserve the source database's actual partial schema/version, all private logs, the verified backup and the fresh baseline; keep writers paused. Do **not** rerun migration, reset, stamp, downgrade, replay financial transactions or restore over `lankapex_db` automatically. MySQL DDL can commit each operation, so a later failed stage can leave earlier stages in place. Diagnose using read-only inventory and row/fingerprint comparisons. A reviewed forward correction may be safer than reversing committed DDL, but requires new authorization. If forward correction is not feasible, restore the verified fresh dump to a **new empty** recovery database, verify all original rows and relationships, then separately authorize any cutover or application configuration change. Account for writes after the backup before any cutover; the paused window is meant to prevent this gap. The successful Phase 3.5 rehearsal demonstrated recoverability of its own backup, but no timed RTO/RPO or real development failover has been measured. The backup is ACL-protected, not proven encrypted or offsite.

## Final blockers

1. A real, documented writer/DDL pause and fresh paused baseline have not been established.
2. A new timestamped maintenance-window backup has not been authorized or created in this phase.
3. The new backup's checksum needs its own isolated populated restore/upgrade rehearsal, new empty target, reviewed runner adaptation and evidence; the Phase 3.5 evidence cannot be relabeled for new bytes.
4. The development command template and post-verifier have static/read-only validation, but the exact maintenance artifact set and command have not been run together. Treat the final upgrade as awaiting operator review, not as approved.
5. Backup encryption/offsite retention, recovery timing and independent writer-pause verification remain operational decisions.
6. Separate explicit authorization for the actual `lankapex_db` upgrade has **not** been granted.

No development upgrade should run until these gates are resolved. AI Summary remains deferred.
