# Steps 279–282 — Demo recovery, SQL export and migration baseline

Source implementation and offline validation only. No live operation has run.
Do not describe this as production-verified or a migration authorization.

## Exact identities

Source: `localhost:3306/lankapex_demo_db`, runtime
`lankapex_demo_app@localhost`, revision `6e3f2c1a9b04`, 26 application tables plus
`alembic_version`. Source permissions remain global USAGE plus exact-schema
SELECT, INSERT, UPDATE, DELETE; snapshots themselves use READ ONLY transactions.

The sole approved-code restore identity is
`lankapex_demo_qr_rehearsal_20261115` / `lankapex_demo_qr_restore@localhost`.
The dated schema name is an identity matching Step 201, not permission to reuse
an old schema. Separately authorize a DBA absence check and provisioning of a
NEW isolated empty target. If it already exists, STOP; do not reset/reuse it.
Choosing another name requires a separately reviewed source/evidence change.

Restore grants: global USAGE and exactly SELECT, INSERT, CREATE, ALTER, INDEX,
REFERENCES on `lankapex\_demo\_qr\_rehearsal\_20261115` only. Escape each
underscore. No roles, proxy, GRANT OPTION, global/other-schema privileges,
DELETE or DROP. Both modes reject partial_revokes=ON, unexpected SQL modes,
inactive FK enforcement, wrong accounts, revisions and inventories.

## Implemented adapter

`backend/scripts/demo_qr_recovery.py` implements a direct PyMySQL/SQLAlchemy
logical backup. No application settings, dotenv, app engine, native-client
password arguments, password environment variables or temporary credential
files are used. Existing account passwords are entered at a hidden terminal
prompt, once per adapter process, and remain only in Python/connector memory.
Do not use an IDE debugger, transcript, command recorder or memory-capture
tool. Python immutable secret copies cannot be comprehensively zeroed.

The actual transport is numeric IPv4 `127.0.0.1:3306`; logical target reports
use `localhost`. A separately trusted public CA PEM and server certificate
valid for IP SAN 127.0.0.1 are mandatory. TLS >=1.2, certificate chain and host
identity are verified. The reviewed PyMySQL implementation must expose required
TLS mode; preferred/plaintext fallback is rejected before authentication.
Connector debug flags must be disabled. No TLS settings or certificates are
changed by the adapter. The prior missing-IP-SAN blocker remains relevant.

Backup captures one consistent read-only snapshot of every table, including
all column values, complete SHOW CREATE TABLE definitions and database default
charset/collation. Rows are PK ordered and typed without float currency
conversion. Full-row SHA-256 includes private fields internally; only hashes
are in evidence. No data, hashes of passwords themselves, connector exceptions
or financial amounts are printed. A second independent snapshot must match
before final backup proof is written; maintain the real writer/DDL pause.

The existing authoritative inventory balance and ledger-total SQL is reused.
Snapshot evidence includes all 27 full-row/schema hashes, ten financial/link
projections, reversal-aware signed balances, ledger totals, duplicate linked
profiles, FK-orphan counts, source hashes and dependency/server versions.
Views, routines, triggers, events, non-InnoDB tables, generated columns, missing
PKs, unsupported data types and unreviewed DDL stop. A finite 256 MiB archive
limit fails closed; row loading is in memory, so review capacity before use.

Metadata visibility of routines/events can be privilege-limited. The mandatory
DBA stored-object-review confirmation attests an independent privileged review
of their absence; runtime metadata alone is not proof. Never tick a flag merely
to satisfy a gate. The adapter does not back up stored objects it cannot review.

## Private artifacts and filesystem protections

Use an independently approved, pre-existing directory:
`.server-logs/private-demo-qr-migration/`, outside Git. Do not create it through
this tool. Existing operator/SYSTEM-only protected DACLs, verified operator
ownership and no reparse components are checked through the reviewed helper.
All ancestor directories are held with Windows handles denying deletion/rename;
final handle paths are checked. New files use CREATE_NEW with operator-owned,
protected operator/SYSTEM-only Full Control DACLs at creation. Existing file
ACLs/owners are never changed. Input handles deny replacement/writes during use.

For one operator-chosen new 32-lowercase-hex artifact ID:

- `source-<id>.lpx`: private UTF-8 JSON logical archive, NOT executable SQL.
- `backup-before-<id>.json`, `backup-after-<id>.json`: full sanitized snapshots.
- `recovery-backup-<id>.json`: archive size/SHA-256, snapshot digest, UTC,
  source binding; recoverability explicitly false.
