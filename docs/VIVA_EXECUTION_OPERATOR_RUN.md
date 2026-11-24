# Executable VIVA recovery and three-stage migration

Status: FULLY_PREPARED_NOT_EXECUTED. No real DB, backup, restore, migration,
grant/global change, service start, .env edit or writer release occurred.
The commands below require separate FUTURE authorizations. Source implementation
approval is not permission to execute them now. Historical MR/native blockers
are unchanged; this is the documented DBA-operated workflow, not their activation.

## Identities and implementation

Source: 127.0.0.1:3306/lankapex_viva_db, MySQL 8.0.46, UUID
7bc6e90d-aced-11f1-be0b-10e7c6704500. Source migrator:
lankapex_viva_migrator@127.0.0.1. Runtime remains lankapex_viva_runtime.
Scratch database: lankapex_migration_verify_viva20261124. Proposed scratch account:
lankapex_viva_rehearsal@127.0.0.1 (the 38-character database name is too long for
a MySQL username). No scratch provisioning or account creation is automatic.

viva_migration_execute.py provides backup, restore, rehearse and migrate modes.
Each requires --execute, its own exact authorization token, target, continuous
freeze assertion and a never-used private evidence directory. There is no
upgrade-head, reset, stamp, downgrade, cleanup or retry mode. Credentials use
getpass/native MySQL hidden prompts; no password argv, environment or option file.
Native children inherit only essential Windows environment entries; database and
provider secrets are not forwarded from the operator process.
No application engine/settings/.env is imported. Dedicated Alembic env accepts
only the runner's exact supplied connection and pinned parent/child.

Strict Python TLS uses the protected CA at C:\Program Files\LankaPex-TLS-Trust\ca.pem,
CERT_REQUIRED, hostname/SAN verification, VERIFY_X509_STRICT, TLS >=1.2, and leaf
DER SHA256 8dc0c2e9b4691a7287432bed7b6292b7b58a7d2d21beed986309f259c6c98488.
The CA-file hash is different and requires independent approval. Native clients
use VERIFY_IDENTITY and the exact CA/endpoint; their console/TLS behavior must
be runtime-verified. This is not a claim that native OpenSSL flags equal Python
VERIFY_X509_STRICT. All executable/client/source hashes are bound into evidence.

## DBA actions requiring separate authorization

Verify private existing VivaCheckpoints parent owner/DACL (operator and SYSTEM
only), held-handle ancestry/reparse protections, CA/binary provenance, free space,
35 baseline tables, revision ae2b7c5f1d48 and zero triggers/routines/views/events.
All baseline data tables must be InnoDB with the canonical types, defaults, keys,
indexes, FKs, enforced CHECKs and table options. No unexplained drift is accepted.

DBA must already have global SELECT, PROCESS, EVENT and full performance_schema/information_schema
visibility. The runner checks UUID, all foreground sessions INCLUDING idle
clients, transactions, pending metadata locks, enabled events and active
replication appliers before mutation, before every stage and at final gates.
Only its own source/scratch/DBA sessions are accepted. Close other clients as
part of the operator freeze; the runner never kills sessions or restarts services.
The explicit operator assertion covers continuous external writer/DDL exclusion;
DBA observations are fresh point-in-time checks, not proof of all future behavior.

Provision the exact empty scratch/account through a separately authorized DBA
procedure with a securely generated private password. Stop on unexplained existing
objects. With partial_revokes=0 ONLY, proposed scope statements (NOT executed):

```sql
GRANT TRIGGER ON `lankapex\_viva\_db`.* TO 'lankapex_viva_migrator'@'127.0.0.1';
```

```sql
GRANT SELECT,INSERT,UPDATE,DELETE,CREATE,ALTER,INDEX,REFERENCES,TRIGGER ON `lankapex\_migration\_verify\_viva20261124`.* TO 'lankapex_viva_rehearsal'@'127.0.0.1';
```

