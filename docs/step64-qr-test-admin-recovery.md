# Step 64 — QR browser test Admin recovery preparation

Status: **source prepared; no recovery executed**. The failed attempt's `qr-browser-admin-fixture.json` and `qr-browser-admin-password.dpapi` remain protected evidence. The last operator inventory reported all 28 application tables empty at revision `7b9e4d2c8a15`; this must be verified again under the maintained writer/DDL pause.

The dedicated `recover_qr_test_admin.ps1` never writes the original files. Its default mode checks that both originals exist, the old manifest is `reserved` for the exact test target and account, its user/audit IDs are absent, and a new recovery attempt has not already been reserved. It runs the existing `check_qr_test_runtime.py` gate and the bootstrap's exact-target, 29-table, revision, grant and zero-row checks. Any unexpected application row, account, revision, manifest state, missing credential or conflicting fixture stops the operation.

For a future separately authorized execution, the wrapper first repeats those read-only checks. It then generates a fresh random run ID, synthetic email and 48-byte password, compares the password with the failed attempt's privately decrypted password, and reserves distinct files with `CreateNew` and a restricted Windows operator ACL. The new credential uses CurrentUser DPAPI; the new manifest uses UTF-8 without a BOM. The Python runner checks that the new identity differs from the failed one, then reuses the original bootstrap's writer-pause confirmation, named lock, second zero-row check, single transaction, Admin audit and post-commit verification. Neither path can create a business, credit account or financial record. If any private-file preparation or database stage fails, preserve all files and database state; no retry, cleanup or repair is automatic.

From `C:\Users\admin\Desktop\LankaPex`, under the Windows admin account that owns the DPAPI credentials, run only the read-only preflight until separate write authorization is granted:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\recover_qr_test_admin.ps1
```

Expected: exact QR test runtime PASS, exact empty Admin bootstrap preflight PASS, then `READ-ONLY QR ADMIN RECOVERY PREFLIGHT COMPLETE; no files or database records created`. A STOP blocks execution. The explicit one-time execution command for later separate authorization, with the writer/DDL pause maintained, is:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\recover_qr_test_admin.ps1 -Execute -ConfirmTarget lankapex_test_db -ConfirmWriterPause
```

This command creates new private files and writes one test Admin if every gate passes; **do not run it during preparation**. The new files are `.server-logs/private-test/qr-browser-admin-recovery-fixture.json` and `.server-logs/private-test/qr-browser-admin-recovery-password.dpapi`. They are outside Git. The original failed files must remain intact. Treat a `pending_commit` marker or STOP as uncertain until a separate read-only inventory confirms the exact Admin and audit rows. Do not use the normal bootstrap as a shortcut: its original fixed-file guard deliberately rejects a second execution.

Remaining risks: the pause switch is an operator assertion, so the operator must maintain the actual pause; MySQL commit and private-manifest write are not atomic with each other; a failure after either stage requires review before any further action. No live database or private credential was accessed while preparing this procedure.
