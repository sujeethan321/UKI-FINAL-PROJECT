# Day 8 Step 8.3: Credit Sales Frontend Integration

Implemented and verified on 2026-11-03 (Asia/Colombo).

## Integration summary

Inspection found no existing Credit Sales page or sale form: the sidebar destination was disabled and no React route was registered. Added the page inside the existing protected ShopOwnerLayout using LankaPex's existing colors, cards, field styles, tables, and typography. Existing customer/dashboard page layouts were preserved.

The page loads trusted business context and chooses an approved business. The dashboard quick action carries its current selection through navigation state; the destination accepts it only when it matches an approved business returned by the backend. Query-string business/customer IDs are not used. The sidebar Credit Sales entry is enabled; repayments and unrelated modules remain disabled.

Customers and account details come from the existing business/customer services. The page displays outstanding balance, credit limit, available credit, account status, and effective credit-sale history for the selected customer. Missing accounts and inactive statuses prevent new sales. Read requests are aborted or ignored when their business/customer scope changes. Data is cleared immediately on scope switches; response scope is checked before display.

## Actual backend contract used

POST /api/v1/shop-owner/credit-sales?business_id=<trusted-business-id>

```json
{
  "customer_id": 456,
  "amount": "1250.50",
  "notes": "Goods supplied on credit",
  "idempotency_key": "credit-sale:<secure-unique-identifier>"
}
```

The service uses the existing Axios client and JWT/session-expiry interceptors. Only customer_id, amount, notes, and idempotency_key are sent in the body. Business ID is a query parameter. Receipt/reference and due date are server-controlled and are displayed after confirmation; no unsupported editable fields were added.

201 means newly created and 200 may mean idempotent replay. Both require a valid scoped response before the UI shows success. Confirmation displays reference, entry ID, amount, outstanding balance, available credit, and supplied dates. Customer/account data and effective sale history are then refreshed through the existing Customer Details API. There is no invented business-wide sale-history endpoint.

## Money and validation

- Amounts stay decimal strings in fields and payloads.
- Positive amount, maximum two decimal places, and the backend Numeric(14,2) range are validated.
- Exact BigInt minor-unit comparisons avoid JavaScript floating-point limit decisions.
- Formatting groups decimal strings without converting money to Number.
- Customer/account selection, approved business, active account, available credit, and maximum 2000-character notes are checked before a new sale is sent.
- Backend authorization and financial checks remain authoritative and unchanged.

## Idempotency and uncertainty

A cryptographically secure UUID (or getRandomValues fallback) identifies each intended operation. The key is persisted with a SHA-256 hash of canonical business/customer/amount/notes and a pending flag in user-scoped sessionStorage. No customer records, amounts, notes, ledger entries, or server responses are stored there. No localStorage is used.

Duplicate clicks are guarded synchronously before asynchronous preparation/POST. Context/form changes are blocked during an active submission. An unchanged retry reuses its key. Editing a rejected operation or explicitly starting a new sale creates a new intention and obtains a new key when submitted.

Timeouts, network failures, 5xx responses, and malformed/mismatched success responses retain the original pending key and show an uncertain-result message. They never clear the form or claim success. The user is instructed to inspect the ledger before starting another sale. A changed operation cannot silently replace an unresolved operation: the UI requires the explicit Start New Sale action after ledger review.

The key survives page reload/remount in the same browser tab. Re-entering the exact original fields recreates the hash and permits a safe retry, including when the earlier successful sale has exhausted credit or the account is now suspended. The backend still authorizes and decides whether it is an actual replay.

Closing the browser tab ends sessionStorage persistence. After losing the original fields/tab state, verify the ledger before recording another intended sale. Sensitive request details are deliberately not persisted for automatic form restoration.

Late completion clears only its own key, so it cannot erase a newer operation. A submission abandoned before secure preparation completes does not dispatch a late POST. In-flight financial POSTs are not automatically cancelled; their saved identity remains available for verification/retry.

## Errors and refresh

400/401/403/404/409/422 errors have safe actionable feedback. Validation details identify fields; 409 retains credit/account/idempotency conflict details. Internal 5xx diagnostics and stack traces are suppressed. Expired sessions use the existing Axios/AuthProvider behavior.

Confirmed success clears the form and updates displayed balances immediately from the response. A later GET failure does not turn a confirmed sale into an uncertain sale: confirmation remains visible, with a separate refresh error. New sales remain blocked until usable customer data is loaded again.