With partial_revokes=1, independently review literal schema-name grants instead.
Effective migrator/scratch privileges must be exactly SELECT, INSERT, UPDATE,
DELETE, CREATE, ALTER, INDEX, REFERENCES, TRIGGER on their schema, without global
rights, roles/default/mandatory grants or GRANT OPTION. Runtime gains NOTHING.
Do not grant SUPER. Preserve the creating migrator accounts and persistent
TRIGGER rights required by their immutable-history triggers; do not revoke/drop
DEFINER identities as generic cleanup. Triggers contain SIGNAL, not a payout.

Backup runs BEFORE the trust window and records log_bin=1/trust=0. For rehearsal
and live trigger creation separately authorize a server-wide DBA change window.
DBA uses existing SYSTEM_VARIABLES_ADMIN, records original value 0 and runs:

```sql
SET GLOBAL log_bin_trust_function_creators=1;
```

The runner refuses CREATE TRIGGER stages unless log_bin=1/trust=1. It never sets
globals. After each approved window the DBA restores and verifies 0, INCLUDING
partial-failure paths, without dropping any created objects:

```sql
SET GLOBAL log_bin_trust_function_creators=0;
```

If that temporary change is not approved, STOP for an explicitly approved DBA
alternative; do not grant SUPER or disable binary logging. Validate persistent
DEFINER rights/trigger behavior after restoring trust=0 before live approval.

## Four operator commands (each separately authorized)

From C:\Users\admin\Desktop\LankaPex, collect independently approved nonsecret
hashes and create a unique destination variable. Do not confuse leaf DER and CA hashes:

```powershell
$parent='C:\Users\admin\AppData\Local\LankaPex\VivaCheckpoints'; $caHash=Read-Host 'Approved CA-file SHA256'; $mysqlHash=Read-Host 'Approved mysql.exe SHA256'; $dumpHash=Read-Host 'Approved mysqldump.exe SHA256'; $backupDir=Join-Path $parent ('viva-current-backup-'+[Guid]::NewGuid().ToString('N'))
```

1. ONE current backup; existing DBA and VIVA migrator passwords are hidden prompts:

```powershell
.\backend\.venv\Scripts\python.exe -B backend\scripts\viva_migration_execute.py backup --execute --authorize ONE_CURRENT_VIVA_BACKUP --confirm-target lankapex_viva_db --freeze FREEZE_MAINTAINED --evidence $backupDir --mysql-sha256 $mysqlHash --mysqldump-sha256 $dumpHash --ca-sha256 $caHash
```

The native dump prompts for the VIVA migrator password again. CREATE_NEW output
is held exclusively, stdout is shell-free, stderr is discarded rather than logged,
and the native process is bounded/reaped. --triggers is retained. Routines/events
are skipped ONLY because their inventory must be zero. All 35 table CREATE/INSERT
inventories, full typed row fingerprints, revision and completion footer are
verified; pre/post source data AND exact schema must match. Manifest remains
BACKUP_ONLY_RESTORE_NOT_VERIFIED. Review its checksum and privately approve it:

```powershell
$manifest=Join-Path $backupDir 'manifest.json'; $manifestHash=Read-Host 'Approved current backup manifest SHA256'
```

2. After DBA scratch provisioning, authorize ONE restore. Enter the scratch
password for the native import, NOT the VIVA password:

```powershell
.\backend\.venv\Scripts\python.exe -B backend\scripts\viva_migration_execute.py restore --execute --authorize ONE_CURRENT_SCRATCH_RESTORE --confirm-target lankapex_migration_verify_viva20261124 --freeze FREEZE_MAINTAINED --evidence (Join-Path $parent ('viva-current-restore-'+[Guid]::NewGuid().ToString('N'))) --manifest $manifest --manifest-sha256 $manifestHash --mysql-sha256 $mysqlHash --mysqldump-sha256 $dumpHash --ca-sha256 $caHash
```

Empty scratch is mandatory. Hash-verified input is held open denying concurrent
write/delete, with binary stdin, --binary-mode, --local-infile=0 and the exact
scratch-only login/schema. SQL-aware validation rejects USE/database selection,
qualified targets, unexpected programs, unsupported statements and altered rows.
Complete restored hashes, canonical schema and all FK orphans are checked.
Original DDL text stays in baseline evidence; restore text differences are never
silently treated as exact matches. Native import failure preserves partial state.

