# Step 200 — Populated demo QR migration plan

Status: OFFLINE PREPARATION COMPLETE; LIVE EXECUTION BLOCKED.
No database, credentials, backups or private evidence were accessed.

## Starting facts and exact scope

The operator's Step 199 inventory reports localhost:3306/lankapex_demo_db at
6e3f2c1a9b04, 26 application tables/27 total, no QR tables or profile uniqueness,
zero duplicate linked profiles and zero reported FK orphans. These are prior
observations, not fresh findings. Preserve that evidence unchanged.

The source graph has 16 linear revisions. Apply ONLY:

    6e3f2c1a9b04 -> 7b9e4d2c8a15

No head/+1/ranges, stamp, seed, reset, downgrade, automatic retry or cleanup.
The populated-demo runner must accept ONLY lankapex_demo_db and reject every
other schema, including development, QR/AI tests and existing verification
databases. A separate rehearsal tool needs its own newly approved target.

The November 15 Tamil fallback browser test is already PASSED:
100.20 purchases, 30.10 repayments, 70.10 outstanding. Do not recreate it.

## Exact upgrade and impact

The unchanged QR migration:

1. Audits duplicate non-null business_id/user_id profiles before any DDL.
2. Creates business_join_links: business_id BIGINT PK/RESTRICT business FK;
   public_code VARCHAR(32), utf8mb4_bin, NOT NULL/unique; created_at DATETIME,
   NOT NULL/current-time default.
3. Creates customer_join_requests: request_id BIGINT auto-increment PK;
   required business/customer user/status/creation time, nullable decision
   time/decider, RESTRICT business/customer/decider FKs, unique business/customer
   pair, pending default and pending/approved/rejected/cancelled status check.
4. Creates ix_customer_join_business_status_created on
   (business_id,status,created_at).
5. Adds uq_customer_profile_business_user on (business_id,user_id).
6. Alembic advances its single existing version row.

No upgrade writes alter financial/customer/order/delivery rows, remove invitations,
create accounts or backfill QR codes. NULL-user manual profiles remain separate;
they are not merged/deleted/linked. MySQL uniqueness allows multiple NULL user IDs.

ALTER may acquire metadata locks/rebuild customer_profiles and consume temporary
disk/IO. Measure duration/space/locking in rehearsal. Do not assume online,
nonblocking or transactionally reversible DDL, or force untested ALGORITHM/LOCK.

## Existing tools cannot be reused unchanged

- upgrade_populated_demo_invitation.py/preflight_populated_demo_upgrade.ps1:
  wrong transition, 15-revision graph and old model counts. Its grant policy
  accepts supersets; do not copy that policy.
- backup_populated_demo.py/capture_demo_baseline.py: pinned to 14c0d3e2f782
  and 26 total definitions; also uses a temporary plaintext client-options file.
  Not suitable for the current backup without new review.
- rehearse_demo_backup_restore.py: pinned to an old dump/revision and existing
  restore target. Do not reuse/access that target or evidence.
- upgrade_qr_test_schema.py: intentionally requires the empty QR test schema.
  Never widen it to the populated demo.
- inventory_demo_database.ps1: suitable for a separately authorized read-only
  inventory, but does not capture protected evidence files or migrate.

Alembic env.py's supplied-connection path invokes db_maintenance guards that do
not accept a populated-demo migration. A new exact-demo, same-connection hook
must be separately implemented/reviewed. Do not bypass that guard, impersonate
another environment or use an unguarded alternate engine path.

## Identities and minimum privileges

Existing convention: lankapex_demo_migrator@localhost and its protected
demo-migrator.dpapi. Current existence/grants are unverified here. Its historical
policy included DELETE, which the QR transition does not need.

Prefer a new temporary lankapex_demo_qr_migrator@localhost with exactly:

    SELECT, INSERT, UPDATE, CREATE, ALTER, INDEX, REFERENCES

CREATE/INSERT support MySQL ALTER internals; UPDATE supports the Alembic version
transition; REFERENCES supports new FKs. No DELETE, DROP, global DML/DDL,
GRANT OPTION, ALL PRIVILEGES, roles, proxy rights or access to other schemas.
Reject additional/unrecognized grants rather than requiring a subset.

