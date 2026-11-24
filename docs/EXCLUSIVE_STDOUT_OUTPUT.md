# Explicit stdout-v1 output integration — offline only

The reviewed legacy `--result-file=<viva.sql>` recipe is unchanged. It is NOT
silently rewritten at execution. `expected_stdout_approval` produces a clearly
labelled NEW proposal, `checkpoint-stdout-v1`, requiring a separately supplied
independently approved SHA-256 before `bind_stdout_approval` can issue a recipe.
Proposal generation is not approval. Tests use fictional approvals; real signer
verification/approval remains a runtime blocker, not a caller boolean.

The new proposal binds the entire stdout argv, base argv/configuration hashes,
reserved job hash, attempt, endpoint/port/server UUID/account, TLS CA path/hash,
source and exact approved destination/viva.sql. Issued-object identity,
immutable retained approval bytes and complete reconstructed argv are checked
again at use. Checksums recomputed over altered inputs cannot authorize them.
Only the explicitly approved new argv omits the legacy result-file argument.

## Exclusive output lifecycle

`run_model` accepts only the exact memory-filesystem and process fixtures. No
real filesystem, client executable, arbitrary callback or database can be
injected. The modeled flow reserves one job attempt before output mutation,
creates an exclusive output entry, verifies parent/ACL/reparse and handle/path
identity, and passes THAT handle as stdout with shell=False. The handle remains
owned through process completion, successful flush, checksum/readback and full
sealed-baseline dump validation, then closes before a model receipt is published.
Pre-existing outputs, substitutions, failure/timeout/interruption, missing flush,
checksum mismatch or partial/altered dump all stop and retain artifacts. Repeated
jobs are latched even when another fixture filesystem is supplied. No retry,
overwrite, release or cleanup path exists.

Memory-only file entries use validated `PureWindowsPath` identities for creation,
existence/reservation checks and lookup, so case-equivalent names collide.
Strict path validation runs before identity normalization; unsupported aliases,
traversal, ADS, device and UNC paths remain rejected. Handle binding still
requires the exact original approved path string. These model checks do not
replace or prove native atomic CREATE_NEW semantics.

Stderr is drained separately into a redaction consumer: no raw contents are
retained or logged. Only fixed status, a capped observed-byte count (16 KiB),
zero retained-content bytes and overflow indication are stored in a separate
exclusive status artifact. A future actual stream consumer must preserve this
bounded behavior concurrently with stdout; do not use unbounded communicate()
buffering or merge stderr into SQL. Failure evidence contains only a fixed phase
and preserve/no-retry status; failure to record it is marked INCOMPLETE.

## Receipt and activation boundary

Successful fixtures issue only `ModelRunReceipt`, with status
MODEL_ONLY_NOT_NATIVE_BACKUP. It binds job, attempt, separate stdout approval,
new argv hash, actual modeled output bytes/hash/size and baseline hash. It is
not a `checkpoint_native.VerifiedDumpRun`, is not registered in its issuer and
cannot authorize its manifest bridge. No real process exit or native receipt
is invented. `NativeStdoutRunner.run` and `issue_native_receipt` reject
unconditionally; no flag or environment override activates them. Existing
native, MySQL, backup and migration blockers are unchanged.

## Remaining native work

`checkpoint_stdout_windows.py` now contains prepared Win32 output and process
primitives. All actual Win32 activation, handle duplication, Popen dispatch and
native receipt issuance remain unconditionally blocked. Mock tests exercise
CREATE_NEW argument binding, parent/owner checks, immediate handle cleanup,
bounded threaded stderr draining, failed launch/exit/interruption and flush.
Only a duplicate of the original owned handle is proposed for CRT/child stdout;
the original and ancestor handles remain owned until operation completion.
Failure closes handles but never deletes output. Child termination/reaping is
process cleanup, not checkpoint cleanup or a retry.

These primitives do not yet form an authorized native run. No native receipt
can be issued, including from a model receipt. Authenticated stdout approval,
durable pre-launch reservation and redacted failure-artifact integration,
same-handle dump readback/full validation and receipt issuance remain mandatory
before activation. The prepared dispatcher now requires interactive stdin and
retains the exact bare --password option for MySQL's own private prompt. Windows
power-loss durability is not established by FlushFileBuffers or these mocks.

Prepared Windows output objects now retain an issuer-side binding to the exact
recipe object, job object/hash, attempt, stdout approval/argv, canonical approved
path, owner, API and original ancestor/output handles and handle values. Dispatch
rechecks this binding before duplication, immediately before launch and after
process completion; an output prepared for another valid job is rejected.