3. Separately authorize ONE populated rehearsal and its DBA trust window:

```powershell
$rehearsalDir=Join-Path $parent ('viva-current-rehearsal-'+[Guid]::NewGuid().ToString('N')); .\backend\.venv\Scripts\python.exe -B backend\scripts\viva_migration_execute.py rehearse --execute --authorize ONE_CURRENT_SCRATCH_REHEARSAL --confirm-target lankapex_migration_verify_viva20261124 --freeze FREEZE_MAINTAINED --evidence $rehearsalDir --manifest $manifest --manifest-sha256 $manifestHash --mysql-sha256 $mysqlHash --mysqldump-sha256 $dumpHash --ca-sha256 $caHash
```

Pinned transitions: ae2b7c5f1d48 -> bf38d2a90176 (40 tables/10 triggers) ->
c04d9e7a6201 (44/16) -> d15a8c902e64 (45/18). Independently derived canonical
schema is checked, not counts alone. SQL guards reject historical DML except
Alembic's version row, database/global/reset commands and other-schema references.
Every stage compares all original 34 application-table projections/hashes and
counts; new tables must be empty and historical address idempotency columns NULL.
This preserves orders.total, credits, repayments, customers, businesses, Drivers,
deliveries and subscriptions. All new FKs/CHECKs/indexes and 18 trigger bodies,
DEFINERs, SQL mode and charset/collation are verified. Source remains unchanged.
Only after final gates is REHEARSAL_PASS/result.json issued. Restore trust=0.

4. After independent rehearsal review and separate live authorization/trust window:

```powershell
$rehearsalResult=Join-Path $rehearsalDir 'result.json'; $rehearsalHash=Read-Host 'Approved rehearsal result SHA256'; .\backend\.venv\Scripts\python.exe -B backend\scripts\viva_migration_execute.py migrate --execute --authorize ONE_CURRENT_VIVA_MIGRATION --confirm-target lankapex_viva_db --freeze FREEZE_MAINTAINED --evidence (Join-Path $parent ('viva-current-live-'+[Guid]::NewGuid().ToString('N'))) --manifest $manifest --manifest-sha256 $manifestHash --rehearsal $rehearsalResult --rehearsal-sha256 $rehearsalHash --mysql-sha256 $mysqlHash --mysqldump-sha256 $dumpHash --ca-sha256 $caHash
```

Live requires the approved rehearsal artifact and fresh final-head inspection of
the still-preserved scratch. The live original baseline must still match backup.
The three exact upgrades run with a supplied pinned socket; no app engine/.env or
db_maintenance.py bypass/fallback. Code/contract hashes are rechecked before every
stage. Final LIVE_MIGRATION_PASS is withheld until source and DBA gates pass.
DBA must restore trust=0 afterward, on success OR failure. Writers stay frozen.

## Stop conditions and offline checks

Any wrong identity, peer certificate, CA/client/source hash, role/grant, revision,
schema/trigger, missing data, orphan, unexplained session, nonempty restore target,
binary-log mismatch, process error/interruption, evidence collision/write failure
or partial DDL is STOP. Artifacts are exclusive, private and immutable; failure
records contain fixed stage/error class and schema inventory where available, not
credentials, rows or raw exceptions. No automatic recovery/cleanup or retry.
Manual continuation needs a new independently authorized decision and destination.

Implementation was tested with memory evidence, fictional populated records,
mocked MySQL/Win32/processes and real source contracts. Windows filesystem/console
behavior, actual DBA privileges, native TLS and MySQL reflection are NOT live
verified. Test limits fail closed at 100,000 rows/table and 64 MiB dump; a larger
source or unsupported SQL/type needs a separately reviewed change, not truncation.
Ordinary backend test conftest connects MySQL; never use it during this freeze.

## Windows failure before reservation (no backup retry)

