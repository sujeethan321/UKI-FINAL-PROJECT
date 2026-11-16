# Day 5 — Demo stabilization and four-role UAT

Status: **PARTIAL** (2026-11-09). Source-level and isolated automated regressions pass. A complete browser UAT on the existing demo accounts and an independent demo-schema revision check remain outstanding. No Day 5 operation wrote to `lankapex_demo_db`, `lankapex_db`, or a rehearsal database.

## Evidence and scope

| Check | Result | Evidence / limit |
| --- | --- | --- |
| Backend regression | PASS | 533 selected auth, Admin, catalogue, order, credit, invitation, driver, and delivery tests passed with `APP_ENV=testing`, `MYSQL_DATABASE=lankapex_test_db`; `backend/tests/conftest.py` checks the actual connected database. These tests use synthetic test data only. |
| Invitation attack tests | PASS | Existing plus new tests cover expired codes, replay, wrong recipient, owner isolation, simultaneous accept, acceptance rate limit (sixth attempt returns 429), and simultaneous reissuance (only the latest code remains usable). The two focused invitation tests passed; they are included in the 533 count. |
| Frontend regression | PASS | 848/848 tests passed after updating seven stale assertions for the previously requested removal of sidebar identity footers and Driver Dashboard profile details. No production UI was changed. |
| Running frontend/backend | PASS, limited | Read-only GET of Vite `/`, FastAPI `/openapi.json`, and `/api/v1/health/database` returned HTTP 200. OpenAPI has 85 paths, including both customer-link invitation routes. The served frontend API module points to `http://127.0.0.1:8001/api/v1`. This does not prove a four-role browser journey or the backend database identity. |
| Demo restart/schema | BLOCKED | The private DPAPI runtime credential cannot be decrypted by this shell. The read-only `preflight_demo_runtime.ps1` must be run by the Windows account that stored it. Current source requires invitation revision `6e3f2c1a9b04`; the actual demo revision has not been independently verified during Day 5. No migration was attempted. |

`backend/scripts/check_demo_backend.py` now checks the current invitation revision `6e3f2c1a9b04` and exact model table inventory before launching the demo API. It retains exact database, account, and DML-only grant checks. If the demo schema is older, restart will stop safely. `frontend/.env.local` still names port 8000; use `frontend/scripts/start_demo_frontend.ps1`, which sets a process-only override to port 8001. Do not start Vite directly without this override. The backend launcher is `backend/scripts/start_demo_backend.ps1` and binds to 127.0.0.1:8001 after its private preflight.

## Workflow audit

| Journey | Code/automated evidence | Browser status |
| --- | --- | --- |
| Registration and four-role login | Auth registration/login/`me`, password hashing and role guard tests passed. Admin provisioning uses its separate operator workflow. | Existing account login reported working before Day 5; not repeated with private credentials. |
| Admin approval of business and Driver | Admin approval routes and role/ownership tests passed; unauthorized roles denied. | Not replayed; approvals are writes. |
| Owner categories and products | Catalogue CRUD and role tests passed; frontend catalogue tests passed. | Existing records can be viewed; new writes deferred. |
| Customer cash order and Owner fulfilment | Quote, order, decision, delivery-link, and customer tracking tests passed. | New order not placed during this audit. |
| Driver jobs and delivery status | Eligibility, single assignment, ownership, transitions, and driver view tests passed. | New acceptance/status writes deferred. |
| Credit sale, partial/full repayment and linked Customer view | Financial, dashboard, statement, and account-link tests passed against isolated test DB; balances are sourced from the ledger. | Existing Owner/Customer displays should be compared manually without new ledger writes. |
| Invitation consent and replay | Owner-issued, recipient-bound, six-digit code; expiry, single-use, isolation, acceptance limit and concurrent issuance tests passed. | New invitation not issued during this audit. |

The in-process invitation acceptance limiter is per worker; it is not a shared distributed limit. Concurrent reissuance is serialized by database locking in the tested MySQL workflow. Keep one backend worker for the viva; do not present the local limiter as a production-wide rate limit. Driver earnings remain explicitly unavailable because payout accounting is not implemented. Do not show a fabricated earnings amount.