The intended grant scope is the backtick-quoted identifier
lankapex\_demo\_db followed by .*, escaping EACH underscore. This scope assumes
partial_revokes=OFF. If enabled, STOP for DBA review of literal-schema semantics.
Do not apply a grant until that setting and exact reflected scope are reviewed.
Account/password/DPAPI provisioning requires separate authorization; no passwords
in source, output or command arguments.

The runtime lankapex_demo_app@localhost stays DML-only. Never use it for DDL
or expand its rights. Backup/restore privileges depend on dump options/stored
objects and need separate review, not runtime privilege expansion.

## Verified recoverable backup prerequisite

1. Establish the writer/DDL pause below.
2. Capture a fresh protected inventory with the SAME projection/hash conventions.
   Compare with immutable Step 199 evidence. Drift is STOP pending review.
   If legitimate drift is later accepted, pin a new authorized baseline and retain
   Step 199; never silently replace it.
3. Create a fresh full private logical backup at 6e3f2c1a9b04. Require exact
   identity/revision, 27 table definitions, full rows/schema, checksum, size, UTC,
   baseline links and protected operator/SYSTEM storage.
4. Detect views/routines/triggers/events: STOP for coverage/privilege review if
   present. Inspect emitted dump SQL for unsafe redirection/DEFINER/global or
   destructive statements. Prefer single-transaction/no table-lock options and
   no add-drop statements. Review credential transport without introducing new
   plaintext secret files; do not reuse the old mechanism unreviewed.
5. Restore the EXACT pinned dump into a newly authorized isolated target.
   Compare complete restored schema/data with the paused source. File existence,
   checksum and a prior snapshot alone do not prove recoverability.
6. Complete the QR rehearsal and pin its success proof to backup SHA-256,
   baseline, migration/runner/guard/env-hook source hashes and server settings.

Step 199 projections do NOT certify every field of every original row. Expanded
private comparisons during restore/rehearsal are required for that claim.
Never print credential hashes, personal information, notes or QR codes.
No private evidence was read or created during Step 200.

## Writer/DDL pause

Under separate authorization, identify all demo writer processes, jobs and
clients. Stop only identified demo app writers, prevent frontend writes, pause
jobs/manual changes, and exclude concurrent pytest/migration sessions.
A DBA must review active transactions/metadata lock waiters without printing
sensitive SQL or automatically killing sessions. Record the maintenance owner,
time, process evidence and confirmation.

Keep the pause through backup, rehearsal acceptance, DDL and independent
post-verification. If released for a long rehearsal, re-establish it and prove
unchanged data against the pinned rehearsed baseline; otherwise STOP/review a
new backup/rehearsal. An advisory lock prevents cooperating duplicate migration
runners only; it does not stop ordinary writers.

## Isolated rehearsal

Proposed NEW target: lankapex_demo_qr_rehearsal_20261115.
Verify absence before separately authorized provisioning. If it exists, STOP:
no reuse, drop/recreate or access to old rehearsal/verification databases.
Use isolated restore/migration identities, never accounts with both source and
rehearsal grants. Restore/migration are distinct authorizations.

The rehearsal tool must hardcode its target, reject protected schemas and source
redirection in dump SQL, refuse pre-existing tables and never fall back to demo
Settings/engine. Restore only the approved synthetic demo copy; do not read QR/AI
fixture evidence or seed additional records.

Sequence: restore pinned backup once; verify full starting schema/data/FKs;
apply the pinned QR revision; verify new structure/empty tables/preservation;
record timing/storage/locking and immutable success evidence. Preserve partial
state on any failure, with no cleanup or retry.

Rehearsal reports must retain their true identity. They cannot be passed to the
demo-only comparator by rewriting the reported database/account. A separate
identity-guarded cross-target rehearsal verifier remains required.

## New populated-demo runner specification — not implemented in Step 200

