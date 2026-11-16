# Day 4 — Customer invitation security test upgrade and results

Date: 2026-11-09 (Asia/Colombo). The preparation and backup were followed by separate, explicit authorization for a one-time test-only upgrade. No demo/development/rehearsal schema was migrated, and no backup was restored.

## Read-only evidence

| Gate | Result |
| --- | --- |
| Configured process and actual `SELECT DATABASE()` | **PASS** — `APP_ENV=testing`, configured/engine/actual database `lankapex_test_db`. |
| Actual account | **PASS** — `CURRENT_USER()` is `lankapex_app@localhost`. |
| Source revision chain | **PASS** — one base, 15 linear revisions; current test revision `03b9c2d1e671`, pending `14c0d3e2f782` then `6e3f2c1a9b04`. Head is `6e3f2c1a9b04`. |
| Starting tables/data | **PASS** — 20 application tables plus `alembic_version`; no invitation table; zero application rows across all 20 tables. No test records require migration/backfill. |
| MySQL prerequisites | **PASS** — MySQL 8.0.46, strict transaction mode and foreign-key checks enabled. The current grant includes migration privileges. |
| Test grant scope | **RISK** — existing `lankapex_app` grant for `lankapex_test_db` is `ALL PRIVILEGES` and uses unescaped underscores; the account also has other schema grants. The prepared runner checks the exact target at settings, engine, DBAPI connection, SQL, and `SELECT DATABASE()` levels. This review did not change grants. Do not reuse this broad grant as a production pattern. |
| Guarded default preflight | **PASS** — `upgrade_customer_link_test_schema.py --database lankapex_test_db` completed read-only. |
| Current test-schema backup/recovery evidence | **PASS for backup integrity** — fresh private dump, checksum and manifest verified below. A restore rehearsal has not been performed. |
| Permission for test migration | **PASS** — separate, explicit authorization received for `lankapex_test_db` only, conditional on fresh checks. |

## Migration review

`14c0d3e2f782` creates `customer_addresses`, `vehicles`, `vehicle_documents`, `user_preferences`, and `business_settings` plus their new indexes, checks and foreign keys. `6e3f2c1a9b04` then creates `customer_link_invitations` with a six-digit-code digest, recipient/issuer/business/profile foreign keys, unique digest and recipient/expiry index. Neither upgrade contains a drop, rename, data backfill, financial-table change, or mutation of an existing table. New foreign keys reference existing tables, and the new invitation table is initially empty. The approved 14-revision chain has previously been rehearsed against an isolated database; the new fifteenth revision has **not** had an execution rehearsal. MySQL DDL is not transactionally reversible; if a stage fails, preserve partial state and stop for operator review. Do not downgrade, stamp or automatically retry.

The test database has no current application rows, but a fresh backup still preserves the starting schema and gives an auditable recovery point. Recommended operator backup (interactive password prompt, no password in arguments or logs), from the project root in PowerShell:

```powershell
$backup = Join-Path (Resolve-Path '.server-logs/private-backups') ('lankapex_test_db_' + (Get-Date -Format 'yyyyMMddTHHmmss') + '.sql')
& 'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe' --host=localhost --user=lankapex_app --password --single-transaction --routines --triggers --events --set-gtid-purged=OFF --no-tablespaces --result-file="$backup" lankapex_test_db
if ($LASTEXITCODE -ne 0) { throw 'Test backup failed' }
Get-Item -LiteralPath $backup | Select-Object FullName,Length
Get-FileHash -Algorithm SHA256 -LiteralPath $backup
```

Record the checksum and verify the dump contains the 20 application table definitions and revision `03b9c2d1e671`, without printing row contents. Keep the backup private and outside Git. Recovery from a partial upgrade requires an operator-reviewed restore into a **new** isolated schema or separately authorized rebuild of the test schema; do not reset the existing test database automatically. Preserve the failed schema and logs for diagnosis.

### Completed backup evidence

The fresh dump was created from a connection that rechecked configured, engine and actual database identity as `lankapex_test_db`, account `lankapex_app@localhost`, revision `03b9c2d1e671`, 21 InnoDB tables, and zero application rows. A short-lived MySQL option file was placed only in the protected backup directory and removed immediately after `mysqldump`; the password was not passed on the command line or logged. The dump completed with exit code 0.

| Artifact/check | Actual result |
| --- | --- |
| SQL dump | `.server-logs/private-backups/lankapex_test_db_20261109T170436Z_03766a27.sql` |
| Manifest | `.server-logs/private-backups/lankapex_test_db_20261109T170436Z_03766a27.json` |
| Size | 39,679 bytes; matches manifest. |
| SHA-256 | `cc56a97abd773509a7b3e4fb7bc67e2b5504c1ba0095d7eff4b7909f697af045`; independently rechecked against the manifest. |
| SQL identity/content | Header names only `lankapex_test_db`; 21 `CREATE TABLE` statements, revision insert `03b9c2d1e671`, zero application-table inserts, dump-completed footer. No `CREATE DATABASE`, `USE`, or `DROP TABLE` statement. |
| Source after dump | Same exact database/revision and zero application rows. |
| Privacy | `.server-logs/` is Git-ignored; dump ACL allows only `SYSTEM` and the current sandbox account; no temporary option file remains. Operator recovery access would require a reviewed handoff of this protected backup. |

