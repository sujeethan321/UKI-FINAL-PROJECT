# Step 210: Sanitized QR storage metadata diagnosis

Source and offline tests only. No real storage diagnostic, registry/profile
inspection, credential read, ACL correction, directory creation or database
operation was executed. Provisioning remains blocked.

## Confirmed findings

The checker previously mapped every exception other than the exact fixed
storage_preparation_required message to metadata_unverified. Open-DemoQrStorageNode
also replaces exceptions after opening a handle with metadata_unavailable.
Consequently the observed single-line STOP cannot identify the underlying check.
This is a confirmed diagnostic limitation, not proof of an incorrect ACL policy
or of the operator's actual failing condition. No security-acceptance rule is
changed here. No NTFS/PowerShell compatibility defect causing this actual failure
has been established.

## Check order and complete failure branches

1. Helper loading: file access, parse/runtime errors or execution restrictions.
2. Operator identity: WindowsIdentity failures; SYSTEM or unauthenticated token.
3. Registered profile: HKLM ProfileList access failure, missing SID subkey,
   missing/invalid ProfileImagePath, unexpected value type, disposal/API errors.
4. Path construction: non-user SID shape, nonabsolute/local drive path, percent
   expansion, noncanonical path, alternate-stream colon, path API failure.
   LOCALAPPDATA is not consulted.
5. Destination and enumeration: wrong destination, collection/path API failure.
6. Ancestors, root first: Test-Path metadata/provider errors, native Add-Type or
   P/Invoke errors, CreateFileW failure (including access denied/sharing conflict).
   Missing components are noted but do not immediately bypass existing checks.
7. Handle identity: final-path API failure/oversized result, unexpected prefix
   or mismatch, string/API errors. Handles forbid delete sharing; other opens
   may conflict. This is fail-closed, not an automatic retry condition.
8. Item/DACL metadata: Get-Item/Get-Acl failure, noncanonical ACL, ACE SID or
   rights conversion errors, owner SID errors. The native helper catch masks
   these as metadata_unavailable, but diagnostic stage now distinguishes them.
9. Directory type and profile owner: non-directory ancestor or operator profile
   not owned by the resolved operator SID or, from Step 214, Windows LocalSystem.
   Administrators and unknown/unavailable owners remain rejected here. This
   narrow profile exception does not change private directory/file ownership.
10. Node policy: unverified metadata/reparse point; empty/null DACL; untrusted
    ancestor owner; missing ACE SID or unsupported type; rights conversion error;
    applicable untrusted allow with DELETE, DELETE_CHILD, WRITE_DAC, WRITE_OWNER,
    WRITE_ATTRIBUTES or WRITE_EA. Generic rights are expanded. InheritOnly ACEs
    are excluded for the current object; inherited applicable rules are assessed.
    Denies are not used to cancel unsafe allows.
11. Private policy: wrong owner/unprotected inheritance; any inherited,
    InheritOnly, deny, unexpected principal or non-Full-Control rule; missing or
    duplicate operator/SYSTEM rules. Exactly two explicit rules are required.
12. After existing ancestors pass, missing directories produce the separate
    storage_preparation_required category. Otherwise credential existence is
    checked. Prepare allows absence; an existing credential is opened metadata-
    only and must be a regular file with the same strict owner/DACL checks.
    Read/Create modes also reject missing/existing credentials respectively.

Unrecognized managed/native/runtime exceptions in these stages still fail
closed. A cleanup exception can also terminate a script; it is not evidence
that storage passed. No secret content is read by any metadata mode.

## Prepared diagnostic

The existing checker now accepts -Diagnostic. A trace dictionary records only
fixed stage labels, a role label or ancestor index, and an allowlisted native
failure category. The output formatter allowlists all fields and fixed check
labels; arbitrary exception messages, paths, identities, SIDs, ACL records and
provider output are never emitted. Only CreateFileW failure captures its native
error category; later API failures are identified by stage without implying
that the native error category is known.

Future operator command, requiring separate authorization; NOT run here:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\check_demo_qr_credential_storage.ps1 -Diagnostic
```

Example only, not an observation of this machine:

```text
STOP: QR credential storage category=metadata_unverified
STOP: QR storage diagnostic stage=native_handle_open surface=ancestor_0 check=metadata_handle native_error=sharing_violation
```

Other useful combinations include profile_registry_open/runtime error,
dacl_read/metadata_unavailable, profile_owner/operator_profile_owner, and
ancestor_acl_policy/ancestor_mutation_or_delete. The latter identifies a policy
failure but intentionally does not disclose the principal or access rule.

## Hypotheses and correction boundary

No specific stage can be ranked confidently from the original output. Native
root/ancestor opens, registry/profile access and conservative ACL rejection are
plausible. Earlier profile metadata limitations do not prove which happened in
the operator's run. Ordinary Windows profile ACLs may be rejected if ownership,
deny/allow interactions or group grants differ from this conservative policy.
Access denied or sharing conflicts can arise even when the ACL would otherwise
be acceptable. Add-Type may be restricted by the execution context. None is a
confirmed local cause without the new sanitized diagnostic output.

PowerShell 5.1 supports the registry, FileSecurity, Add-Type and SafeFileHandle
APIs used here, but syntax/offline mocks do not prove native access works under
the operator token. Do not weaken sharing, accept an unknown owner, skip an
ancestor, remove ACL checks, or change filesystem permissions to force PASS.
The smallest current correction is visibility only: preserve all gates and add
stage tracing. A functional/API or ACL correction needs separate source review
after the actual failing stage is known.

Trace tests inject synthetic profile, existence and node providers and use
in-memory handles. They do not invoke native opens or query actual ACLs. The
existing policy tests are retained. No claim of complete Windows Authz effective
access or elimination of TOCTOU races is made. Privileged/trusted writers remain
outside this protection boundary.

The shared helper is migration-source-fingerprinted. These diagnostic-only
changes alter its hash, invalidating any rehearsal proof for earlier source
bytes; never rewrite historical evidence. Future directory/ACL preparation,
credential creation, database logging inspection and provisioning still require
their own authorizations. This diagnostic authorizes none of them.