- `restore-proof-<id>.json`: created only after complete restore comparison;
  restore true, migration false, migration-runner compatibility false.

Creation is exclusive. Missing inputs, existing outputs, checksum/source drift,
unsafe paths or unavailable metadata STOP without retry, deletion or overwrite.
Keep partial output and the isolated target unchanged for separate diagnosis.

## Restore behavior and limits

Restore first verifies pinned archive and baseline SHA-256, exact source/revision,
all typed row hashes and CREATE TABLE statements. It never executes raw data as
SQL or accepts client commands, multiple statements, comments, cross-schema DDL,
DROP, stored routines or target redirection. Exact isolated identity, grants and
table/stored-object emptiness are checked again immediately before first DDL.

The isolated session temporarily disables FK checks to handle cyclic table
relationships, creates all tables with original constraints, and inserts typed
values through bound parameters. It reenables FK checks and commits. A new
read-only snapshot then explicitly audits every FK (reenabling alone does not
validate old rows), schema/full-row hashes, revision, database defaults and all
financial/link fingerprints. Partial DDL may persist on failure; closing rolls
back only uncommitted DML. No retry or automatic source recovery is provided.
Concurrent administration/writes to the new isolated schema must be excluded.

## Step 282 SQL export and migration baseline

Two additional separately gated modes reuse the archive and protected store.
Default invocation still does no private reads/writes, prompts or connections.

`baseline` verifies the pinned archive/snapshot and current recovery sources,
then captures a fresh consistent read-only source snapshot. Full rows, schema
and financial facts must match the archive. Within that SAME transaction it
runs the existing inventory collector, `demo_qr_preservation.validate`, and the
exact expanded `demo_qr_migration_guard.META` queries. Metadata is read twice.
The full schema hash uses the unchanged guard's `schema_digest`, including
column defaults, EXTRA and table collation. Old inventory/SHOW CREATE hashes
are not substituted. Both typed recovery hashes and original inventory hashes
are retained in snapshots; their conventions are not relabeled.

An independently reviewed expected expanded schema SHA-256 is mandatory. Obtain
it through separately authorized exact-source metadata review using the guard's
META/schema_digest convention. Step 277's ordinary schema hash is not equivalent.
Missing/mismatched review stops without issuing a baseline.

Exclusive outputs: `baseline-<id>.json` (the exact four-field guard format) and
`baseline-binding-<id>.json` (actual baseline FILE hash, archive/snapshot hashes,
schema hash, and separate recovery/migration source maps). Counts, original-
convention financial fingerprints, balances, ledger totals and FK counts must
agree with the archive snapshot. No restore/migration success is attested.

`export-sql` is file-only: no credentials or connection. It checks the pinned
archive, migration-baseline FILE hash, binding report and current source maps.
It creates `source-<id>.sql` exclusively and rereads protected bytes for SHA-256
and positive size. `sql-export-<id>.json` binds these to the archive/baseline;
sql_restore_verified, backup_proof_issued and migration_verified remain false.

SQL is deterministic UTF-8 without BOM. Unicode strings use UTF-8 hex/CONVERT,
binary uses hex, NULL remains NULL, Decimal uses fixed notation without floats,
and dates/times use controlled literals. Unsupported values, ambiguous names,
unsafe schema and stored objects stop. Quoted schema defaults are preserved.
All CREATE/INSERT and FK references explicitly name the isolated rehearsal
schema. No USE, CREATE DATABASE, DROP, DELETE, TRUNCATE, account/grant changes
or source/development table writes are emitted. Session-only mode/UTC/FK/charset
state is saved/restored. Cyclic FKs still require explicit orphan verification.

Do not run this target-bound SQL as a privileged DBA or repurpose it for source
recovery. Future SQL restore tooling must enforce exact target/account/grants/
emptiness and verify the EXACT SQL artifact. Restoring the `.lpx` cannot certify
the SQL. SQL restore tooling and QR rehearsal are excluded from this step.

Source changes invalidate prior archive bindings. Freeze/review code before a
new separately authorized backup; never rewrite historical hashes or evidence.

## Migration evidence compatibility — partial, never readiness

Step 201 `validate_evidence`/`load_evidence` were inspected. They require:

