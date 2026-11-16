# Step 78 — Guarded QR browser fixture ownership tracking

Status: **source tooling prepared; fixture reservation, browser writes, evidence capture and cleanup remain separately authorized operations**. No database connection, credential, private manifest, server, user, business, migration or cleanup was created during Step 78.

## Ownership boundary

`backend/scripts/manage_qr_browser_fixture.ps1` installs an exact process-only testing configuration and reuses `check_qr_test_runtime.py`. The gate requires `lankapex_test_db`, `lankapex_qr_test_runtime@localhost`, revision `7b9e4d2c8a15`, 29 tables, global `USAGE`, and only escaped exact-database SELECT/INSERT/UPDATE/DELETE grants. It never falls back to demo or development credentials.

A reservation uses a cryptographically random 128-bit lowercase run ID. The following identities are deterministically derived from it:

- `qr-owner-{run_id}@lankapex-test.example.com`
- `qr-customer-{run_id}@lankapex-test.example.com`
- `QR Browser Shop {first 12 run-id characters}`
- registration number `QR-{run_id}`

The wrapper generates separate 48-byte random Owner and Customer passwords, protects each with Windows DPAPI CurrentUser, and stores them under `.server-logs/private-test`. It creates the credential and manifest paths with `CreateNew`, applies an ACL for the current Windows operator, and never prints a password. Reservation is refused unless the database has the exact protected baseline: active Admin `124671`, its committed provisioning audit, and zero rows in every other application table. The committed Admin recovery manifest, original failed bootstrap evidence, Admin credential and Admin audit are never fixture-owned.

The immutable private reservation is `qr-browser-fixture-{run_id}.json`. It contains synthetic identifiers and credential filenames, but no passwords, hashes, tokens or QR secret. Each later browser stage gets a new append-only evidence file:

1. `users_registered`
2. `business_created`
3. `business_approved`
4. `join_link_created`
5. `join_requested`
6. `join_approved`

The collector uses one consistent read-only transaction. It resolves records by the run-scoped email/registration identities and then proves exact foreign-key relationships. It records exact primary keys for the two users, business, membership, approval audit, approval notification, join request and linked customer profile. The permanent QR code is represented only by a SHA-256 fingerprint. Every stage requires the prior snapshot and refuses overwrite.

Because the isolated database started empty except for the protected Admin, each stage requires an exact global count for all 28 application tables. Any unrelated row, duplicate, missing record or unexpected dependent record stops the collector. Financial and fulfilment tables must remain at zero, including credit accounts, ledger entries, reminders, orders/items, deliveries/assignments/status events. QR approval creates only a linked `customer_profiles` row; it must not create credit, debt, sale, repayment, order or delivery data.

## Future operator commands

Run from `C:\Users\admin\Desktop\LankaPex` under the Windows account that owns the runtime and JWT DPAPI files. The following first command connects read-only and creates nothing:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\manage_qr_browser_fixture.ps1 -Mode Preflight
```

After separate authorization to create private files, reserve one run. This still performs no database write:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\manage_qr_browser_fixture.ps1 -Mode Reserve -Execute -ConfirmTarget lankapex_test_db -ConfirmAdminId 124671 -ConfirmWriterPause
```

Retain the emitted non-secret run ID. After each separately authorized browser stage, capture evidence with the exact stage name. This reads MySQL but creates one private evidence file, so it also requires explicit execution confirmation:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\manage_qr_browser_fixture.ps1 -Mode Collect -Stage users_registered -RunId <32-lowercase-hex-run-id> -Execute -ConfirmTarget lankapex_test_db -ConfirmAdminId 124671 -ConfirmWriterPause
```

Repeat in order for `business_created`, `business_approved`, `join_link_created`, `join_requested`, and `join_approved`. Do not skip stages. A STOP leaves any reserved empty/partial private file as diagnostic evidence and is not a retry target.

After the final snapshot, this command performs a read-only cleanup review. It never deletes rows or changes files:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\manage_qr_browser_fixture.ps1 -Mode CleanupReview -RunId <32-lowercase-hex-run-id>
```

## Cleanup safety design

There is intentionally no cleanup execution mode. A later separately reviewed cleanup tool must load the immutable reservation and final snapshot, rerun the exact runtime gate, maintain the writer pause, recheck every recorded ID and relationship, and stop if current state differs. It may delete only recorded IDs in this dependency order:

1. approval notification;
2. linked customer profile;
3. customer join request;
4. permanent join link;
5. business approval audit;
6. owner membership;
7. business;
8. Customer user;
9. Shop Owner user.

It must never include Admin `124671`, the Admin provisioning audit, either Admin bootstrap attempt, or an unrelated row. Broad DELETE, TRUNCATE, DROP, foreign-key disabling, reset and cleanup-by-name are prohibited. Any financial, order, delivery, invitation, communication, catalogue, preference or other unexpected dependent blocks cleanup for review.

## Remaining blockers

1. Separate authorization is required to run the live read-only preflight.
2. Separate authorization is required to reserve the private run manifest and credentials.
3. Browser server startup and each registration/approval/join database write remain unauthorized.
4. Evidence must be collected successfully after every stage before the next stage is trusted.
5. Cleanup has only a reviewed gate and dependency design; no delete-capable tool exists or is authorized.

The smallest next operation is the read-only `-Mode Preflight` command above while the writer/DDL pause remains maintained.
