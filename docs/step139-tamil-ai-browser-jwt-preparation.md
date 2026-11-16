# Step 139 — Test-only Tamil AI browser JWT preparation

Status: **PASS for source and offline safety; BLOCKED for credential creation pending separate operator authorization.** The preparation did not create, read, or modify any credential or private evidence.

The backend launcher requires `.server-logs/private-ai-tests/tamil-ai-browser-jwt.dpapi`. The dedicated creator pins the AI snapshot database context and fixture RunId, generates 48 cryptographically random bytes (64 Base64 characters), protects the secret with Windows CurrentUser DPAPI, writes ciphertext through exclusive `CreateNew`, and applies the reviewed DACL-only SID grants through `tamil_ai_private_acl.ps1`. It never changes `backend/.env` or another JWT configuration.

Default mode is read-only:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\create_tamil_ai_browser_jwt.ps1
```

With the file currently absent, expected output is:

```text
PASS: test-only browser JWT credential is absent and creation prerequisites are ready; no file created
```

If the file exists, default mode validates its protected operator/SYSTEM-only DACL, CurrentUser decryptability, and minimum 48-character plaintext length without printing either plaintext or ciphertext.

The future one-time creation command requires separate filesystem authorization:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\create_tamil_ai_browser_jwt.ps1 -Execute -ConfirmTarget lankapex_ai_snapshot_test_db -ConfirmRunId 14405b71b0504036a35ff55c7a9da132 -ConfirmJwtCreation
```

The operation refuses an existing target and uses exclusive creation. A failure after creation preserves the file as evidence and returns nonzero; it never deletes or retries it. Successful completion occurs only after DPAPI decryption, length checking, and DACL readback pass.
