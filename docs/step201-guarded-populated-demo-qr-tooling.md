# Step 201 — Guarded populated-demo QR runner

Source preparation and offline validation only. No live runner, evidence access,
DPAPI decryption, database operation, backup/restore, server startup or cleanup
was executed. The populated demo is NOT certified ready for migration.

## Scope and architecture

The only database/account accepted is localhost:3306/lankapex_demo_db with
lankapex_demo_qr_migrator@localhost, for 6e3f2c1a9b04 -> 7b9e4d2c8a15.
No runtime-account DDL privileges are added. All other source/test/rehearsal
schemas are rejected. Existing migration tools and general maintenance guards
are unchanged.

New entry points:

- backend/scripts/upgrade_populated_demo_qr.ps1
- backend/scripts/upgrade_populated_demo_qr.py
- backend/scripts/demo_qr_migration_guard.py
- backend/scripts/check_demo_qr_private_path.ps1
- backend/alembic_demo_qr/env.py

Default mode performs no connection, credential read or evidence read.
PreflightOnly is a LIVE read-only database operation and needs separate approval.
Execute additionally requires exact target/revision confirmation and the
maintained writer/DDL pause assertion.

The Python runner does not import application Settings, models, DB engines or
Groq clients, and never loads backend/.env. It constructs one explicit MySQL URL.
The wrapper invokes Python with -I to ignore inherited Python path/user-site
configuration. It restores its process environment and disposes private buffers.
The DBAPI target and SQLAlchemy URL are verified, followed by actual database,
account, port, roles, grants, MySQL 8.0, STRICT_TRANS_TABLES and FK checks=1.
ANSI_QUOTES/NO_BACKSLASH_ESCAPES and partial_revokes modes are intentionally
unsupported: STOP rather than broaden quote/grant matching.

The separate Alembic environment has no engine/settings fallback. It requires a
single-use permit bound to the exact guarded Connection, rechecks its identity
and predecessor revision, and uses the existing revision directory. General
backend/alembic/env.py and db_maintenance.py are untouched.

The existing QR migration source SHA-256 is pinned. All 16 revision sources,
runner/guard/wrapper/ACL-validator/SQL-inventory sources and installed
SQLAlchemy/Alembic/PyMySQL versions are fingerprint-bound to rehearsal proof.
SQLAlchemy DDL is compiled offline to an exact ordered allowlist: two CREATE
TABLEs, one CREATE INDEX, one unique ALTER, then the exact single-row Alembic
version UPDATE. No migration function is run to build this allowlist.

Only that sequence may write, and only after all evidence and baseline gates.
Comments/multiple statements, unexpected binds, executemany, cross-schema
references, other DDL/DML, repeated writes and unexpected connections STOP.
Legitimate Alembic table-qualified revision SELECT is accepted. Only narrowly
listed read-only dialect initialization probes precede connection binding.

## Private prerequisites — not created by this step

Protected operator/SYSTEM-only files owned by the operating Windows user:

    <verified operator profile>/AppData/Local/LankaPex/PrivateDemoQr/demo-qr-migrator.dpapi
    .server-logs/private-demo-qr-migration/

The credential is the existing CurrentUser ConvertFrom-SecureString format.
Step 208 relocates only the QR credential, using demo_qr_credential_storage.ps1.
Its directory has not been created. See step207-dedicated-qr-storage-design.md
for metadata-only preflight, separate preparation authorization, ancestor policy
and limitations. Existing runtime/JWT files stay unchanged. This helper and the
changed migration wrapper are source-fingerprinted: old rehearsal source maps
cannot authorize the changed code. Preserve historical evidence; obtain fresh
rehearsal proof for the actual new sources before migration. The existing
repository migration-evidence storage still needs its own security review.
The new migrator identity/credential has NOT been verified or provisioned.
Its exact grants must be global USAGE only, no active roles, and:

    SELECT, INSERT, UPDATE, CREATE, ALTER, INDEX, REFERENCES