Operator reported WindowsIOBlocked after all three credential prompts, with no
evidence directory. Previously diagnostic() hid every WindowsIOBlocked message.
Those credentials are prompted before PrivateEvidence.__enter__; MySQL connect,
DBA inspection, source capture and mysqldump are reached only AFTER that method
successfully creates/opens the directory and writes attempt.json. The exact
original Windows guard is not recoverable from the redacted output alone.

All WindowsIOBlocked sources in checkpoint_windows_io.py are:

| Path | Checks / operations | Reachable before evidence directory creation? |
| --- | --- | --- |
| _Win32 construction / operator_sid / sid | Windows platform, process token and token size, SID conversion | Yes |
| open | CreateFileW; existing ancestors request 0x20080, share READ/WRITE but not DELETE, OPEN_EXISTING and OPEN_REPARSE_POINT/BACKUP_SEMANTICS | Yes |
| facts | Open-handle state, metadata, disk/type/link/reparse checks, local matching final path, owner, non-null protected DACL, exactly two explicit allow ACEs with correct inheritance, FullControl and operator/SYSTEM SIDs | Yes, on ancestors; owner/DACL policy on the checkpoint parent |
| security | In-memory private security descriptor conversion | Yes |
| Handle.close | CloseHandle during cleanup | Yes; cleanup failure must not replace the primary error |
| write_and_flush | Valid owned handle/bytes, WriteFile, complete writes, FlushFileBuffers | No, after exclusive artifact creation |
| IsolatedTestRoot / isolated_test_root / IsolatedWindowsFiles | Test-root capability/platform/name/handle ownership, create/open/facts/write/close | Not used by this executor |
| ProductionWindowsFiles | Unconditional production-provisioning and power-loss blockers | Not called by this executor; unchanged |

CreateDirectoryW failure now also has typed, sanitized Win32 reporting. Other
native process failures use VivaStop/other exception classes, not WindowsIOBlocked;
process dispatch cannot explain this pre-directory failure. No ACL policy, access
mask, sharing mode or historical blocker was relaxed.

Codex's local read-only observation used SID ending 1004 and was denied access
to the operator-private parent. This does NOT reproduce or explain the operator's
failure under SID ending 1001; no elevation or permission change was attempted.
Use the original non-elevated operator console for the following diagnostic:

```powershell
.\backend\.venv\Scripts\python.exe -B backend\scripts\viva_migration_execute.py inspect-windows --read-only --confirm-parent 'C:\Users\admin\AppData\Local\LankaPex\VivaCheckpoints' --operator-sid S-1-5-21-2860134247-1001507606-3016684065-1001
```

This repeats the executor's held-ancestor and private-parent policy plus in-memory
SDDL conversion. It creates no files, asks for no credentials and cannot connect
to MySQL or launch a process. It first checks the approved operator SID. Indexes
0..6 identify C:\, Users, operator profile, AppData, Local, LankaPex, VivaCheckpoints
respectively, without printing paths/SIDs. On failure retain ERROR_CLASS,
DIAGNOSTIC_CODE, WINDOWS_LOCATION, WINDOWS_OPERATION and WINDOWS_ERROR if present.
Policy failures have no fabricated Win32 error. GetSecurityInfo's returned status
is captured directly; other failing APIs capture last-error before cleanup.
Unknown exception messages remain redacted. Incomplete handle cleanup is explicit.
PASS only verifies pre-creation observations; creation/write/durability remain
unverified and no backup retry is authorized by that diagnostic result.

The old DBA client query incorrectly included FOREGROUND server daemons.
The corrected guard excludes only thread/sql/event_scheduler and
thread/sql/compress_gtid_table with their expected internal user, Daemon command,
no connection type/database and a null/local internal host. Client instrument
names, event workers, unknown daemons, idle application clients and malformed
daemon identities remain blocking. Enabled events, transactions, replication and
pending-lock checks are unchanged. Daemons were NOT the pre-directory Windows
failure; the DBA gate had not yet been reached. No live daemon inventory was
queried during this correction.

## Step 13.46: SOURCE_BEFORE ValueError (no retry)