## Files created

- frontend/src/pages/shopOwner/ShopOwnerCreditSales.jsx
- frontend/src/pages/shopOwner/creditSaleWorkflow.js
- frontend/src/services/shopOwnerCreditSaleService.js
- frontend/src/utils/creditSale.js
- frontend/tests/creditSales.test.js
- frontend/tests/creditSalesView.test.js
- docs/day8-credit-sales-frontend.md

## Files modified

- frontend/package.json: added npm test using the existing Node test runner; no dependencies added.
- frontend/src/App.jsx: added protected Credit Sales route.
- frontend/src/components/shopOwner/ShopOwnerSidebar.jsx: enabled Credit Sales only.
- frontend/src/components/shopOwner/QuickActions.jsx: enabled the existing Record Credit Sale action, preserving its styling.
- frontend/src/pages/shopOwner/ShopOwnerDashboard.jsx: passes selected business to that action.

No backend files were changed in Step 8.3. Existing uncommitted Step 8.2 backend work and the unrelated .gitignore edit were preserved. No commit or push was made.

## Executed verification

| Check | Actual final result |
| --- | --- |
| npm test | 69 passed, 0 failed, 0 skipped; 14.63 seconds |
| npm run build | Passed; 2130 modules transformed; 7.05 seconds |
| Targeted ESLint | Passed for new page/workflow/service/utilities/tests, App, sidebar, and quick actions |
| Browser smoke | Unavailable: no connected browser surfaces; opening iab failed with Browser is not available |

Tests use controlled API promises, the existing Node test runner, Vite's JSX transform, React server rendering, and a controlled Axios adapter. No test makes real API requests or creates development financial entries. Tests cover all requested workflow categories, including scoped response handling, initial rendering, existing dashboard/customer components, account eligibility, money validation, confirmation/history refresh, duplicate clicks, idempotency rotation/recovery, session-storage isolation, HTTP errors, malformed success, disposal, and business/customer switching.

These are workflow and server-rendered component checks, not browser interaction or visual acceptance tests. Existing login/customer/account management behavior was preserved by source review, initial component rendering, existing frontend tests, and build verification; a live interactive regression pass is not claimed. The full-project lint command was not claimed clean; only the targeted files above were linted. Backend regression was not rerun because Step 8.3 made no backend changes.

## Manual browser checklist

Use a separately prepared test account/environment for write checks. Do not create automated financial transactions in lankapex_db.

1. Sign in as an approved Shop Owner; open Credit Sales from the sidebar and dashboard action. Confirm the dashboard's selected business is carried into the page.
2. Compare sidebar, cards, typography, colors, field styles, and responsive layout with Customers/Dashboard.
3. Verify no-business, pending-business, no-customer, loading, and failed-read states.
4. Select customers with no account, active accounts, suspended accounts, and closed accounts. Verify new-sale eligibility.
5. Enter zero, negative, excessive-precision, and above-credit amounts; confirm no request is sent. Test an amount exactly at available credit.
6. Record a valid sale. Verify reference/entry ID, amount, due date, refreshed balances, and effective history.
7. Double-click Record Credit Sale and confirm one intended operation is sent. Check the browser console/network for errors and exact API paths.
8. Simulate a timeout/5xx in the test environment. Confirm the uncertain message and unchanged fields/key; refresh the ledger and retry the exact sale with that same key.
9. Reload the same tab during uncertainty, re-enter identical fields, and verify key recovery. Confirm changing fields cannot silently dispatch a different unresolved sale.
10. After reviewing the ledger, explicitly start another sale and verify a fresh key. Confirm no financial records are stored in localStorage/sessionStorage.
11. Switch customers/businesses rapidly while reads are delayed. Verify old responses never reappear in the new scope.
12. Verify safe 401/403/404/409/422 messages, login redirect on expired sessions, and a confirmed sale remaining confirmed when only its subsequent refresh fails.
13. Revisit Dashboard and Customers; manually verify Add Customer, Edit Customer, details, credit-account management, and ledger history.
14. Verify keyboard navigation, small-screen layout, empty history, disabled controls, and no missing-key or JavaScript console errors.

Remaining scope: live browser acceptance; Credit Sales remains based on the selected customer's supported effective ledger rather than a new business-wide history API. Repayments, printable receipts, and backend changes are outside Step 8.3.
