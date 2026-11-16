# Phase 3.8: development database upgrade readiness

2026-11-09, Asia/Colombo. **Readiness review only; no development migration or database write occurred.** Target under review: existing `lankapex_db`, currently `c9d5e8f7a237`. Proposed head: `14c0d3e2f782`. Separate explicit authorization and a real writer/DDL pause are required before any execution.

## Evidence and current status

The [Phase 3.7 report](phase37-development-upgrade-safety-checks.md) records that the pinned 2026-11-09 10:55:02 +05:30 backup restored into `lankapex_migration_verify_recovery20261109b`; the five revisions applied in order; 25 application tables plus `alembic_version` existed at head; every original row fingerprint, all six ledger entries, effective credit balance fingerprint and tested account/ledger relationships survived; all eight new tables remained empty; and Alembic model comparison found no differences. The first 1044 preflight failure was resolved by DBA setup before the successful run. The private populated-rehearsal evidence is an operator attestation tied to that exact backup SHA, not a substitute for the actual report and command output.

Read-only revalidation in Phase 3.8 found:

| Check | Actual result | Status |
|---|---|---|
| Backup SQL | Protected `.server-logs/private-backups/lankapex_db_20261109T105502+0530.sql`, 38,177 bytes; SHA-256 `1588a78f4e5b5e95d9556233d79241991ea063224fd6e73da363ae545e78245e` equals manifest and rehearsal evidence | PASS |
| Private validation/evidence | Source and rehearsal revisions are `c9d5e8f7a237` and `14c0d3e2f782`; application-row and effective-balance fingerprints agree with the audit | PASS |
| Live development source | Read-only exact `lankapex_db` connection still at source revision; table inventory and **all** original row fingerprints match the backup | PASS at review time; repeat under pause |
| Revision/model static check | 14-revision graph, five expected pending revisions, 25 model tables and MySQL offline model/migration validation passed without DB writes | PASS |
| Guarded development template | Python syntax passed; argument choices accept only `lankapex_db`; exact normal-engine/database checks, pre-DBAPI target gate, source revision/table/row checks, exact backup SHA and validation contract, matching isolated rehearsal evidence, expected revision tail, explicit `--execute`, `--confirm-target`, `--confirm-writes-paused`, per-stage revision checks and final row/schema checks reviewed | PASS for static review; **not executed** |
| Sustained writer/DDL pause | Phase 3.7 observed inactivity at backup time only; no continuous maintenance freeze exists now | **BLOCKER** |
| Development upgrade authorization | Not granted in this task | **BLOCKER** |

The [guarded operator template](operations/phase33-upgrade-development.py.example) uses the normal development Alembic path because the supplied-connection hook correctly refuses development. It has no backup/restore/reset or financial repair action. Its SQL gate rejects known non-development database references and database/global/reset statements. Its flags are assertions by the operator, **not proof** that writers are paused. The separately invoked [read-only post-upgrade verifier](../backend/scripts/verify_development_upgrade.py) checks the final schema and financial baseline. Neither tool has been executed as a development migration in this phase.

## Writer and DDL pause procedure — required before execution

Assign one maintenance operator and a defined window. Preserve a private record of the operator, start/end times, services and sessions inspected. The operator must first prevent new user actions at the API boundary, then stop known FastAPI/uvicorn reload and worker processes through their actual launch terminal/service manager. Pause any scheduled reminders, scripts, imports, queues, webhooks, admin jobs and manual MySQL writers. Verify the scheduler/task inventory and agree with every person or automation holding development credentials that no direct SQL/DDL will run. The frontend alone is not the writer; MySQL must remain running. Do not stop an unknown process or change MySQL grants/global `read_only` as part of this plan.

After draining in-flight requests, repeat the following **read-only observations** and retain sanitized aggregate evidence, not command lines, SQL text, tokens or financial values:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -match 'python|uvicorn|node|npm|celery' } |
  Select-Object ProcessId,Name

Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
  Where-Object { $_.LocalPort -in 8000,8001,5173,5174 } |
  Select-Object LocalPort,OwningProcess

Get-ScheduledTask |
  Where-Object { $_.TaskName -match 'LankaPex|backend|reminder|celery' } |
  Select-Object TaskName,State
