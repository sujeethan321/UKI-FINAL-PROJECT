# Step 46 — guarded local-PC QR browser test preparation

Status: **source tooling prepared; live browser test blocked pending separate authorization and fixture review**. No MySQL connection, server, test account, seed, migration, or browser test was run in this step.

## Launchers and gates

- `backend/scripts/start_qr_browser_backend.ps1` accepts `-PreflightOnly`. It reads the existing `.server-logs/private-test/qr-test-runtime.dpapi` and a **separate** `.server-logs/private-test/qr-browser-jwt.dpapi`, both using the creating Windows account's DPAPI CurrentUser key. It sets process-only `APP_ENV=testing`, exact `lankapex_test_db` and `lankapex_qr_test_runtime`, loopback CORS `http://127.0.0.1:5174`, `APP_DEBUG=false`, and warning-level logging. It first runs the database-free browser configuration gate and then the existing read-only `check_qr_test_runtime.py` gate. The latter requires actual `SELECT DATABASE()`, `CURRENT_USER()`, revision `7b9e4d2c8a15`, 29 tables, and only escaped exact-test-database SELECT/INSERT/UPDATE/DELETE grants plus global USAGE. A failed gate prevents Uvicorn from starting. The API binds only `127.0.0.1:8013`, with access logs disabled. No migration or seeding is built in.
- All critical database settings and the JWT secret come from explicit process variables, and the configuration gate checks that effective settings match them; a `backend/.env` demo/development database, account, or JWT secret cannot silently replace them. Other optional backend settings may still come from `backend/.env`; review it privately for unexpected test behavior before a live run. The normal `.env` file is neither edited nor printed.
- `frontend/scripts/start_qr_browser_frontend.ps1` uses process-only `VITE_API_URL=http://127.0.0.1:8013/api/v1`, rejects other inherited `VITE_` variables, binds Vite only to `127.0.0.1:5174`, and restores the prior API URL on exit. Vite's existing public-environment validator rejects unreviewed `VITE_` file entries. No credential enters Vite variables. This launcher does not call either demo launcher.
- Launchers stay in the foreground. Stop each with Ctrl+C in its own terminal. They do not stop other processes, clean data, or adjust grants.

## Private JWT prerequisite (future operator action)

Under the same Windows operator account that owns the test runtime DPAPI credential, create a new random JWT secret in the existing private directory. The path must be absent; never overwrite it. Do not print the secret or DPAPI file. Review directory ACLs first and restrict the new file to the operator account. This is a **separate setup action**, not performed by Step 46.

```powershell
Set-Location C:\Users\admin\Desktop\LankaPex
$path = '.server-logs\private-test\qr-browser-jwt.dpapi'
if (Test-Path -LiteralPath $path) { throw 'STOP: test JWT credential already exists' }
$bytes = New-Object byte[] 48
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
$plain = [Convert]::ToBase64String($bytes)
try {
    $secure = ConvertTo-SecureString $plain -AsPlainText -Force
    try { $secure | ConvertFrom-SecureString | Set-Content -LiteralPath $path -Encoding ASCII -NoNewline }
    finally { $secure.Dispose() }
} finally { $plain = $null; [Array]::Clear($bytes, 0, $bytes.Length) }
```

The command uses DPAPI CurrentUser. Confirm `.server-logs` is excluded from Git and enforce private NTFS ACLs before entering any real test credentials. A different Windows user cannot decrypt the file.

## Future commands — require separate authorization

Run these in separate PowerShell terminals under the operator account. The first command reads the test database; it does not start a server. **Do not run it during source-only preparation.**

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\start_qr_browser_backend.ps1 -PreflightOnly
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\frontend\scripts\start_qr_browser_frontend.ps1 -PreflightOnly
```

Only after both gates pass and a fixture plan is approved, start the local-PC API and frontend separately:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\start_qr_browser_backend.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\frontend\scripts\start_qr_browser_frontend.ps1
```

The URL is `http://127.0.0.1:5174`; the API is `http://127.0.0.1:8013/api/v1`. Confirm the API gate's PASS line immediately before startup. Do not run concurrent pytest suites or other browser fixtures while committed browser records exist.

