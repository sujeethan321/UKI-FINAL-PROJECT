# Step 90F — Ownership-first business lookup diagnostic

Status: **source diagnostic prepared; no live query executed**.

The failed final reconciler searches:

```sql
SELECT business_id, business_name, registration_number, approval_status
FROM businesses
WHERE business_name = :reserved_name
   OR registration_number = :reserved_registration
```

It then requires exactly one row and requires both fields to equal the immutable reservation. The reservation derives `QR Browser Shop 6d2a5a8c093c` and `QR-6d2a5a8c093c48509bbc2878ae50ded3`. Since the verified inventory contains exactly one business, diagnostic category `business_lookup` means the query returned zero rows: neither field matched the reservation. The normal onboarding form permits an arbitrary required business name and an optional registration number, trims both, and submits a blank registration as `NULL`. Manual entry therefore explains the result without implying that ownership or QR relationships are invalid.

`DiagnoseBusiness` retains the complete exact runtime, grant, Admin, inventory, and financial-zero gates. In one consistent read-only transaction it locates the Owner by the reservation-derived exact email, then locates the sole approved business through an active `owner` membership. It prints only whether the reserved name matches and whether the reserved registration matches. It never prints either actual value, the Owner email, IDs, credentials, tokens, hashes, or the QR code. It creates no file.

```powershell
Set-Location C:\Users\admin\Desktop\LankaPex
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\manage_qr_browser_fixture.ps1 -Mode DiagnoseBusiness -RunId 6d2a5a8c093c48509bbc2878ae50ded3
```

If membership ownership passes and either identity boolean is false, a later separately reviewed reconciliation policy may treat the exact Owner membership and the globally unique single business as authoritative while explicitly recording the manifest discrepancy. It must continue verifying the approval audit, notification, link, request, profiles and zero financial state. It must not rewrite the manifest, rename the business, populate the registration number, fabricate historical snapshots, or infer ownership from display names.
