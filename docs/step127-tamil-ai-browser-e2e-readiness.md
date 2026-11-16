# Step 127 — Guarded Tamil AI browser E2E readiness

Status: **PASS for source and offline guard readiness; BLOCKED for every live phase pending separate operator authorization.** No database, server, browser, GroqCloud request, credential, or private evidence was accessed or changed while preparing this workflow.

## Architecture and fixture decision

The browser exercises the normal React → Uvicorn → request-scoped SQLAlchemy path. The existing MySQL integration fixture keeps one connection inside an outer rollback transaction; a separately running Uvicorn process cannot safely share that transaction, and concurrent browser requests would not exercise the production session lifecycle if forced through a global test connection. A true rollback-only browser test is therefore **not supported safely by the current architecture**.

Use one short-lived, exact-ID persistent fixture in the already dedicated, initially empty `lankapex_ai_snapshot_test_db`. The fixture contains two active synthetic users, one approved owner-linked business, one linked customer profile, one active credit account, a `LKR 100.20` credit sale, and a `LKR 30.10` repayment. The authoritative expected outstanding balance is `LKR 70.10`. All remaining application tables must be empty. Live AI stays disabled and `GROQ_API_KEY` is removed from the browser processes.

The phases are intentionally separate:

1. Read-only empty-schema preflight.
2. Private reservation and owner credential creation (filesystem mutation only).
3. Exact fixture creation with pending/committed evidence around the database commit.
4. Independent read-only fixture verification.
5. Backend and frontend preflights, then separately authorized loopback startup.
6. Manual browser assertions.
7. Read-only cleanup review.
8. Separately authorized exact-ID cleanup and empty-schema postflight.

Any failure after a pending evidence file exists makes commit state uncertain. Preserve the database and files; do not retry, reset, or clean automatically.

### Windows evidence DACL handling

Private files use a DACL-only `icacls.exe` operation with SID grants for the current Windows operator and Local System (`S-1-5-18`). The operation removes inherited access and grants Full Control only to those two principals; it does not request or modify a SACL, owner, or audit policy. Read-only fixture modes validate this state and never rewrite permissions. Environment restoration and secure-memory disposal remain in the outer `finally`, so they run even when file protection fails. Component output is buffered during file-creating operations, and the wrapper emits its final PASS only after the new files pass DACL validation.

Run `14405b71b0504036a35ff55c7a9da132` was committed before the earlier `Set-Acl` failure. Its existing files require a separately authorized, exact-RunId DACL repair. The default repair command is read-only:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\repair_tamil_ai_browser_evidence_acl.ps1 -RunId 14405b71b0504036a35ff55c7a9da132
```

It reports PASS only when the reservation, Owner DPAPI file, pending evidence, and committed evidence already have protected operator/SYSTEM-only DACLs. The future one-time repair requires separate filesystem authorization:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\repair_tamil_ai_browser_evidence_acl.ps1 -RunId 14405b71b0504036a35ff55c7a9da132 -Execute -ConfirmRunId 14405b71b0504036a35ff55c7a9da132 -ConfirmAclRepair
```

The repair refuses missing required evidence, any cleanup evidence, an unexpected explicit principal, a wrong RunId, or incomplete confirmation. It does not read file contents, connect to MySQL, or alter fixture records. After repair, use the normal read-only verification command; it validates all four DACLs before opening its read-only database transaction:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\manage_tamil_ai_browser_fixture.ps1 -Mode Verify -RunId 14405b71b0504036a35ff55c7a9da132
```

## Isolation and evidence

The guards require environment `ai_snapshot_testing`, database `lankapex_ai_snapshot_test_db`, account `lankapex_ai_snap_runtime@localhost`, revision `7b9e4d2c8a15`, exactly 29 tables, and exact-schema DML grants with global `USAGE` only. Reservation identity is derived from one random lowercase 128-bit run ID. The owner password is held only in a Windows CurrentUser DPAPI file; the synthetic Customer password is random, hashed immediately, and discarded because the owner-facing flow does not require customer login.

The browser backend also sets the exact process flag `LANKAPEX_DISABLE_DOTENV=true`. Configuration accepts it only with the pinned `ai_snapshot_testing` database, runtime account, loopback CORS, disabled AI, warning logging, private runtime/JWT credentials, and an absent `GROQ_API_KEY`. In that context every `Settings` construction removes dotenv as a source and the application singleton is explicitly built with `_env_file=None`. Windows PowerShell removes the Groq variable instead of assigning an empty string. Development, production, migration, demo, and unrelated test contexts cannot use this flag. Other environments retain their existing dotenv behavior.

The immutable reservation, pending commit evidence, committed exact-ID evidence, cleanup pending evidence, and cleanup completion evidence live under `.server-logs/private-ai-tests/`. Files are exclusive-create and never overwritten. Evidence binds a deterministic fingerprint of the empty pre-state, the exact IDs and financial amounts, and the restored-empty post-cleanup state. Cleanup first reproves all IDs, relationships, two ledger amounts, the authoritative `70.10` balance, the exact whole-schema row inventory, and the evidence SHA-256 fingerprint. It deletes only the recorded primary keys in dependency order: ledger entries, credit account, customer profile, membership, business, then the two users. It never uses `DROP`, `TRUNCATE`, reset, or unscoped SQL deletion.

## Operator commands (future, separately authorized)

From `C:\Users\admin\Desktop\LankaPex` under the Windows account that owns the existing runtime DPAPI credential, the **first action** is read-only:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\manage_tamil_ai_browser_fixture.ps1 -Mode Preflight
```

