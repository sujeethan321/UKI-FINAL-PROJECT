# Current checkpoint execution components — preparation only

Baseline: exact `lankapex_viva_db`, `ae2b7c5f1d48`, 35 tables and zero triggers.
No live observation, backup or restore is claimed by this work. Keep the freeze.

## Reuse-correction review

The existing capture/destination/dump/manifest attempt binding prevents ordinary
API substitution. Captures remain immutable process-local capabilities issued
after complete typed hashing, not proof of live capture or authenticated DBA
evidence. The in-memory consumption store was correctly documented as a simulation.
It did not provide OS-process persistence; the filesystem candidate below closes
that implementation gap for offline review, not production approval.

## Reservation implementation candidate

`FilesystemConsumptionStore` in `current_checkpoint_plan.py` operates only on an
already existing supplied root. It never provisions a checkpoint directory.
Reservation files contain the attempt, both capture hashes and manifest binding.
An OS-level nonblocking exclusive lock serializes scanning and exclusive journal
creation across processes (Windows msvcrt / POSIX flock). All conflict checks run
under that lock. One immutable reservation represents all keys, avoiding a
partially acknowledged multi-key update. File contents are flushed/fsynced before
success; POSIX directory metadata is also fsynced. COMPLETE and redacted FAILURE
are separate exclusive artifacts; reservations are never removed or released.

A crash before/during acknowledgement leaves either no acknowledged reservation
or an existing partial/complete file. Existing reservations always block reuse.
Malformed reservation files, unexplained entries and orphan terminal evidence
stop the store rather than being cleaned up. Lock contention/unavailable storage
fails immediately; there is no automatic retry. Roots/entries reject observed
symlinks and Windows reparse attributes. Root ACLs and protected handle ownership
are still mandatory in a future runtime boundary; these checks do not eliminate
filesystem TOCTOU risks on a directory writable by another actor.

Windows filesystem/power-loss durability, underlying volume guarantees and secure
handle-relative journal creation require independent platform review. File fsync
tests and child-process interruption tests do not prove those guarantees. The
candidate must not be called production-durable yet.

## Private Windows directory and native dump preparation

`checkpoint_execution_prepare.py` supplies immutable recipes only. The directory
recipe uses CreateDirectoryW with the protected operator/SYSTEM security
descriptor supplied AT creation, avoiding a create-then-tighten ACL interval.
It requires approved parent handles, non-reparse ancestors, absent target,
exclusive creation, exact owner/protected inheritance/no extra ACEs, empty
contents, held handles preventing rename/delete, CREATE_NEW/no-reparse outputs
and final-file owner/ACL checks. Native Windows provisioning remains disabled;
the recipe and observation checks are not implementation of those Win32 calls.

The dump recipe reuses the current plan's exact private `viva.sql` child and
trigger-aware VERIFY_IDENTITY argv, with shell=False, private native password
prompt, no credential argv/env/options file, bounded timeout, and private error
capture with redacted public status. No subprocess client execution is wired.
On future implementation, verify the exact CA bytes/hash and matching IP SAN,
use the reviewed client binary and reject client tracing or inherited credential
environment/option defaults. Neither a recipe hash nor caller booleans establish
approval or successful TLS.

### Authoritative recipe and reserved-job correction

`bind_approved_configuration` binds exact externally approved configuration bytes
to their independently supplied SHA-256 and the issued destination capability.
It retains immutable bytes covering endpoint, port, server UUID, schema, account,
CA path/hash, destination and attempt. Tests use explicitly fictional approval
bytes: hashing caller-created data does NOT create real independent approval.
Real authenticated approval issuance remains an unconditional blocker.

Only this issued configuration can produce an issued `NativeDumpRecipe`.
Validation requires the original issued object, its unchanged complete fields,
and exact complete argv reconstructed from the retained configuration. Recomputed
checksums, new dataclass instances, changed host/CA/output, omitted/reordered flags
and appended overrides cannot authorize an altered command.

`reserve_prelaunch` now requires the completed issued pre-capture and independently
approved expected post-capture identity. It binds configuration/recipe hashes,
directory/security descriptor, dump and manifest paths, inventory/server/attempt,
exact pre-capture hash and expected post identity into the execution journal.
It returns an issuer-only reserved-job capability only after successful reservation.
Capture identities are unique per attempt in the offline issuer; a second object
cannot be issued with the same identity to substitute the expected post-capture.

`prepare_manifest` requires this capability and checks its exact issuing store,
destination and pre-capture objects, journal hash/token, expected post identity,
inventory, server, output and manifest path. The manifest retains the job,
configuration and recipe hashes. Direct entry without the issued job fails.
Reopened stores, failed/interrupted jobs and modified journal bindings cannot
resume or replace the reserved job. Existing one-time capture/attempt reservation
still prevents identical replay or changed dump details after consumption.
The in-memory issuer registries are not a sandbox against arbitrary Python code.

## Future single-attempt runtime sequence — not executable now

1. Independently approve endpoint/UUID/account/grants, CA identity, source and
   inventory, private destination and continuing writer/DDL freeze. Authenticate
   fresh DBA evidence with durable replay controls; never accept mock evidence.
2. Complete coherent pre-capture under the continuing freeze, then reserve the
   execution attempt BEFORE directory creation or launching any dump.
   `reserve_prelaunch` binds the directory/security descriptor, native argv hash,
   approval and attempt in an exclusive execution journal via `reserve_execution`.
   Only its issuing store instance can finalize that attempt's capture reservation;
   reopening after interruption refuses automatic resume. Failure before post-
   capture can still leave exclusive redacted evidence. The manifest reservation
   remains separate from pre-launch reservation because the post-capture does not
   exist at launch. These are prepared filesystem operations, not a live wrapper.
3. Provision/check the directory using the held-handle Windows recipe. Revalidate
   the pre-capture and its freshness through the separately reviewed source reader.
4. Recheck gates immediately before one shell-free dump. Never retry after a
   launch, timeout, interruption or uncertain outcome.
5. Validate actual dump completion/object inventory/schema content, nonempty
   file, checksum/readback; perform complete coherent post-capture and compare
   all 35 tables, exact schema and typed content fingerprints. No sampling.
6. Bind the attempt/destination/dump and captures, consume them once, then write
   exclusive private manifest/checksum/readback/result artifacts. Reserve first;
   do not acknowledge success before durable evidence is verified. Preserve
   all failed/uncertain state without cleanup or resetting reservations.

The real DBA verifier, live capture, private Windows creation,
native runner and dump parser are NOT enabled/implemented by these
recipes. All real methods in `DisabledBackupBoundary` and existing blockers
unconditionally reject, with no activation flags. They require a separately
reviewed implementation/release and explicit operator backup authorization.
No scratch restore or migration executor is added.

## Focused offline tests

```powershell
.\backend\.venv\Scripts\python.exe -B backend\offline_tests\current_checkpoint_suite.py
.\backend\.venv\Scripts\python.exe -B backend\offline_tests\checkpoint_execution_suite.py
```

Only disposable temporary state directories are used. Child Python processes
test journal exclusion/reopen/interruption; they do not invoke MySQL. Windows ACL
and native execution observations are fictional. No real checkpoint artifacts
or historical evidence are modified.