on exactly the escaped lankapex_demo_db schema, with partial_revokes=OFF.
No DELETE, DROP, GRANT OPTION, role/global/other-schema rights. Every extra or
unrecognized grant is rejected. Legacy demo-migrator credentials are not reused.
Runtime lankapex_demo_app remains unchanged/DML-only.

Every evidence file, the private evidence directory and the full dump require
protected operator/SYSTEM-only DACLs, correct owner and no reparse components.
The wrapper validates these before decrypting the credential. Direct Python
invocation independently calls the read-only PowerShell artifact ACL validator.
There is no automatic ACL repair or directory/file creation.

## Required evidence contracts

All JSON proofs live directly in private-demo-qr-migration, use UTF-8 (BOM accepted),
and have a new 32-lowercase-hex artifact ID. Their SHA-256 values are supplied
independently by the operator. Baseline JSON is not identical to the raw Step 199
stdout report; a separately reviewed capture/approval procedure is required.
No proof-producing tool or private artifact was fabricated in Step 201.

1. baseline-<id>.json:
   - format=1; schema_reviewed_for_start=true.
   - inventory: the complete sanitized Step 199-style runtime inventory.
     It must pass demo_qr_preservation.validate for START, including all 26
     original tables, complete projections, zero duplicates/orphans, original
     runtime grants, absent QR tables and absent profile unique constraint.
   - full_schema_sha256: the independently reviewed full predecessor schema hash
     under THIS guard's META/schema_digest convention.
     This extends the earlier metadata query with column defaults/EXTRA and
     table collation, so it is NOT the older schema_metadata_sha256.

2. backup-proof-<id>.json:
   - format=1; database=lankapex_demo_db; revision=START; total_tables=27.
   - complete_schema_and_rows=true; stored_objects_reviewed=true.
   - baseline_sha256 equals the pinned baseline file hash.
   - dump_path is exactly private-demo-qr-migration/source-<id>.sql.
   - positive integer size_bytes and dump_sha256.
   The dump bytes are streamed only to verify size/SHA, never printed.

3. rehearsal-proof-<id>.json:
   - format=1; database=lankapex_demo_qr_rehearsal_20261115.
   - source_database=lankapex_demo_db, start_revision=START, end_revision=END.
   - restore_verified, migration_verified, full_row_preservation_verified and
     post_schema_verified must all be true.
   - backup_sha256 and baseline_sha256 bind the exact artifacts above.
   - source_hashes equals demo_qr_migration_guard.source_hashes() exactly.
   This proof must result from independently reviewed restore AND migration
   rehearsal on a NEW separately authorized isolated target, never an existing
   verification schema. Rehearsal tools/account provisioning remain separate work.

4. pause-proof-<id>.json:
   - format=1; database=lankapex_demo_db; baseline_sha256.
   - writers_paused, ddl_paused, active_transactions_reviewed and
     maintained_until_signoff must all be true.
   - verified_utc is timezone-aware, not future, no older than ten minutes.
   It is checked again immediately before DDL. It is operator/DBA attestation,
   not a mechanism that stops arbitrary writers. Maintain the actual pause.

Never set these fields true merely to satisfy a gate. Checksums bind content,
not truth: independent authorized review and the actual completed operations
are mandatory. The runner cannot remotely prove a human assertion or restore.
An old backup snapshot alone cannot satisfy recoverability.

## Live sequence, only after separate authorizations

1. Validate all artifacts/grants/ACLs and current source hashes.
2. Execution acquires a nonblocking advisory lock on the SAME connection.
   This protects against cooperating duplicate runners, not ordinary writers.
3. Fresh consistent REPEATABLE READ/READ ONLY snapshot verifies predecessor
   revision/table set, absence of partial QR state, zero duplicates/orphans,
   all original row counts, financial/relationship projections and signed
   reversal-aware balance fingerprints. All must match the pinned baseline.
   Full live predecessor schema metadata must match its reviewed pinned hash.
4. Recheck source/pause proof; perform immediate duplicate audit.
5. Set bounded metadata lock wait (15 seconds), enter the dedicated Alembic
   environment and run only END on the verified connection. The migration's
   own duplicate audit also precedes its first DDL.