The operator supplied a failed attempt containing only attempt.json/failure.json
at viva-current-backup-0270d591c5914c288f66c542e428fecb. Those files were not read,
changed, deleted or reused by this investigation. Windows creation now passes,
according to the operator. The redacted ValueError does not identify its cause.

SOURCE_BEFORE is assigned AFTER source connection/TLS/identity/grants, the initial
revision read and first DBA gate succeed. Its reachable sequence before the
missing source-before.json is: snapshot -> repeated identity/TLS/grants/revision
-> read-only repeatable-read snapshot setup -> canonical source contract build
-> inventory/column/type/default/key/FK/CHECK/index/options/trigger inspection
and comparison -> orphan counts -> full typed rows and fingerprints -> rollback
-> JSON serialization/exclusive source-before.json write. Backup capacity is
later, after that artifact; native dump execution is later still.

Realistic ValueError sources are strict TLS guards on the repeated identity
check; source AST/framework-version assertions; MySQL type/default or CHECK
parsing; canonical column/PK/FK/UNIQUE/CHECK/index/options mismatch; Decimal or
numeric conversion; typed JSON/string serialization. Connection initialization
and first DBA preflight would retain RESERVE, not SOURCE_BEFORE. Revision/grant
and typed-row guards normally raise VivaStop/GuardFailure, not ValueError.
Invalid native dump literals and backup-manifest JSON parsing are later paths,
not explanations for the supplied SOURCE_BEFORE attempt. No specific parser or
schema mismatch has been established as the actual operator failure.

Installed versions were inspected offline: CPython 3.14.7, PyMySQL 1.2.3,
SQLAlchemy 2.1.6, Alembic 1.20.1. Hand-authored MySQL-style address metadata
(all 12 columns, microsecond clocks, Decimal precision, explicit/supporting
indexes, FK and four CHECKs), tinyint defaults, charset literals and redundant
parentheses normalize successfully against the real source contract. Altered
precision still fails. These fixtures do not establish live schema parity.

Confirmed adjacent corrections, not claimed causes of the original ValueError:

- PyMySQL returns illegal/zero DATETIME as str; the old generic fingerprint
  accepted it as text before the dump literal parser failed later. Source row
  families/nullability/finite Decimal/naive timestamp checks now fail closed.
- Snapshot setup was outside rollback protection; setup failures now roll back
  and preserve the primary exception if rollback also fails.
- Parameter-free queries passed an empty binding tuple; real PyMySQL percent
  interpolation rejected valid SQL containing literal percent characters.
  The helper now omits bindings when none exist and retains real parameterization.
- JSON encoding now rejects non-finite numbers instead of writing nonstandard JSON.

Failures now include fixed diagnostic codes, stage/substage, allowlisted source
module/function, a known schema table/column when available, exception class and
database_connection_started/baseline_capture_started/native_dump_started flags.
Started means that operation was attempted, not that it completed. No traceback
locals, raw exception messages, SQL, URLs, credentials or row values are emitted.
The same diagnostics cover restore, rehearsal, live migration and final evidence.
No schema equivalence, TLS, privilege or financial-preservation check was removed.

Smallest remaining operator action: from the original private console, close
other MySQL clients, reconfirm the continuing freeze, supply the independently
approved CA-file hash (not the leaf certificate hash), and run once:

```powershell
$approvedCaHash=Read-Host 'Independently approved CA-file SHA256'; .\backend\.venv\Scripts\python.exe -B backend\scripts\viva_migration_execute.py inspect-source --read-only --confirm-source lankapex_viva_db --freeze FREEZE_MAINTAINED --ca-sha256 $approvedCaHash
```

This is an operator-executed live read-only diagnostic, NOT executed by Codex.
It checks the pinned TLS/server/account/source identity, exact grants and DBA
freeze visibility; captures/validates the full baseline within the existing
bounded read-only snapshot; exercises JSON serialization in memory; rechecks
DBA visibility; closes sessions. No checkpoint directory/artifact, dump process,
financial mutation or DDL is created. --execute/--evidence are rejected. Return
only the sanitized STOP fields, or SOURCE_BEFORE_READ_ONLY=PASS. No failed backup
attempt is resumed; a later backup needs separate authorization/new destination.

