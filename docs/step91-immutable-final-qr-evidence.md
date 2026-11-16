# Step 91 — Immutable final QR test evidence preparation

Status: **source tooling prepared; no live reconciliation or evidence file creation executed**.

The existing strict reconciliation and immutable reservation remain unchanged. Final evidence uses the separately reviewed membership-authoritative reconciliation and is pinned to run `6d2a5a8c093c48509bbc2878ae50ded3` and its verified primary IDs. A differing ID, relationship, count, discrepancy flag, Admin audit, financial zero-state, database identity, revision or grant stops preservation.

## Evidence design

The private destination is:

```text
.server-logs/private-test/qr-browser-fixture-final-evidence-6d2a5a8c093c48509bbc2878ae50ded3.json
```

The PowerShell wrapper first completes a read-only preflight before creating any path. A separately confirmed preservation run repeats the complete `ReconcileFinalByMembership` operation immediately before writing. It reserves the destination with `CreateNew`, applies a Windows-current-user-only ACL, and refuses an existing path. Failure preserves a partial file for diagnosis and never retries or overwrites it.

The JSON records:

- format version, evidence type, final state and UTC timestamp;
- exact test database/account/revision and fixture run ID;
- verified Admin, Owner, Customer, business, membership, approval, notification, request and both profile IDs;
- verified foreign-key relationship labels;
- membership-authoritative ownership and both business-identifier mismatch booleans;
- explicit `historical_snapshots: not captured; not fabricated`;
- explicit unlinked-profile ambiguity and zero dependents;
- financial, order, delivery and unrelated-record zero state;
- SHA-256 of the unchanged reservation manifest bytes;
- SHA-256 of the canonical evidence payload, excluding only the fingerprint field itself;
- a SHA-256 fingerprint of the QR public code, never the raw code.

It stores no names, registration values, emails, passwords, password hashes, credentials, access tokens or raw QR code. After writing, the Python process rereads the evidence, recomputes the payload fingerprint, and revalidates every pinned field.

## Future commands

Keep browser writers quiescent. Run under the Windows account that owns the private DPAPI files.

Read-only preflight, which creates no file:

```powershell
Set-Location C:\Users\admin\Desktop\LankaPex
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\manage_qr_browser_fixture.ps1 -Mode FinalEvidencePreflight -RunId 6d2a5a8c093c48509bbc2878ae50ded3
```

Only after separate explicit authorization, perform the one-time private-file write:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\manage_qr_browser_fixture.ps1 -Mode PreserveFinalEvidence -RunId 6d2a5a8c093c48509bbc2878ae50ded3 -Execute -ConfirmTarget lankapex_test_db -ConfirmAdminId 124671 -ConfirmWriterPause
```

Neither command modifies MySQL. The execution command only creates the exact private evidence file. Cleanup, manifest changes and historical snapshot generation remain unavailable and unauthorized.