6. Commit the guarded Alembic revision UPDATE after the exact write sequence.
7. Fresh read-only snapshot verifies END, 29 tables, empty QR tables, QR
   columns/types/nullability/defaults/collations, PKs/uniques/check/index/FKs,
   preserved original counts/projections/balances, and four expected new
   zero-orphan FKs. Original metadata must match exactly after removing only
   the two QR tables and the approved profile unique constraint/index.
8. Leave writers paused until a separately authorized independent runtime
   inventory confirms preservation and unchanged runtime grants.

Unexpected automatic MySQL index changes also cause STOP; do not silently
normalize them away. Rehearsal must resolve exact compatibility first.
The projection baseline is not all-row proof; independent full-row restore/
preservation review is still required, carried by the pinned rehearsal evidence.

## Exact future interface — NOT EXECUTED

Offline/default, no private access:

~~~powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\upgrade_populated_demo_qr.ps1
~~~

After separately approved artifact preparation, assign the eight path/checksum
variables below privately from the reviewed evidence. No variable is a password.

Live READ-ONLY preflight (also reads evidence and decrypts the migrator credential):

~~~powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\upgrade_populated_demo_qr.ps1 -PreflightOnly -ConfirmTarget lankapex_demo_db -Baseline $Baseline -BaselineSha256 $BaselineSha256 -BackupProof $BackupProof -BackupProofSha256 $BackupProofSha256 -RehearsalProof $RehearsalProof -RehearsalProofSha256 $RehearsalProofSha256 -PauseProof $PauseProof -PauseProofSha256 $PauseProofSha256
~~~

One-time DDL execution, requiring separate explicit authorization:

~~~powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\upgrade_populated_demo_qr.ps1 -Execute -ConfirmTarget lankapex_demo_db -ConfirmRevision 7b9e4d2c8a15 -ConfirmWriterDdlPause -Baseline $Baseline -BaselineSha256 $BaselineSha256 -BackupProof $BackupProof -BackupProofSha256 $BackupProofSha256 -RehearsalProof $RehearsalProof -RehearsalProofSha256 $RehearsalProofSha256 -PauseProof $PauseProof -PauseProofSha256 $PauseProofSha256
~~~

No plain alembic command, historical invitation upgrade or test runner is an
approved substitute. The new default mode is not a live readiness certification.

## Failure/recovery boundaries

Every failure exits nonzero with a sanitized category; Python also reports
ddl_attempted. Raw exceptions, SQL, records, prompts, credentials and proof
contents are never printed. New evidence/log files are not created.
Before DDL, all target access is read-only. After DDL starts, assume partial
schema/commit uncertainty even if a SQLAlchemy transaction rolls back.
Keep writers paused and preserve evidence for read-only operator diagnosis.
No retries, reset, stamp, downgrade, fixture cleanup, grant changes, backup
creation or automatic restoration exist in this tooling.

Metadata snapshots do not lock out concurrent DDL. Advisory locks and checks
cannot substitute for the real pause. Source/evidence files and account context
must remain under operator control. Immutable Python/.NET secret copies cannot
be comprehensively zeroed, though environment/BSTR/SecureString cleanup is used.
Native filesystem/DDL/provider behavior remains untested here.

## Offline validation and remaining gates

Tests use synthetic reports, mocked connections/adapters and compiled SQL only.
The Alembic command is mocked in its invocation test; no upgrade function or
database-backed integration test is executed. PowerShell sources are parsed,
not run against private paths.

Recorded offline validation: 22 focused runner tests and 50 existing offline
demo tests passed (72 total); Python compilation, PowerShell parsing and
whitespace/conflict-marker checks passed. No live runner execution occurred.

Remaining blockers: restricted migrator/credential verification or provisioning;
independently approved baseline/schema capture; fresh protected full backup;
isolated restore/migration rehearsal and pinned proof; real writer/DDL pause;
live preflight; explicit one-time execution authorization; independent runtime
post-check and startup/resumption authorization. Step 201 clears none of these
live gates.
