# Step 55 — Guarded QR browser test Admin bootstrap

Status: **prepared, not executed**. The previous operator inventory found an empty `lankapex_test_db` at `7b9e4d2c8a15`. The bootstrap requires a fresh check; that earlier inventory alone does not authorize a write. No Admin account or credential was created while preparing these tools.

## Safety boundary

`backend/scripts/bootstrap_qr_test_admin.ps1` uses only the existing `.server-logs/private-test/qr-test-runtime.dpapi` credential under the Windows account that encrypted it. It sets a process-only testing environment with `MYSQL_DATABASE=lankapex_test_db` and `MYSQL_USER=lankapex_qr_test_runtime`, invokes the existing exact-target runtime preflight, then verifies all 28 modeled application tables contain zero rows. The Python gate also checks the actual database and MySQL account, revision, all 29 tables and exact escaped database-scoped DML grants. An existing Admin, any other application row, an existing bootstrap credential/manifest, an unexpected database, or a failed check stops execution.

The execution mode additionally requires `-Execute -ConfirmTarget lankapex_test_db -ConfirmWriterPause`. The operator must first establish and maintain a pause of pytest, browser servers, clients and other writers/DDL against the test database. The switch is an operator attestation, not proof of a pause. The Python process rechecks the database and zero-row state immediately before writing and takes a named lock to serialize another copy of this bootstrap. It creates one active `admin` User and one Admin audit using the existing production-compatible provisioning and password-hashing service in one database transaction. It creates no business, credit, order or delivery records.

Execution generates an unpredictable synthetic email identifier and a 48-byte random password. The password is stored with Windows CurrentUser DPAPI in `.server-logs/private-test/qr-browser-admin-password.dpapi`; it is passed to Python only through the child process environment. The private ownership manifest is `.server-logs/private-test/qr-browser-admin-fixture.json` and records the exact database, run ID, synthetic email, new `user_id`, and audit ID. Both files are created exclusively with an ACL for the Windows operator account. The password, hash, JWT signing key and tokens are never printed. These files are ignored by Git. Keep them with the operator's private evidence; do not upload or commit them.

The manifest is marked `pending_commit` before commit and `committed` only after post-commit verification. If execution stops after either private file is created, preserve both files and the database state. Do not delete the files or retry automatically: MySQL commit outcome may require operator diagnosis. The wrapper refuses a second execution while either file exists. This is test-only tooling; it does not promote an existing user or bypass the normal Admin role check.

## Future operator commands (separate write authorization required)

Run from `C:\Users\admin\Desktop\LankaPex` in PowerShell under the Windows account that can decrypt the QR test runtime credential. The first command is read-only and creates no credential or application row:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\bootstrap_qr_test_admin.ps1
```

Expected: the existing QR runtime identity PASS, the empty Admin bootstrap preflight PASS, and `READ-ONLY ADMIN BOOTSTRAP PREFLIGHT COMPLETE; no account created`. Any STOP blocks execution. After separate authorization, verify the writer/DDL pause remains in place, then run once:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\bootstrap_qr_test_admin.ps1 -Execute -ConfirmTarget lankapex_test_db -ConfirmWriterPause
```

The execution command repeats both preflights before generating the credential and rechecks them immediately before the transaction. A successful result reports only the new synthetic Admin user ID and the private fixture location. Keep the account password private; the operator can retrieve it from the DPAPI file only under the creating Windows identity, without posting it to logs or chat.

## Fixture ownership and cleanup

Record all later browser fixture IDs in a separate private manifest. Treat every pre-existing record as protected. Before any future cleanup, verify exact test target/account and match the `user_id`, audit ID, synthetic email and run ID to this manifest; remove dependent browser fixture records in foreign-key order using exact IDs only, then the Admin audit by exact audit ID and the synthetic Admin by exact user ID. Confirm no financial records were created. Cleanup requires separate review and authorization. Never use broad `DELETE`, `TRUNCATE`, `DROP`, reset, or migration commands here.

Remaining gates: fresh operator-run preflight, sustained writer/DDL pause, separate explicit authorization for the single Admin write, and private handling of the fixture credential. No browser server should start until those gates pass.
