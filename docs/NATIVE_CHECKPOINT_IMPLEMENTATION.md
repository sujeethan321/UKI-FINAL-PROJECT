# Native checkpoint candidates — offline, partial, execution disabled

This step adds `checkpoint_native.py`, `checkpoint_dump_inspection.py` and focused
tests. It does not change MR/checkpoint blockers, historical artifacts, feature
flags or maintenance state. No private key or real trust anchor is created.

## Implemented boundaries

- Pinned Ed25519 approval verification interface accepts only externally supplied
  public-key bytes matching the separately approved hash and signer identity.
  Exact signed bytes bind configuration SHA-256, attempt/server/endpoint/accounts,
  CA identity, source and continuing freeze. Duplicate fields, wrong scope,
  stale/expired signatures and mismatched pins fail closed. Immutable issued
  authorization objects are rechecked against a fresh clock at use. A private,
  separately approved existing replay root uses the checkpoint filesystem
  reservation store to consume signer/nonce before issuing authorization. No
  mock signer fallback exists in production code. `authorized_recipe` feeds the
  signed configuration binding into the existing issued-recipe interface.
- The cryptographic implementation requires the reviewed `cryptography` Ed25519
  primitive. That dependency is NOT installed in the inspected environment. No
  package was installed or requirements changed; verification fails closed with
  REVIEWED_SIGNATURE_DEPENDENCY_UNAVAILABLE. Tests explicitly mock signature
  success to test scope/replay plumbing; they do not prove real signature validity.
- `capture_model` reuses MR-09's exact fixture session/inspector, complete canonical
  35-table metadata, identity/SELECT-only/TLS observation checks, owned bounded
  consistent read and typed full row fingerprints. Signed freeze times/nonce
  must match capture evidence. Same-count mutation during capture fails and no
  capture capability is issued before snapshot close succeeds. The method rejects
  real DBAPI sessions. Actual source-reader transport remains unimplemented and
  blocked, rather than allowing arbitrary connection callbacks.
- Native Windows candidates include SDDL-at-CreateDirectoryW and CREATE_NEW /
  OPEN_REPARSE_POINT / WRITE_THROUGH file calls behind an unconditional blocker.
  Each operational entry point rejects BEFORE loading Win32 libraries or calling
  the API. Mandatory held-handle observations reject incorrect final path/owner,
  reparse points, delete sharing, multiple links or extra/wrong ACEs. These model
  checks are not actual GetSecurityInfo/GetFinalPathNameByHandle implementation.
  Unblocking directory creation now would preserve partial state and fail rather
  than claim successful private provisioning. Do not remove the blocker.
- The dump inspector consumes only bounded supplied bytes (64 MiB maximum),
  performs SQL-aware string/comment tokenization without SQL execution, compares
  exact CREATE TABLE tokens with the capture's definitions, decodes all supported
  literal INSERT tuples and compares complete typed hashes/counts for all 35
  tables. It checks the actual Alembic row and completion marker. Only enumerated
  mysqldump session SET directives are accepted, including version-comment SETs.
  Any routines/events/triggers/views, cross-schema statements, unknown syntax,
  altered DDL/data or excess resources fail. No raw SQL/rows are logged. This is
  a deliberately strict supported grammar, not a universal MySQL SQL parser.
- Actual byte hash/size and inspected inventory can be bound to the existing
  job/capture/manifest gates ONLY with an issued successful native-run receipt.
  No such receipt issuer is enabled. Parsed SQL bytes alone cannot fabricate a
  zero process exit or claim backup success. Signed configuration, receipt recipe,
  reserved job, byte hash and attempt must agree.

### Authoritative dump-baseline correction

After coherent capture closes successfully, the native capture interface seals
immutable inventory, canonical table/column metadata and CREATE definitions against
that exact issued capture. Every CREATE definition SHA-256 must equal its captured
schema hash; canonical metadata and column projections must agree exactly with
the captured inventory, as must every row count/content fingerprint. Failed or
incomplete binding cannot issue a dump-baseline capability.

