# MR-09 — Guarded MySQL adapter (offline implementation)

Status: offline implementation complete; real execution unconditionally disabled.
No database connections, SQL execution, migrations, backups or restores were performed.
The maintenance freeze and disabled optional features remain unchanged.

## Files and boundaries

- `backend/scripts/mr09_mysql_adapter.py`: explicit MySQL inspection plans, observed-metadata normalization, guarded capture and single-stage execution interfaces.
- `backend/offline_tests/mr09_mysql_adapter_suite.py`: fictional raw metadata and mocked execution regression tests.
- This document: review scope and remaining release requirements.

`DisabledRealTransport.connect`, `fetch` and `upgrade` always reject execution.
The module entry point also rejects execution. There is no activation flag or environment override.
The existing MR-02 production execution blocker is unchanged. Inspectors accept only the
mock session implementation; they cannot silently accept a real connection or callback.
The stage executor changes fictional fixtures only, never a database.

## Identity, evidence and authorization

The source is exactly `lankapex_viva_db`; the scratch target is exactly
`lankapex_mr02_rehearsal`, using `lankapex_mr02_rehearsal@127.0.0.1`.
The proposed separate source reader is `lankapex_mr03_source_reader@127.0.0.1`.
No application defaults, environment connection targets or credentials are read.
Observed server UUID, selected schema and CURRENT_USER must match approved evidence.
The reviewed server version is pinned to MySQL 8.0.46; TLS and strict session settings
are required by the observation contract.

Complete SHOW GRANTS results must contain only the exact permitted schema scope and
rights. Wildcard underscores are escaped when required by partial-revokes semantics.
Role grants, active roles, mandatory roles, global rights and grant options are rejected.
This does not introduce SELECT permission on mysql.* for the source reader.

Every gate revalidates immutable approved manifest and backup bytes, source fingerprints,
canonical artifact provenance and adapter source hash. Fresh, single-use MR-05 issuer
receipts bind server, schemas, accounts and scopes with a maximum 300-second age.
Additional issuer-bound mock observations require no unexplained sessions, transactions,
data/metadata locks, DDL, enabled events or replication appliers, plus continuing writer
and DDL freezes. An unsigned user dictionary is not treated as trusted DBA evidence.
The mock issuer is only an offline trust simulation; real attestation verification remains blocked.

## Inspection and preservation

Explicit read-only query plans cover identity, TLS, grants, Alembic revision, tables,
columns, ordered keys, foreign keys, CHECK definitions/enforcement, indexes, trigger
bodies/DEFINER/context, routines, events, collations, SHOW CREATE TABLE, counts and rows.
Identifiers and projections are allowlisted; arbitrary inspection SQL is rejected.

All five complete table inventories and all trigger inventories are compared, including
the Alembic framework table. Missing and unexpected objects both fail. Canonical column,
PK, FK, UNIQUE, CHECK and index semantics are checked, with physical indexes retained.
Only a proven matching UNIQUE-index representation is classified to avoid double counting.
Effective engine, charset and collation are observed independently. Expected inheritance
is resolved through checked table policy and collation metadata, without copying expected
column semantics into observed results. Unknown metadata fails closed.

The capture contract owns a bounded REPEATABLE READ, consistent read-only snapshot
(30 seconds, at most 100,000 rows per table). Coordinated counts and typed, sorted-row
fingerprints preserve NULLs, binary data and Decimal values. Same-count content changes
and mixed-time fixture mutations fail. Actual MySQL metadata/DDL coherence still requires
independent runtime writer/DDL exclusion; offline tests do not establish that property.

Original table projections and financial fingerprints are preserved at every stage.
Driver approval/exemption rules, empty new tables, and historical address-request NULL
fields are checked separately. Source capture remains bound to the approved baseline.
No financial row contents or credentials appear in result artifacts.

Only one explicitly authorized adjacent transition is accepted per attempt:

| Previous | Target | Tables | Triggers |
|---|---|---:|---:|
| 9d1a6f4e0c37 | ae2b7c5f1d48 | 35 | 0 |
| ae2b7c5f1d48 | bf38d2a90176 | 40 | 10 |
| bf38d2a90176 | c04d9e7a6201 | 44 | 16 |
| c04d9e7a6201 | d15a8c902e64 | 45 | 18 |

The initial stage contains 33 tables and zero triggers. There is no unrestricted upgrade
head, downgrade, stamp, schema creation/deletion, grant operation, retry or cleanup path.

## Failure evidence

MR-05 exclusive evidence creation, checksums, fsync and incomplete markers are reused.
Failure latches prevent mutation retries. The original categorized failure is preserved
before attempting partial-state inspection. Partial observations include revision values,
actual table/trigger inventories and per-object metadata hashes when obtainable; missing
metadata is explicitly unavailable. Evidence I/O failure does not replace the original
failure or imply success. Temporary-directory tests do not prove private Windows ACLs.

## Offline validation

Focused suites passed: MR-02 29, MR-03 35, MR-05 24, MR-07 29, MR-09 31:
148 tests total. The MR-09 suite rejects wrong UUID/accounts, stale/missing DBA evidence,
backup changes, missing/extra tables, altered triggers, FK/CHECK/option differences,
source fingerprint changes and unauthorized transitions. It covers partial migration,
evidence failures, coherent capture and unconditional real-execution blocking.

Controller tests intentionally use independently authored minimal fictional schemas and
raw MySQL-shaped result sets. They are not a claim that production MySQL reflection has
passed. A separate unmocked source-only assertion checks the saved MR-07 canonical artifact
against its actual source builder. Compile both new Python files without importing them.

## Remaining prerequisites

Independent review is required before any future adapter release. A separately reviewed
real read-only transport and pinned stage runner, real DBA attestation trust/replay store,
certificate validation, actual effective-grant/DEFINER checks, resource bounds and private
durable evidence permissions remain runtime prerequisites. Do not enable these through
a flag in this module. Real MySQL rehearsal is not authorized or ready in MR-09.