Expected output ends with:

```text
PASS: exact empty AI snapshot test schema, revision, inventory and DML-only grant
READ-ONLY TAMIL AI FIXTURE PREFLIGHT COMPLETE; no files or records changed
```

After separate filesystem authorization, reserve a run (this creates private files but no database rows):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\manage_tamil_ai_browser_fixture.ps1 -Mode Reserve -Execute -ConfirmTarget lankapex_ai_snapshot_test_db -ConfirmEmpty -ConfirmWriterPause
```

Record the reported run ID privately. After separate database-write authorization:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\manage_tamil_ai_browser_fixture.ps1 -Mode Create -RunId <run-id> -Execute -ConfirmTarget lankapex_ai_snapshot_test_db -ConfirmEmpty -ConfirmWriterPause
```

Read-only verification and server preflights:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\manage_tamil_ai_browser_fixture.ps1 -Mode Verify -RunId <run-id>
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\start_tamil_ai_browser_backend.ps1 -PreflightOnly -RunId <run-id>
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\frontend\scripts\start_tamil_ai_browser_frontend.ps1 -PreflightOnly
```

The backend requires a distinct `.server-logs/private-ai-tests/tamil-ai-browser-jwt.dpapi`. If it does not exist, its future creation is a separate filesystem action. Use PowerShell 5.1, refuse overwrite, generate at least 48 random bytes, protect it with CurrentUser DPAPI, and restrict the private directory ACL to the operator and SYSTEM. Never copy the secret to a `VITE_*` variable.

After separately authorizing server startup, start each process in its own administrator terminal by omitting `-PreflightOnly`. The backend binds only `127.0.0.1:8014`; the frontend binds only `127.0.0.1:5175` and calls `http://127.0.0.1:8014/api/v1`.

## Browser assertions

Login with the fixture owner identity and its DPAPI-protected password. In the existing Shop Owner Customers screen, select the exact synthetic business, customer, and credit account.

- The Customer Details panel shows the synthetic credit account.
- **Generate Tamil Summary** issues exactly one `POST` to `/api/v1/shop-owner/businesses/{business_id}/customers/{customer_id}/credit-accounts/{credit_account_id}/tamil-credit-summary` with no request body.
- The action is disabled while pending, so repeated clicks do not create concurrent requests.
- The response displays authoritative purchases `100.20`, repayments `30.10`, and outstanding `70.10` separately from explanatory Tamil text.
- Because `AI_ENABLED=false`, the source indicator must show deterministic fallback and no GroqCloud request occurs.
- Switching customer/business/account or authenticated user clears the displayed result.
- An expired/missing session shows the existing safe authentication behavior. A controlled sixth generation within the configured local rate-limit window should produce the existing safe `429` UI; do this only after the principal happy-path assertion because the limiter is process-local.

Do not alter values through the browser. The summary endpoint is read-only, but read-only verification must still pass before cleanup.

Cleanup review and the later, separately authorized cleanup are:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\manage_tamil_ai_browser_fixture.ps1 -Mode CleanupReview -RunId <run-id>
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\manage_tamil_ai_browser_fixture.ps1 -Mode Cleanup -RunId <run-id> -Execute -ConfirmTarget lankapex_ai_snapshot_test_db -ConfirmWriterPause
```

Stop both loopback servers before cleanup and maintain the writer pause. If cleanup or postflight stops, preserve state and evidence; never rerun automatically.

## Remaining gates

- Fresh empty-schema preflight must pass.
- No pytest, server, browser, migration, SQL client, or other writer may use the isolated database during fixture phases.
- Reservation, credential, fixture creation, server startup/browser execution, and cleanup each require separate authorization.
- The dedicated JWT DPAPI file must exist and be decryptable by the same Windows operator.
- Browser DevTools may be used to inspect method/path/body and sanitized response fields, but tokens, cookies, passwords, and headers must not be captured in shared evidence.
