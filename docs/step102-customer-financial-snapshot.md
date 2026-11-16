# Step 102 — Customer-scoped financial snapshot

`CustomerFinancialSnapshotService` accepts only the authenticated Customer user
ID, the requested credit-account ID, and an injected repository. Missing,
foreign, malformed, inactive-user and inactive-account cases all produce the
existing generic `404 Credit account not found` response. The caller cannot
provide a customer or business ID as authorization evidence.

The production repository uses one request-scoped SQLAlchemy Session
transaction. It verifies an active Customer user, reuses
`customer_dashboard_service.scoped_accounts(user_id)` to enforce the linked
profile/account/business relationship and approved business, requires an
active credit account for new AI generation, then uses the existing bounded
ledger loader, `effective_entries` and `account_balances`. It issues SELECTs
only and never commits, flushes, rolls back, creates an account or writes an
audit record.

The snapshot contains only LKR purchases, repayments, current outstanding,
optional overdue and a timezone-aware capture time. Reversed originals are
excluded using the existing effective-ledger rules. Negative ledger positions
remain advances and therefore produce zero outstanding, matching current
customer dashboard behavior.

## Domain limitations

- Totals are lifetime effective totals, not a selected statement period.
- Existing storage does not allocate repayments to individual sales, so an
  authoritative overdue amount is unavailable and remains `None`.
- Existing customer statements allow closed and suspended accounts to remain
  readable. This new AI snapshot is intentionally stricter and accepts only
  active credit accounts, as required for AI generation eligibility.
- The existing interactive ledger bound still applies. Oversized histories
  fail rather than being silently truncated.
- The service does not call an AI provider. A future authenticated route must
  reuse the active-Customer JWT dependency and must keep the same generic
  object-level authorization failure.