## Step 13.49: confirmed INFORMATION_SCHEMA CHECK representation correction

The initial missing-fixture review is superseded by the original attachment at
C:\Users\admin\Downloads\viva_check_constraints_89.txt, verified at 104,586 bytes,
89 unique enforced rows and SHA-256
47C5834A0A9F39098BB946E507C9FB2F8588EA2570A93C9B9024A656E35E9EA7.
The byte-for-byte regression fixture is
backend/offline_tests/fixtures/viva_check_constraints_89.txt. The original file
and historical checkpoint evidence were not modified.

BEFORE correction: only 39/89 original CHECK_CLAUSE values parsed. First failure:
admin_audits.ck_admin_audit_action, at the backslash before the opening quote:

```text
(`action` in (_utf8mb4\'driver_approved\',_utf8mb4\'driver_rejected\',_utf8mb4\'account_suspended\',_utf8mb4\'account_reactivated\',_utf8mb4\'admin_provisioned\'))
```

This is NOT a terminal/copied-text escape inferred by guessing. MySQL 8.0.46's
fill_dd_check_constraints calls convert_and_print on the whole expression when
constructing check_clause_utf8; String::print adds one quote/backslash/control
escaping layer. The INFORMATION_SCHEMA view returns that field. mysql's table
printer does not add quote escaping. References:
[dictionary capture](https://github.com/mysql/mysql-server/blob/mysql-8.0.46/sql/dd/dd_table.cc#L1676-L1685),
[conversion](https://github.com/mysql/mysql-server/blob/mysql-8.0.46/sql/item.cc#L10034-L10046),
[String::print](https://github.com/mysql/mysql-server/blob/mysql-8.0.46/sql-common/sql_string.cc#L869-L898),
[CLI table printer](https://github.com/mysql/mysql-server/blob/mysql-8.0.46/client/mysql.cc#L3584-L3598).

The correction explicitly selects mysql8_information_schema only at CHECK_CLAUSE
inspection call sites. It decodes exactly one validated String::print layer,
then tokenizes SQL with reviewed MySQL literal escaping. Ordinary migration SQL
and SHOW CREATE reflection retain the original parser mode. No auto-detection,
global replace, unicode_escape, recursive unescape, eval, charset stripping or
collation override is used. Invalid/mixed/double encodings and unknown escapes
fail closed. Literal backslashes, apostrophes, control characters and case remain
distinct. Only the already reviewed utf8mb4 introducer equivalence is accepted;
other charsets and explicit COLLATE still stop under the strict policy.

AFTER correction: 89/89 actual expressions parse and 89/89 match the independently
source-derived baseline, including exact table/name inventories and enforcement.
No genuine CHECK discrepancy was found in the supplied snapshot. This is offline
comparison of operator-provided evidence, not fresh live schema verification.

Pending stage CHECK totals: 100, 115, 118. Finance adds 11; Support adds 15 and
replaces two notification definitions; Addresses adds 3. Tests cover all 31 added
or replaced definitions. Future-stage metadata controls are explicitly generated
from those source declarations and are NOT represented as live MySQL reflection.
Unchanged baseline checks retain the exact captured operator expressions.
The MR07 artifact's two parser/canonicalizer checksum fields were refreshed only
after asserting every other field, including all expected definitions, unchanged.

Known CHECK names, table, parser failure category and source function remain in
sanitized diagnostics; raw expressions/exception messages/records do not. Tests
reject altered case, values, operators, signs, limits, NULL tests, grouping,
function arguments, identifiers, missing/extra/disabled checks and unsupported SQL.
No constraints, grants, ACLs, TLS certificates, global settings or feature gates
were changed. No DB connection, backup, restore or migration was executed.

Next operator action: close other MySQL clients, reconfirm the continuing freeze
and run the existing inspect-source --read-only command from Step 13.46 once.
Do not retry the backup until that fresh diagnostic passes and separate backup
authorization/new destination are approved. Native backup runtime remains unverified.

## Step 13.52: DBA client inventory investigation

Operator-provided later snapshot: event_scheduler THREAD_ID 44 / PROCESSLIST_ID 5;
compress_gtid_table 47 / 7; manual root connection 69 / 28. The reported internal
users/hosts/databases/commands match the narrow daemon rules. CONNECTION_TYPE was
not supplied, so it cannot be assumed NULL. The snapshot was taken after the
failed runner closed its source/DBA sockets; it is not the failing gate's inventory
and cannot establish that failure's cause. Zero transactions/locks and subsequent
manual root disconnection are point-in-time operator observations only.

The original code already used PROCESSLIST_ID, never THREAD_ID, and shared the
same dba_gate across inspect-source, backup, restore, rehearse and migrate. The
earlier daemon correction was present in that shared code. No confirmed incorrect
classification of a complete real daemon row has been established.

Confirmed offline defects/contract gaps corrected:

- Missing dictionary fields previously looked identical to SQL NULL under get().
  Required thread columns are now mandatory; NULL remains actual None, never a
  string or a missing field. Unknown foreground rows with NULL IDs are captured
  and rejected instead of being removed by the query predicate.
- Set equality concealed duplicate IDs and accepted bool/Decimal integer aliases.
  Expected and observed IDs must be unique positive native integers.
- SQL CONNECTION_ID() was not independently compared with the PyMySQL handshake
  ID. verified_connection_id now checks both and pins the ID to the owned socket.
  A changed/reconnected identity is terminally rejected, never silently resumed.
- A DBA close failure could mask the primary visibility/guard error. Cleanup now
  preserves the original exception and explicitly reports incomplete cleanup.

All call sites use gate_for on their still-owned sockets, freshly verifying IDs
before every gate. Each gate independently checks its new DBA socket's handshake,
TLS, UUID and authenticated user, then validates the complete visible inventory.
Expected application clients must be the exact source/scratch migrator accounts,
schemas and TLS sessions; root is accepted only for the independently identified
DBA connection, never by a username whitelist. One source client is required;
one scratch client is required only while its owned connection is open. Scratch
is excluded from final expectations after close. All other clients, including
idle root sessions and event workers, remain blocking. No connection is killed.

Read-only inspection normally expects two clients (source + DBA); an open scratch
stage expects three. Daemons are counted separately. An exact reproduction of
the later three-row manual snapshot, with hypothetical NULL internal connection
types, still correctly blocks when a running migrator is expected but absent.
Tests explicitly label unreported connection types as conditional fixture values,
not additional operator evidence.

Failure codes distinguish:

- DBA_CONNECTION_ID_INVALID/MISMATCH/CHANGED and expected-ID collisions.
- DBA_THREAD_METADATA_INCOMPLETE/INVALID or duplicate PROCESSLIST_ID.
- DBA_INTERNAL_DAEMON_CLASSIFICATION_FAILED, with fixed daemon/reason labels.
- DBA_SELF_CONNECTION_NOT_VISIBLE, DBA_EXPECTED_CONNECTION_NOT_VISIBLE,
  DBA_UNEXPECTED_CLIENTS_STOP or DBA_UNEXPECTED_AND_MISSING_CLIENTS_STOP.
- DBA_EXPECTED_CLIENT_IDENTITY_MISMATCH.
- DBA visibility privileges, denied/unavailable metadata queries and close failure.

Sanitized details include expected/observed/internal/unexpected/missing counts,
self visibility, bounded numeric connection-ID lists and safe MySQL error codes.
They exclude session usernames/hosts/databases, SQL text, credentials, customer
records and raw error messages. Transactions, event writers, replication and
pending metadata-lock checks remain blocking and unchanged. The CHECK parser,
TLS/CA/certificate pins, ACL policy and financial preservation guards are unchanged.

No real MySQL operation was performed. The original runtime cause remains
unconfirmed until one fresh operator-run inspect-source --read-only result is
available with the richer diagnostics. Close other MySQL clients, keep the freeze
maintained, run that command once, and return only PASS or sanitized STOP fields.
No backup retry, grant/global change, session termination or migration is implied.