- `baseline-<id>.json` containing the exact inventory format and independently
  approved expanded `full_schema_sha256`.
- `backup-proof-<id>.json` with complete_schema_and_rows, stored_objects_reviewed,
  baseline FILE hash, dump_path and a pinned `source-<id>.sql` dump.
- A rehearsal proof at BOTH predecessor and QR target revisions, full-row and
  post-schema verification, and the exact guard `source_hashes()` map.

The new baseline satisfies the unchanged baseline format/hash convention in
offline tests. The `.sql` filename and checksum fit its backup-path requirements,
but NO successful backup-proof or rehearsal-proof is issued. Independent restore
of the EXACT SQL, full preservation checks and actual QR rehearsal are required.
Neither `.lpx` restore proof nor export report is a substitute. Guard and runner
remain unchanged.

## Operator sequence — commands are future proposals, not authorization

1. Review exact schema/account, independently approve protected storage and
   target absence/provisioning, trusted public CA/IP-SAN readiness, DBA object
   absence, metadata privileges, connector version and Windows API compatibility.
2. Separately authorize and maintain the source writer/DDL pause, review active
   transactions/metadata locks without printing SQL, and exclude concurrent
   isolated-target administration. No sessions are automatically killed.
3. Separately authorize ONE backup. Use a new artifact ID; keep output private.
   No source rows/schema are written. Successful backup is not recoverability.
4. Independently review the private backup proof and obtain its `dump_sha256`
   and `baseline_sha256` without displaying full archive/snapshot contents.
5. Separately authorize ONE isolated restore. Source is never connected in
   restore mode. Review full verification before making any recovery claim.
6. Only after SQL restore verification, compatible successful proof production,
   isolated QR rehearsal, a fresh pause
   proof and exact grants/source fingerprints: separately authorize migration.
   MySQL DDL rollback must never be assumed. Resume writers only after an
   independent preservation post-check. No automatic restore/stamp/downgrade.

Offline/default (no file reads, prompts or connections):

```powershell
& .\backend\.venv\Scripts\python.exe -I .\backend\scripts\demo_qr_recovery.py
```

Future backup, after its separate authorization; replace placeholders privately:

```powershell
& .\backend\.venv\Scripts\python.exe -I .\backend\scripts\demo_qr_recovery.py --mode backup --execute --confirm-target lankapex_demo_db --confirm-writer-ddl-pause --confirm-private-console --confirm-dba-stored-object-review --artifact-id <NEW_32_LOWERCASE_HEX_ID> --tls-ca <APPROVED_PUBLIC_CA_PEM>
```

Future restore, after separate schema/account provisioning AND restore approval:

```powershell
& .\backend\.venv\Scripts\python.exe -I .\backend\scripts\demo_qr_recovery.py --mode restore --execute --confirm-target lankapex_demo_qr_rehearsal_20261115 --confirm-new-isolated-target --confirm-private-console --confirm-dba-stored-object-review --artifact-id <SAME_ID> --dump-sha256 <PINNED_ARCHIVE_SHA256> --baseline-sha256 <PINNED_SNAPSHOT_DIGEST> --tls-ca <APPROVED_PUBLIC_CA_PEM>
```

Future baseline (live read-only source access AND private evidence creation):

```powershell
& .\backend\.venv\Scripts\python.exe -I .\backend\scripts\demo_qr_recovery.py --mode baseline --execute --confirm-target lankapex_demo_db --confirm-writer-ddl-pause --confirm-private-console --confirm-dba-stored-object-review --artifact-id <SAME_ID> --dump-sha256 <PINNED_LPX_SHA256> --baseline-sha256 <PINNED_SNAPSHOT_CONTENT_DIGEST> --reviewed-schema-sha256 <INDEPENDENTLY_REVIEWED_EXPANDED_SCHEMA_SHA256> --tls-ca <APPROVED_PUBLIC_CA_PEM>
```

Future SQL export (private file reads/writes only; no database connection):

```powershell
& .\backend\.venv\Scripts\python.exe -I .\backend\scripts\demo_qr_recovery.py --mode export-sql --execute --confirm-target lankapex_demo_qr_rehearsal_20261115 --confirm-private-export --artifact-id <SAME_ID> --dump-sha256 <PINNED_LPX_SHA256> --baseline-sha256 <PINNED_SNAPSHOT_CONTENT_DIGEST> --migration-baseline-sha256 <PINNED_BASELINE_FILE_SHA256>
```

