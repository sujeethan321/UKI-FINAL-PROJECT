# Day 7 Step 7.5 verification report

Date: 2026-11-03 (Asia/Colombo).

## Result

Required automated verification passed. The Day 7 code is ready for a local Git checkpoint. Browser acceptance remains manual because the available computer-use runtime reported no browsers and could not open the in-app browser. No browser interaction or visual acceptance pass is claimed.

## Features verified

- Real JWT login, customer listing, creation, details, editing, account creation, and account updates against MySQL.
- Creation and editing persist across independent API request sessions and are visible to an independent SQLAlchemy observer session.
- Name/address whitespace normalization, Sri Lankan phone normalization, duplicate phone conflicts, invalid inputs, and nullable optional fields.
- Customers without credit accounts remain usable; account creation is explicit.
- Credit limits, payment terms, activation, suspension, closure, duplicate-account rejection, debt-limit checks, and settlement before closure.
- Mutation responses and subsequent GET requests contain the updated data used by frontend refreshes.
- The Customers page obtains data from Axios services. No mock customer records are present. Its route, sidebar link, API paths, selection/refresh code, search/filter code, and modal wiring were inspected.
- All six customer API operations are declared once and exposed through the mounted application OpenAPI schema.

## Security and isolation

- All six operations reject missing/invalid tokens with 401, and customer/driver/admin roles with 403.
- Inactive users, inactive memberships, pending businesses, and unowned businesses are denied.
- Foreign customer IDs cannot escape the selected business scope; details and mutations return 404.
- Injected database failures return generic 500 messages without SQL diagnostics and roll back their request transactions.
- Customer forms give safe guidance for 401/403/404, preserve actionable 409/422 errors, and suppress internal 5xx diagnostics.
- Full Axios error logging was removed from the Customers page to avoid logging request authorization headers.
- Source review found parameterized SQLAlchemy customer queries and no schema/migration changes. No tracked environment/private-key files were found. The staged checkpoint was separately reviewed for credentials and generated artifacts.
- Existing raw error logging in older dashboard/onboarding modules is outside this Day 7 change and should be addressed in a separate security cleanup.

## Ledger integrity

- Credit sales increase debt; partial repayments reduce debt.
- Sale reversals exclude the sale; repayment reversals restore the debt.
- MySQL rejects a second reversal targeting the same original entry with duplicate-key error 1062.
- Decimal values such as 0.30 and 0.10 produce exact running balances. Detail, customer-list, and dashboard balances agree.
- Account updates preserve the original ledger entries and reversal references.
- Customer advances must also be settled before closing an account.
- Financial test entries were inserted only into lankapex_test_db inside outer rollback transactions. No development financial transactions were created.

## Executed checks

| Check | Actual result |
| --- | --- |
| Configured database and SELECT DATABASE() | Both lankapex_test_db |
| Test table engines | InnoDB |
| python -m pytest -v -p no:cacheprovider | 247 passed, 0 failed, 0 skipped; 36.83 seconds |
| node --test tests/customerError.test.js | 13 passed, 0 failed, 0 skipped |
| npm run build | Passed; 2126 modules transformed |
| ESLint for AddCustomerModal, ManageCustomerModal, customerError utility and its tests | Passed |
| Test database row counts before/after complete suite | Unchanged in users, businesses, business_members, customer_profiles, credit_accounts, ledger_entries, business_approval_audits |
| Browser smoke test | Unavailable: no connected browser; in-app browser unavailable |

The pytest cache plugin was disabled because the existing cache directory produced permission warnings in earlier runs. Assertions were not relaxed. The suite reports one existing InsecureKeyLengthWarning from the deliberately short incorrect key in test_tampered_token_rejected. The pre-existing Customers page has three react-hooks/set-state-in-effect lint findings; no page-wide lint pass is claimed.

## Bugs and coverage gaps repaired

1. The Add Customer phone check now uses a locking current read after the business lock, avoiding a stale MySQL repeatable-read snapshot during a concurrent customer change. Sequential duplicate behavior is covered; simultaneous-request load testing was not performed.
2. Removed full Axios diagnostics from the Customers page.
3. Centralized safe customer-form error messages, including explicit missing-record guidance and protection against malformed validation errors.
4. Restored real database rejection assertions to previously empty constraint tests, removing duplicate shadowed definitions.
5. Added 67 integration cases using real JWT authorization and independent request sessions, including persistence, isolation, ledger consistency, reversal uniqueness, and sanitized database failures.
6. Added 13 frontend error-handling cases without introducing new dependencies.

## Manual browser acceptance checklist

Use disposable data in the test environment for write checks; do not create development financial transactions.

- Sign in as an approved Shop Owner; open Customers from the sidebar and verify the original layout.
- Add a customer, confirm list refresh, open details, edit name/phone/address, and confirm details/list refresh without changing selection unexpectedly.
- Search by name, phone, address, and ID; combine search with account-status filters and use pagination.
- Check empty lists, no matches, and customers without accounts.
- Open/cancel each modal, test double-submit protection and loading states, then switch between businesses/customers and verify no stale details or form values.
- Create a credit account; edit its limit, terms, and status. Verify conflict and validation messages.
- Confirm expired sessions redirect to login, and rejected saves do not show success feedback.
- Inspect the browser console/network for runtime errors, API paths, cancellation behavior, and missing React keys.

## Checkpoint files

The checkpoint includes previously uncommitted Day 7 implementation plus this verification work:

- backend/app/routers/shop_owner.py
- backend/app/schemas/customer.py
- backend/app/services/shop_owner_customer_create_service.py
- backend/app/services/shop_owner_customer_details_service.py
- backend/app/services/shop_owner_customer_manage_service.py
- backend/tests/conftest.py
- backend/tests/test_database_constraints.py
- backend/tests/test_day7_integration.py
- backend/tests/test_shop_owner_customer_management.py
- backend/tests/test_shop_owner_dashboard.py
- frontend/src/App.jsx
- frontend/src/components/shopOwner/ShopOwnerSidebar.jsx
- frontend/src/pages/shopOwner/AddCustomerModal.jsx
- frontend/src/pages/shopOwner/ManageCustomerModal.jsx
- frontend/src/pages/shopOwner/ShopOwnerCustomers.jsx
- frontend/src/services/shopOwnerCustomerService.js
- frontend/src/utils/customerError.js
- frontend/tests/customerError.test.js
- docs/day7-integration-report.md

The existing backend/tests/confest.py is not auto-loaded by pytest; the correctly named conftest.py enforces the configured and actual test-database checks before collection. The unrelated .gitignore edit remains outside the checkpoint. No push is authorized or performed.

Next priorities: complete the manual browser checklist, add a connected browser to automate the UI flows, and address older-page logging and existing lint findings in separate scoped changes.
