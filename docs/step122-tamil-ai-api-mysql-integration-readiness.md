# Step 122 — Guarded Tamil AI API MySQL integration-test readiness

Status: **source ready; live execution remains blocked pending separate authorization.**
No MySQL connection, fixture write, external AI request, migration, server startup, or
persistent configuration change is performed by this preparation.

## Fixed isolation boundary

- Environment: `ai_snapshot_testing`
- Database: `lankapex_ai_snapshot_test_db`
- Runtime account: `lankapex_ai_snap_runtime@localhost`
- Revision: `7b9e4d2c8a15`
- Inventory: 28 application tables plus `alembic_version`
- Credential: `.server-logs/private-ai-tests/ai-snapshot-test-runtime.dpapi`

The PowerShell launcher sets every identity as a process-only value, forces
`AI_ENABLED=false`, clears `GROQ_API_KEY`, and restores the prior process environment
afterward. The Python preflight verifies configured, engine and actual identities,
the exact revision and table set, exact DML-only grant, and zero rows in every
application table. Any mismatch stops before pytest.

## Endpoint coverage and rollback

The existing snapshot repository tests remain in the same suite. The endpoint tests
add real JWT and SQLAlchemy coverage for approved ownership, exact customer/account
relationships, cross-business denial, missing and invalid authentication, wrong roles,
inactive and unlinked Customers, malformed creditor relationships, authoritative
credit/repayment totals, reversal semantics, disabled-AI fallback, and an injected
provider-failure fallback. No Groq transport is constructed.

Each test creates unique synthetic rows inside the existing outer transaction. Request
sessions join that transaction through savepoints. Tests fingerprint users, businesses,
memberships, profiles, accounts and ledger rows immediately before and after endpoint
calls. The fixture rolls back unconditionally. After pytest exits, including after a
test failure, the wrapper reruns the exact empty-schema preflight. It never deletes,
truncates, resets, retries, or repairs data. A failed postflight preserves the database
for operator review.

## Operator commands

Read-only preflight only:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\run_ai_snapshot_integration_tests.ps1
```

Expected final line:

```text
READ-ONLY PREFLIGHT COMPLETE; no fixture writes or tests executed
```

Separately authorized execution:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\run_ai_snapshot_integration_tests.ps1 -Execute -ConfirmTarget lankapex_ai_snapshot_test_db
```

Execution requires a fresh passing preflight, an empty dedicated schema, the Windows
operator who owns the DPAPI credential, no concurrent runner, and explicit authorization
for rollback-controlled fixture writes. A STOP requires preserving state and evidence;
do not rerun or clean up automatically.