Before live use, prepare/review/offline-test a new runner and PowerShell wrapper.
Default: no connection/decryption. Separate read-only preflight mode.
DDL requires explicit execution, exact target/revision, maintained pause,
verified backup, immutable baseline and matching successful rehearsal proof.

The runner must:

- Check configured/actual host, port, database/account, exact grants, MySQL
  version/settings, strict mode, FK checks enabled, InnoDB, source hashes and
  full 16-revision graph.
- Require 27 starting tables, 26 exact application names, known predecessor
  columns/constraints, BOTH QR tables absent and profile uniqueness absent.
  Any partial migration is STOP.
- Check baseline row counts/projections/balances, zero orphans and duplicates.
- Acquire a nonblocking advisory migration lock on the SAME verified connection
  used by Alembic. Recheck schema/baseline and execute the migration's duplicate
  audit immediately before first DDL. Set a reviewed bounded metadata-lock wait.
  Do not disable FK checks or relax SQL mode.
- Allow only the two exact CREATE TABLE operations, exact request index,
  customer-profile unique ALTER and Alembic's one-row revision UPDATE, plus
  reviewed read/setup statements. Reject destructive/global/cross-schema SQL,
  other DML/DDL, unexpected connections/binds and executemany writes.
- Distinguish table-qualified columns from schema-qualified references.
  Never manually advance a failed revision, stamp or run downgrade.
- Dispose connections/credentials and restore process environment on every path.
  Report sanitized stage/DDL uncertainty, with no automatic retry/restore.

## Independent post-migration verification, still paused

Use a fresh read-only runtime connection:

- Single revision row exactly 7b9e4d2c8a15; 28 application/29 total tables.
- Two EMPTY QR tables; exact reviewed columns/types/nullability/defaults/
  collations, PKs, uniques, status check, index and four RESTRICT FKs.
- Exact customer_profiles uniqueness on business_id,user_id.
- No other original column/default/constraint/index changes.
- Exact row counts for ALL 26 original application tables.
- Unchanged financial/customer-link/order/delivery projections, signed account
  balances and ledger-type totals fingerprints.
- Original FK inventory unchanged/zero orphans; exactly four expected new FKs,
  zero orphans. Runtime grants and private fixture/evidence ownership unchanged.

demo_qr_preservation.py provides the sanitized demo-report comparison only.
It checks original counts/projections/balances, empty new QR tables, compatible
schema flags and exact new FK inventory, without DB/file access. It explicitly
returns full_row_preservation_proven=False. Full schema/default checks and
private all-row preservation proof remain separate requirements.
The schema metadata hash is EXPECTED to change.

No QR issuance, joining, approval, seeding or financial write is required for
preservation verification. Only after signoff may separately authorized startup
and read-only role smoke review proceed.

## STOP and recovery boundaries

STOP for identity/grants/source mismatch; missing pause, backup or rehearsal;
active writers; partial schema; duplicates; orphans; baseline drift; insufficient
space/privileges; metadata lock timeout; lost connection; conflicting lock;
unsafe/unexpected SQL; version-update uncertainty; or failed post-checks.

Before DDL: no target change is allowed. Preserve failed evidence.
After DDL starts: assume partial schema persists. Keep writers paused and obtain
read-only diagnosis. Never retry, stamp, drop new tables, remove constraints,
downgrade, reset or restore over the populated demo automatically.
Recovery needs separate review/authorization: validated restoration into a newly
approved replacement target/cutover, or a precise reviewed forward repair.
No automatic new database creation or application configuration switch.

## Commands and future authorizations

AVAILABLE, OFFLINE:

~~~powershell
.\backend\.venv\Scripts\python.exe -m unittest discover -s backend/offline_tests -p test_demo_qr_preservation.py -v
~~~

AVAILABLE, LIVE READ-ONLY; requires later authorization:

~~~powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\inventory_demo_database.ps1 -Execute -ConfirmTarget lankapex_demo_db
~~~

PROPOSED EXACT INTERFACES BELOW — tools do NOT exist yet; do not run:

~~~powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\backup_demo_qr_source.ps1 -Execute -ConfirmTarget lankapex_demo_db -ConfirmWriterDdlPause

powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\rehearse_demo_qr_upgrade.ps1 -Execute -ConfirmTarget lankapex_demo_qr_rehearsal_20261115 -BackupManifest $BackupManifest -BackupSha256 $BackupSha256 -Baseline $Baseline

powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\upgrade_populated_demo_qr.ps1 -PreflightOnly -ConfirmTarget lankapex_demo_db -BackupManifest $BackupManifest -BackupSha256 $BackupSha256 -Baseline $Baseline -RehearsalProof $RehearsalProof

powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\upgrade_populated_demo_qr.ps1 -Execute -ConfirmTarget lankapex_demo_db -ConfirmRevision 7b9e4d2c8a15 -ConfirmWriterDdlPause -BackupManifest $BackupManifest -BackupSha256 $BackupSha256 -Baseline $Baseline -RehearsalProof $RehearsalProof
~~~

Variables are reviewed private evidence paths/hashes, never credentials.
Do not substitute plain alembic upgrade or the historical runners.

Remaining gates: new source tooling/env-hook review; DBA identity/grant inventory
and any account/DPAPI provisioning; pause/start-stop work; protected evidence
capture/backup; new rehearsal provisioning/restore/migration; demo read-only
preflight; one-time demo DDL; independent verification; startup/resumption.
Each requires its own applicable authorization. None was executed here.
# Reviewed existing migrator profile — source-only adjustment

The current populated-demo QR runner and its PowerShell wrapper now pin only
`lankapex_demo_migrator@localhost` on localhost:3306/lankapex_demo_db. Historical
references below to `lankapex_demo_qr_migrator` describe the superseded execution
profile; they must not be used to provision or select credentials for this run.
Other provisioning/verification tools have not been repurposed by this change.

The exact existing-account privilege contract is SELECT, INSERT, UPDATE, DELETE,
CREATE, ALTER, INDEX, REFERENCES on the fully escaped `lankapex\_demo\_db` scope,
plus global USAGE only. No extra rights, roles, proxy grants, GRANT OPTION,
wildcard scope or other-schema grant is accepted. Actual CURRENT_USER, database,
host/port, driver identity and active roles are still verified by the runner.

DELETE is explicitly accepted as a pre-existing schema-scoped account capability,
not as required migration permission. The source-reviewed SQL gate still rejects
every DELETE, arbitrary DML, DROP and any non-allowlisted or out-of-order DDL.
This does not reduce the account's power outside this runner: exclude other uses
of the credential during the maintained writer/DDL pause. Do not grant DELETE to
a narrower account. A dedicated narrower account remains preferable where this
existing-account exception is not approved.

Both `-PreflightOnly` and `-Execute` additionally require the explicit PowerShell
switch `-ConfirmExistingMigratorPolicy` (Python equivalent
`--confirm-existing-migrator-policy`). Missing acknowledgment stops before private
credential access. Default mode remains offline. This switch acknowledges this
documented policy exception; it never replaces backup, rehearsal or pause proof.

Before activation, independently verify that the protected credential selected
by the wrapper belongs to the new exact identity. The storage filename is not
proof of account identity. No credential file has been read, rewritten or created
by this adjustment; existing credentials must never be silently overwritten.

The unchanged SQL backup, baseline, financial/FK preservation, exact migration
checksum, isolated rehearsal and fresh maintained-pause requirements still apply.
Matching four row counts and a successful restore alone do not satisfy them.
The source changes invalidate prior runner/rehearsal source bindings; freeze the
reviewed source and obtain truthful new evidence from independently verified
operations. Never edit historical hashes to make evidence pass. Recovery archives
bound to changed sources may also need refreshing before downstream verification.

Shortest execution path: verify account/credential and exact grants, review the
complete backup/restore preservation evidence, rehearse the exact SQL backup and
QR transition under these frozen sources, establish the maintained writer/DDL
pause, then run the existing wrapper once in preflight mode with all pinned
proofs and the new policy switch. Only after success and separate execution
authorization run the same reviewed evidence-bound command with `-Execute`,
exact target/revision confirmation and pause confirmation. No live execution or
migration command is authorized by this source preparation.