Stderr cleanup tracks successful thread startup and never joins an unstarted
reader. On interruption it reaps the child, signals cancellation, and prepares
Win32 CancelSynchronousIo for a blocked read (also unconditionally disabled).
It uses bounded joins and never cross-thread closes a buffered pipe being read.
Unresolved cleanup retains ownership references, blocks reuse and reports fixed
cleanup codes. An earlier exception is re-raised with its identity preserved and
cleanup_status/cleanup_codes attached; cleanup errors do not replace it. No
successful result is returned before cleanup completes. Actual Win32 pipe
cancellation remains unverified; mocked cancellation is not runtime evidence.

Incomplete cleanup additionally latches the sealed attempt ID/job hash in
process-local issuer state, retaining the prepared binding, fixed diagnostics
and unresolved ownership references. Every wrapper checks this state before
duplication or launch; replacing the wrapper or prepared-output object cannot
clear it. Unrelated independently issued jobs remain unaffected. There is no
reset/release operation. This is cross-instance protection within one Python
process, not durable cross-process protection; the latter still requires the
reviewed journal integration before any native activation.

## Durable stdout model integration

### Authenticated approval, source capture and manifest boundary

The existing `PinnedApprovalVerifier.verify_stdout` verifies an Ed25519-signed
`checkpoint-stdout-approval-v1` envelope. It binds exact proposal bytes/hash,
complete argv hash, job, attempt, destination and base configuration to the same
pinned signer and a fresh nonce. Freshness is bounded by the base authorization;
replay uses the existing private nonce store. `bind_authenticated_stdout` requires
that issued capability, and the prepared Windows integration rejects unsigned
checksum-only recipes. No chat message or model receipt can substitute for it.
Tests mock signature success explicitly; no signer/trust anchor is created.

`capture_transport_model` connects the existing MR14 read-plan/TLS policy with
the existing coherent capture and sealing interface, accepting exact mock
sessions only. It binds the approved UUID, endpoint, source schema, SELECT-only
account, CA identity and signed freeze. It permits the current approved 35-table
revision in addition to the historical baseline, without arbitrary SQL. Actual
connection/fetch activation remains blocked. Incomplete capture issues no sealed
success. `compare_sealed_source` requires ordered distinct captures, the expected
post-capture identity, matching fresh freeze evidence and exact full inventories
and fingerprints.

Prepared completion now requires a sealed post-capture and source comparison
before durable success. The caller-supplied capture is a fictional preissued
fixture in offline tests; real post-process capture acquisition remains blocked.
`bind_stdout_manifest` requires a separately issued native stdout receipt,
authenticated recipe, exact dump bytes, source-preservation proof and a durable
result hash matching the complete validated result. It writes explicit stdout-v1
approval/argv fields through the existing manifest contract, leaving legacy
recipes unchanged. `issue_stdout_native_receipt` remains unconditionally blocked;
tests register an explicitly fictional receipt only to exercise this bridge.

No real cryptographic verification is claimed: the reviewed dependency and
externally approved pinned signer are still missing. Live capture, trusted
runtime evidence, native receipt issuance and Windows execution remain disabled.

`run_model(..., journal=store)` reuses the exact `FilesystemConsumptionStore`
that issued its reserved job. No second store or journal framework is created.
The existing root/OS lock/exclusive-write/fsync mechanism now accepts immutable
`stdout_reserved`, `stdout_launch` and `stdout_validated` transitions. Each binds
the attempt, issued job SHA-256, stdout approval SHA-256, full argv SHA-256 and
exact validated output path. Reservation is written before memory output
creation; launch consumption is written before calling the mocked process.

Only the reserving store instance owns its in-memory continuation tokens.
Reopening a store cannot reconstruct them, and an existing launch record cannot
authorize another launch. Crashes after reservation or consumption therefore
leave terminally blocked evidence even when no child actually started. Nothing
resumes, resets, overwrites or deletes these records. New execution requires
independent authorization, a new attempt, fresh capture/approval and destination.

Failures use the existing `.failure.json` artifact, with the same attempt/job
binding, fixed stage/failure labels and allowlisted cleanup codes. Original
exceptions are preserved. Failed failure-record writes report INCOMPLETE, while
the durable reservation/launch still blocks restart. Malformed, truncated,
conflicting and orphan stdout transition records fail closed at their gates.
Successful model receipts follow output closure, flush/hash/full sealed-baseline
validation and the exclusive model-validation record. They remain model-only
and cannot authorize native execution or the native manifest bridge.

