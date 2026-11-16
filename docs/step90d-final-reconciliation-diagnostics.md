# Step 90D — Sanitized final-state reconciliation diagnostics

Status: **source diagnostic prepared; no live diagnostic executed**.

The prior output proves the exact runtime database/account/revision/table/grant gate passed. The known aggregate inventory also matches the reconciliation count gate. Source alone cannot identify which later identity or relationship predicate failed because the production reconciliation intentionally reduced every exception to one generic STOP.

The strongest current hypothesis is `business_manifest_identity`: the immutable reservation derives business name `QR Browser Shop 6d2a5a8c093c` and registration number `QR-6d2a5a8c093c48509bbc2878ae50ded3`, while the business was entered manually in the browser. This is not treated as confirmed until the diagnostic runs. Other possible categories are protected Admin evidence, fixture-user identity, Owner membership, business approval audit, approval notification, permanent link, approved request, or linked/unlinked profile pair.

`DiagnoseFinal` calls the same exact `reconcile_final_state` function under the same process-only testing configuration and consistent read-only transaction. It does not relax or bypass any predicate. On failure it maps an exact reviewed exception to a fixed category such as `business_manifest_identity`, `owner_membership`, or `customer_profile_pair`. Unknown exceptions become `unclassified_read_only_failure`. Exception text and row values are never emitted. On success it emits the same sanitized reconciliation report.

Run under the Windows account that owns the test DPAPI files, with browser writers quiescent:

```powershell
Set-Location C:\Users\admin\Desktop\LankaPex
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\manage_qr_browser_fixture.ps1 -Mode DiagnoseFinal -RunId 6d2a5a8c093c48509bbc2878ae50ded3
```

The mode has no `-Execute` parameter, creates no evidence file, changes no manifest, and performs no database write or cleanup. Preserve the category output for the next source review. Do not rerun registration, approval, or joining to try to satisfy a failed category.
