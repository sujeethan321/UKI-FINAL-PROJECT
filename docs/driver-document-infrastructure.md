# Step 385: private Driver document foundations

Step 386 implements the new-registration workflow; see
`driver-registration-documents.md` for the current multipart contract and
remaining deployment/Admin-review gates. Historical next-phase descriptions
below describe the infrastructure boundary at Step 385.

Prepared schema revision `ae2b7c5f1d48` follows `9d1a6f4e0c37`.
It is NOT applied. Do not restart/deploy this model against the old schema:
DriverProfile queries now include the new column and require the separately
authorized migration first. No existing account approval service or endpoint
was changed. Mandatory registration uploads and approval gating are NEXT-phase
work, not an implemented enforcement claim.

## Schema and integration boundary

New tables: driver_verification_documents and driver_document_audits. The only
existing-table change is driver_profiles.legacy_document_exempt. The proposed
migration marks only profiles already approved at migration time as exempt;
it does not mark documents verified or change any approval decision. Financial
tables are untouched. Destructive downgrade is deliberately unsupported.

Versions use UUID identities, immutable content/storage metadata, monotonically
increasing per-kind versions, same-Driver/type predecessor references, and a
nullable current_slot=1 protected by a composite unique constraint. NULL allows
historical versions. ORM guards prevent evidence deletion and content mutation;
these guards are not a substitute for DB access control. The service locks the
Driver before replacement and resets the new document's review to PENDING.
Submitted audit metadata contains actor/document references and fixed actions,
not original filenames or identity-document numbers.

append_version owns no commit. Its caller must atomically append BOTH required
types and the pending application; integrate this in a separately authorized
registration phase. On an ambiguous commit NEVER delete validated candidates or
repeat registration automatically. This infrastructure deliberately has no
delete API for returned candidates, no retention worker, and no review/download
route. Failed staging removes only exclusive-created files of that attempt.
Accepted but unattached candidates require private operator reconciliation.

## Storage and validation

PrivateDocumentStore accepts an explicitly configured absolute root. It must
already exist outside the repository/web roots, without symlinks/reparse points.
Construction and each staging attempt verify restricted permissions. Windows
requires protected ACLs, operator ownership and Allow entries only for that
operator and SYSTEM; POSIX requires owner-only mode 0700. No directory/ACL is
created automatically. The operator must select and separately provision the
private directory; production service ownership is a deployment decision.

Keys are 256-bit random lowercase hex. Client filenames cannot include path
separators, colons or NUL and are never saved. Server paths/storage keys must
never enter API responses, URLs or application logs. No StaticFiles mount exists.
Payloads are streamed in 64 KiB reads, max 5 MiB each, with a shared 11 MiB budget.
The opt-in DriverDocumentBodyLimit must be mounted BEFORE multipart parsing on
future upload routes; it caps actual body bytes and receive time, irrespective
of Content-Length. It is intentionally not mounted on existing registration.

JPG/JPEG, PNG and PDF require matching extension/MIME/signature and native decode.
Pillow is pinned. Images are bounded at 20 megapixels, single-frame, copied to a
fresh RGB image and re-encoded without EXIF/ICC/comments. Normalized output must
also fit 5 MiB. Sanitization changes bytes/hash; only sanitized bytes are retained.

Native parsers run in a fresh, isolated-mode Python process. Windows Job Objects
enforce 512 MiB process memory, one process, 8 seconds CPU, kill-on-close; the
parent enforces 15 seconds wall time and suppresses parser output. The worker
waits for input until Job assignment. POSIX workers install address-space, CPU,
file-size, descriptor and core limits before native imports. Unsupported or
failed limits reject the upload; no in-process parser fallback is permitted.
The worker has no DB/config imports or inherited app secrets. This is process
and resource isolation, not a full filesystem/network security sandbox against
a native-code exploit. Python network calls are blocked defensively; it is not
an OS egress policy. Antivirus is not implemented and no malware-free claim is made.

PDFs: at most 10 pages/20,000 xrefs; encrypted, repaired, malformed, interactive,
scripted, attached-file, signature/form, link and annotated PDFs are conservatively
rejected. Escaped PDF object names are rejected rather than normalized around
the action denylist. Page dimensions and rasterization totals are bounded.
Accepted pages are raster-flattened into a new metadata-free PDF, stripping the
original object graph. Output stays PDF; signatures/searchable text are not
preserved. These restrictions intentionally exclude some otherwise valid PDFs.
No public third-party scanning service is called.

## Next-phase access/approval requirements

Only active Admins may fetch document metadata or bytes; Drivers receive only
their own status. Use authenticated IDs, no direct filesystem/URL input. Audit
preview/download, enforce no-store/nosniff/attachment or sanitized previews, and
revoke frontend Blob URLs. New approvals must require two current reviewed
documents; legacy exemption must remain explicit and separate from verification.
Existing approved Drivers cannot replace evidence through append_version without
a separately reviewed resubmission policy. No existing decision is changed here.

## Retention proposal -- inactive until operator approval

Proposed configuration: PRIVATE_DRIVER_DOCUMENT_ROOT (explicit provisioned root),
DRIVER_DOCUMENT_RETENTION_ENABLED=false, REJECTED_DOCUMENT_RETENTION_DAYS,
SUPERSEDED_DOCUMENT_RETENTION_DAYS, APPROVED_DOCUMENT_RETENTION_DAYS,
DOCUMENT_AUDIT_RETENTION_DAYS, and LEGAL_HOLD_ENABLED. Leave durations unset until
the operator approves purpose, jurisdiction, appeal period, backup treatment and
deletion responsibilities. No scheduler, expiry deletion, or irreversible deletion
of submitted documents is implemented. Purge dry-run/approval/hold checks belong
to a separate task. Use only fictional fixtures for viva testing.

## Offline checks

Run `backend/.venv/Scripts/python.exe backend/offline_tests/driver_documents_suite.py`.
Tests use temporary synthetic files and isolated SQLite; fixture ACL inspection
is mocked, while parser processes use real Windows resource limits. Actual
private-root provisioning/ACL acceptance remains an operator verification gate.
No MySQL connection, migration execution, frontend edit or Stripe operation occurs.
