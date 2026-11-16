# Step 216: Exclusive QR credential directory preparation

SOURCE PREPARATION ONLY. No live storage preflight or directory creation was
executed, no real ACL/owner was modified, and no credentials, private evidence
or database were accessed. The Step 215 operator result established that the
then-existing ancestors passed and at least one storage directory was missing;
it did not identify which directory components were missing or certify a future
creation attempt. Fresh metadata inspection is required before authorization.

## Scope and security

The exact destination comes from the shared Step 208/214 resolver:

    <verified operator profile>\AppData\Local\LankaPex\PrivateDemoQr

The current authenticated operator SID and its HKLM registered profile are used.
Inherited LOCALAPPDATA/USERPROFILE values and caller-selected paths are not used.
The registered profile may be operator- or SYSTEM-owned; PrivateDemoQr MUST be
owned by the actual operator. No Windows profile ownership/permissions change.

The shared validator adds a separate DirectoryPlan mode. Existing Prepare,
Create and Read modes retain their prior behavior. DirectoryPlan validates and
pins all existing ancestors, returns the exact missing path components, and
rejects an existing final directory even if its current ACL is secure. It does
not examine secret contents and does not create anything. Metadata errors,
reparse points, unknown ownership, dangerous DELETE/DELETE_CHILD or other
untrusted mutation rights still STOP. If the existing LankaPex application parent
is present, creation planning additionally requires its operator ownership and
protected operator/SYSTEM-only ACL. Do not adopt a broadly writable/shared parent
or change its permissions automatically. A failed stricter parent check requires
separate review; Step 215's ordinary ancestor check does not override it.

Only two creation plans are permitted:

- PrivateDemoQr missing, with an existing approved LankaPex parent.
- Both LankaPex and PrivateDemoQr missing.

Missing profile, AppData or Local is an unsupported prerequisite, not permission
to recreate OS directories. Preflight reports the known component labels only;
actual paths, usernames, SIDs and raw ACL data are never printed.

Immediately before EACH create, rerun the shared ancestor/ownership/DACL checks
and verify exact operator, profile, destination and remaining missing components
against the initial confirmed plan. Retain all ancestor handles and pin each
new directory immediately after creation. No automatic retry or adoption of a
racing directory. Handle pinning mitigates ordinary rename/replacement races;
trusted privileged actors can still change ACLs and native behavior needs
operator-side validation. This is not a claim of complete Windows Authz analysis
or elimination of all TOCTOU races. Use a trusted operator/session/source tree.

Creation uses CreateDirectoryW with a supplied SECURITY_ATTRIBUTES descriptor,
operator owner and a protected DACL containing ONLY operator and SYSTEM Full
Control. No SACL is supplied. No existing object has its owner or DACL changed.
The descriptor is present at creation, avoiding a permissive-inheritance window.
Unlike Directory.CreateDirectory/New-Item convenience APIs, existing-directory
success is NOT accepted: a native already-exists result stops the procedure.
Each new directory, including any new LankaPex parent, is then checked using the
shared strict private-node policy. A final shared Create-mode validation verifies
the complete storage path and requires that the credential file is still absent.
No credential file, backup, ownership manifest or evidence file is created.

## Future commands: do not run without separate authorization

From the project root, offline/default preparation (no metadata access):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\prepare_demo_qr_credential_directory.ps1
```

Expected:

```text
PASS: offline QR directory preparation only; no filesystem metadata or credentials accessed
```

Separately authorized metadata-only creation preflight:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\prepare_demo_qr_credential_directory.ps1 -PreflightOnly
```

Expected plan, if existing metadata passes, is ONE of:

```text
PASS: QR storage directory plan missing_components=PrivateDemoQr; no directories or credentials created
PASS: QR storage directory plan missing_components=LankaPex,PrivateDemoQr; no directories or credentials created
```

Obtain explicit authorization for the exact reported components, directory
creation with owner/DACL supplied at creation, and post-creation metadata checks.
This authorization does not cover credentials, accounts, grants or migration.

If and only if preflight reports PrivateDemoQr alone:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\prepare_demo_qr_credential_directory.ps1 -Execute -ConfirmDirectoryCreation -ConfirmMissingComponents 'PrivateDemoQr'
```

If and only if preflight reports both components, use instead:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\prepare_demo_qr_credential_directory.ps1 -Execute -ConfirmDirectoryCreation -ConfirmMissingComponents 'LankaPex,PrivateDemoQr'
```

Both commands freshly revalidate and STOP if the missing-component plan changed.
Successful output:

```text
PASS: dedicated QR credential directories created and metadata verified; no credential or database operation performed
```

Future independent metadata-only verification, separately authorized:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\check_demo_qr_credential_storage.ps1 -Diagnostic
```

## STOP and partial recovery

STOP reports fixed stage/check labels and observed successful component count,
never exception text or private values. A create attempt followed by an error
can leave uncertain state even if the observed count is zero. No rollback,
delete, permission repair, recreation or retry is automated. Preserve any new
directory as-is and retain the sanitized operator output. Do not rerun Execute
to infer whether the first attempt succeeded; an existing target is rejected.

Separately authorize metadata-only inspection of exact planned directories,
owners, ACLs, reparse and ancestor state to determine what exists. A partial
LankaPex-only result needs explicit review and fresh authorization before a new
PrivateDemoQr-only attempt. A fully existing target must be verified independently,
not adopted by rerunning directory creation. Incorrect owner/ACL means STOP; do
not adjust it automatically. Any repair or exact-directory cleanup needs its own
reviewed procedure and authorization. Never recursively delete or change profile
or existing application directories. No backup is needed to undo existing ACL
changes because this procedure performs none; future repairs must have their
own protected metadata-backup prerequisites.

The shared helper changed, so its source fingerprint changes. Earlier rehearsal
source maps cannot certify this version; do not rewrite old evidence. Fresh
source-matching rehearsal proof is required before migration. Directory approval
does not resolve MySQL logging safety or account-administration pause. Credential
creation, account provisioning, backup/rehearsal and migration remain separately
authorized future operations.
