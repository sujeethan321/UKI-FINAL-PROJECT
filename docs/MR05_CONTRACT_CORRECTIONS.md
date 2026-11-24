# MR-05 offline contract corrections — partial completion

Status: corrected offline evidence/capture/failure boundaries; full semantic
migration parity remains UNRESOLVED. No MySQL rehearsal is authorized or ready.
MR-02/MR-03 real-execution blockers remain unconditional. No database/client,
SQL, migration, backup, restore, service, grant, credential or feature operation
was performed. The writer/DDL freeze remains active.

## 1. Independent source object ledger

New artifact: backend/contracts/MR05_SOURCE_OBJECTS.json.
Builder: backend/scripts/mr05_source_contracts.py.

The builder reads migration AST and literal SQL text only. It does not import a
migration, execute its functions, run SQL, use Alembic or read observed mock state.
Simple declaration helpers are expanded by AST substitution, not Python execution.
It preserves actual column, PK, FK, UNIQUE, index, CHECK and trigger declarations,
replaces explicitly altered CHECKs in order, and records unresolved declarations
instead of silently supplying an empty list. Migration/model source hashes bind
the artifact. The saved artifact must match a fresh source-only build.

| Revision | Application tables | Including Alembic | Triggers | Unresolved declaration extractions |
|---|---:|---:|---:|---:|
| 9d1a6f4e0c37 | 32 | 33 | 0 | 0 |
| ae2b7c5f1d48 | 34 | 35 | 0 | 0 |
| bf38d2a90176 | 39 | 40 | 10 | 0 |
| c04d9e7a6201 | 43 | 44 | 16 | 0 |
| d15a8c902e64 | 44 | 45 | 18 | 0 |

Head model COLUMN NAME parity passed for all declared tables. This is not full
model/migration semantic parity. The following remain explicit blocking items:

- Alembic's framework-owned version table DDL is not declared by these migrations.
- Translating SQLAlchemy AST/literal MySQL declarations into independently reviewed
  reflected metadata, including implicit names/defaults/options and equivalent
  type forms, is not implemented.
- Full model type/default/constraint semantics have not been established by the
  column-name comparison. Some source table options remain preserved as symbolic
  declarations such as **options; they are not invented reflected values.

`require_runtime_parity` rejects these unresolved items. The source ledger is
marked SOURCE_EXTRACTED_REQUIRES_INDEPENDENT_SEMANTIC_REVIEW and execution_ready=false.
Do not use this artifact as a completed actual-schema contract or approve live
execution by merely hashing it. Existing normalized MR-02 mock manifests remain
test fixtures, NOT proof of source-to-reflection parity. No live path is enabled.
New negative tests use hand-authored expectations and reject removed/changed
columns, FKs, UNIQUEs, indexes, CHECKs and triggers; source-specific tests also
assert real financial/destination constraint names independently.

## 2. Approved identities and fresh DBA evidence

MR-03 approved manifests now require dba_approval with exact server_uuid, source,
scratch, source_account, scratch_account, source_scope, scratch_scope, issuer and
max_age_seconds. Constructor UUID values must match that approved manifest.
Actual mocked database/account/TLS/grants still undergo their separate checks.

The only supported authority is explicitly MockAttestationAuthority. It issues
in-process evidence identities; verification requires that exact issued payload,
issuer, scope and server binding. It checks evidence_id, observed_at/expires_at,
bounded age (at most 300 seconds), writer/DDL freeze and trigger/DEFINER attestation.
Reused tokens/evidence IDs are rejected within the issuer's in-process registry.
Altered/unsigned dictionaries do not produce a receipt. Capture receipts are
immutable, issuer-recorded and single-use. Each mock gate/capture consumes fresh
evidence; exhaustion fails closed. Tests advance a fictional clock explicitly.

THIS IS NOT DBA AUTHENTICATION. A caller-created mock authority or timestamp is
not real independent trust. `verify_real_attestation` always blocks. Eventual live
trust needs separately approved pinned DBA signing identities/public keys,
authenticated issuance, signed manifest/attempt/server/schema/account scope and
nonce, bounded trusted-clock policy, key revocation and durable cross-process
anti-replay storage. New adapter/release review is required; no flag can enable it.
The mock registries do not claim replay protection across process restarts.

## 3. Orchestration-owned immutable backup evidence

