# Step 193 — Demo compatibility gate correction

Source-only preparation. No database identity, revision or data has been verified by this change.

The demo gate now requires revision 7b9e4d2c8a15, exactly 28 modeled application tables and 29 total tables including alembic_version. It checks QR column inventory, primary keys, named unique constraints (including customer_profiles.uq_customer_profile_business_user on business_id,user_id), request status check, request index, and business/user foreign keys. MySQL's omitted default RESTRICT and utf8mb4 check-literal reflection are supported. This is focused QR validation, not a complete historical schema-diff certification.

Exact configured/effective localhost:3306, lankapex_demo_db and lankapex_demo_app credentials remain required. Actual database/account, exact DML-only grants, escaped schema scope and absence of active roles remain checked. No migrations, data writes, resets or automatic retries were added.

The launcher pins AI_ENABLED=false, warning logging, debug=false, local rate limits, CORS http://127.0.0.1:5173 and loopback allowed hosts. It removes the inherited Groq process key, refuses the unsupported inherited LANKAPEX_DISABLE_DOTENV flag, and restores every overridden variable in finally. Credential decoding is inside the cleanup boundary. Authentication and JWT semantics are unchanged.

LIMITATION: development Settings still loads backend/.env. A Groq key may therefore exist in effective Settings even after the process variable is removed. The explicit process AI_ENABLED=false overrides dotenv and is validated before startup, so the existing summary dependency selects deterministic fallback without creating a Groq client. This change does not claim key-free/full dotenv isolation. A dedicated demo dotenv-isolation design would require separate review; the AI snapshot isolation override has not been repurposed. Other unpinned settings can still come from dotenv/environment.

Before any startup, separately authorize read-only demo inspection: actual revision, full structural compatibility, duplicate linked profiles and preservation baselines. If still at 6e3f2c1a9b04, this corrected gate intentionally stops. A populated-demo QR migration requires separate preparation, backup/recoverability checks, writer/DDL pause, rehearsal and execution authorization. Do not reuse the empty QR test runner or stamp the revision.

Future operator read-only runtime check (connects to the demo database; separate authorization required):

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\preflight_demo_runtime.ps1

The standalone runtime preflight does not establish the launcher's pinned presentation settings; review it before using it as the final configuration check. No live command was executed during Step 193.

## Sanitized startup diagnosis

The gate now reports fixed failure categories rather than one generic RuntimeError.
Run the following once from the Windows operator session authorized to read the
existing CurrentUser DPAPI credentials. It performs the same guarded read-only
checks and never starts Uvicorn, migrates, retries or creates evidence:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\start_demo_backend.ps1 -PreflightOnly
```

For example, `schema_revision_mismatch` means the revision guard rejected the
schema; it does not authorize an upgrade or prove the precise current revision.
Other categories distinguish effective configuration, identity, QR schema, grants,
authentication and connection failures. Unknown errors remain sanitized.
The preflight still decrypts the existing runtime/JWT credentials in memory and
uses read-only MySQL metadata checks; it requires operator authorization.
These source changes alter recovery/migration source fingerprints. Preserve old
evidence; never edit hashes to make it pass. Reassess source-bound evidence before
any future backup, rehearsal or migration execution.
