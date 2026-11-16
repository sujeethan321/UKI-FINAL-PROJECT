# Step 70 — Read-only reconciliation of the QR test Admin

Status: **prepared; not executed**. Preserve the writer/DDL pause, both attempts' private files and the pending recovery manifest. Codex has not connected to MySQL or decrypted either DPAPI credential.

The recovery runner calls `bootstrap.main` with new private paths. Before commit, the bootstrap writes `pending_commit` with the new user and audit IDs. After `connection.commit()`, it performs a Core `Connection.execute(select(User))`, takes `scalar_one_or_none()`, and then accesses `verified.platform_role`. Core execution returns the first selected column (the numeric user ID) as the scalar, not an ORM `User` object. That attribute access is a source-confirmed post-commit defect and explains the generic STOP with one committed Admin and a still-pending manifest. The original exception was suppressed, so this precise historical exception is strongly supported but cannot be proved from the retained log.

Other post-commit failure points include the verification SELECT, counting all application tables, writing the `committed` manifest, and releasing the named lock. The manifest cannot be marked committed merely from its current `pending_commit` value. A failed password check must stop; never reset the password automatically.

From `C:\Users\admin\Desktop\LankaPex`, run the following **read-only** command under the Windows account that owns the QR test DPAPI files:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\reconcile_qr_test_admin.ps1
```

The wrapper privately decrypts the test runtime, JWT and recovery Admin credentials into the process environment, invokes the existing QR test runtime preflight, and then runs a consistent read-only transaction. It checks the exact `lankapex_test_db` identity, `lankapex_qr_test_runtime@localhost` account, revision `7b9e4d2c8a15`, 29 tables and DML-only grant. It requires the original manifest to remain `reserved` with no IDs and the recovery manifest to be `pending_commit` for user ID `124671` with a positive audit ID. It verifies the one active Admin's exact ID and synthetic email against the recovery manifest; the audit's exact ID, actor, target, action and state; one User and one audit row with zero rows in every other application table; and the privately decrypted password against the stored hash. It prints only PASS or sanitized STOP, never the email, password, hash, run ID, JWT or financial data.

The database does not store the private run ID. The strongest available attempt linkage is the manifest's distinct run ID and synthetic email, the exact User email, exact audit IDs and the password-hash verification. A PASS establishes those matches; it does not prove a cryptographic database-to-manifest run-ID link.

If and only if reconciliation passes, a **separate explicitly authorized** follow-up may change only the recovery manifest state from `pending_commit` to `committed` after rechecking its exact target, IDs, account, file ownership and no intervening database changes. Preserve the original failed-attempt files and recovery credential; do not rerun bootstrap or recovery. Any STOP leaves the manifest untouched and the fixture blocked for browser testing pending operator review.
