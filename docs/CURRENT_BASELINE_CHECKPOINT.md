# Current viva checkpoint — offline integration

Source: `lankapex_viva_db`, `ae2b7c5f1d48`, exact SV-02 35-table inventory,
including `alembic_version`; zero triggers, views, routines and events.
These are required expectations, not a fresh live observation.

`backend/scripts/current_checkpoint_plan.py` reuses SV-02 inventory validation and
MR-03 typed fingerprints. No existing checkpoint script, artifact or runtime
blocker is changed. No executable backup/restore path is provided. `connect`,
`backup`, `restore` and `write` unconditionally reject. There is no activation flag.

## Offline integration sequence

1. Independently approve server UUID, exact endpoint, existing backup account/grants,
   CA certificate bytes/hash and IP SAN for `127.0.0.1:3306`. This integration pins
   that endpoint to match SV-02; a different endpoint requires review.
2. Approve a NEW timestamp/GUID private destination outside repository/public
   roots. `destination_policy` checks supplied approval equality, absence,
   non-reparse ancestors and the exact protected operator/SYSTEM inheritance
   policy. These supplied observations are not proof of actual ACLs. A future
   separately authorized operator wrapper must inspect/recheck filesystem state,
   provision only a new directory and verify every final file ACL and owner.
3. An authorized, separately reviewed capture implementation must own one bounded
   REPEATABLE READ / consistent snapshot / READ ONLY transaction per capture.
   Independently trusted DBA freeze evidence must cover its entire lifetime;
   all application, webhook, scheduled and operator writers/DDL remain paused
   through pre-capture, dump and post-capture. Metadata coherence requires that
   separate DDL exclusion. The module checks supplied ownership/time/freeze
   contracts, not real transaction state or authenticated DBA issuance.
4. Supply complete actual column projections and all rows from all 35 tables to
   `capture_fingerprints`, with independently captured counts and hashes. It
   preserves exact Decimal, NULL, binary and datetime serialization using MR-03.
   No financial or nonfinancial table is omitted. Both missing and extra row
   columns fail. The 100,000-row limit per table fails closed; it never silently
   truncates or samples. A larger table requires separately reviewed bounded
   external sorting/streaming work before execution, not a raised limit or skip.
   A successful capture now issues an immutable, process-local capability bound
   to the complete inventory hash (including column metadata), actual typed
   fingerprints, revision, UUID, snapshot/owner identity and freeze evidence.
   Failed or partial streams issue nothing. These capabilities validate supplied
   offline evidence; they do not authenticate DBA evidence or establish live reads.
5. Preserve exact SHOW CREATE TABLE hashes and full column/default/option,
   PK/UNIQUE/index/FK/CHECK enforcement metadata in the approved inventory. The
   SV-02 validator checks inventory structure; it is not independent proof of
   MySQL schema parity or completeness. Collect orphan checks separately.
6. `dump_arguments` prepares a shell-free native argv list with VERIFY_IDENTITY,
   explicit CA, TLS 1.2/1.3, hidden native `--password` prompt, single-transaction,
   quick/hex-blob/order-by-primary and explicit triggers/routines/events. No
   `--databases`, trigger omission or credential-bearing option file is allowed.
   This function does not run the command or read a CA. Before future execution,
   verify the actual CA bytes/hash and IP SAN; reserve an exclusive attempt and
   recheck absent output paths. Never log prompts, credentials or row data.
   It requires a destination capability issued only after destination-policy
   validation. Only the exact `viva.sql` filename directly inside that approved
   directory is accepted. Noncanonical Windows paths, traversal, alternate data
   streams, device/reserved names and destination substitution are rejected.
   Destination and output absence/reparse observations are mandatory. A future
   writer must re-inspect these properties immediately before exclusive creation,
   hold safe handles and reject symlinks/junctions/reparse escapes; the offline
   capability cannot prevent filesystem races or replace actual ACL inspection.
7. After one authorized dump, verify exit/completion, actual full dump object
   inventory and nonempty file. Hash actual bytes with SHA-256 and read back.
   Capture the source again under the continuing freeze. Require exact pre/post
   inventory (including all content and schema hashes) equality. The module does
   not parse dump SQL: `completion_verified` and `dump_inventory` must originate
   from separately reviewed actual output validation, not operator guesses.
