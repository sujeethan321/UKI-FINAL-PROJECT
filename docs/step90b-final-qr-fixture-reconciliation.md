# Step 90B — Final QR fixture reconciliation preparation

Status: **source tooling prepared; live reconciliation not executed**. The browser workflow reached its final state before the six historical evidence snapshots were collected. This procedure validates only the present completed state and explicitly records that historical snapshots were not captured or fabricated.

## Why two customer profiles exist

Public Customer registration calls `registration_service._create_user` and inserts only a `users` row. It does not create a `CustomerProfile`. QR owner approval in `customer_join_service.decide` creates exactly one profile linked through `user_id` to the registered Customer.

The separate `shop_owner_customer_create_service.create_business_customer` path creates a business-owned manual customer profile with no `user_id`. Therefore, the observed unlinked profile did not come from Customer registration or QR approval. It is consistent with the Shop Owner manually creating a customer record before or during the browser workflow. Because its `user_id` is null, it cannot be asserted to belong to the registered Customer account from identity evidence. The reconciler verifies only that it is the sole unlinked profile for the exact fixture business, has no unexpected dependent records, and coexists with exactly one properly linked profile. It preserves the row and does not classify it as duplicate or cleanup-safe.

## Guarded reconciliation

`manage_qr_browser_fixture.ps1 -Mode ReconcileFinal` reuses the existing process-only testing environment and `check_qr_test_runtime.py`. It requires the exact database, account, revision, 29-table inventory, and escaped DML-only grant. It reads the immutable reservation manifest for the supplied 128-bit run ID and the committed Admin recovery manifest.

One consistent, explicitly read-only transaction then requires the exact global inventory:

- three users: protected Admin, derived fixture Owner, and derived fixture Customer;
- one Admin provisioning audit;
- one approved business matching both the derived name and registration number;
- one active Owner membership;
- one Admin approval audit and its exact Owner notification;
- one permanent join link;
- one approved join request decided by the fixture Owner;
- two profiles for the fixture business: one linked to the fixture Customer and one with `user_id` null;
- zero rows in every other modeled application table, including all financial, order, delivery, invitation, communication, catalogue, preference, address, vehicle and settings tables.

The output is a sanitized JSON report containing primary IDs, verified relationship labels, a SHA-256 fingerprint of the QR public code, and explicit flags stating that no database or evidence file changed. It never prints emails, names, credentials, tokens, password hashes, or the raw QR code. Any missing, duplicated, conflicting or unexpected row produces `STOP`.

## Future read-only command

Run under the Windows account that owns the private DPAPI files:

```powershell
Set-Location C:\Users\admin\Desktop\LankaPex
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\manage_qr_browser_fixture.ps1 -Mode ReconcileFinal -RunId 6d2a5a8c093c48509bbc2878ae50ded3
```

This mode accepts no `-Execute` flag, reserves no path, creates no evidence, and performs no cleanup. The browser servers should remain quiescent during the consistent snapshot. A successful report is evidence of current state only. Creating an immutable final report file or designing cleanup requires separate review and authorization.
