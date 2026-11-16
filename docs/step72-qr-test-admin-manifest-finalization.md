# Step 72 — Guarded QR test Admin manifest finalization

Status: **prepared; not executed**. The operator's read-only reconciliation reported one active Admin (`user_id=124671`), its exact audit, a usable private credential and zero rows in every other application table. The recovery manifest remains `pending_commit`. Keep the writer/DDL pause in place and preserve the original failed bootstrap manifest and credential.

The dedicated finalizer accepts only the recovery manifest, and changes only its `state` from `pending_commit` to `committed`. Default mode is read-only. The Windows wrapper loads the existing test runtime, JWT and recovery Admin DPAPI credentials privately, runs the existing exact-target preflight, and invokes the read-only reconciler. The Python finalizer repeats reconciliation in its own process immediately before any file write. That check enforces the actual `lankapex_test_db` identity, `lankapex_qr_test_runtime@localhost`, revision `7b9e4d2c8a15`, 29-table inventory, exact restricted grant, Admin role/status, exact user/audit IDs, matching synthetic email, password-hash verification, and zero dependent application rows. A missing, modified or already committed manifest stops it. No SQL write occurs.

Execution requires the exact target, `user_id=124671` and an operator-confirmed maintained writer/DDL pause. After the first reconciliation, the wrapper creates two distinct zero-length files with `CreateNew` and Windows-current-user-only ACLs: `.server-logs/private-test/qr-browser-admin-recovery-fixture.pending-commit.backup.json` and `.server-logs/private-test/qr-browser-admin-recovery-fixture.replacement.tmp`. The Python process repeats reconciliation, copies the exact pending bytes into the backup and fsyncs it, writes a replacement JSON changing only `state`, fsyncs it, verifies the source has not changed, and atomically replaces the manifest in the same directory. The replacement inherits the restricted temporary file's ACL. It does not touch the failed attempt's files, recovery DPAPI credential or any database row. Private values and full manifest contents are never printed.

Run from `C:\Users\admin\Desktop\LankaPex` under the Windows account that owns the DPAPI files. This command is read-only:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\finalize_qr_test_admin_manifest.ps1
```

Expected: exact runtime preflight PASS, read-only reconciliation PASS, `PASS: finalization preflight only; manifest remains pending`, and `READ-ONLY FINALIZATION PREFLIGHT COMPLETE; no file or database changed`. Any STOP blocks execution.

Only after separate explicit authorization and confirmation that the writer/DDL pause remains in force, the one-time execution command is:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\finalize_qr_test_admin_manifest.ps1 -Execute -ConfirmTarget lankapex_test_db -ConfirmAdminId 124671 -ConfirmWriterPause
```

If file preparation fails, the manifest remains pending; preserve any new empty files for review. If backup or replacement writing fails, preserve the pending manifest, backup and temporary file. If the atomic replacement fails, the pending manifest and exact-byte backup remain; do not retry automatically. If an error occurs after replacement, inspect only the manifest's state and compare its non-secret fields with the private backup under the Windows operator account; then rerun read-only database reconciliation through a procedure that accepts the committed state after separate review. Never delete, overwrite or reset evidence to make a retry possible without authorization. Keep all files outside Git and do not release the writer/DDL pause until the operator has verified the final state.

Remaining risk: database reconciliation and filesystem replacement are separate operations. The maintained writer/DDL pause and repeated exact-target checks limit the gap, but they cannot form a single transaction across MySQL and NTFS. No live database or private file was accessed during preparation.