## Synthetic fixture ownership and exact cleanup plan

There is **no automatic fixture creation or deletion** in these launchers. Before browser testing, review a separate test-only fixture utility or operator procedure. It must verify process environment, configured and actual database/account, revision, table inventory, and grants before **every write or cleanup**. It must create an unpredictable run ID and retain private evidence of exact primary keys and expected ownership in `.server-logs/private-test`. Refuse a second seed if an unresolved run exists. Never include passwords or tokens in the evidence or logs.

Preferred real-API sequence: privately provision or designate an authorized synthetic test Administrator; register a unique synthetic Shop Owner via `POST /api/v1/auth/register/shop-owner`; register a unique synthetic Customer via `POST /api/v1/auth/register/customer`; authenticate via `POST /api/v1/auth/login` and verify `/api/v1/auth/me`; create one pending business via `POST /api/v1/shop-owner/businesses`; approve it through the authorized `PATCH /api/v1/admin/businesses/{business_id}/decision` route. The existing `provision_admin.py --demo-only` guard targets `lankapex_demo_db` and **must not** be used for this test. Whether a suitable synthetic test Admin already exists is unknown until a later authorized read-only database check. A separate guarded test-only Admin bootstrap or explicit test fixture is needed if none exists; never promote a normal account or insert an unverified password hash.

With the approved business, the owner issues `POST /api/v1/shop-owner/businesses/{business_id}/join-link`; a public scan opens `/join/{public_code}`. Verify unauthenticated preview, Customer login/registration return, explicit request, owner approval, Customer My Shops and restored `approved` status on repeat scan. Also check `none` before submission and `pending` afterward. Compare exact fixture-owned counts before and after: **zero new credit accounts, ledger entries, repayments, orders and deliveries**. The QR never carries internal IDs, credentials, or financial data.

For cleanup, stop the browser API and frontend and ensure no test requests are in flight. Revalidate the exact test target and load the private run-ID/primary-key manifest. Check that each row still matches the synthetic run and has no non-fixture dependents. Delete only recorded IDs, in dependency order: fixture-created notifications, join requests, linked customer profiles, join link, business approval audit, business membership, business, then fixture-created Customer and Owner users. If a fixture-created Admin is to be removed, first review and delete only its recorded approval/admin audit and notification dependents, then that Admin. Any unexpected credit, ledger, order, delivery, invitation, communication, or other dependent row **stops cleanup** for operator review. Do not use broad DELETE, TRUNCATE, DROP, database reset, or foreign-key disabling. Preserve evidence on failed cleanup. Existing test Admin and all pre-existing records are never fixture-owned and must remain untouched.

The test runtime account's DML-only grant is sufficient for the listed application inserts, updates and exact-ID deletes; it cannot migrate, create tables, or grant privileges. An Admin actor still requires an existing active `admin` user and the normal authorized route. The present QR pytest concurrency fixture commits unique IDs and deletes them itself, but its cleanup is not a substitute for browser fixture ownership. Complete that fixture utility and independently inspect current test records before authorizing browser writes.

## Later phone test (not enabled)

The present launchers are **loopback-only**. A phone cannot reach `127.0.0.1` on the PC. Later mobile testing needs a separately reviewed phone-reachable trusted frontend and API origin, matching exact CORS allowlist, firewall rules limited to the test device/network, and an HTTPS certificate trusted by that phone. The frontend QR URL comes from `window.location.origin`, so opening a local-PC QR on a phone would point back to the phone itself. Do not change `--host` to `0.0.0.0`, open firewall ports, or use a public tunnel under this step.

## Remaining gates

1. Operator creates and privately protects the separate test JWT secret.
2. Review current test database state and whether a synthetic test Admin exists; no such check was run in Step 46.
3. Build/review exact-ID fixture setup and cleanup, including audit/notification dependencies and financial zero-state checks.
4. Obtain separate approval for the read-only live preflight, server startup, and test-database writes.
5. Complete real-database integration tests of the new `by-code` status route before or alongside controlled local-PC browser validation.
