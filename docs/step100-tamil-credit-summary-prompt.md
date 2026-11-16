# Step 100 — Privacy-safe Tamil credit summary prompt

`FinancialSummarySnapshot` is an immutable, database-free transfer object. It
contains only LKR totals supplied by authoritative LankaPex financial logic and
a timezone-aware capture time. It intentionally has no customer, business,
account or transaction identifiers and no names, contact details, notes or raw
ledger entries.

All currency values must be finite, nonnegative `Decimal` values with at most
two decimal places. An optional overdue balance is accepted only when an
authoritative service has already calculated it, and it cannot exceed the
outstanding balance. LankaPex currently reports overdue allocation as
unavailable, so callers must normally leave it absent. The builder does not
assume purchases minus repayments equals outstanding because reversals,
advances and period boundaries can make that equation misleading.

The deterministic prompt asks for two or three short Sri Lankan Tamil
sentences, prohibits invented transactions, due dates, promises, independent
authoritative calculations, credit decisions and requests for personal data,
and distinguishes outstanding from overdue amounts. Its combined UTF-8 size
is checked against the same 16 KiB boundary used by the Groq adapter.

This step does not query a database or call an AI provider. A later authorized
application service must first enforce JWT and object-level access, compute the
snapshot with existing ledger rules, and only then pass this request to the AI
client.