## Reproducible browser UAT checklist

Before the session, use the same Windows account that owns the private DPAPI blobs. Run the read-only runtime preflight with `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\preflight_demo_runtime.ps1`; record its PASS line without credentials. Keep the demo backend on 8001 and launch the frontend with `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\frontend\scripts\start_demo_frontend.ps1`; confirm the browser's API calls go to 8001, not 8000. Confirm the health endpoint is 200. If the preflight fails, stop; do not point the frontend to a different database or run a migration during the demo.

Use the four existing synthetic accounts and a clean browser session per role. Record expected versus actual screen, HTTP status, and timestamp; redact tokens, passwords, invitation codes, and personal/financial details. Read-only checks can proceed now:

1. **Admin:** log in, confirm role and dashboard; inspect existing business and Driver approval states. Check that other roles cannot open Admin routes.
2. **Owner:** log in, inspect the approved business, existing categories/products, orders, deliveries, customer accounts, balance and statement. Record an existing credit sale and repayment's amounts and compare the displayed outstanding balance.
3. **Customer:** log in, browse the approved shop and catalogue, inspect existing cash/credit orders and delivery progress. Confirm the linked shop balance, credit sales, repayments and statement match the Owner view. Open another customer's guessed URL and confirm no financial data appears; do not use a real customer's ID.
4. **Driver:** log in, inspect eligible jobs, assigned deliveries and history. Confirm profile/approval status is shown on its dedicated route and that no earnings are claimed. Check that an unrelated job cannot be updated through the UI.
5. **Navigation/errors:** traverse every primary sidebar link, refresh deep links, test empty lists, expired session handling, and mobile menu. Capture network 4xx/5xx and console errors.

The write-flow extension (new registration, approval, category/product, order, delivery acceptance/status, credit sale/repayment, invitation issuance/acceptance) requires a separately approved synthetic demo-data session. Use the isolated test results for these flows until that session. Do not reset existing accounts or financial records merely to repeat UAT.

## 8–10 minute technical viva demonstration

| Time | Show | Key explanation |
| --- | --- | --- |
| 0:00–0:45 | Architecture and four roles | React → FastAPI `/api/v1` → MySQL; JWT and server-side role/ownership checks. |
| 0:45–1:45 | Admin | Existing business/Driver approvals and protected management views. |
| 1:45–3:00 | Shop Owner catalogue | Approved business, categories/products, real stored data. |
| 3:00–4:15 | Customer | Shop browsing, an existing order and delivery progress; cash versus credit choice. |
| 4:15–5:45 | Owner financial screens | Existing credit sale and partial repayment; explain decimal ledger and outstanding-balance invariant. |
| 5:45–6:45 | Customer credit | Consent-based account link, same balance and transaction history from the Customer's view. |
| 6:45–8:00 | Driver | Approved profile, eligible jobs, owned delivery status/history; no invented earnings. |
| 8:00–9:15 | Security/testing | Cross-role denial, single-use invitation, single assignment and test counts. |
| 9:15–10:00 | Limits/questions | Local rate limiter, no Driver payouts or AI Summary, and next improvement. |

Use existing records and read-only views for the live presentation. If a write demonstration is separately approved, prepare a fresh fictional transaction and record expected before/after values in advance. Never improvise a financial write during the viva.

## Safe fallback and next action

If login or an API request fails, check the backend and frontend ports and the browser network URL. Restart only through the guarded launchers and only after the operator's read-only preflight passes. If revision/table inventory fails, stop the backend launch; present the passing isolated tests and static architecture screenshots rather than migrating the demo database during the viva. If a role page fails, move to an already working read-only role screen and record the exact status for later diagnosis. If a balance differs, stop financial writes and use the ledger regression evidence; do not repair live balances in the browser.

**Highest-priority next action:** have the DPAPI-owning operator run the read-only runtime preflight and record the exact PASS/FAIL for the current demo revision/table inventory, then rehearse the four-role read-only browser checklist. A mismatch requires a separately planned backup and guarded demo-schema upgrade authorization. Keep days 13–14 of the 14-day schedule exclusively for technical viva study.
