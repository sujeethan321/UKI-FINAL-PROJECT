# Step 154 — Synthetic Owner credential comparison

Source preparation only. No live comparison has been executed.

Run from the project root under the Windows account owning the existing CurrentUser DPAPI files.
Default preparation performs no private-file reads, decryption, database access, or authentication request:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\verify_tamil_ai_owner_credential.ps1 -RunId 14405b71b0504036a35ff55c7a9da132
```

After separate authorization for credential decryption and read-only database access:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\verify_tamil_ai_owner_credential.ps1 -Execute -RunId 14405b71b0504036a35ff55c7a9da132 -ConfirmTarget lankapex_ai_snapshot_test_db
```

Existing protected files required under `.server-logs/private-ai-tests/`:
`ai-snapshot-test-runtime.dpapi`, `tamil-ai-browser-jwt.dpapi`, and this run's
`tamil-ai-browser-fixture-<RunId>-owner.dpapi`, reservation `.json`, and `-created.json`.
Only the exact legacy `ai-snapshot-test-runtime.dpapi` path accepts protected
operator-only Full Control, with optional SYSTEM Full Control. This is compatible
with CurrentUser DPAPI and grants no new access. All other files still require
explicit operator and SYSTEM Full Control. Inherited rules, unexpected principals,
deny rules, or missing operator Full Control always stop verification. The legacy
file must be a regular file rather than a reparse point. No ACL mutation is needed.
No files or ACLs are created or repaired. The existing JWT is used only for the unchanged
isolated configuration gate; no token or login request is generated.

Execution removes the process Groq key, disables dotenv and AI using the reviewed browser
context, checks configured identity, and starts one consistent read-only transaction.
Existing fixture checks enforce actual database/account, revision, all 29 tables, exact
grants, complete fixture inventory, ownership, evidence fingerprint and LKR 70.10 balance.
The exact evidence Owner ID, derived email, active state and role are checked before the
production password verifier compares the protected credential. The transaction is rolled
back and environment restored in finally blocks; temporary secure buffers are disposed.

Success prints only `PASS: reserved Owner credential matches committed fixture`.
STOP categories include confirmation, evidence, owner_identity, credential_mismatch,
and evidence_or_infrastructure. No exception detail or secret is printed. A mismatch
does not authorize reset, fixture recreation, cleanup, or retry. Unexpected infrastructure
errors remain deliberately generic. Close unused shells after execution; process memory
necessarily holds decrypted values briefly, and managed-string erasure cannot be guaranteed.
