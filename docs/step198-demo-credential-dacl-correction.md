# Step 198 — Guarded file-only demo credential DACL procedure

SOURCE PREPARATION ONLY. No live credential metadata, contents or permissions
were inspected or changed during this step. No database or server operation
is part of this procedure.

## Exact scope and path correction

The supported target is:

    C:\Users\admin\Desktop\LankaPex\.server-logs\private-demo\demo-app.dpapi

The Step 198 prompt omitted the separator between LankaPex and .server-logs.
That misspelled path is rejected. Review the canonical path above before
execution. No recursive or parent-folder ACL correction is provided.

Existing inventory requirements remain unchanged. The demo launcher uses the
same credential format, but does not enforce the inventory wrapper's ACL gate.
Neither script is modified here.

## Safety and backup sequence

The default command is offline preparation only, not an ACL inspection.
Execution requires -Execute, exact -ConfirmTarget and -ConfirmFileOnlyDacl.

The correction checks the literal absolute target, every existing path component
for reparse points, current Windows operator, exact owner match, and DACL
metadata. It refuses an already-protected target (including repeat execution),
unexpected explicit principals or Deny rules. Other inherited entries can be
removed only under this reviewed file-only authorization.

A native handle requests READ_CONTROL and WRITE_DAC, not credential data access.
It opens the existing file without following a final reparse point, rejects
directories/multiple hard links, and retains a read-only share mode to prevent
normal data writers, deletion and replacement while correction is in progress.
Existing incompatible handles cause STOP. Volume/file index, length and
last-write metadata bind the operation to the same file.

The procedure creates one fresh directory:

    .server-logs/demo-dacl-backup-<new-guid>/

It uses exclusive Windows directory creation with an operator/SYSTEM-only
protected DACL supplied at creation. A directory handle prevents normal
rename/deletion during use. It never reuses an existing backup directory.
The new objects' owner is assigned to the current operator at creation;
the credential's existing ownership is never changed.

The file original-dacl.json is created with CreateNew and an operator/SYSTEM-only
protected DACL supplied at creation. It contains only ACL/ownership/file identity
metadata, UTC capture time and the parent DACL baseline. It contains no credential
ciphertext or password. The file is flushed, closed, checked for reparse points,
checked for private DACL/owner, reread and compared with the original metadata
before the credential DACL can change. No backup is overwritten or removed.
.server-logs/ is already excluded by the repository .gitignore.

Immediately before correction, owner, original DACL, identity and parent DACL
are rechecked. One SetSecurityInfo call on the held handle supplies only
DACL_SECURITY_INFORMATION and PROTECTED_DACL_SECURITY_INFORMATION. Owner,
group and SACL pointers are null. The new DACL contains only explicit Allow
Full Control for the verified operator and SYSTEM. This replaces inherited
access without a separate removal/grant interval and does not require SACL
or SeSecurityPrivilege operations.

Post-verification checks the private DACL, owner, unchanged parent DACL, held
file identity and a newly opened handle to the exact original path. No credential
bytes are read or written, so no content hash is taken. All handles are disposed.

## Proposed commands — operator review required before execution

From C:\Users\admin\Desktop\LankaPex, offline preparation:

~~~powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\repair_demo_credential_dacl.ps1
~~~

Expected:

    PASS: offline DACL procedure preparation only; no private metadata read or permission changed

After reviewing the corrected target path, run under the actual owning Windows
admin account, not the Codex execution identity. The following would change the
target DACL and create the private ACL backup; IT WAS NOT EXECUTED:

~~~powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\repair_demo_credential_dacl.ps1 -Execute -ConfirmTarget 'C:\Users\admin\Desktop\LankaPex\.server-logs\private-demo\demo-app.dpapi' -ConfirmFileOnlyDacl
~~~

Expected success:

    PASS: exact credential file DACL corrected and verified; owner/identity preserved; credential contents unread

Failure reports a fixed stage, backup_verified and target_change_attempted
booleans, exits nonzero, and preserves partial backup objects. There is no
automatic rollback, cleanup or retry. A true target_change_attempted does not
prove whether the native update succeeded; obtain metadata-only review.
Raw exception text, SIDs, usernames and backup paths are not logged.

## Metadata-only post-verification — no decryption or database connection

This is distinct from inventory execution:

~~~powershell
& {
    $ErrorActionPreference='Stop'
    try {
        . .\backend\scripts\demo_credential_dacl.ps1
        $target='C:\Users\admin\Desktop\LankaPex\.server-logs\private-demo\demo-app.dpapi'
        Assert-DemoDaclPath $target $target
        Assert-DemoDaclNoReparse $target
        Assert-DemoDaclPrivate (Get-DemoDaclMetadata $target) (Get-DemoDaclOperator)
        'PASS: exact credential metadata is protected operator/SYSTEM-only'
    } catch {
        'STOP: credential metadata verification failed; no automatic repair'
    }
}
~~~

Do not rerun inventory, decrypt the credential or start a server as part of this
ACL correction. Those remain separate operations.

## Separate operator-reviewed rollback

Restoring the original DACL reintroduces the original broader inherited access.
It requires separate rollback authorization and both confirmation switches.
The correction wrapper NEVER invokes rollback.

Privately identify the exact new backup file using directory metadata; do not
print its contents or account identifiers. If exactly one backup exists, the
following is a reviewable way to select it without printing private paths:

~~~powershell
$backupFiles=@(
    Get-ChildItem -LiteralPath .\.server-logs -Directory -Filter 'demo-dacl-backup-*' |
    ForEach-Object { Join-Path $_.FullName 'original-dacl.json' } |
    Where-Object { Test-Path -LiteralPath $_ -PathType Leaf }
)
if ($backupFiles.Count -ne 1) {
    throw 'STOP: select the exact reviewed backup privately; do not guess'
}
$backupFile=$backupFiles[0]
~~~

If there are zero or multiple candidates, STOP for private metadata review.
Never choose the newest file automatically or reuse unrelated evidence.

After separate review/authorization:

~~~powershell
. .\backend\scripts\demo_credential_dacl.ps1
$result=@(Invoke-DemoCredentialDaclRollback -BackupFile $backupFile -ConfirmRollback -ConfirmOriginalBroaderAccess)
$result | Select-Object -SkipLast 1
if ([int]$result[-1] -ne 0) { throw 'STOP: rollback requires review; no retry' }
~~~

Rollback requires the exact approved backup location, private directory/file
DACLs, original operator ownership, same credential identity and unchanged parent
DACL. It restores only the backed-up DACL with the appropriate protected or
unprotected flag; it never restores owner/SACL or changes credential bytes.
An already-restored DACL is rejected. Failed/incomplete backups, changed ownership,
changed parent ACLs or identity mismatches require manual review, not a bypass.
The backup remains private and is never deleted automatically.

## Limitations and offline validation

Mocked tests cover wrong paths/owner, missing/reparse targets, unsafe/existing
backup locations, write/readback/ACL verification failures, native correction
failure, unexpected remaining principals, owner/identity/parent changes,
repeat correction, success, and no target mutation before verified backup.
Rollback has separate mocked confirmation, ownership, failure, success and
duplicate checks. In-memory security descriptors and native declarations are
compiled/checked without calling filesystem mutation APIs. Default wrapper
execution and invalid confirmations do not inspect private metadata.

The actual native filesystem mutation paths have NOT been exercised against
private files. Windows PowerShell 5.1/.NET Framework is required. Privileged
actors can bypass DACLs; the broader parent-directory permissions are not fixed
by this file-only operation. Do not use this as proof of DPAPI decryptability,
database identity or application compatibility.
