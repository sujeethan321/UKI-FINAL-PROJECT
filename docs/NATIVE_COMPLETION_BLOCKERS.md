# Bounded native completion attempt — BLOCKED, not runtime-ready

No MySQL connection, database SQL, dump, backup, restore or migration was executed.
No package, real trust anchor or private key was installed/created. Maintenance
freeze and all production execution blockers remain unchanged.

## Signature dependency

Installed distribution inspection found `cryptography` ABSENT. No independently
approved cryptography version pin was located in the inspected checkpoint or
requirements documentation. Real Ed25519 vector verification is BLOCKED: no
package installation or substitute/mock verification was performed for that
requirement. Existing fictional signature-plumbing regression tests are not real
signature tests. Required next input is an independently approved exact version
and separately authorized installation, followed by real positive/negative RFC
vectors and signed-configuration substitution tests with that backend.

## Windows-native implementation candidate

`checkpoint_windows_io.py` implements Win32 calls for exclusive creation with an
SDDL supplied at creation, protected exact operator/SYSTEM DACL inspection using
GetSecurityInfo/GetAce, final path and attributes from held handles, reparse/device
and file hard-link rejection, non-delete-sharing ancestor ownership, CREATE_NEW,
no-sharing output handles, bounded WriteFile and FlushFileBuffers. Handle ownership
and closure are explicit. It does not delete partial files or retry failed opens.

Only an issuer-created disposable `lankapex-native-test-*` root can be exercised
through the test facade. Production provisioning/file creation methods always
reject. There is no CLI/environment activation switch. Low-level Python internals
are not a sandbox against arbitrary code in the same process.

Actual isolated Windows verification failed with ERROR_ACCESS_DENIED (Win32 5)
while acquiring mandatory ancestor handles. No checkpoint child/file was created
by the native implementation. No privileges or ACLs were changed to bypass it.
The focused suite records these cases as BLOCKED/skipped, never successful native
verification. The production/power-loss blocker test passes separately. Do not
remove ancestor handles, add DELETE sharing or accept weaker ACL checks merely
to pass in this environment. A separately approved operator test context is needed.

### Operator follow-up and handle-cleanup correction

The operator subsequently reports that all six ancestors from `C:\` through
`C:\Users\admin\AppData\Local\Temp` passed CreateFileW and held-handle facts
inspection using FILE_READ_ATTRIBUTES (`0x80`). This is operator-provided evidence,
not an independently repeated Codex observation. The earlier access-denied result
was not reproduced and its cause remains unexplained; neither record is erased.
The follow-up does not prove checkpoint-path ACLs, reparse/race protection, file
creation, crash recovery or power-loss durability.

The constructor now registers each successfully opened handle before facts()
validation, so failure closes the current handle as well as previous owned handles.
Focused mocked tests cover first/later facts failure, reverse-order cleanup, open
failure and unchanged production blockers. They make no native calls or directories.

The next smallest Windows check is read-only inspection of the operator-approved
EXISTING checkpoint parent and its chain in the same standard operator context:
hold the required directory handles, verify final paths/reparse attributes and
read the intended parent's owner/DACL with FILE_READ_ATTRIBUTES | READ_CONTROL
(`0x20080`). Do not assume the historical checkpoint parent is currently approved.
Do not change its ACLs, create children, rename it, flush it or elevate. A failure
must remain blocked. Success would establish that limited parent inspection only;
exclusive child creation/ACL enforcement still needs separate isolated-test scope.

Crash interruption must preserve reservations and any created files, close only
owned handles, record a fixed redacted phase if possible, and never automatically
resume/retry/clean up. Existing exclusive filesystem journals retain that policy.
Normal process termination and successful file FlushFileBuffers do not establish
Windows directory-entry or volume/controller power-loss durability. Those remain
explicitly unverified and production durability approval remains BLOCKED.

## Unchanged dependent blockers

- Existing complete capture integration remains model-only, using the exact
  mocked MR-09 connection and bounded snapshot/fingerprint checks. No real
  connection was activated and no database-connected tests were run.
- Shell-free dump execution is still blocked. The reviewed `--result-file`
  pathname recipe cannot be silently converted to stdout; an explicitly approved
  full-argv/output-handle binding is required. Actual exclusive Windows output
  verification was itself blocked, so no successful output guarantee is simulated.
- No native-run receipt is issued without an actual successful authorized process,
  flushed/verified exclusive output, sealed-baseline validation and exact job/hash
  agreement. Existing receipt issuance remains disabled. Offline manifest drafts
  do not prove backup execution.

The task is PARTIAL/BLOCKED. Do not claim completion or request backup execution
on the strength of these source candidates. First resolve the dependency pin and
the authorized Windows test context, then complete/review exclusive stdout/native
receipt integration without weakening any accepted bindings.

## Accepted operator held-handle observations — limited scope

The operator now reports HELD_HANDLE_INSPECTION=PASS_READ_ONLY_OBSERVATIONS and
HANDLE_CLEANUP=PASS in the non-elevated operator session (SID ending 1001).
All seven ancestors through the existing VivaCheckpoints parent opened at
0x20080; final handle paths matched and reparse attributes were false. The
checkpoint parent owner was the approved operator, with only operator/SYSTEM
FullControl in its DACL. Codex did not independently repeat this inspection.
The exact observation time was not supplied. This report is evidence, not
independent authorization for creation, execution or a future session.

Existing-directory handle access is RESOLVED for that reported operator session.
The earlier unexplained access denial and distinct Codex-identity limitation are
preserved. This does not establish race-safe exclusive child creation, inherited
file ACLs, held-handle output routing, crash recovery or power-loss durability.
All native execution blockers and the maintenance freeze remain unchanged.

The smallest remaining output work is an explicitly versioned/approved stdout
transport bound to the issued configuration, job and exact viva.sql destination;
CREATE_NEW with restrictive ACL and reparse/final-path inspection; and routing
only the required duplicated owned output handle to shell=False mysqldump.
Do not silently strip --result-file from the previously approved argv. Keep
the handle owned through child completion, flush/validate bytes and sealed
baseline, then issue a receipt bound to actual exit, byte hash, job and attempt.
Test overwrite/substitution/interruption with harmless isolated fixtures before
requesting any real backup authorization. No output work was implemented here.

Dependency approval still requires an explicit cryptography==X.Y.Z selection,
approved distribution source and wheel SHA-256 compatible with the intended
backend Python 3.14.7/Windows environment, followed by separate installation
authorization. No version has been selected or approved by this assessment.
After installation, real RFC 8032 section 7.1 public-key/signature vector and
tampering tests must pass without mock verification. No installation was done.
