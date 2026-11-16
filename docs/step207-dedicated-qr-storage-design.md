# Steps 207–208: Dedicated QR credential storage foundation

Source-only implementation. No real storage creation, ACL/owner modification,
credential generation/read, private evidence access, MySQL, or migration was
performed. The proposed directory remains uncreated by these tools. Prior
metadata observations are not certification of present operator-side safety.

## Decision and path

Prefer dedicated storage over modifying the shared demo credential directory:

    <verified operator profile>\AppData\Local\LankaPex\PrivateDemoQr\demo-qr-migrator.dpapi

For the intended admin profile this is:

    C:\Users\admin\AppData\Local\LankaPex\PrivateDemoQr\demo-qr-migrator.dpapi

Resolve WindowsIdentity.User, require an authenticated non-SYSTEM domain/local
user SID, read only its registered ProfileList/ProfileImagePath from HKLM, and
require an absolute canonical local drive path with no variable expansion.
LOCALAPPDATA and USERPROFILE overrides are ignored. As of Step 214, only the
exact registered profile directory may be owned by either the actual operator
SID or Windows LocalSystem. This accommodates the operator-verified trusted
SYSTEM-owned profile without changing its filesystem permissions. Administrators,
unknown and unavailable owners remain rejected by this profile-specific rule.
All ancestor DACL, reparse, identity and deletion-right checks still apply.
PrivateDemoQr and the credential file still require exact operator ownership,
not SYSTEM ownership, and their strict protected operator/SYSTEM-only DACLs.
Run as the intended Windows admin: the tool
does not impersonate that account or accept another user's profile as input.
Registry/OS and the reviewed executable/source files remain trusted prerequisites.

## Shared policy and metadata-only command

demo_qr_credential_storage.ps1 contains functions only. Provisioning, migration
and check_demo_qr_private_path.ps1 share its resolver and validator. Prepare
checks existing storage without credential reads. Create additionally requires
credential absence. Read requires an existing validated regular credential file.
No mode creates a directory or reads secret contents.

Future operator-side metadata verification, separately authorized; NOT run here:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\check_demo_qr_credential_storage.ps1
```

Possible sanitized outputs:

```text
STOP: QR credential storage category=storage_preparation_required
STOP: QR credential storage category=metadata_unverified
PASS: dedicated QR credential storage metadata verified; no credentials read or files changed
```

Missing storage yields preparation-required only after existing ancestors have
passed. Unsafe/inaccessible existing ancestors yield metadata_unverified first.
PASS does not certify database logging, account absence, source-code trust, or
MySQL privileges. It can pass for a secure directory without a credential; it
does not imply that the credential exists or is decryptable.

## Ancestor and private-object rules

Open existing components root-to-leaf with READ_CONTROL/READ_ATTRIBUTES,
OPEN_EXISTING, OPEN_REPARSE_POINT and BACKUP_SEMANTICS; share read/write but not
delete. Keep these handles until the consumer finishes (a disposable lease).
Check the handle's final path, reject reparse points, non-directories, unresolved
metadata, noncanonical or empty/null DACLs, and untrusted owners. Check owner and
DACL while the component and its existing parents are pinned.

On ordinary ancestors, trust the operator, SYSTEM, built-in Administrators and
the exact Windows TrustedInstaller service SID. Read/traverse rules for other
identities can be acceptable. Applicable untrusted allow ACEs containing DELETE,
DELETE_CHILD, WRITE_DAC, WRITE_OWNER, WRITE_ATTRIBUTES or WRITE_EA are rejected.
Generic rights are expanded. For files also reject untrusted write/append.
Parent DELETE_CHILD and each object's DELETE are thus both checked. Creation
of unrelated siblings alone is not automatically classified as replacement.

PrivateDemoQr and the credential each require operator ownership, protected
inheritance and exactly two explicit applicable Full Control allow rules:
operator and SYSTEM. No other rules are accepted. Exclusive credential creation
with an explicit DACL remains in the provisioner; no existing file is overwritten.

This is a conservative upper-bound permission policy, NOT a complete Authz
effective-access calculation. Every untrusted user/group grant is treated as
potentially usable regardless of current token membership. InheritOnly ACEs do
not apply to the current object; inherited applicable ACEs do. Deny ACEs never
cancel unsafe allows for acceptance. Group interactions that might render an
allow ineffective can cause safe false rejections; STOP for review, never bypass.
It covers all possible untrusted group members without guessing memberships.
Trusted administrator/system/service identities and OS privileges are part of
the trust boundary. Backup/restore privileges, malicious administrators, kernel
actors and concurrent trusted DACL changes are not neutralized by these checks.

Handle pinning reduces ordinary rename/replacement races. It does not make all
path-string reads race-free, make content immutable, or prevent trusted writers
changing ACLs. Handle opens can fail because another process uses incompatible
sharing; STOP rather than retry or weaken sharing. Native opens and real Windows
effective-access behavior still need operator-side validation. The automated
tests use synthetic metadata and in-memory disposable handles, not live paths.

## Preparation, recovery and evidence boundaries

Step 216 adds a separately gated source-only directory-preparation tool; see
step216-secure-qr-directory-preparation.md. It has NOT been executed. Separately
review and authorize exclusive creation of any missing directory components, with private
DACLs supplied at creation and fresh validated ancestor leases. Refuse existing
unexpected components; never adopt a name merely because another actor created
it. Never recursively change profile, AppData, repository or existing demo ACLs.
Any existing-directory ACL change requires a verified protected owner/DACL
backup first. A backup destination must itself pass equivalent checks; no backup
is made here. Refuse overwrite and retain metadata for explicit reviewed rollback.

Credential creation, DBA logging inspection, account-administration pause,
account creation/grants and migration remain distinct authorization gates. Keep
the provisioner blocked until each applies. Preserve partial files/accounts on
STOP; no deletion, regeneration, password reset, relocation fallback or automatic
rollback. Never fall back to .server-logs/private-demo for the new QR credential.
Existing demo runtime/JWT files and launcher behavior remain untouched.

demo_qr_migration_guard.source_hashes now includes the shared helper. It already
incorporates the Step 214 owner-policy change through the helper's new hash.
Earlier rehearsal evidence cannot certify this source version and must not be
rewritten. Obtain fresh source-matching rehearsal evidence before migration. It
includes the changed migration wrapper and private-path checker. Any prior
rehearsal source map differs and must be rejected. Obtain fresh rehearsal proof
for the actual reviewed sources; never rewrite old evidence. Existing baseline
and backup evidence is not automatically discarded, but still needs independent
freshness/validity review. Repository-based migration evidence storage has not
been relocated or fully secured by this credential-only change.
