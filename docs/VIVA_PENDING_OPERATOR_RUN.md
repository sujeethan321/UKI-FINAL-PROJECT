# Current VIVA three-revision preparation

The executable implementation and current scratch-account name are documented in
[VIVA_EXECUTION_OPERATOR_RUN.md](VIVA_EXECUTION_OPERATOR_RUN.md). The following
is retained as the earlier preparation/reference plan, not an execution command.

Status: PREPARED_NOT_EXECUTED. No database connection, account/privilege change,
backup, restore, migration, service or maintenance-freeze change was performed.
The new runner validates source contracts and emits a plan only. execute_stage
always refuses execution; no generic Alembic command is offered as a fallback.
Historical Step 322/336 scripts are references only and remain unchanged.

## Fixed identities and offline command

Source: 127.0.0.1:3306/lankapex_viva_db, UUID
7bc6e90d-aced-11f1-be0b-10e7c6704500, MySQL 8.0.46.
Migrator: lankapex_viva_migrator@127.0.0.1. Runtime:
lankapex_viva_runtime@127.0.0.1. Proposed separate rehearsal:
lankapex_migration_verify_viva20261124, account of the same name @127.0.0.1.
These scratch identities are proposals, not provisioning approval.

Run from the project root (one terminal command):

```powershell
powershell.exe -NoProfile -File backend/scripts/prepare_viva_pending.ps1
```

Expected: PREPARED_NOT_EXECUTED, zero database actions. Application environments,
.env and db_maintenance.py are unchanged. No application settings or engine are
imported by the preparation CLI. No password is requested in plan mode.

## TLS

VIVA mode now uses C:\Program Files\LankaPex-TLS-Trust\ca.pem with CERT_REQUIRED,
hostname verification, SAN-only matching, VERIFY_X509_STRICT and TLS >=1.2.
Missing/invalid CA fails closed. The shared engine's VIVA connect hook verifies
the real SSL socket and the exact independently supplied leaf DER SHA-256:
8dc0c2e9b4691a7287432bed7b6292b7b58a7d2d21beed986309f259c6c98488.
That is NOT the CA-file hash. Independently record the CA-file SHA-256 separately.
No fallback to encryption-only TLS is retained for the VIVA database. Existing
non-VIVA default development/testing/production branches remain intact.
Legacy launchers that explicitly demand CERT_NONE must not be used as a fallback.
No certificate verification against a real server was performed here.

## DBA preflight and binary logging

After separate read-only DBA authorization, verify exact current identity,
ae2b7c5f1d48, all 35 table names, zero triggers/routines/views/events, InnoDB,
utf8mb4/utf8mb4_unicode_ci, enforced CHECKs, strict SQL mode, FK/unique checks,
roles/default/mandatory roles and all effective grants. Record approved CA/leaf
identities and fresh DBA freeze visibility (sessions including idle clients,
transactions, locks, scheduled events and replication appliers). Every writer
and DDL source must remain paused throughout capture/backup/rehearsal/live gates.
An observation dictionary accepted by the offline guard is NOT trusted evidence.

Example read-only SQL for the DBA (one line):

```sql
SELECT @@server_uuid,@@hostname,@@port,VERSION(),DATABASE(),CURRENT_USER(),CURRENT_ROLE(),@@GLOBAL.log_bin,@@GLOBAL.log_bin_trust_function_creators,@@GLOBAL.partial_revokes,@@GLOBAL.mandatory_roles;
```

Migration minimum scope: SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX,
REFERENCES, TRIGGER on the exact target only, no GRANT OPTION, roles, global
privileges or SUPER. Existing runtime rights remain unchanged and must not gain
DDL/TRIGGER privileges. Scope patterns must use escaped underscores when
partial_revokes=0; inspect actual server semantics before any grant decision.

With binlog enabled and trust_function_creators=0, TRIGGER privilege alone may
not permit CREATE TRIGGER. Do not grant SUPER or disable binary logging. Have a
separately authorized DBA with existing SYSTEM_VARIABLES_ADMIN temporarily set
the GLOBAL trust setting to 1 ONLY under an approved server-wide change window.
Record its original value (expected 0), evidence/owner/time, and prevent unrelated
stored-program creation. The runner must never change this global automatically.
The proposed SQL, not executed or authorized here, is one line:

```sql
SET GLOBAL log_bin_trust_function_creators=1;
```

The same DBA must restore and verify 0 after the approved creation window,
including on partial migration failure; preserve created objects and failure
evidence, never retry or drop triggers automatically. Restoration SQL:

```sql
SET GLOBAL log_bin_trust_function_creators=0;
```

If this temporary change is not approved, STOP for an independently approved
DBA/isolated-instance alternative. Do not silently disable logging. Rehearsal
must test creation under the chosen policy and trigger invocation again after
restoring trust=0. Triggers use the creating account as DEFINER: keep that
account and the target-table TRIGGER privileges needed to execute them. Do not
drop/lock/revoke it as generic cleanup; review persistent DEFINER dependencies.
Runtime DML fires triggers using those definer rights. Preserve DEFINERs in future
backups and rehearse restoration without granting global privileges to runtime.