`validate_dump_bytes` now accepts only authorization, actual bytes and an issued
reserved job. Caller inventories, definitions, metadata and fingerprint overrides
are rejected. The job resolves its exact pre-capture and sealed baseline; current
reservation, signed configuration, attempt, server, paths, inventory and capture
hashes must agree. The parser accepts only the issued baseline capability and
checks all 35 definitions and complete typed rows against those retained values.
Returned status binds the exact byte hash/size, baseline hash, job hash and attempt.
Matching caller-generated replacement hashes cannot replace any retained value.

The manifest bridge derives its pre-inventory and pre-capture from the reserved
job and its post-inventory from a sealed, issued post-capture. It rejects caller
pre/post inventories and caller-reported dump hashes/results. The native-run
receipt must additionally bind the same job AND baseline hashes, recipe, attempt,
actual bytes and successful exit. No real receipt issuer is enabled. Fictional
receipt objects in offline tests do not claim an actual backup was executed.
The existing lower-level manifest helper remains an offline draft builder, not
proof of a native run; the blocked native boundary must use this receipt bridge.

The INSERT column-list parser now requires an identifier after every comma.
Trailing commas, consecutive/leading commas and non-identifier list elements
fail; the valid explicit-column form remains supported. Unknown syntax still
fails closed without accepting a partial backup.

## Execution-blocking implementation gaps

1. Independently review/install/pin the signature dependency and external signer
   approval process. Supply approved public key/configuration hashes, not secrets.
   Review replay-root ACLs and the inherited filesystem durability limitations.
2. Implement/review held-handle Windows owner/DACL/final-path inspection and
   race-safe parent traversal. All ancestors and output handles must reject
   reparse/junction escapes and rename/delete races. Implement final file ACL
   checks and safe security-descriptor lifetime/handle cleanup. No native
   provisioning was exercised by this step.
3. Establish actual Windows file AND directory-entry persistence guarantees on
   the approved local filesystem/volume. File fsync / WRITE_THROUGH candidates and
   normal process-interruption tests do not prove power-loss recovery. Directory
   flush remains unimplemented/blocked. Failure to prove persistence must STOP;
   never release uncertain reservations or resume an interrupted attempt.
4. Implement/review the real bounded read-only DB transport with SAN-only verified
   TLS and exact accounts, independently observed metadata and continuous DBA
   writer/DDL exclusion. The complete model interface is not a live capture.
5. Resolve native dump output exclusivity: the current approved recipe contains
   `--result-file`, which opens by pathname and does not guarantee CREATE_NEW.
   A shell-free runner must use a reviewed exclusive held output handle/stdout
   recipe or prove equivalent isolation. It must NOT silently rewrite issued
   argv, overwrite a pre-existing file or weaken output/path binding. Until that
   recipe/handle integration is independently reviewed, NativeDumpRunner rejects
   unconditionally and invokes no client process. No native receipt can be issued.
6. Exercise a sanitized genuine mysqldump fixture offline before release. Unknown
   serialization (e.g. unreviewed binary/charset forms or version directives) must
   remain blocked; do not fall back to counts or skip financial data. The current
   tests validate fictional supported grammar, not an actual private backup.

The existing filesystem journal can preserve exclusive redacted phase records;
a future wrapper must invoke it on every operation failure, flush/verify those
artifacts and retain incomplete state. This step does not claim new Windows
durability guarantees or an end-to-end execution wrapper.

## Verification

Only focused checkpoint suites and in-memory compilation are used. Native tests
use public RFC test-vector key bytes, explicitly mocked signature success,
fictional raw DB metadata/dump bytes and disposable replay journals. No real
signer, private key, MySQL connection, SQL execution, client backup, restore,
native checkpoint directory or historical checkpoint is created/modified.

Independent review is appropriate for these partial candidates. Backup execution
is NOT ready; operator authorization alone cannot enable incomplete code.