```

An authorized DBA should check **aggregate** MySQL session/transaction activity with sufficient visibility. The application account could see zero other development sessions in Phase 3.7 but could not read `information_schema.INNODB_TRX`; that limitation must not be called a transaction PASS. For example, from an authorized read-only administrative session:

```sql
SELECT COUNT(*) AS other_dev_sessions
FROM information_schema.PROCESSLIST
WHERE DB = 'lankapex_db' AND ID <> CONNECTION_ID();

SELECT COUNT(*) AS active_innodb_transactions
FROM information_schema.INNODB_TRX;

SELECT COUNT(*) AS development_events
FROM information_schema.EVENTS
WHERE EVENT_SCHEMA = 'lankapex_db';
```

If the DBA cannot see all transactions or any unexplained writer/DDL path remains, **stop**. Process/port/session snapshots alone do not prevent later connections. The operator must maintain the API block and coordinated writer/DDL freeze throughout baseline capture, backup-currentness review, migration and post-checks. Recheck shortly before execution and while post-checks run. Do not release the pause based solely on the guarded script's advisory lock.

## Pre-upgrade gate and exact prepared command

With the pause active, rerun the guarded read-only audit and retain its private baseline file (and checksum). Require exact `lankapex_db`, `c9d5e8f7a237`, 18 original tables, no unexpected drift, five expected pending revisions, zero incompatible notification rows, validated ownership/financial fingerprints and no new writers. Compare the freshly captured application row fingerprints and table counts with the protected 10:55 backup validation and populated rehearsal evidence. Recompute the SQL SHA-256 and verify private ACL/Git exclusion. **If the source differs, do not change the evidence or proceed with the old backup.** Obtain a new backup and an isolated populated rehearsal of its exact bytes before reconsidering an upgrade.

```powershell
.\backend\.venv\Scripts\python.exe .\.server-logs\phase33-development-audit.py
```

Once every gate passes **and separate development-upgrade authorization is given**, the prepared command is:

```powershell
.\backend\.venv\Scripts\python.exe .\docs\operations\phase33-upgrade-development.py.example `
  --database lankapex_db `
  --baseline .\.server-logs\phase33-development-audit.json `
  --backup .\.server-logs\private-backups\lankapex_db_20261109T105502+0530.sql `
  --backup-manifest .\.server-logs\private-backups\lankapex_db_20261109T105502+0530.manifest.json `
  --backup-validation .\.server-logs\private-backups\lankapex_db_20261109T105502+0530.validation.json `
  --restore-evidence .\.server-logs\private-backups\lankapex_db_20261109T105502+0530.populated-rehearsal-evidence.json `
  --execute --confirm-writes-paused --confirm-target lankapex_db
```

This command was **not run**. Review the exact paths and fresh baseline before executing it. The script should reject drift, wrong target, wrong revision, missing/mismatched backup, wrong evidence or a nonmatching five-revision tail. No direct `alembic upgrade head` invocation is approved by this plan.

## Post-upgrade acceptance, while writers remain paused

After a zero-exit guarded upgrade, run the separate read-only verifier against the **same** pre-upgrade baseline:

```powershell
.\backend\.venv\Scripts\python.exe .\backend\scripts\verify_development_upgrade.py --database lankapex_db --baseline .\.server-logs\phase33-development-audit.json
```

Require: one Alembic row at `14c0d3e2f782`; 25 application tables plus version; no model metadata difference; every original table row count and PK-ordered fingerprint unchanged; six ledger entries with original type counts; original effective credit-account balance and ledger fingerprints unchanged; zero tested account/business or ledger/account orphans; eight new tables empty. Independently review CHECK/FK/index definitions where metadata comparison is incomplete and perform only approved **read-only** application smoke checks. Record timestamps and sanitized failures. Resume writers only after operator acceptance; then monitor application errors and perform an authorized follow-up read-only health check. No new order/repayment/delivery writes or financial repair belong in the migration acceptance check.

## Expected failure points and recovery

The five reviewed revisions may fail at order table FKs/indexes or notification CHECK replacements (`d0`), order/delivery uniqueness and same-business FK (`e1`), later notification checks (`f2`, `03`), or the five enhancement table FKs/indexes (`14`). Source data or schema drift, concurrent DDL/writes, MySQL lock timeout, disk space, permissions or charset settings can cause failure despite isolated success. The vehicle-document self-supersession invariant remains a future service-level check because MySQL cannot CHECK its AUTO_INCREMENT identifier; no document write API is enabled by these migrations.

