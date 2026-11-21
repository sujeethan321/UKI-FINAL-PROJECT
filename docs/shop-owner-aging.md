# Shop Owner Reports aging

Aging is a current position, independent of selected trend dates. It uses the same
naive database NOW() clock as Reports. No geographical timezone is inferred.

Effective repayments are pooled within each customer credit account and allocated
to effective sales by `(recorded_at, entry_id)` ascending. This is a reporting-only
FIFO assumption, not persisted sale-level settlement history. Advances never
offset other accounts. Reversals cancel the full original under ledger_service
semantics; invalid references, duplicate reversals and chronology are rejected.

Saved due_at dates define Current (due today or later), 1–30, 31–60, 61–90 and
91+ overdue calendar days. Missing, timezone-aware or pre-sale due dates leave
unpaid residuals Unclassified; current account terms never reconstruct dates.

Every account's residual is reconciled to max(authoritative balance, 0), then
aggregate buckets plus Unclassified are reconciled to current outstanding.
Future ledger timestamps make aging unavailable. Unclassified debt makes exact
overdue unavailable while known buckets remain explicitly partial. No estimate
is substituted. Zero is a valid complete result for empty or fully paid accounts.

The existing report, CSV and multilingual PDF share this dataset and disclose
the policy, coverage and current-position meaning. Existing authorization,
business scope, ledger-size/date bounds and no-store headers remain in force.
No allocation or financial record is written. Existing Reports layout is retained.

Offline verification:

```powershell
.\backend\.venv\Scripts\python.exe backend\offline_tests\aging_suite.py
```

Live verification requires a separately authorized backend reload/restart. No
restart, MySQL connection or Stripe operation was performed during implementation.
