# Step 101 — Tamil credit summary orchestration

`TamilCreditSummaryService` accepts only an immutable, already validated
`FinancialSummarySnapshot` and an injected provider-neutral `AIClient`. It has
no database, ORM, logging or financial-writer dependency. It builds the Step
100 prompt, makes one client call, and returns either conservatively validated
Tamil text or a deterministic Tamil fallback containing the exact supplied LKR
amounts.

Generated text is accepted only when it is bounded, contains Tamil and LKR,
includes every authoritative amount, contains no other numeric fact or date,
distinguishes an unavailable or supplied overdue amount, and contains no HTML,
common Markdown, control characters, contact patterns, internal identifier
labels or selected prescriptive claims. All provider failure categories and
unexpected exceptions use the fallback without exposing exception text.

These checks reduce obvious hallucination and disclosure risks; they cannot
prove that arbitrary natural-language prose is semantically or financially
correct. Accepted output remains labelled `generated`, while the snapshot from
LankaPex remains authoritative. A future UI must show that distinction and
must never use generated prose to approve credit or post a transaction.

The fallback performs no arithmetic. It formats the purchases, repayments,
outstanding balance and optional overdue value already present in the snapshot.
When overdue is absent it explicitly says that an authoritative overdue amount
was not calculated.
