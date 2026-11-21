# Step 387 -- Admin Driver verification (offline implementation)

No new schema is needed beyond the unapplied ae2b7c5f1d48 migration. No storage
directory was provisioned, service restarted, or live account/document accessed.
Do not deploy/restart against the previous schema.

Existing GET /api/v1/admin/drivers/{user_id} now includes a verification object:
Driver reference, explicit legacy exemption, approval readiness, and exactly two
document slots. Each slot contains opaque identity/version, kind, MIME, review
state/reviewer/time and integrity status. No storage key, original filename,
document number, digest, or filesystem path is returned.

Admin-only current-document endpoints:

- GET /api/v1/admin/drivers/{user_id}/documents/{uuid}/preview
- GET /api/v1/admin/drivers/{user_id}/documents/{uuid}/download
- PATCH /api/v1/admin/drivers/{user_id}/documents/{uuid}/review

Review body: decision approve/reject; rejection_code must be null for approval
and one of UNREADABLE, WRONG_DOCUMENT, EXPIRED, OTHER for rejection. The existing
UI uses OTHER when rejecting; no sensitive free-text reason is collected.
Identical repeats preserve the original review and audit; conflicting repeats
return 409. Replaced, guessed or foreign-Driver identities return 404.

Access rechecks active Admin, current version, private-root permissions, size,
SHA-256 and MIME signature before returning previously normalized bytes.
This serves only Step 385 sanitized content; no unsafe original is retained or
rendered. Responses use no-store, nosniff, restrictive CSP sandbox and generated
inline/attachment filenames. File access and decisions commit their audit before
success is returned. Audit failure prevents delivery/confirmation. Error messages
are fixed and never include files, storage keys, parser output or SQL details.

Review, retrieval and final approval lock Admin, Driver User, DriverProfile and
current documents in a consistent order. Replacement locks Driver User first;
therefore final approval rechecks current review state and stored bytes under
the same per-Driver serialization boundary. Approval rejects missing, pending,
rejected, replaced or corrupted documents. Exemption applies only to existing
approved legacy profiles, not pending applications with an exemption flag.
New replacement versions are PENDING and do not inherit old review metadata.

The existing Admin details panel now contains the two document controls without
altering routes or page layout. Driver approval stays hidden until the validated
metadata says both documents are approved; the server independently enforces it.
Blob reads use the existing authenticated Axios instance. Switching Driver/detail,
logout or closing preview aborts reads/revokes preview URLs; late reads cannot
create a new preview after unmount. PDF preview uses a sandboxed iframe and the
download fallback remains available. Actual browser PDF-viewer behavior requires
a later controlled live check; it is not established by SSR tests.

Offline checks use synthetic files/SQLite and native limited parser processes:

```powershell
.\backend\.venv\Scripts\python.exe backend\offline_tests\admin_driver_documents_suite.py
```

SQLite tests exercise stale/replacement interleavings and conflicts; they do not
prove MySQL row-lock scheduling under real concurrent sessions. That is a separate
authorized acceptance gate. No upload, review, access audit or financial write
has been performed against viva during this task.