These are distinct approvals from backup/restore. `--baseline-sha256` retains
the logical recovery snapshot CONTENT digest; `--migration-baseline-sha256`
means SHA-256 of the actual new baseline FILE bytes. Do not interchange them.
The inventory's `evidence_file_created=false` describes its read-only collector,
not the baseline producer, which explicitly creates private files afterward.

Do not paste angle-bracket placeholders literally into PowerShell. Quote paths
containing spaces. Neither command contains a password. Confirmations represent
real completed reviews; they are not instructions to fabricate evidence.

Offline tests only:

```powershell
& .\backend\.venv\Scripts\python.exe -m unittest discover -s backend/offline_tests -p test_demo_qr_recovery.py
```

## Step 283: independent exact-SQL restore verification

The `verify-sql-restore` mode independently restores the exact exported SQL
artifact, not the logical archive's parameterized restore. Its default mode
accesses no files, credentials or database. Execution requires separate explicit
authorization for isolated-target DDL/data restoration and private proof creation.

Before execution, independently approve the exact fixed isolated target
`lankapex_demo_qr_rehearsal_20261115`, provision its reviewed restore account and
exact grants, verify object absence/metadata visibility, protect the artifact
directory, and exclude concurrent target administrators. The target must have no
tables, routines or events. Do not run the logical archive restore into this
target first: a populated target is rejected, never automatically cleaned.
Verified TLS with IP identity 127.0.0.1 remains mandatory. No source connection
is made by SQL verification; its source evidence must already be reviewed.

Future separately authorized command (replace all placeholders privately):

```powershell
& .\backend\.venv\Scripts\python.exe -I .\backend\scripts\demo_qr_recovery.py --mode verify-sql-restore --execute --confirm-target lankapex_demo_qr_rehearsal_20261115 --confirm-new-isolated-target --confirm-private-console --confirm-dba-stored-object-review --artifact-id <SAME_ID> --dump-sha256 <PINNED_LPX_SHA256> --baseline-sha256 <PINNED_SNAPSHOT_CONTENT_DIGEST> --migration-baseline-sha256 <PINNED_BASELINE_FILE_SHA256> --sql-sha256 <PINNED_SQL_FILE_SHA256> --sql-export-report-sha256 <PINNED_EXPORT_REPORT_FILE_SHA256> --tls-ca <APPROVED_PUBLIC_CA_PEM>
```

The archive, baseline, baseline binding and export report must bind to the same
source revision, inventory and current source fingerprints. SQL size/checksum
must match both the independently pinned checksum and export report. Bytes must
also equal deterministic regeneration from the validated archive. Only those
checked bytes are split and executed, once; no generic SQL import is accepted.
Identity, exact grants, session safety and target emptiness are checked again
immediately before execution. All writes are explicitly target-qualified.

An independent read-only post-restore capture checks all 27 tables, complete
schema DDL, full-row counts/hashes, authoritative financial fingerprints,
relationship preservation, zero foreign-key orphans, defaults and revision.
Only exact approved self-schema FK qualifications in restored SHOW CREATE
output are normalized; external references remain rejected. Session and
connector/TLS safeguards are retained.

Only after these checks and source-fingerprint revalidation succeed are
`sql-restore-proof-<ID>.json` and then `backup-proof-<ID>.json` exclusively created
in the existing protected migration artifact directory. The latter uses the
unchanged migration guard's baseline-file hash, SQL path, positive size and SQL
hash contract, and binds the independent restore proof hash. Export evidence is
never rewritten. Successful output is:

`PASS: exact SQL restore and preservation verified; backup proof issued; QR rehearsal unverified`

On STOP, preserve all partially restored objects and artifacts. MySQL DDL is not
transactionally reversible; there is no automatic rollback, retry, cleanup or
replacement proof. A second run with existing proof files is rejected. Review
any partial state and obtain separate recovery authorization.

This does not produce rehearsal or writer-pause evidence, run the QR migration,
or establish migration readiness. Guard compatibility is offline contract-tested;
native Windows protection and live restoration remain unverified. Changes to
the recovery source fingerprint invalidate earlier source-bound archives: freeze
reviewed sources before a newly authorized backup/baseline/export sequence; never
edit historical proof to match new code.

Historical backup/restore scripts remain unchanged and must not be used for this
revision. Native Windows and live MySQL behavior are not proven by offline tests.