## Manual backup and isolated recovery

Use docs/SV02_SECURITY_AND_RECOVERY.md, not the unfinished native checkpoint
runner or obsolete 33-table dump verifier. Require separate backup authorization,
one new private timestamp/GUID directory, operator/SYSTEM-only ACLs, no reparse
ancestors, absent outputs and an exclusive attempt record. Before and after the
dump capture complete typed content hashes over all 35 tables and exact DDL,
column/key/index/FK/CHECK/options metadata plus trigger/routine/view/event inventory.
Use the reviewed mr03 typed-value/fingerprint algorithm, ordered original column
projections and fail-closed complete-row limits. Never use counts alone, repr
serialization or truncated data as preservation proof. Independent DBA capture
and evidence review remain necessary; this preparation CLI does not capture data.

The following one-line dump command assumes separately approved variables and
private absent output; it is NOT execution authorization:

```powershell
& 'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe' --no-defaults --protocol=TCP --host=127.0.0.1 --port=3306 --user=$approvedBackupUser --password --ssl-mode=VERIFY_IDENTITY --ssl-ca='C:\Program Files\LankaPex-TLS-Trust\ca.pem' --tls-version=TLSv1.2,TLSv1.3 --default-character-set=utf8mb4 --single-transaction --quick --hex-blob --order-by-primary --set-gtid-purged=OFF --no-tablespaces --column-statistics=0 --triggers --routines --events --skip-add-drop-table --skip-add-locks --skip-disable-keys --skip-lock-tables --result-file=$approvedNewDump lankapex_viva_db; if($LASTEXITCODE -ne 0){throw 'STOP: preserve partial dump; no retry'}; Get-FileHash -LiteralPath $approvedNewDump -Algorithm SHA256
```

The native client's VERIFY_IDENTITY is not proof of Python's strict-X509 policy;
verify native client TLS behavior separately. Backup-account privileges must be
approved for observed MySQL version and stored objects (SELECT, SHOW VIEW,
TRIGGER, EVENT and routine-definition visibility as applicable). Do not elevate
runtime to satisfy dump metadata requirements.

Separately authorize scratch provisioning and a single restore. Verify scratch
absence/emptiness, exact scratch-only account privileges (including global,
schema, table and inherited roles), TLS and denial of source/development/test/
recovery schemas. Inspect the dump for schema selection/creation, qualified writes
and DEFINER hazards. Use mysql.exe with a shell-free argument list, explicit
scratch database, verified TLS, native hidden password prompt and binary dump
stdin. Preserve source pre/post fingerprints. No unsafe shell string, MYSQL_PWD,
password argument or credential-bearing temporary option file is permitted.
An exact restore executor for this new target still needs implementation/review;
do not repurpose historical runners by bypassing their target/revision guards.

## Pinned stages and financial preservation

| Parent | Stage | Total tables | Triggers |
|---|---|---:|---:|
| ae2b7c5f1d48 | bf38d2a90176 | 40 | 10 |
| bf38d2a90176 | c04d9e7a6201 | 44 | 16 |
| c04d9e7a6201 | d15a8c902e64 | 45 | 18 |

Graph and exact object sets derive from actual migration sources and the existing
SV02/MR07 contracts, not current observed metadata. Require both name/definition
parity and counts. Finance adds five tables and provenance unique constraints;
support adds four tables and the approved notification CHECK change; addresses
adds one destination table, address idempotency columns and constraints. These
are expected schema changes, not permission to modify original row contents.

Before/after EACH stage compare every original application table (34 tables,
excluding alembic_version) using the exact original ordered columns, row count
and complete typed content hash. Preserve financial/customer/business/order/
delivery/Driver/Stripe data. Exclude added columns from old-row hashes, but verify
them separately: historical address request fields must be NULL. New tables must
be empty. Verify all FKs/orphans, CHECK enforcement, exact trigger bodies and
DEFINERs, schema types/defaults/options and expected revision after each stage.

The new preparation runner refuses actual stage execution. A separately reviewed
execution release must bind a dedicated connection, hidden credentials, UUID,
account, strict socket/pin and grants, trusted fresh freeze/backup/recovery
evidence, original projections, complete reflected schema, exclusive attempt
marker and immutable redacted failure evidence. Use one explicit revision per
invocation, never upgrade head. No application engine/environment fallback and
no db_maintenance.py bypass. MySQL DDL can partially commit: any unexpected state
is terminal, preserve evidence, no downgrade/stamp/reset or automatic retry.

## Remaining blockers

This is bounded preparation, not an executable production migration release.
Fresh trusted DBA evidence, backup capture/recovery, scratch provisioning/restore,
runtime schema reflection, stage execution adapter and live authorization remain
outstanding. No complete restore/stage executor is claimed by the plan CLI.
Run permitted offline tests only; never backend/tests/conftest.py during freeze.