Approval hashes are binding identifiers, not authentication. Tests use existing
fictional issued approvals; separately authenticated stdout-v1 approval remains
mandatory before any future native integration. The no-journal `run_model` mode
is retained solely for existing memory-only tests and supplies no durability.
No native adapter is activated by passing a journal. Windows private-root ACL,
held-handle race defenses and metadata/power-loss durability remain unresolved
runtime requirements. File fsync alone does not establish those guarantees.

Output closure is guarded before receipt eligibility or failure recording. A
close error adds the allowlisted `OUTPUT_CLOSE_INCOMPLETE` cleanup code; an
otherwise successful run fails at `CLOSE`. Any earlier process/validation error
remains the primary exception, with its phase retained. The existing failure
journal is written once after cleanup so it includes the close outcome. Journal
write errors mark evidence INCOMPLETE without replacing the primary exception.
Reservation and launch consumption remain terminal, and no receipt is issued.

### Bounded native completion (offline)

`NativeWindowsStdoutAdapter.run_prepared_model` joins the existing Windows file
and process primitives to the same reserved-job journal. Tests mock native API
activation, descriptor duplication and child launch. Reservation precedes
output creation; durable launch consumption precedes dispatch. Original handles
are held through flush, two bounded same-handle reads, byte hashing and full
sealed-baseline validation. Closure and durable model completion precede the
existing model receipt. Failure recording preserves the original exception and
fixed cleanup codes; a failed journal write marks evidence incomplete.

Preparation-phase cleanup also preserves the original security exception and
traceback. If closing owned handles fails, the exception gains the existing
allowlisted OUTPUT_CLOSE_INCOMPLETE code; ownership references and the terminal
attempt/job latch are retained. The outer integration journals CREATE_NEW and
the cleanup code without replacing the primary exception. Evidence-write failure
marks INCOMPLETE. No descriptor duplication, launch or receipt follows such a
preparation failure; unrelated independently issued attempts remain unaffected.

Prepared readback uses GetFileSizeEx, SetFilePointerEx and ReadFile on the owned
handle, rejects empty/oversized/short reads and size changes, and never reopens
by pathname. Native activation and receipt issuance still reject unconditionally.
The real readback method itself is also blocked. Native tests exercise its
algorithm using mocked kernel calls; they do not prove Windows runtime behavior.

Credential entry is delegated to mysqldump's existing bare --password prompt
in an independently approved private interactive console. Python does not read,
store, log or pass the secret via argv, environment additions or files. The
prepared dispatcher rejects a noninteractive stdin and a password-valued option.
Real MySQL console prompting, stderr routing and cancellation have NOT been
verified. No process is started in these tests.

Implemented/tested offline: integrated ordering, job/handle binding, same-handle
read algorithm, full validation, redacted failure journaling and model-only
receipt gating. Prepared, not runtime-verified: Win32 handles/ACLs, console
prompting, pipe cancellation, process inheritance and storage flushing.
Not implemented/approved for execution: authenticated stdout approval activation,
reviewed real source capture and native-run receipt issuance. Windows power-loss
durability remains unestablished. Separate authorization and independent review
are required for every future real runtime exercise; no execution flag exists.

Focused journal tests use disposable temporary roots and Python-only restart
workers, never a real checkpoint output, database client or backup executable.

- Independently approve/authenticate the NEW stdout proposal; the old recipe's
  approval does not cover it. Resolve the existing signature-dependency approval.
- Map the already defined Win32 CREATE_NEW/private-ACL/reparse/held-parent checks
  and exclusive handle ownership to the new transport. Only the intended child
  stdout handle may be duplicated/inherited. Hold the original handle and parent
  protection throughout the child lifetime; never reopen output by pathname.
- Implement/review real shell-free process dispatch, private password prompting,
  bounded stderr draining, timeout/interruption ownership and safe child reaping.
- Prove actual flush/checksum/validation and durable attempt/failure recording;
  issue a real receipt only after these checks, binding the stdout approval and
  new actual argv as well as the existing job/configuration/sealed baseline.
- Windows create/race/power-loss guarantees remain unverified by these mocks.

Run only the focused offline suite:

```powershell
.\backend\.venv\Scripts\python.exe -B backend\offline_tests\checkpoint_stdout_suite.py
```

Output/process interfaces are mocked, with no native directory provisioning,
mysqldump, SQL, backup or restore. Existing fixture approval replay tests may use
disposable temporary journals; no real checkpoint directory or historical
artifact is touched. Real backup execution is NOT ready.