MySQL DDL commits outside one encompassing transaction. If any stage or post-check fails, **stop**, preserve the actual partial schema/version and backup, keep writers paused, and collect read-only inventory/fingerprints and sanitized errors. Do not automatically retry, downgrade, stamp, reset, drop objects, change financial rows or restore over `lankapex_db`. A narrowly reviewed forward correction requires separate authorization. If forward correction is not viable, restore the verified backup into a **new empty** recovery database and verify its original rows/balances, then obtain separate cutover/configuration approval. Reconcile any writes after the backup before cutover; the writer pause is intended to prevent that gap. The Phase 3.7 rehearsal demonstrates restoreability of this exact backup on the current isolated MySQL server, but not a timed recovery or development cutover.

**Backup protection risks:** the SQL contains private customer and financial data. Its local ACL and Git exclusion passed, but encryption at rest, offsite copy, key custody and recovery from host loss are **not verified**. Do not claim those controls passed or upload the dump through chat, source control or an unapproved service. An operator must decide whether this backup posture meets the development recovery policy before approving the upgrade; no offsite/crypto operation is performed here.

## Remaining approvals and readiness decision

- Isolated populated restore, migration and financial preservation: **PASS** for the pinned backup.
- Current live source/back-up equality: **PASS at read-only review time**, subject to recheck under pause.
- Sustained writer/DDL pause, full transaction visibility and operator signoff: **NOT YET VERIFIED**.
- Backup encryption/offsite recovery and measured recovery time: **UNRESOLVED operational risks**.
- Separate explicit authorization to run the development command: **NOT GIVEN**.

**Readiness decision: CONDITIONAL / DO NOT EXECUTE YET.** Stop after this report. No AI Summary integration, deployment or push is part of Phase 3.8.

## Authorized development-upgrade attempt — preflight stopped

The user subsequently authorized the guarded `lankapex_db` upgrade **only if every final safety check passed**, including a maintained writer/DDL pause and verified active transactions. The first live read-only gate failed, so **the upgrade command was not run**. No Alembic command, backup restore, schema modification, financial write, service stop or grant change occurred.

| Mandatory gate | Actual read-only observation | Result |
|---|---|---|
| Process inventory | No visible LankaPex Python/uvicorn/celery or frontend Node process among inspected candidates; MySQL and unrelated runtime processes observed | PASS for snapshot only; does not prove sustained pause |
| Development database identity | `SELECT DATABASE() = lankapex_db`; `CURRENT_USER() = lankapex_app@localhost` | PASS |
| Other sessions selecting development DB | `information_schema.PROCESSLIST` count 0 at this sample | PASS for snapshot only |
| Active InnoDB transactions | `information_schema.INNODB_TRX` denied to app account, MySQL **1227** | **FAIL: not verified** |
| Alternate transaction view | `performance_schema.events_transactions_current` denied, MySQL **1142** | **FAIL: not verified** |
| Scheduled/background job inventory | Windows `Get-ScheduledTask` failed with HRESULT **0x80070057** | **FAIL: not verified in this attempt** |
| Sustained writer/DDL pause | No operator-maintained freeze or complete transaction visibility was established | **FAIL: mandatory gate unmet** |
| Exact source revision/fingerprints and backup recheck under pause | Not attempted after the earlier mandatory gate failed | NOT RUN |
| Guarded development migration and post-upgrade validation | Not attempted | NOT RUN |

The earlier Phase 3.7 observation of inactivity and the previous successful isolated rehearsal remain valid historical evidence but cannot satisfy this attempt's required live transaction and sustained-pause gates. A privileged DBA should perform the **read-only** transaction/session inspection in the pause checklist above, with access to `information_schema.INNODB_TRX` or an equivalent complete transaction view, and provide a sanitized count/time result. The maintenance operator must also verify scheduled jobs with a functioning task inventory or approved alternative and document how new writers/DDL are blocked throughout the window. Do not grant the app account broad new privileges solely to make this check pass, and do not infer zero transactions from access-denied errors.

