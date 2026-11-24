# MR-03 mock-only MySQL adapter interfaces

Status: prepared for independent source review; REAL EXECUTION DISABLED.
The writer/DDL freeze remains ACTIVE. Optional features are unchanged. No database
connection, SQL, migration, backup, restore, account/grant change or service action
was performed. MR-02, SV-02, historical guards and checkpoints are unchanged.

## Safety boundary

`backend/scripts/mr03_adapter.py` is an injectable implementation of the MR-02
adapter interface using exact, in-memory mock ports. It is not a live MySQL driver.
There is no database-client import, application settings import, credential input,
normal engine, Alembic command invocation, subprocess or network API. The module
does not provide CLI options or environment switches. Direct invocation prints a
disabled status and exits 2. `blocked_real_connection` always raises
MR03_REAL_CONNECTION_DISABLED, regardless of arguments/environment.

ReadOnlyCapture rejects real connection objects, arbitrary transport implementations
and subclasses. Mock fixture trees reject callbacks/custom objects BEFORE deepcopy.
PreparedAdapter accepts only the exact mock capture, writer and memory evidence
types. These are regression boundaries, not a Python sandbox; untrusted arbitrary
Python code must never be imported as an adapter.

The MR-02 production CLI blocker is unchanged:
LIVE_ADAPTER_NOT_PREPARED_OR_AUTHORIZED. No automatic linkage from that CLI to this
module was added. A real implementation requires a separately reviewed release
and explicit authorization, not a flag, token, alternate URL or monkey patch.

## Explicit bindings (proposals, not provisioned accounts)

| Capability | Database | Authenticated account |
|---|---|---|
| Migration capture/writer | lankapex_mr02_rehearsal | lankapex_mr02_rehearsal@127.0.0.1 |
| Recovery comparison capture | lankapex_mr02_recovery | lankapex_mr02_recovery@127.0.0.1 |
| Source read-only capture | lankapex_viva_db | lankapex_mr03_source_reader@127.0.0.1 |

All use explicitly bound TCP 127.0.0.1:3306, an independently approved server UUID,
actual database/account identity, verified TLS 1.2/1.3, strict SQL mode and enabled
FK/unique checks. The source cannot be a migration target. No default application
credentials are used. The proposed source reader must have SELECT only, not the
application runtime's write grants. No account is created by this tooling.

## Read-only capture interfaces

MockCatalogPort provides independent reads; ReadOnlyCapture validates and combines
them. No metadata is fabricated from the expected post-migration contract.

| Interface | Future independently reviewed MySQL data source |
|---|---|
| identity / permissions | Actual DATABASE(), CURRENT_USER(), server UUID, transport/TLS/session settings; effective global/schema/table grants and every role source |
| actual_revision | Complete alembic_version rows; exactly one reviewed revision |
| table_names / table / show_create | Complete base-table inventory, ordered columns, PK, UNIQUE, indexes, FK definitions/actions, table options and exact SHOW CREATE TABLE |
| CHECK metadata | CHECK_CONSTRAINTS and TABLE_CONSTRAINTS, exact definitions and ENFORCED state; same-name incompatible definitions fail |
| triggers | TRIGGERS plus SHOW CREATE TRIGGER: names, target, timing/event, body, DEFINER, SQL mode and creation charset/collations |
| stored_objects | Full views/routines/events inventory; unexpected objects stop for review |
| rows / row_count | Coherent bounded read-only snapshots and independent counts, no timezone conversion |
| relationships | One result for EVERY named FK; composite MATCH SIMPLE/nullable behavior from MR-02's NOT EXISTS query contract |
| freeze_observation | Fresh independent DBA session/transaction/lock/DDL/event/applier visibility and continuous writer freeze |

The MySQL query/reflection collectors are not implemented or executed in MR-03.
Mock transport fields represent observed results, not evidence that a live DBA
gate passed. Unknown/missing metadata fails closed. Real collectors must also
preserve generated-column/index attributes and exact ordering and detect concurrent
schema/data changes; these cannot be established by fictional metadata tests.

Captured schema/trigger data is compared to independently approved stage contracts,
not to itself. Counts are supplemental: expected stages are 33/0, 35/0, 40/10,
44/16 and 45/18 tables/triggers. Every approved column, constraint, index, CHECK,
trigger body/context/DEFINER and DDL hash remains part of the strict comparison.

## Fingerprints and approved backup binding

Fingerprint format is `mr03-typed-sorted-row-sha256-v1`. The manifest must declare
that algorithm and bind this adapter source hash in adapter_provenance, in addition
to MR-02's migration/tool source hashes. Reuse of an old differently serialized
fingerprint without independent review is rejected. Do not overwrite old evidence.