New issuer-only ValidatedEvidence binds approved exact manifest bytes, approved
source fingerprint and actual backup bytes. It stores immutable strings/bytes and
is checked against the private issuer registry; forged objects and mutated fields
fail. MR-02 execute_prepared now REQUIRES this capability, centrally revalidates
manifest/backup bytes, calls full manifest validation itself, and repeats binding
checks per stage and before success. An adapter returning preflight=True cannot
skip them. MR-03 constructs a capability only after its own approved checks.

The operator-approved SHA-256 remains an out-of-band trust input; the issuer does
not invent approval or claim that a valid backup hash proves a successful restore.
No real backup was read in MR-05. Tests use only temporary fictional bytes.
New source hashes invalidate old approval manifests; do not silently reapprove
historical evidence. Production CLI execution still stops unconditionally.

## 4. Coherent capture contract

MockConsistentSnapshot has one owner, REPEATABLE READ/read-only intent, a bounded
monotonic lifetime (default 30 seconds, maximum 60), a single-use trusted MOCK
freeze receipt and a detached typed view. It checks the full typed state before
and after capture; equal counts do not mask same-count updates. Wrong owners,
expired/closed views, interruptions, mixed-time content/metadata and replacement
of the catalog state stop capture. No timezone conversion or financial rounding
is introduced. MR-03 source and stage captures now use this boundary.

This is a mock transaction contract, not an implementation of InnoDB transactions.
A future real collector must own and close a bounded read-only consistent snapshot,
coordinate counts/rows/projections within that snapshot, verify isolation/session
settings, and independently exclude writers/DDL. MySQL metadata/DDL is not made
transactionally coherent merely by REPEATABLE READ. Fresh DBA visibility, metadata
locks/DDL review, source identity checks and coordinated freeze remain mandatory.

## 5. Durable offline failure evidence

OfflineEvidenceSink creates a NEW mr05-test-<16 hex> directory exclusively under
an existing non-reparse parent. It writes INCOMPLETE evidence first. Artifacts
use exclusive creation, flush/fsync and SHA-256 sidecars; no existing artifact is
overwritten or deleted. A terminal exclusive COMPLETE marker is trusted only with
all checksums. Partial marker/data/sidecar writes remain INCOMPLETE; no cleanup or
mutation retry occurs. Completion is evidence completion, NEVER migration success.

DurableMockEvidence connects that sink to the mocked adapter. Failure records
contain a safe category, revision, actual table/trigger names and schema digest.
One best-effort original-record fingerprint and source-preservation fingerprint
are retained when obtainable; otherwise UNAVAILABLE is explicit. Partial DDL is
preserved, not repaired. A failure is recorded before additional observations.
Raw exceptions, credentials, document contents, private paths and financial rows
are excluded by the sink interface. Tests use isolated temporary directories only.

Filesystem ACL ownership, directory flush/atomicity guarantees on the real Windows
volume and attacker-resistant live publication remain separate review requirements.
No current private checkpoint or document directory was opened or changed. The
sink is not enabled for actual recovery evidence and does not claim Windows ACL
verification. The original incomplete marker stays as append-only history; the
reader requires the complete/checksum set before accepting completion.

## Targeted verification and next step

Run only mr02_guard_suite.py, mr03_adapter_suite.py and mr05_contract_suite.py using
the backend virtualenv Python with -B. Ordinary backend/tests/conftest.py is not
used. All data is fictional, sockets are forbidden in tests, and transitions are
in-memory mock state changes. Python compilation and source graph/contract checks
do not import migrations or execute SQL.

Remaining blocker: independent full declaration-to-reflection/model semantic
parity and framework DDL review. Keep the live adapter absent and execution
disabled. Request review of the source ledger and offline corrections; do not
request or start a MySQL rehearsal based on these results. Actual DBA trust,
runtime coherent snapshot enforcement and live private evidence sink verification
remain future independently authorized release work.

Observed offline results: 29 MR-02, 35 MR-03 and 24 MR-05 tests passed (88 total).
Python compilation passed for seven changed/new Python files. Source extraction
reported the expected stage table/trigger counts, zero unresolved extraction
operations and zero head-model column-name differences. Full semantic parity is
still blocked as stated above. No unrelated suite or database operation ran.

Changed files: backend/scripts/mr02_rehearsal.py, mr03_adapter.py,
mr05_evidence.py and mr05_source_contracts.py; backend/offline_tests/
mr02_guard_suite.py, mr03_adapter_suite.py and mr05_contract_suite.py;
backend/contracts/MR05_SOURCE_OBJECTS.json; docs/MR05_CONTRACT_CORRECTIONS.md.