Once those external checks and a sustained pause are actually established, the existing conditional authorization can be evaluated against a fresh source/backup preflight. Until then, **STOP / DEVELOPMENT UPGRADE BLOCKED**. The database remained at the previously verified source revision; no execution-stage command was issued in this failed preflight.

## Phase 3.8 failed-gate diagnosis and operator evidence procedure

The user requested resolution of the **preflight gates only**. No grants, database objects, services, jobs, backups or financial records were changed. The guarded development upgrade was not retried.

### MySQL transaction visibility

The actual configured account is `lankapex_app@localhost` on `lankapex_db`. `SHOW GRANTS` contains no global `PROCESS` privilege and no `SELECT` privilege on `performance_schema`. Therefore its `INFORMATION_SCHEMA.INNODB_TRX` query failed with **1227** and its `performance_schema.events_transactions_current` query failed with **1142**. The [MySQL 8.0 manual](https://dev.mysql.com/doc/refman/8.0/en/information-schema-innodb-trx-table.html) confirms `PROCESS` is required for `INNODB_TRX`; [MySQL privileges](https://dev.mysql.com/doc/refman/8.0/en/privileges-provided.html) explain that `PROCESS` exposes all threads. This is a visibility limitation, **not evidence that active transactions exist or do not exist**. Do not grant `PROCESS` or Performance Schema access to the application account for this maintenance check.

An **already authorized DBA account** with `PROCESS` should run the following *read-only* queries privately while the operator has paused all app/manual writers. Repeat at the start of the window, immediately before the guarded command, after each migration stage if the operator's monitoring permits, and before releasing the pause. Record only timestamps, identity, counts and exception codes; do not publish statement text, credentials, SQL parameters or customer/financial rows.

```sql
SELECT UTC_TIMESTAMP(6) AS observed_at_utc,
       CURRENT_USER() AS observer,
       @@version AS mysql_version,
       (SELECT COUNT(*) FROM information_schema.INNODB_TRX)
         AS active_innodb_transactions,
       (SELECT COUNT(*) FROM information_schema.PROCESSLIST
        WHERE DB = 'lankapex_db' AND ID <> CONNECTION_ID())
         AS other_development_sessions;

SELECT UTC_TIMESTAMP(6) AS observed_at_utc,
       COUNT(*) AS visible_other_sessions,
       SUM(CASE WHEN INFO REGEXP '^[[:space:]]*(CREATE|ALTER|DROP|RENAME|TRUNCATE)[[:space:]]'
                THEN 1 ELSE 0 END) AS visible_ddl_statements
FROM information_schema.PROCESSLIST
WHERE ID <> CONNECTION_ID();
```

Required evidence: observed UTC time and DBA identity; successful query execution with **complete** thread visibility; zero active InnoDB transactions at the pre-execution gate (or a documented operator-reviewed explanation of unrelated activity); zero unexplained development sessions and visible DDL; and the operator's separate confirmation that all manual writers/DDL are paused. A zero count is a snapshot, not a lock. The second query supplements, but cannot replace, operational DDL control because command text can be absent or statements can start later. If the DBA lacks complete visibility or results are ambiguous, keep the gate **BLOCKED**. No DBA evidence has been supplied yet.

### Windows scheduled-task inventory diagnosis

The Windows **Schedule** service is running (`Automatic`). In the ordinary sandbox, `Get-ScheduledTask -TaskPath '\'` returned **access denied** (`0x80041003`), and `schtasks /Query` returned a path error. With elevated **read-only** execution, `Get-ScheduledTask` still failed in its CIM provider (`CimException`, with an earlier `0x80070057` parameter error), but `schtasks.exe /Query /FO CSV /NH` succeeded (exit 0, 251 task rows). The elevated verbose CSV query also succeeded (exit 0, 353 rows). Its parsed `TaskName`, `Task To Run` and `Status` columns were confirmed present; filtering names and actions for LankaPex/backend/uvicorn/celery/reminder/Phase 3 produced **zero candidates**. No task was stopped, disabled or edited. The discrepancy points to the ScheduledTasks CIM provider/host access path; it is **not** a general Task Scheduler service outage. The exact provider defect remains undiagnosed and is not necessary to fix if the CLI inventory is accepted by the maintenance operator.

For the maintenance window, use a read-only elevated `schtasks.exe /Query /V /FO CSV` inventory, verify exit 0, and inspect **both task names and actions** for the actual backend/project paths. Keep raw action command lines private because they may contain credentials. Recheck immediately before and during the window. If an app-related task appears, obtain specific authorization to pause it and record the task name, pause method and resumption owner. The Phase 3.8 CLI result establishes **no matching scheduled job at the time of this diagnostic query**, not an indefinite pause.

### Maintained writer/DDL pause checklist

1. Assign a maintenance operator, a DBA observer and a named backup/recovery owner. Record exact `lankapex_db` source revision, approved command, start time and communication to all users who can write through the API or manually.
2. Prevent new application requests at the ingress/API boundary. Drain in-flight requests, then stop the known FastAPI/uvicorn process tree and any imports, reminders, queues, webhooks, scripts and background workers using their actual service managers. Do not stop MySQL. No process stop is authorized by this diagnostic request.
3. Run the read-only process/listener inventory and elevated verbose `schtasks` check. Identify every matching action, not only familiar task names. Coordinate with holders of direct SQL/DDL credentials; no one should run a manual client or schema change during the window. An advisory lock alone does not block these writers.
4. Have the DBA run the timestamped queries above and privately inspect any nonzero thread/transaction/DDL count. Record zero or a reviewed explanation. If there is no complete transaction visibility, stop.
5. Keep API ingress and workers disabled, scheduled jobs paused, manual writers/DDL frozen and the DBA observer available while capturing the read-only baseline, validating the exact pinned backup, running each guarded stage and performing the post-upgrade checks. Monitor process/listener/task status and DBA aggregates at agreed checkpoints; if unexpected activity appears, stop before the next stage and preserve the current state.
6. Repeat the source identity/revision, table inventory, all application-row fingerprints and exact backup SHA under the established pause. They must match the Phase 3.7 protected baseline and rehearsal evidence. Only then does the existing conditional authorization permit executing the guarded command. Keep the pause through the read-only post-upgrade verifier; release it only after operator acceptance.

### Current disposition

**Scheduled-task visibility:** a read-only elevated CLI workaround now provides an inventory and found zero LankaPex name/action candidates. **MySQL transaction visibility and sustained writer/DDL pause:** still **BLOCKED** pending DBA and maintenance-operator evidence. Therefore no refreshed source/backup preflight was run under a verified pause, and no development upgrade was executed. The previously granted authorization remains conditional and cannot substitute for these missing gates.

## Final safety-gate handoff — DBA and operator evidence pending

The user requested final *preparation* without running the development upgrade or changing services, grants, schema, backup or financial data. This section is the exact evidence contract. It does **not** claim a pause has begun. The prior elevated `schtasks` inventory is a point-in-time result; it must be repeated within the eventual maintenance window.

### DBA: execute privately with an already authorized account

Use an existing DBA account with server-wide thread visibility (`PROCESS` for `INFORMATION_SCHEMA.INNODB_TRX` and full `PROCESSLIST`). Do **not** grant `PROCESS` or any additional administrative privilege to `lankapex_app`. Run these read-only statements **after** the operator has established the writer/DDL pause. Record the UTC timestamp, `CURRENT_USER()`, server identity/version, aggregate counts and any error code. Do not copy statement text from processlist or customer/financial rows into the report. Repeat immediately before the guarded command and at post-stage checkpoints while the pause is maintained.

```sql
SELECT UTC_TIMESTAMP(6) AS observed_at_utc,
       CURRENT_USER() AS observer,
       @@hostname AS server_name,
       @@port AS server_port,
       @@version AS mysql_version;

SELECT UTC_TIMESTAMP(6) AS observed_at_utc,
       COUNT(*) AS active_innodb_transactions
FROM information_schema.INNODB_TRX;

SELECT UTC_TIMESTAMP(6) AS observed_at_utc,
       COUNT(*) AS other_server_sessions,
       COALESCE(SUM(`USER` = 'lankapex_app'), 0) AS app_account_sessions,
       COALESCE(SUM(`DB` = 'lankapex_db'), 0) AS development_selected_sessions,
       COALESCE(SUM(`INFO` REGEXP
         '^[[:space:]]*(CREATE|ALTER|DROP|RENAME|TRUNCATE)[[:space:]]'), 0)
         AS visible_ddl_statements
FROM information_schema.PROCESSLIST
WHERE ID <> CONNECTION_ID();

SELECT UTC_TIMESTAMP(6) AS observed_at_utc,
       COUNT(*) AS development_events
FROM information_schema.EVENTS
WHERE EVENT_SCHEMA = 'lankapex_db';
```

`PROCESSLIST.DB` can be NULL even for a client capable of issuing fully qualified development writes. The DBA must privately review every unexplained app-account or external session and any DDL statement, not merely the `development_selected_sessions` subtotal. `INNODB_TRX` covers active InnoDB transactions, while a zero count does not prevent a future transaction or prove that DDL cannot start. If the DBA cannot see all sessions/transactions, if a count is unexplained, or if server identity differs from the target, the gate fails. No DBA result has been provided for this request.

### Operator: establish and maintain the pause

The operator records a signed/timestamped maintenance log (private; no credentials or raw SQL). Required entries:

1. Identify the backend launch method, all FastAPI/uvicorn workers and reload parents, frontend ingress, imports, reminders, queues, webhooks, maintenance scripts, Windows scheduled tasks and any external/manual MySQL writer. Name the person or service owner for each. Do not assume an absent process snapshot prevents later restart.
2. With separate authorization for process/service actions, block new API requests and pause every known writer/job through its service manager; drain in-flight requests. Keep MySQL running. Pause manual DDL and direct SQL activity by coordination with every holder of development credentials. If an owner cannot enforce the freeze, stop the plan.
3. Record read-only Windows process and listener inventories before the pause and at checkpoints. Use the elevated `schtasks.exe /Query /V /FO CSV` path that actually worked, filter **names and actions**, verify exit code zero, and record any job paused and its resumption owner. An empty matching list is a snapshot, not a durable disablement.
4. Inspect established connections on the MySQL port (including non-loopback clients) and coordinate those clients with the DBA. The DBA's server-wide `PROCESSLIST` review must account for clients whose selected DB is NULL or another schema. Record any externally reachable ingress/database path and how new requests are prevented for the whole window.
5. After the pause is established, obtain the DBA's timestamped statements above. The operator and DBA jointly sign off that no app/manual writer or DDL can start during baseline capture, guarded stages and post-checks. Keep an observer monitoring processes, scheduled tasks, sessions and transactions. If any unexpected activity appears, stop before the next stage and preserve state.
6. Under the maintained pause, run the exact source/backup read-only preflight in the earlier section: `lankapex_db`, source revision `c9d5e8f7a237`, all original row fingerprints, table inventory, pending chain and pinned backup SHA `1588a78f4e5b5e95d9556233d79241991ea063224fd6e73da363ae545e78245e`. The rehearsal evidence must still match. Do **not** perform this step before the DBA/operator gates pass. Maintain the pause through the post-upgrade verifier and release only after operator acceptance.

### Evidence register for this request

| Required evidence | Result | Gate |
|---|---|---|
| Elevated scheduled-task name/action inventory | Earlier read-only CLI exit 0, zero matching candidates; repeat within window pending | HISTORICAL PASS / LIVE PENDING |
| DBA account/server identity and UTC observation | Not supplied | BLOCKED |
| DBA complete active InnoDB transaction count | Not supplied; app account lacked required visibility | BLOCKED |
| DBA complete server/app/external session and DDL review | Not supplied | BLOCKED |
| Operator-maintained writer/job/DDL pause with start time and owners | Not established or supplied | BLOCKED |
| Fresh source identity/revision/fingerprints under verified pause | Not run because earlier mandatory gates remain blocked | NOT RUN |
| Pinned backup checksum and evidence recheck under verified pause | Not run because earlier mandatory gates remain blocked | NOT RUN |
| Guarded development upgrade | Prohibited by this request; not run | NOT RUN |

**Decision: BLOCKED.** The operator should provide the private maintenance log and the DBA's sanitized timestamped counts. Only after those are reviewed and all mandatory gates pass may the conditional upgrade authorization be reconsidered. The exact prepared command remains the one in the earlier "Pre-upgrade gate and exact prepared command" section; it was not executed here. No database or file backup changes were made in this handoff.
