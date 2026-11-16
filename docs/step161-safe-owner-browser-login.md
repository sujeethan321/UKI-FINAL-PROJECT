# Step 161 — Fill-only isolated Owner login

Preparation only; no real credential or browser has been accessed.
The confirmed credential/hash match makes input/focus/layout errors or the wrong
browser API target plausible explanations for the previous failure; its cause is
still unproven. Existing CDP scripts inject tokens and target other fixtures, so
they must not be run for this workflow.

The new helper fills the normal React fields with native setters and input events,
without OS focus or keyboard interpretation. It verifies the exact login URL,
one matching tab, a masked enabled password field in the same form as the email,
and the loaded Vite Axios module's exact isolated API base URL. It never submits,
reads tokens, writes session storage, or calls authentication directly.

No-connection preparation from the project root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\fill_tamil_ai_owner_login.ps1
```

Expected: `PASS: fill-only preparation; no credential read or browser connection`.

Future steps require separate authorization for a new dedicated Chrome process/profile,
credential decryption and DOM fill, and one manual normal login. Do not stop/restart
existing servers or Chrome. Use a unique absent profile directory; never attach to
personal Chrome or expose its debugger to LAN. After authorization, in PowerShell:

```powershell
$chrome = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
$profile = Join-Path $env:TEMP ('LankaPex-Tamil-Login-' + [guid]::NewGuid().ToString('N'))
if (-not (Test-Path -LiteralPath $chrome -PathType Leaf)) { throw 'STOP: Chrome executable missing.' }
if (Test-Path -LiteralPath $profile) { throw 'STOP: profile already exists.' }
if (Get-NetTCPConnection -LocalPort 9238 -State Listen -ErrorAction SilentlyContinue) { throw 'STOP: debugger port occupied.' }
Start-Process -FilePath $chrome -ArgumentList @('--remote-debugging-address=127.0.0.1','--remote-debugging-port=9238',('--user-data-dir="' + $profile + '"'),'--no-first-run','--no-default-browser-check','http://127.0.0.1:5175/login')
```

This visible interactive window is intentional. Do not add extensions, enable password
saving, open DevTools recording, or navigate to other sites in it. Confirm the debugger
listener is loopback-only using `Get-NetTCPConnection -LocalPort 9238 -State Listen`;
stop if it binds a wildcard or LAN address. Keep exactly one matching login tab.

Then, under the Windows account that owns the existing DPAPI file:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\fill_tamil_ai_owner_login.ps1 -Execute -ConfirmRunId 14405b71b0504036a35ff55c7a9da132
```

Expected: `PASS: exact isolated Owner login form filled; no login submitted`.
The only secret transfer is CurrentUser DPAPI → operator-process memory → anonymous
child stdin → loopback CDP → masked browser field. Nothing is copied to clipboard,
printed, saved as plaintext, or placed in command-line arguments. No JWT, database
credentials, or database connection is needed. Existing Owner ACL checks remain strict.

Inspect the email and masked password field without revealing the password. Click
Log In once manually. The existing React flow sends URL-encoded username/password to
`http://127.0.0.1:8014/api/v1/auth/login`, then calls `/auth/me`. The normal authentication
context manages the resulting session. Do not export Network payloads/HARs. On failure,
stop, record only URL/status/error category, and do not automatically fill or submit again.
If it succeeds, navigate to Customers and follow the existing Tamil summary runbook.

Limitations: debugging access can control this test browser, so use a trusted local PC
and close this dedicated Chrome window after testing. Browser password-saving and
page scripts can access entered credentials; do not enable recording or untrusted
extensions. Managed memory cannot be guaranteed erased. DOM readback proves field
values; only the later normal login verifies React/authentication end to end. API
base validation reflects the current trusted local source; it is not a network firewall.
No helper retries, profile deletion, server startup, or cleanup are performed.
