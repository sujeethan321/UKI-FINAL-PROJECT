# Step 386: Driver multipart registration (offline implementation)

Step 387 adds Admin document review and approval gating; see
`admin-driver-document-review.md` for current endpoints and verification limits.
The next-phase descriptions below record the registration implementation boundary.

No migration, storage provisioning or live registration was performed. Revision
ae2b7c5f1d48 and a privately provisioned DRIVER_DOCUMENT_PRIVATE_ROOT are prerequisites
for deployment. Do not restart the viva backend against the old schema.

POST /api/v1/auth/register/driver now accepts multipart/form-data only. Required
text fields: full_name, email, password, vehicle_type, registration_reference.
Optional existing fields: phone, preferred_language. Required files:
driving_licence and vehicle_ownership_proof. Duplicate/unrecognized form fields
and missing files are rejected. Customer/Shop Owner JSON contracts are unchanged.

The exact Driver POST path receives an 11 MiB pre-parser byte/time limit. Other
mutations retain the existing lower request cap. Existing registration throttling
runs before multipart parsing. Parsing spools remain in bounded memory instead
of the shared OS temporary directory; actual file validation/staging uses Step
385 private storage and isolated workers. Each file remains limited to 5 MiB.

Both files validate before any account is inserted. A single DB transaction
creates User, pending DriverProfile, two PENDING immutable document versions and
submission audits. Email uniqueness arbitrates concurrent duplicates. Driver
approval is never automatic. Failures roll back the account transaction. A failed
or uncertain COMMIT preserves validated files; accepted but unattached candidates
are private and require explicit operator review, not automatic purge or retries.
This is not a filesystem/database distributed transaction or a cleanup scheduler.

POST /driver/profile can no longer create a document-free application. Existing
approved legacy profiles remain readable and retain eligibility/decisions. Existing
unsubmitted accounts need a separately scoped authenticated document submission
workflow; the old profile-only form cannot complete that flow. Admin document
preview/review and document-aware approval gating are also a separate next phase;
do not enable new live onboarding before that phase is integrated and reviewed.

The Driver-only registration fields use the existing form styles and en/ta/si
catalogs. Files stay in component/controller memory, never browser persistence.
Multipart lets the browser generate its boundary and clears the global JSON
Content-Type for this request only. Duplicate clicks share one request. Network
or 5xx outcomes stop re-submission and ask for sign-in/operator confirmation;
there is no automatic retry. File names render as escaped React text.

Offline checks:

```powershell
.\backend\.venv\Scripts\python.exe backend\offline_tests\driver_registration_suite.py
```

Synthetic SQLite and files only; no MySQL or provider requests. Existing
MySQL integration tests that register Drivers via JSON/profile-only submission
require future fixture migration to the new contract; they were not executed.