8. `prepare_manifest` returns deterministic draft JSON bytes and their checksum;
   it does not write anything. Bind private pre/post inventory files by SHA-256,
   actual dump hash/size, server/revision and freeze evidence ID. Recovery remains
   NOT_EXECUTED. Future authorization must separately cover exclusive writing,
   readback validation, private ACLs and an evidence record linking approved
   destination, account/TLS approval and reviewed tool hashes. A draft is never
   proof of backup execution or independently trusted evidence.
   Both complete issued pre/post captures are mandatory. The function rechecks
   their exact inventory bindings and freeze expiry at the supplied current
   verification time, requires distinct ordered capture identities and continuous
   identical freeze evidence, and compares complete fingerprints. Dictionaries,
   unissued objects and inventory substitutions cannot replace captures. Manifest
   bytes include both capture hashes and IDs. Production must use a trusted fresh
   clock and independently authenticated evidence. Python process-local registries
   are not a security boundary against arbitrary code running in that process.
   A later correction additionally requires an issued pre-launch job capability
   bound to approved configuration, exact recipe/destination, pre-capture object
   and expected post-capture identity. The reserved journal must match at final
   manifest creation. See `CHECKPOINT_EXECUTION_PREPARATION.md` for that binding.

## Single-attempt capture consumption correction

Every capture, destination capability, dump plan and manifest requires the same
immutable `checkpoint-<32 lowercase hexadecimal digits>` attempt identity. A
manifest must bind that identity to the exact approved directory, `viva.sql`
path, dump hash/size and both capture hashes. Cross-attempt substitutions fail.
No caller-supplied consumed-state flag is accepted.

`OfflineConsumptionStore` is exclusively a shared in-memory state simulation.
Under a lock it reserves the attempt and both capture keys as one operation
before returning any manifest. Both RESERVED and COMPLETE reject subsequent
use, including a changed dump, identical replay, or newly issued captures for
the same attempt. An interrupted reservation is never released. New simulated
clients share the same ledger; this models restart recovery semantics but is
NOT cross-process storage or actual durability. Unavailable/uncertain state
must fail closed. There is no reset, retry or cleanup interface.

The future independently reviewed durable boundary must implement atomic unique
reservation of all keys, durable flush before acknowledgement, cross-process
mutual exclusion and conflict rejection, and persistent RESERVED/COMPLETE
records. It must preserve interrupted or partial reservations indefinitely for
operator review; never infer unused state from missing completion. Durable
failure or uncertain acknowledgement must stop before artifact publication.
`DisabledDurableConsumptionStore` always rejects. A subsequent filesystem
reservation candidate and pre-launch journal are now prepared and tested in
temporary directories; see `CHECKPOINT_EXECUTION_PREPARATION.md`. They remain
subject to independent Windows durability, ACL and crash-recovery review. No real
checkpoint directory is created. Keep all backup/write execution blockers active.

On failure, `failure_record` prepares only an allowlisted phase and INCOMPLETE
status. A future writer must exclusively persist it before/after the attempt as
appropriate, preserving partial files without retry, overwrite or cleanup. This
offline module cannot guarantee durability because all writes remain disabled.

## Operator sequence, after separate review/authorization

Fresh DBA/TLS/grant/capacity gate → protected new directory → complete pre-capture
→ one trigger-aware dump → dump validation and complete post-capture → exclusive
manifest/checksum/readback/ACL verification. No historical checkpoint is replaced.

Restore requires separate exact-target provisioning and restore authorizations,
reviewed scratch-only SQL import, full 35-table content/schema/constraint/object
comparison and source-preservation verification. Do not use historical 33-table
Step 391/400 runners unchanged. A restored baseline at this revision leaves only
three future upgrades: Driver Finance, Support, then Customer Addresses.

## Focused offline verification

```powershell
.\backend\.venv\Scripts\python.exe -B backend\offline_tests\current_checkpoint_suite.py
```

Fixtures are fictional and network access is blocked. No real checkpoint directory,
CA approval, trusted evidence, live snapshot, dump, restore or manifest is created.
