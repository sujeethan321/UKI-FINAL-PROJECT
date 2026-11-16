# Step 194A — Guarded demo database inventory

## Source review

No existing procedure satisfies the full requested inventory unchanged:

- `check_demo_backend.py` is a startup compatibility gate, not a preservation inventory. It rejects old revisions before collecting a baseline.
- `capture_demo_baseline.py`/`verify_live_demo_baseline.ps1` require the historical 14c0d3e2f782 baseline, use a migrator credential, read unrestricted table projections and write private manifests.
- `verify_demo_post_migration.py` is pinned to the older invitation transition and existing private backup evidence.
- `preflight_demo_runtime.ps1` calls the startup gate and does not pin the newly required effective presentation settings.

None was executed or modified for this step. No private credential/evidence contents were inspected.

## New procedure

`backend/scripts/inventory_demo_database.ps1` defaults to OFFLINE preparation: no credential read/decryption, database connection, file creation or server startup. Actual inventory requires both `-Execute` and `-ConfirmTarget lankapex_demo_db`.

The wrapper uses only the existing `.server-logs/private-demo/demo-app.dpapi` CurrentUser SecureString format. It requires a protected, non-inherited DACL with operator Full Control; only the operator and optional SYSTEM are accepted. It refuses a file reparse point, does not change ACLs, and stops if permissions differ. Such a STOP requires separate review, not an automatic ACL repair. Run from the owning Windows account, outside a credential/debug transcript. Process variables are restored and SecureString/BSTR memory released on every path.

The Python tool does NOT import application settings, models, database engines or AI adapters. It never loads backend/.env, JWT secrets or Groq keys. It builds an explicit connection only after validating development/localhost/3306/lankapex_demo_db/lankapex_demo_app process values. It verifies actual DATABASE(), CURRENT_USER(), server port, no active roles, global USAGE only and exact escaped-schema SELECT/INSERT/UPDATE/DELETE grants. It never echoes grant strings or connection URLs. Other schemas, views, non-InnoDB tables, unreviewed table names, unknown revisions or unavailable required metadata cause STOP.

All application reads occur after a consistent REPEATABLE READ, READ ONLY transaction starts; session read-only mode is also set. Only exact metadata/identity/ledger statements and three constrained read-query grammars are permitted through the reader. No DML, DDL, temporary tables, FOR UPDATE, table locks, COMMIT, retries or automatic repair exist. Reads end in rollback and engine disposal. Schema metadata/revision are read again before output; a detected change stops the run. Concurrent DDL is not locked out, so the operator should maintain a writer/DDL pause for a useful preservation baseline.

## Coverage

The sanitized stdout JSON contains exact approved target/account/host/port and effective privilege names; one known Alembic revision; table names and counts; missing current tables; QR field/type/nullability, PK, unique, index and FK verification indicators; schema fingerprints and QR state (absent/complete/partial_or_mismatched); duplicate non-null business/user profile pair count; all application row counts; projected financial/relationship SHA-256 fingerprints; reversal-aware signed account-balance fingerprint; ledger entry-type aggregate fingerprint; FK orphan counts; and a UTC snapshot time.

Financial projections cover credit accounts, ledger records and payment-reminder amounts. Relationship projections cover customer links, owner memberships, orders/items, and delivery requests/assignments/events. Financial values and individual record IDs are used internally for hashing, never printed. No names, emails, addresses, notes, password hashes, credential ciphertext, tokens or QR public codes are selected. Hash encoding is UTF-8 JSON arrays with Decimal/date values rendered as strings, newline-delimited and ordered by primary keys. This is a baseline, not proof of agreement with prior private evidence.

Balance SQL mirrors effective-ledger semantics: only sales/repayments not reversed by a same-account reversal contribute; zero-entry accounts remain included and advances retain negative signed balances. It does not change credit limits or recalculate stored data. Entry-type aggregate hashes include raw reversal rows; the signed balance hash is separately reversal-aware.

An older known revision is reported, not automatically treated as unsafe to inspect or accepted as current compatibility. Missing columns/tables make individual fingerprints unavailable and are explicitly listed; unreadable required metadata/queries STOP rather than being interpreted as absence. QR checks do not certify every historical column/default/constraint. The scope intentionally excludes full-row hashes of private/credential fields and provides no cleanup ownership authorization.

## Operator commands — DO NOT execute until authorized

From `C:\Users\admin\Desktop\LankaPex`, no-connection preparation:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\inventory_demo_database.ps1
```

Expected:

```text
PASS: offline inventory preparation only; no credentials loaded or database connected
```

The new tool's live execution requires separate authorization:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\inventory_demo_database.ps1 -Execute -ConfirmTarget lankapex_demo_db
```

Success prints sanitized JSON, followed by:

```text
PASS: read-only demo inventory complete; compatibility is reported separately; no files or database records changed
```

A completed inventory can correctly report `current_schema_compatible: false`. That is not permission to migrate or start the application. Failed identity/grants/metadata/private-file prerequisites produce categorized STOP and a nonzero exit, without exception contents. Missing metadata privileges are reported as `read_or_metadata_unavailable`; no grants should be broadened automatically.

No output files are created by this procedure. If durable evidence is desired, separately review private output capture/ACLs before redirecting stdout. Preserve all existing fixtures, baseline manifests and credential files. On STOP, do not retry or change anything automatically.

## Offline validation

Use the backend virtual environment with unittest discovery only in `backend/offline_tests` for `test_demo*.py`; this avoids the DB-connected `backend/tests/conftest.py`. Tests use mocks/synthetic metadata, plus one transient SQLite :memory: SQL semantic check, with no MySQL/network access or persistent fixture files. Python syntax compilation, PowerShell AST parsing and explicit whitespace/conflict-marker checks are required. Live MySQL behavior is intentionally unverified.
