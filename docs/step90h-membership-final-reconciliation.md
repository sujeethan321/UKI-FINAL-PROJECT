# Step 90H — Membership-based final QR reconciliation

Status: **source implementation prepared; no live reconciliation executed**.

The original strict `ReconcileFinal` remains unchanged. `ReconcileFinalByMembership` is a separate read-only mode for the completed run whose manually entered business name and optional registration number differ from the immutable reservation.

## Verification authority

The new mode reads the immutable reservation and uses its derived synthetic Owner and Customer emails. It requires exactly one active `shop_owner` for the Owner email and exactly one active `customer` for the Customer email. It identifies the business only through the Owner user's sole active `owner` membership foreign key, then requires that business to be approved. Business name and registration number are compared with the reservation but are never used as ownership evidence and are never printed. The report retains both match booleans and `identity_discrepancy=true` when appropriate.

The same consistent read-only snapshot then verifies:

- protected Admin `124671` and its exact provisioning audit;
- one approval audit for the membership-owned business, performed by Admin `124671`;
- the corresponding approval notification to the exact Owner;
- one permanent join link belonging to that business;
- one approved join request for the exact derived Customer, decided by the exact Owner;
- one profile linked to the exact business and Customer user;
- one additional profile under the exact business with `user_id=NULL` and no asserted Customer-account identity;
- zero dependents for the unlinked profile because every dependent/unrelated application table must remain empty;
- zero credit accounts, ledger/repayment entries, reminders, orders, deliveries, invitations, communications, products, settings, preferences, addresses, vehicles, documents and all other unrelated records.

The strict global inventory requires three users, one business, one membership, one approval audit, one notification, one link, one request, two profiles and the protected Admin audit. Duplicate businesses, memberships, approvals, requests or profiles stop reconciliation.

The sanitized report includes verified primary IDs, relationship statuses, business identity match booleans, a QR-code SHA-256 fingerprint, and zero-state indicators. It excludes actual business names, registration numbers, emails, credentials, tokens, password hashes and the raw QR code. It states that historical snapshots were not captured or fabricated and that no database or evidence file changed.

## Future operator command

Keep browser writers quiescent and run under the Windows account that owns the test DPAPI files:

```powershell
Set-Location C:\Users\admin\Desktop\LankaPex
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\manage_qr_browser_fixture.ps1 -Mode ReconcileFinalByMembership -RunId 6d2a5a8c093c48509bbc2878ae50ded3
```

The mode accepts no `-Execute`, creates no file, performs no cleanup and cannot modify the reservation. A PASS is a current-state report only. Persisting evidence or preparing exact-ID cleanup requires separate review and authorization.