Each projected row is typed and hashed, then fixed-length row digests are sorted
with multiplicity and counted. This supports tables without PKs, preserves
duplicate rows and is independent of row-return ordering. NULL, bool, integer,
Decimal, text, binary, naive date/time/datetime have distinct representations.
Decimals use exact formatting without context rounding; floats, non-finite values,
aware timestamps and unsupported objects fail. Database wall-clock values are not
converted. Maximum 100,000 rows per table capture is a fail-closed preparation
limit, not silent truncation; larger databases require a reviewed bounded streaming
implementation before use. Independent row-count disagreement stops capture.

Original row projections include every original application table, including
financial, subscription, business, customer, order, delivery and Driver data.
The approved Driver-status map determines only the legacy exemption expectation.
Source capture additionally checks exact baseline schema, triggers and FK orphans:
unchanged row hashes alone do not permit source schema drift. Historical address
request columns must remain NULL and new migration tables must remain empty.

PreparedAdapter revalidates exact manifest bytes, source fingerprint approval,
backup bytes, adapter/migration provenance and disabled-feature contracts before
each mocked stage. Missing or changed evidence stops before mutation. Private
manifest paths, raw rows, passwords and raw database errors are not logged.

## Separated migration capability and failure evidence

MockMigrationPort only applies a supplied fictional stage state in memory. It has
no SQL execution method. It accepts only the four explicit adjacent transitions,
rejects replay/head/skips, checks the current revision and preserves target/grants
identity. PreparedAdapter additionally requires an exclusive mock attempt marker,
fresh gates, approved previous snapshot and source preservation. MR-02 performs
post-stage comparisons and records completion only after all checks pass.

Partial-DDL injection deliberately permits an altered fixture schema with an old
or new revision, then raises a safe failure. Both writer and adapter latch failure;
no automatic retry, downgrade, reset, cleanup or grant change is exposed.
MemoryEvidence records a sanitized failure BEFORE one best-effort partial-state
inspection. That inspection does not require a valid complete schema: it retains
actual revision(s), table/trigger names and metadata/DDL/trigger digests even when
normal validation fails. Changed state is marked partial_ddl_suspected; it is not
a claim of rollback or proof that every committed statement has been identified.
If inspection fails, the original stop record survives and no retry follows.

Evidence is in memory only. A future private filesystem sink still needs separate
review of exclusive files, ownership/ACLs, reparse protection, durable writes,
checksums and no-overwrite behavior. No private checkpoint was written here.

## Recovery comparison

ReadOnlyCapture.recovery_snapshot captures all table counts/content hashes,
schemas, exact DDL hashes, triggers/DEFINER/context, revision and FK/orphan results.
MR-02 verify_recovery checks an independently approved source snapshot fingerprint
and exact separately bound recovery target/account. It performs no restore and
does not normalize schema names, DDL text or DEFINERs. Differences require review.
Full recovery PASS still requires a fresh source-preservation observation,
separately authorized isolated restore, and restricted-runtime UPDATE/DELETE
denial tests against real matching fictional rows—not zero-row updates.

## Focused offline verification

```powershell
.\backend\.venv\Scripts\python.exe -B backend\offline_tests\mr03_adapter_suite.py
.\backend\.venv\Scripts\python.exe -B backend\offline_tests\mr02_guard_suite.py
```

Only fictional metadata/rows, temporary fictional backup/manifest bytes and mocked
in-memory transitions are used. Socket connection attempts are forbidden in tests.
Coverage includes identity/TLS, grants/roles/patterns, backup/manifest provenance,
revision progression, schema/CHECK/trigger drift, immutable original fingerprints,
source schema changes, orphan/count checks, typed serialization, partial DDL,
failure latching, credential redaction and the unchanged CLI execution blocker.
No unrelated frontend/full-project suite is needed or run.

Observed MR-03 results: 35 adapter tests and 29 MR-02 guard tests passed (64 total).
Python compilation passed for the two new Python files. Static inspection found
no database/application imports or real connection/SQL/Alembic execution calls
in the adapter; MR-02's execution blocker remains unchanged. These are offline
results, not evidence of live MySQL correctness or recovery readiness.

## Remaining prerequisites

1. Independent review of these interfaces and the proposed account/target bindings.
2. A separately reviewed real collector and scratch-only Alembic executor release,
   with pre-connection/SQL guards and no normal-engine fallback; no activation via
   current CLI/environment. Review grants, DEFINER dependencies and source denial.
3. Independently approved real backup, manifests and complete stage contracts in
   the explicitly declared fingerprint format. The initial source contract remains
   revision 9d1a6f4e0c37; never downgrade/stamp a newer source to fit it.
4. Fresh DBA freeze/identity/TLS/grant evidence, private evidence-sink review, and
   separate explicit authorization for every real rehearsal/recovery mutation.

No real rehearsal may begin from MR-03's mock results alone. Features stay disabled
and the existing maintenance freeze remains active.
