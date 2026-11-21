# Shop Owner financial reports — Phase 1

`GET /api/v1/shop-owner/reports/financial?business_id=…&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
is read-only and requires an active Shop Owner with active owner membership in
the approved business. Successful and service-error responses use `no-store`.
There are no schema changes, Stripe operations or application-data writes.

Dates use the stored database wall clock. No geographical timezone is asserted
or converted. The inclusive range is bounded to 366 daily points; omitted dates
default to the 30 calendar days ending on the database reporting day. Account
and ledger sizes use the existing interactive limits and fail rather than
truncate. Collected Today uses `NOW()` from the same database reporting session,
independently of the selected period. Current outstanding keeps the dashboard's
per-customer calculation, including advances without offsetting other debtors.

Credit sales and repayments come only from customer-account ledger events.
Original events remain on their recorded days. A reversal adjusts its own day
by the full original amount, regardless of a legacy reversal's descriptive
amount, matching customer-statement semantics. Reversed repayments contribute
negative repayments; reversed sales contribute negative sales. Invalid reversal
chronology or a missing same-account original fails closed. Future reversals
do not rewrite prior periods. Trend totals therefore need not equal the
statement's gross sales/repayment fields: their difference is the explicitly
dated reversal adjustment. Credit orders are not summed again from order totals.

The original page sections, card classes and chart grid remain in place. Date
controls live within Financial Overview; daily bar charts include signed values,
tooltips and expandable accessible daily tables inside the existing containers.
Overdue Amount and Outstanding Credit Aging remain unavailable.
Money is calculated with Decimal and returned as decimal strings. Browser
floating-point values are used only for bar geometry, not financial arithmetic.

Offline verification:

```powershell
.\backend\.venv\Scripts\python.exe backend\offline_tests\reports_suite.py
cd frontend
node --test tests/shopOwnerReports.test.js tests/shopOwnerRestoration.test.js tests/financialDocuments.test.js tests/financialDocumentsView.test.js
```

The backend suite blocks application network connections and uses SQLite;
the MySQL-connected test suite is not part of this check. Live MySQL report
verification and browser visual inspection remain separate operator checks.

## CSV export — Step 373

`GET /api/v1/shop-owner/reports/financial.csv` requires explicit `business_id`,
`start_date` and `end_date`. It reuses the JSON endpoint's active approved-owner
authorization and the same report service, bounds and ledger semantics. It
returns a UTF-8 BOM CSV attachment with `no-store` and `nosniff` headers. Stable
English CSV headings identify the selected inclusive period, current overview,
database reporting day, wall-clock limitation, UTC generation time and daily
net values. Export button, loading and error feedback follow English/Tamil/Sinhala
UI localization. No customer names, contact details or raw ledger rows are exported.

The existing Export Report button downloads the displayed business and **applied**
dates. Unapplied input edits do not change export selection. CSV is a fresh read,
not an immutable copy of the earlier screen; concurrent writes can change its
current/period values. The CSV itself discloses this limitation. Selection changes
and unmount abort/discard pending downloads; duplicate clicks are suppressed.

Only validated Decimal monetary cells are emitted as numeric fixed two-decimal
values. Text beginning with spreadsheet formula characters is neutralized,
CSV fields are quoted, and filenames contain only a numeric business ID and
validated ISO dates. Temporary browser Blob URLs are revoked. CSV export adds
no new Reports section, schema modification or financial write.

## PDF export — Step 375

The existing Export Report control now offers CSV and PDF through the shared
accessible dropdown. `GET /api/v1/shop-owner/reports/financial.pdf` takes the same
required business/start/end dates plus `language=en|ta|si`. It calls the same
authorized report function as JSON and CSV. Headers are attachment, no-store
and nosniff; filenames contain only validated IDs/dates and a language allowlist.
Step 379 adds current overdue and aging to this same dataset; see
`shop-owner-aging.md` for the approved FIFO policy and coverage safeguards.
There is no new Reports page section or ledger change.

PDFs contain current outstanding and database-day net collections, separately
labelled selected-period sales/repayment totals, and paginated daily trend tables.
Clock, reversal, currency, aging coverage and fresh-read limitations are
localized. Decimal formatting is shared with CSV; no PDF-specific financial
calculations are introduced. UTC generation time is distinct from ledger dates.

PyMuPDF 2.1 (already installed locally, now explicitly pinned in requirements)
provides native complex-script shaping and in-memory HTML/table pagination.
Existing ReportLab infrastructure supplies the embedded English Vera font;
the plain ReportLab statement renderer cannot simply be reused for Indic shaping.
PDF generation is serialized with a bounded lock and a 40-page cap.

Tamil/Sinhala use installed Windows Nirmala UI, whose glyph coverage is checked
before rendering. No Windows font is copied or redistributed. Non-Windows
deployments can supply licensed static `NotoSansTamil-Regular.ttf` and
`NotoSansSinhala-Regular.ttf` under `backend/app/assets/fonts`; English optionally
uses `Vera.ttf` there. Missing fonts or rendering failures return safe HTTP 503,
never a silently garbled PDF. This local Windows environment has both required
script ranges, and synthetic English/Tamil/Sinhala exports were rendered and
visually inspected. Rendering requires no network or font download at request time.

PDF and CSV share duplicate-click suppression, cancellation on business/applied
date/language changes and unmount, generic localized errors, and Blob URL cleanup.
No automatic application restart or live financial export was performed during
implementation. Live authenticated download checks follow separate operator
authorization and do not require any migration.