The guarded read-only preflight was rerun after backup and **passed**. A wrong-target invocation using `--database lankapex_db` was rejected by argument validation before any connection. The runner has no default execution path; only `--execute` plus exact `--confirm-target lankapex_test_db` can begin migration after its fresh identity/schema checks.

## Guarded commands used for the authorized test-only upgrade

The script is preflight-only by default. It rejects other database names and requires exact confirmation for execution; it checks zero application rows and expected starting schema/revision before any write. It upgrades one revision at a time, verifies each recorded revision, then checks 26 modeled application tables plus `alembic_version`, model/schema consistency and zero application rows. It does not seed data.

```powershell
# Read-only recheck immediately before the approved change:
$env:APP_ENV = 'testing'
$env:MYSQL_DATABASE = 'lankapex_test_db'
.\backend\.venv\Scripts\python.exe .\backend\scripts\upgrade_customer_link_test_schema.py --database lankapex_test_db

# Executed once after separate explicit approval and verified backup:
.\backend\.venv\Scripts\python.exe .\backend\scripts\upgrade_customer_link_test_schema.py --database lankapex_test_db --execute --confirm-target lankapex_test_db
```

Run the commands from `C:\Users\admin\Desktop\LankaPex` with the existing private test credential. Do not edit normal environment files. Stop on any failed identity, revision, table, row-count, privilege, MySQL, or backup check. The command was separately authorized and executed once after all verified gates passed.

## Security tests after the test upgrade

`backend/tests/test_customer_link.py` currently covers Owner-only invitation, foreign Owner denial, unauthenticated denial, six-digit format, wrong recipient denial, expiry, reissue, successful Customer consent, single-use replay denial, exact `CustomerProfile.user_id` link, preserved ledger balance/history, and foreign Customer account isolation. Run it only after the guarded schema upgrade and fresh database identity check:

```powershell
$env:APP_ENV = 'testing'
$env:MYSQL_DATABASE = 'lankapex_test_db'
.\backend\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider .\backend\tests\test_customer_link.py
```

**Coverage gap at preparation time:** concurrent acceptance, concurrent reissuance/collision behavior, and the dedicated acceptance rate limit had no targeted test. A concurrent acceptance test was subsequently added and passed; reissuance/collision and dedicated rate-limit scenarios remain for later hardening.

## Readiness decision

**PASS** for target identity, static migration review, private backup/checksum and repeated guarded read-only preflight. The later authorized test-only upgrade and invitation tests also **PASSED**, as detailed below. The demo and development databases, existing backups and all financial records remain untouched.

## Authorized execution and post-upgrade verification

- Revalidated the pinned private SQL dump and manifest immediately before the change: checksum and size matched, source was `lankapex_test_db` at `03b9c2d1e671`.
- The first process inventory attempt was permission-denied. An elevated **read-only** process inventory then identified editor formatter processes, a demo backend on port 8001 and a MySQL client targeted at `lankapex_demo_db`; no pytest, Alembic or dump process was running. The application account's MySQL session list showed no other visible active session. No process was stopped. The application account does not provide DBA-wide session visibility; this is a residual visibility limit, not evidence of a conflicting runner.
- Fresh guarded read-only preflight passed directly before execution. It rechecked exact configured/actual target, `lankapex_app@localhost`, empty 20-table application schema, `03b9c2d1e671`, grants, MySQL settings and the 15-revision chain.
- Ran the exact guarded `--execute --confirm-target lankapex_test_db` command **once**. Stage `03b9c2d1e671 → 14c0d3e2f782`: **PASS**. Stage `14c0d3e2f782 → 6e3f2c1a9b04`: **PASS**. No retry, downgrade, stamp or cleanup was necessary.
- Guarded and independent read-only post-checks: final revision `6e3f2c1a9b04`; **26** application tables plus `alembic_version` (**27** total); no model/schema differences; zero application rows immediately after migration. The 20 starting tables had zero rows before the upgrade, so no original application rows were altered.
- `backend/tests/test_customer_link.py`: **1 passed**. Covers six-digit format, Owner role/business ownership, Customer recipient binding, expiry, reissue, replay denial, profile link, linked balance/history and foreign Customer isolation.
- Added `backend/tests/test_customer_link_concurrency.py` with independent MySQL connections and a held business row lock. Simultaneous acceptance yielded one **200** and one **404**, replay **404**, exactly one linked profile and no remaining invitation row. Invitation tests together: **2 passed**.
- Customer dashboard and history regressions after upgrade: **80 passed**. Final read-only test database check: revision unchanged, 27 total tables, **zero application rows** (including zero invitation rows); synthetic committed race fixtures were removed by exact IDs.

Remaining risk: the existing test account grant is broad/unescaped, and the MySQL session inventory lacks DBA-wide visibility. This did not change during the test-only upgrade. Dedicated rate-limit and concurrent reissuance/collision tests remain to be added before public rollout. The private backup and checksum manifest are preserved.
